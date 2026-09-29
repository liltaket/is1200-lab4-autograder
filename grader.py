"""Shared grading engine for the IS1200/IS1500 Lab 4 local grader.

The command line interface and the small web UI both call this module.  The
engine deliberately reports unavailable hardware checks as ERROR/UNVERIFIED;
it never turns a successful process exit into a PASS.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional


ASSIGNMENTS = (1, 2, 3, 4, 5)
REPO_HINTS = (Path("Bruno"), Path("bruno"))


@dataclass
class CheckResult:
    name: str
    status: str = "PENDING"  # PENDING, RUNNING, PASS, FAIL, ERROR, UNVERIFIED
    message: str = ""
    diagnostics: list[str] = field(default_factory=list)
    elapsed: float = 0.0
    trace: list[dict] = field(default_factory=list)
    subresults: dict[str, dict] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


@dataclass
class RunResult:
    state: str = "IDLE"
    started_at: float | None = None
    finished_at: float | None = None
    elapsed: float = 0.0
    assignments: dict[str, CheckResult] = field(default_factory=dict)
    paths: dict[str, str] = field(default_factory=dict)
    log: list[str] = field(default_factory=list)
    verbose: bool = False
    keep_temp: bool = False

    def to_dict(self) -> dict:
        value = asdict(self)
        value["assignments"] = {key: asdict(item) for key, item in self.assignments.items()}
        return value


def find_repo_root(start: Path | None = None) -> Path:
    start = (start or Path(__file__)).resolve()
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists() and (candidate / "Bruno").exists():
            return candidate
    return Path.cwd().resolve()


def discover_inputs(repo_root: Path) -> tuple[Path | None, Path | None]:
    """Find current inputs without assuming they are at repository root."""
    circ = sorted(repo_root.rglob("processor_riscv.circ"), key=lambda p: p.stat().st_mtime, reverse=True)
    asm = sorted(
        [*repo_root.rglob("factorial.s"), *repo_root.rglob("factorial.S")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    # Prefer the Bruno Lab 4 tree when copies exist.  The mtime tie-breaker
    # makes the selection deterministic for multiple working copies.
    def preferred(items: list[Path]) -> Path | None:
        if not items:
            return None
        bruno = [p for p in items if "bruno" in str(p).lower()]
        return (bruno or items)[0]
    return preferred(circ), preferred(asm)


def detect_tool(explicit: str | None, names: Iterable[str], extra_roots: Iterable[Path] = ()) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        return path if path.exists() else path
    for name in names:
        found = shutil.which(name)
        if found:
            return Path(found).resolve()
    roots = [Path.cwd(), *extra_roots, Path.home() / "AppData/Local/Programs", Path.home() / "Downloads"]
    for root in roots:
        if not root.exists():
            continue
        try:
            for pattern in ("*.jar", "**/*.jar"):
                for path in root.glob(pattern):
                    lower = path.name.lower()
                    if any(token in lower for token in names):
                        return path.resolve()
        except OSError:
            continue
    return None


def detect_java(repo_root: Path) -> Path | None:
    bundled = repo_root / "tools" / "jre21" / "jdk-21.0.12.1+1-jre" / "bin" / ("java.exe" if os.name == "nt" else "java")
    if bundled.exists():
        return bundled.resolve()
    found = shutil.which("java")
    return Path(found).resolve() if found else None


def _parse_rows(path: Path) -> tuple[list[str], list[list[str]]]:
    headers: list[str] = []
    rows: list[list[str]] = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if not headers:
            headers = fields
        else:
            rows.append(fields)
    return headers, rows


def _u32(value: str) -> int:
    return int(value, 0) & 0xFFFFFFFF


def _s32(value: int) -> int:
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def validate_vector_file(path: Path, expected_min_rows: int = 1) -> tuple[bool, str, list[str]]:
    try:
        headers, rows = _parse_rows(path)
    except Exception as exc:
        return False, f"Could not parse {path.name}: {exc}", []
    if not headers or len(rows) < expected_min_rows:
        return False, f"Expected at least {expected_min_rows} data rows in {path.name}", []
    diagnostics: list[str] = []
    for index, row in enumerate(rows, start=1):
        if len(row) != len(headers):
            diagnostics.append(f"row {index}: {len(row)} fields, expected {len(headers)}")
    return not diagnostics, f"Parsed {len(rows)} vectors from {path.name}", diagnostics


def validate_assembly(path: Path) -> tuple[bool, str, list[str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        return False, f"Could not read assembly: {exc}", []
    lines = [line.split("#", 1)[0].strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    labels = {line[:-1].strip() for line in lines if line.endswith(":")}
    diagnostics: list[str] = []
    instructions = [line for line in lines if not line.endswith(":")]
    if not instructions:
        diagnostics.append("no instructions found")
    allowed_registers = {f"x{i}" for i in range(8)} | {"zero", "ra", "sp", "gp", "tp", "t0", "t1", "t2"}
    allowed_mnemonics = {"addi", "add", "beq"}
    if instructions and not re.fullmatch(r"addi\s+t0\s*,\s*zero\s*,\s*-?\d+", instructions[0], re.IGNORECASE):
        diagnostics.append("first instruction must be addi t0, zero, <integer input>")
    for index, instruction in enumerate(instructions, start=1):
        parts = re.split(r"\s+", instruction, maxsplit=1)
        mnemonic = parts[0].lower()
        operands = [item.strip() for item in parts[1].split(",")] if len(parts) == 2 else []
        if mnemonic not in allowed_mnemonics:
            diagnostics.append(f"instruction {index}: unsupported or debug mnemonic {mnemonic!r}")
            continue
        if mnemonic == "addi":
            valid = len(operands) == 3 and operands[0] in allowed_registers and operands[1] in allowed_registers and re.fullmatch(r"-?\d+", operands[2])
        elif mnemonic == "add":
            valid = len(operands) == 3 and all(item in allowed_registers for item in operands)
        else:
            valid = len(operands) == 3 and operands[0] in allowed_registers and operands[1] in allowed_registers and (operands[2] in labels or re.fullmatch(r"-?\d+", operands[2]))
        if not valid:
            diagnostics.append(f"instruction {index}: invalid operands or register")
    if instructions:
        final_match = re.fullmatch(r"beq\s+zero\s*,\s*zero\s*,\s*([A-Za-z_][A-Za-z0-9_]*)", instructions[-1], re.IGNORECASE)
        final_index = next((index for index, line in reversed(list(enumerate(lines))) if line == instructions[-1]), None)
        target = final_match.group(1) if final_match else None
        if not final_match or target not in labels:
            diagnostics.append("final instruction must be a stop self-branch: beq zero, zero, <label>")
        elif final_index is None or final_index == 0 or lines[final_index - 1] != target + ":":
            diagnostics.append("stop self-branch label must immediately precede the final instruction")
    if any(re.search(r"\b(?:ecall|ebreak|syscall|print|debug)\b", line, re.IGNORECASE) for line in lines):
        diagnostics.append("debug/output instructions are not allowed")
    if diagnostics:
        return False, "Assembly structure is incomplete", diagnostics
    return True, f"Parsed {len(instructions)} instructions with allowed mnemonics/registers", []


def _result(name: str, status: str, message: str, diagnostics: list[str] | None = None, elapsed: float = 0.0) -> CheckResult:
    return CheckResult(name=name, status=status, message=message, diagnostics=diagnostics or [], elapsed=elapsed)


def set_subresult(check: CheckResult, name: str, status: str, message: str, diagnostics: list[str] | None = None) -> None:
    check.subresults[name] = {"name": name, "status": status, "message": message, "diagnostics": diagnostics or []}


def aggregate_subresult_status(subresults: dict[str, dict]) -> str:
    statuses = [item.get("status") for item in subresults.values()]
    if not statuses or any(status in ("ERROR", "UNVERIFIED") for status in statuses):
        return "ERROR"
    if any(status == "FAIL" for status in statuses):
        return "FAIL"
    return "PASS" if all(status == "PASS" for status in statuses) else "ERROR"


def parse_logisim_result(output: str, expected_count: int | None = None) -> tuple[str, str]:
    """Interpret Logisim output conservatively.

    A zero exit code is insufficient: require a nonzero test count (or passed
    count) and an explicit zero failure count. This accepts normal summaries
    such as ``Tests: 25\nPassed: 25\nFailed: 0`` without treating the word
    ``Failed`` as a failure by itself.
    """
    text = output or ""
    def numbers(patterns: tuple[str, ...]) -> list[int]:
        found: list[int] = []
        for pattern in patterns:
            found.extend(int(match.group(1)) for match in re.finditer(pattern, text, re.IGNORECASE))
        return found
    tests = numbers((r"\b(?:tests?|vectors?|executed|total)[ \t]*[:=][ \t]*(\d+)", r"\b(\d+)[ \t]+(?:tests?|test[ \t]+vectors?|vectors?)\b"))
    passed = numbers((r"\bpassed[ \t]*[:=][ \t]*(\d+)", r"\b(\d+)[ \t]+passed\b"))
    failures = numbers((r"\b(?:failed|failures?)[ \t]*[:=][ \t]*(\d+)", r"\b(\d+)[ \t]+(?:failed|failures?)\b"))
    if not tests and not passed:
        return "ERROR", "Logisim output did not report a nonzero executed/passed test count"
    if not failures:
        return "ERROR", "Logisim output did not report an explicit failure count"
    if any(count > 0 for count in failures):
        return "FAIL", f"Logisim reported {max(failures)} failed vector(s)"
    if not passed:
        return "ERROR", "Logisim output did not report a passed vector count"
    executed = tests[-1] if tests else passed[-1]
    if expected_count is not None:
        if any(count != expected_count for count in tests + passed):
            return "ERROR", f"Logisim vector counts did not consistently match the {expected_count} expected vectors"
        executed = expected_count
    elif any(count != executed for count in tests + passed):
        return "ERROR", "Logisim test and passed counts were inconsistent"
    if executed <= 0:
        return "ERROR", "Logisim output reported no executed vectors"
    return "PASS", f"Logisim reported {executed} executed vector(s) and zero failures"


def copy_vector_for_logisim(source: Path, destination: Path) -> None:
    """Copy vectors byte-for-byte, including stateful metadata columns."""
    shutil.copyfile(source, destination)


def build_datapath_harness(source: Path, destination: Path, rom_words: list[str] | None = None) -> None:
    """Create a temporary Datapath-only harness for the supplied circuit.

    The student's circuit is read and copied. The temporary Datapath copy
    receives only the documented test instrumentation: an input clock pin, a
    PC debug output pin, and the reference ROM program. No source artifact is
    edited.
    """
    tree = ET.parse(source)
    root = tree.getroot()
    datapath = next((circuit for circuit in root.findall("circuit") if circuit.get("name") == "Datapath"), None)
    if datapath is None:
        raise ValueError("circuit has no Datapath subcircuit")
    clocks = [comp for comp in datapath.findall("comp") if comp.get("lib") == "0" and comp.get("name") == "Clock" and comp.get("loc") == "(70,390)"]
    if len(clocks) != 1:
        raise ValueError("Datapath clock harness point was not found")
    datapath.remove(clocks[0])
    roms = [comp for comp in datapath.findall("comp") if comp.get("lib") == "5" and comp.get("name") == "ROM"]
    if len(roms) != 1:
        raise ValueError("Datapath reference ROM was not found")
    rom_words = rom_words or ["00400293", "00228393", "005383b3", "00538663", "ffd38393", "fe000ce3", "00000033"]
    contents = "addr/data: 8 32\n" + " ".join(rom_words)
    content_nodes = [node for node in roms[0].findall("a") if node.get("name") == "contents"]
    if len(content_nodes) != 1:
        raise ValueError("Datapath ROM contents were not found")
    content_nodes[0].text = contents

    def pin(loc: str, label: str, pin_type: str, width: int | None, facing: str) -> ET.Element:
        comp = ET.Element("comp", {"lib": "0", "loc": loc, "name": "Pin"})
        ET.SubElement(comp, "a", {"name": "appearance", "val": "classic"})
        ET.SubElement(comp, "a", {"name": "facing", "val": facing})
        ET.SubElement(comp, "a", {"name": "label", "val": label})
        ET.SubElement(comp, "a", {"name": "type", "val": pin_type})
        if width is not None:
            ET.SubElement(comp, "a", {"name": "width", "val": str(width)})
        return comp

    datapath.append(pin("(70,390)", "CLK_TEST", "input", None, "south"))
    datapath.append(pin("(300,490)", "PCdbg", "output", 8, "west"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    tree.write(destination, encoding="utf-8", xml_declaration=True)


def build_factorial_datapath_vector(destination: Path, expected_t2: int, cycles: int = 200) -> None:
    """Build a temporary sequential vector that checks factorial's final t2."""
    rows = ["CLK_TEST t2[32] <set> <seq>", "0 <DC> 1 1"]
    for cycle in range(1, cycles + 1):
        value = f"0x{expected_t2 & 0xFFFFFFFF:08X}" if cycle == cycles - 1 else "<DC>"
        rows.append(f"{cycle % 2} {value} 1 {cycle + 1}")
    destination.write_text("\n".join(rows) + "\n", encoding="utf-8")


def assemble_text_words(java_path: Path, rars_path: Path, assembly_path: Path, destination: Path) -> list[str]:
    """Assemble a temporary RARS text dump and return its 32-bit words."""
    completed = subprocess.run(
        [str(java_path), "-jar", str(rars_path), "a", "dump", ".text", "HexText", str(destination), str(assembly_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"RARS assembly failed: {completed.stderr or completed.stdout}")
    words = [line.strip().lower() for line in destination.read_text(encoding="utf-8").splitlines() if re.fullmatch(r"[0-9a-fA-F]{8}", line.strip())]
    if not words:
        raise RuntimeError("RARS produced no text words")
    return words


def build_logisim_command(logisim_path: Path, subcircuit: str, vector_path: Path, circuit_path: Path, java_path: Path | None = None) -> list[str]:
    """Build Logisim evolution's documented test-vector invocation."""
    return [str(java_path or "java"), "-jar", str(logisim_path), "--test-vector", subcircuit, str(vector_path), str(circuit_path)]


class Grader:
    def __init__(self, repo_root: Path | None = None, circ_path: Path | None = None,
                 asm_path: Path | None = None, logisim_path: Path | None = None,
                 rars_path: Path | None = None, verbose: bool = False,
                 keep_temp: bool = False, on_update: Optional[Callable[[RunResult, str], None]] = None):
        self.repo_root = (repo_root or find_repo_root()).resolve()
        discovered_circ, discovered_asm = discover_inputs(self.repo_root)
        self.circ_path = Path(circ_path).resolve() if circ_path else discovered_circ
        self.asm_path = Path(asm_path).resolve() if asm_path else discovered_asm
        self.logisim_path = Path(logisim_path).resolve() if logisim_path else detect_tool(None, ("logisim", "logisim-evolution"), (self.repo_root / "tools",))
        self.rars_path = Path(rars_path).resolve() if rars_path else detect_tool(None, ("rars", "rars1_6"), (self.repo_root / "tools",))
        self.java_path = detect_java(self.repo_root)
        self.verbose = verbose
        self.keep_temp = keep_temp
        self.on_update = on_update
        self._lock = threading.Lock()
        self.current: RunResult | None = None

    def _emit(self, result: RunResult, line: str = "") -> None:
        if line:
            result.log.append(line)
        if self.on_update:
            self.on_update(result, line)

    def _paths(self) -> dict[str, str]:
        return {
            "processor_riscv.circ": str(self.circ_path) if self.circ_path else "(not found)",
            "factorial.S": str(self.asm_path) if self.asm_path else "(not found)",
            "Logisim jar": str(self.logisim_path) if self.logisim_path else "(not found)",
            "RARS jar": str(self.rars_path) if self.rars_path else "(not found)",
            "Java runtime": str(self.java_path) if self.java_path else "(not found)",
        }

    def run(self, selected: Iterable[int] = ASSIGNMENTS) -> RunResult:
        selected = tuple(dict.fromkeys(int(a) for a in selected if int(a) in ASSIGNMENTS))
        result = RunResult(state="RUNNING", started_at=time.time(), paths=self._paths(), verbose=self.verbose, keep_temp=self.keep_temp)
        result.assignments = {str(a): CheckResult(name=f"Assignment {a}") for a in selected}
        self.current = result
        self._emit(result, "Starting Lab 4 grader")
        self._emit(result, "processor_riscv.circ: " + result.paths["processor_riscv.circ"])
        self._emit(result, "factorial.S: " + result.paths["factorial.S"])
        handlers = {1: self._assignment1, 2: self._assignment2, 3: self._assignment3, 4: self._assignment4, 5: self._assignment5}
        for number in selected:
            check = result.assignments[str(number)]
            check.status = "RUNNING"
            started = time.perf_counter()
            self._emit(result, f"Assignment {number}: running")
            try:
                check = handlers[number](check, result)
            except Exception as exc:
                check.status = "ERROR"
                check.message = f"Unexpected grader error: {exc}"
                check.diagnostics.append(repr(exc))
            check.elapsed = time.perf_counter() - started
            result.assignments[str(number)] = check
            self._emit(result, f"Assignment {number}: {check.status} — {check.message}")
        result.finished_at = time.time()
        result.elapsed = result.finished_at - (result.started_at or result.finished_at)
        statuses = [check.status for check in result.assignments.values()]
        result.state = "PASS" if statuses and all(status == "PASS" for status in statuses) else ("ERROR" if any(status in ("ERROR", "UNVERIFIED") for status in statuses) else "FAIL")
        self._emit(result, f"Final state: {result.state} ({result.elapsed:.2f}s)")
        return result

    def _hardware_unavailable(self, check: CheckResult, tool: str) -> CheckResult:
        check.status = "ERROR"
        check.message = f"UNVERIFIED: {tool} is unavailable"
        check.diagnostics.append("Install/configure the tool and rerun this assignment.")
        return check

    def _vector_context(self, check: CheckResult, filename: str) -> None:
        vector = self.repo_root / "Bruno" / "tests" / filename
        if not vector.exists():
            check.diagnostics.append(f"Reference vector not found: {vector}")
            return
        ok, message, diagnostics = validate_vector_file(vector)
        check.diagnostics.append(message)
        if diagnostics:
            check.diagnostics.extend(diagnostics)

    def _run_logisim_vector(self, check: CheckResult, vector_name: str, subcircuit: str) -> CheckResult:
        """Run Logisim's documented vector mode against a temporary vector copy.

        The supplied register file vectors carry two bookkeeping columns that
        are not circuit pins, so they are removed in the temporary copy. The
        student's circuit is opened read-only by Logisim and is never edited.
        """
        if not self.logisim_path or not self.logisim_path.exists():
            return self._hardware_unavailable(check, "Logisim jar")
        source = self.repo_root / "Bruno" / "tests" / vector_name
        if not source.exists():
            check.status = "ERROR"; check.message = f"Reference vector was not found: {source}"; return check
        valid, validation_message, validation_diagnostics = validate_vector_file(source)
        if not valid:
            check.status = "ERROR"; check.message = validation_message
            check.diagnostics.extend(validation_diagnostics)
            return check
        expected_count = len(_parse_rows(source)[1])
        temp_path: Path | None = None
        temp_dir = None
        try:
            temp_dir = tempfile.TemporaryDirectory(prefix="lab4-grader-")
            temp_path = Path(temp_dir.name) / source.name
            copy_vector_for_logisim(source, temp_path)
            # Logisim evolution's documented order is circuit name, vector,
            # then project file. Preserve all vector metadata for sequential
            # components such as RegisterFile.
            command = build_logisim_command(self.logisim_path, subcircuit, temp_path, self.circ_path, self.java_path)
            # Logisim may emit Windows-1252 punctuation even when Python is
            # running in UTF-8 mode. Replace undecodable bytes so diagnostics
            # remain visible and the grader can still inspect the result.
            completed = subprocess.run(command, capture_output=True, text=True,
                                       encoding="utf-8", errors="replace", timeout=45)
            output = (completed.stdout + "\n" + completed.stderr).strip()
            if self.verbose and self.current:
                self._emit(self.current, output[-4000:])
            status, message = parse_logisim_result(output, expected_count)
            if completed.returncode != 0:
                status = "ERROR"
                message = f"Logisim exited with code {completed.returncode}"
            if status != "PASS":
                check.status = status
                check.message = f"Logisim {subcircuit}: {message}"
                check.diagnostics.append(output[-2500:] or message)
                return check
            check.status = "PASS"
            check.message = f"Logisim {subcircuit} vectors passed: {message}"
            check.diagnostics.append("Executed documented --test-vector mode with a temporary vector file.")
            return check
        except subprocess.TimeoutExpired:
            check.status = "ERROR"; check.message = f"Logisim {subcircuit} vector run timed out"; return check
        except OSError as exc:
            check.status = "ERROR"; check.message = f"Could not start Logisim: {exc}"; return check
        finally:
            if self.keep_temp and temp_path and temp_path.exists():
                keep = self.repo_root / "tools" / "lab4-autograder" / "temp"
                keep.mkdir(parents=True, exist_ok=True)
                shutil.copy2(temp_path, keep / temp_path.name)
            if temp_dir:
                temp_dir.cleanup()

    def _circ_missing(self, check: CheckResult) -> CheckResult | None:
        if not self.circ_path or not self.circ_path.exists():
            check.status = "ERROR"
            check.message = "processor_riscv.circ was not found"
            check.diagnostics.append("Use --circ to select the current circuit file.")
            return check
        return None

    def _assignment1(self, check: CheckResult, result: RunResult) -> CheckResult:
        if self._circ_missing(check): return check
        self._vector_context(check, "alu_tests.txt")
        return self._run_logisim_vector(check, "alu_tests.txt", "ALU")

    def _assignment2(self, check: CheckResult, result: RunResult) -> CheckResult:
        if self._circ_missing(check): return check
        self._vector_context(check, "registerfile_tests_v2.txt")
        return self._run_logisim_vector(check, "registerfile_tests_v2.txt", "RegisterFile")

    def _assignment3(self, check: CheckResult, result: RunResult) -> CheckResult:
        if self._circ_missing(check): return check
        self._vector_context(check, "controlunit_tests.txt")
        return self._run_logisim_vector(check, "controlunit_tests.txt", "ControlUnit")

    def _run_datapath_harness(self, check: CheckResult, result: RunResult) -> CheckResult:
        vector = self.repo_root / "Bruno" / "tests" / "datapath_assignment4_testvector.txt"
        if not vector.exists():
            check.status = "ERROR"; check.message = "Datapath reference vector was not found"; return check
        valid, validation_message, validation_diagnostics = validate_vector_file(vector)
        if not valid:
            for name in ("4.A", "4.B", "4.C", "4.D"):
                set_subresult(check, name, "ERROR", validation_message, validation_diagnostics)
            check.status = "ERROR"; check.message = validation_message; return check
        expected_count = len(_parse_rows(vector)[1])
        if not self.logisim_path or not self.logisim_path.exists():
            for name in ("4.A", "4.B", "4.C", "4.D"):
                set_subresult(check, name, "ERROR", "UNVERIFIED: Logisim jar is unavailable")
            return self._hardware_unavailable(check, "Logisim jar")
        if not self.java_path or not self.java_path.exists():
            for name in ("4.A", "4.B", "4.C", "4.D"):
                set_subresult(check, name, "ERROR", "UNVERIFIED: Java runtime is unavailable")
            return self._hardware_unavailable(check, "Java runtime")
        temporary_directory = None
        harness: Path | None = None
        try:
            temporary_directory = tempfile.TemporaryDirectory(prefix="lab4-datapath-")
            harness = Path(temporary_directory.name) / "processor_datapath_harness.circ"
            build_datapath_harness(self.circ_path, harness)
            command = build_logisim_command(self.logisim_path, "Datapath", vector, harness, self.java_path)
            completed = subprocess.run(command, capture_output=True, text=True,
                                       encoding="utf-8", errors="replace", timeout=60)
            output = (completed.stdout + "\n" + completed.stderr).strip()
            if self.verbose:
                self._emit(result, output[-5000:])
            status, message = parse_logisim_result(output, expected_count)
            if completed.returncode != 0:
                status = "ERROR"; message = f"Logisim exited with code {completed.returncode}"
            if status != "PASS":
                for name in ("4.A", "4.B", "4.C", "4.D"):
                    set_subresult(check, name, status, f"Datapath harness: {message}")
                check.status = status
                check.message = f"Datapath temporary harness: {message}"
                check.diagnostics.append(output[-3000:] or message)
                return check
            for name, detail in (
                ("4.A", "temporary clock input harness executed"),
                ("4.B", "reference ROM program loaded in the temporary copy"),
                ("4.C", "PCdbg output was included in 23 executed vectors"),
                ("4.D", "t2 output was included in 23 executed vectors"),
            ):
                set_subresult(check, name, "PASS", detail)
            check.status = "PASS"
            check.message = f"Datapath temporary harness passed: {message}"
            check.diagnostics.append("PCdbg and t2 were observed by the executed vector checker; no synthetic trace is reported.")
            return check
        except (OSError, ET.ParseError, ValueError, subprocess.TimeoutExpired) as exc:
            for name in ("4.A", "4.B", "4.C", "4.D"):
                set_subresult(check, name, "ERROR", f"UNVERIFIED: could not execute temporary harness ({exc})")
            check.status = "ERROR"; check.message = f"Datapath temporary harness unavailable: {exc}"; return check
        finally:
            if self.keep_temp and harness and harness.exists():
                keep = self.repo_root / "tools" / "lab4-autograder" / "temp"
                keep.mkdir(parents=True, exist_ok=True)
                shutil.copy2(harness, keep / harness.name)
            if temporary_directory:
                temporary_directory.cleanup()

    def _run_factorial_datapath(self, check: CheckResult, result: RunResult) -> None:
        """Run factorial's assembled text through a temporary Datapath copy."""
        if not self.circ_path or not self.circ_path.exists():
            set_subresult(check, "5.B", "ERROR", "UNVERIFIED: processor circuit was not found")
            return
        if not self.logisim_path or not self.logisim_path.exists():
            set_subresult(check, "5.B", "ERROR", "UNVERIFIED: Logisim jar is unavailable")
            return
        if not self.rars_path or not self.rars_path.exists() or not self.java_path or not self.java_path.exists():
            set_subresult(check, "5.B", "ERROR", "UNVERIFIED: RARS and Java are required to assemble the temporary ROM")
            return
        temporary_directory = None
        try:
            temporary_directory = tempfile.TemporaryDirectory(prefix="lab4-factorial-datapath-")
            directory = Path(temporary_directory.name)
            words = assemble_text_words(self.java_path, self.rars_path, self.asm_path, directory / "factorial.hex")
            input_match = re.search(r"(?im)^\s*addi\s+t0\s*,\s*zero\s*,\s*(-?\d+)\b", self.asm_path.read_text(encoding="utf-8"))
            if not input_match:
                raise ValueError("could not identify factorial input")
            input_value = int(input_match.group(1))
            if input_value < 0 or input_value > 8:
                raise ValueError(f"factorial input {input_value} is outside the bounded 0..8 harness range")
            expected = 1
            for value in range(2, input_value + 1):
                expected *= value
            harness = directory / "processor_factorial_harness.circ"
            vector = directory / "factorial_datapath_vectors.txt"
            build_datapath_harness(self.circ_path, harness, words)
            build_factorial_datapath_vector(vector, expected)
            completed = subprocess.run(
                build_logisim_command(self.logisim_path, "Datapath", vector, harness, self.java_path),
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            )
            output = (completed.stdout + "\n" + completed.stderr).strip()
            if self.verbose:
                self._emit(result, output[-5000:])
            expected_count = len(_parse_rows(vector)[1])
            status, message = parse_logisim_result(output, expected_count)
            if completed.returncode != 0:
                status = "ERROR"; message = f"Logisim exited with code {completed.returncode}"
            if status == "PASS":
                set_subresult(check, "5.B", "PASS", f"temporary Datapath factorial harness passed ({message}; final t2={expected})")
            else:
                set_subresult(check, "5.B", status, f"temporary Datapath factorial harness: {message}", [output[-3000:] or message])
        except (OSError, ET.ParseError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            set_subresult(check, "5.B", "ERROR", f"UNVERIFIED: factorial Datapath harness could not run ({exc})")
        finally:
            if temporary_directory:
                temporary_directory.cleanup()

    def _assignment4(self, check: CheckResult, result: RunResult) -> CheckResult:
        if self._circ_missing(check): return check
        self._vector_context(check, "datapath_assignment4_testvector.txt")
        return self._run_datapath_harness(check, result)

    def _assignment5(self, check: CheckResult, result: RunResult) -> CheckResult:
        set_subresult(check, "5.B", "ERROR", "UNVERIFIED: Logisim datapath harness is unavailable")
        if not self.asm_path or not self.asm_path.exists():
            set_subresult(check, "5.A", "ERROR", "factorial.S was not found")
            check.status = "ERROR"; check.message = "5.A ERROR; 5.B UNVERIFIED"; return check
        ok, message, diagnostics = validate_assembly(self.asm_path)
        if not ok:
            set_subresult(check, "5.A", "FAIL", message, diagnostics)
            check.status = "FAIL"; check.message = "5.A FAIL; 5.B UNVERIFIED"; check.diagnostics = diagnostics; return check
        check.message = message
        if not self.rars_path or not self.rars_path.exists():
            set_subresult(check, "5.A", "ERROR", "UNVERIFIED: RARS jar is unavailable")
            check.status = "ERROR"; check.message = "5.A UNVERIFIED; 5.B UNVERIFIED"; return check
        # Run several inputs from temporary copies. This catches solutions
        # that only happen to produce 3! and keeps all instrumentation outside
        # the student's submitted file.
        expected = {0: 1, 3: 6, 8: 40320}
        check.trace = []
        try:
            with tempfile.TemporaryDirectory(prefix="lab4-rars-") as directory:
                original = self.asm_path.read_text(encoding="utf-8")
                match_input = re.search(r"(?im)^(\s*addi\s+t0\s*,\s*zero\s*,\s*)(\d+)(\s*(?:#.*)?)$", original)
                if not match_input:
                    set_subresult(check, "5.A", "ERROR", "Could not identify the factorial input instruction")
                    check.status = "ERROR"; check.message = "5.A ERROR; 5.B UNVERIFIED"; return check
                for number, expected_value in expected.items():
                    temporary = Path(directory) / f"factorial-{number}.s"
                    patched = original[:match_input.start(2)] + str(number) + original[match_input.end(2):]
                    temporary.write_text(patched, encoding="utf-8")
                    if self.keep_temp:
                        keep = self.repo_root / "tools" / "lab4-autograder" / "temp"
                        keep.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(temporary, keep / temporary.name)
                    completed = subprocess.run(
                        [str(self.java_path or "java"), "-jar", str(self.rars_path), "nc", "1000", "x7", str(temporary)],
                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
                    )
                    output = completed.stdout + "\n" + completed.stderr
                    if self.verbose:
                        self._emit(result, output[-4000:])
                    if completed.returncode != 0:
                        message = f"RARS exited with code {completed.returncode} for n={number}"
                        set_subresult(check, "5.A", "ERROR", message, [output[-2000:]])
                        check.status = "ERROR"; check.message = "5.A ERROR; 5.B UNVERIFIED"; check.diagnostics.append(output[-2000:]); return check
                    # The supplied program intentionally loops at `stop`; the
                    # bounded step message confirms RARS reached that loop.
                    if "maximum step limit" not in output.lower():
                        message = f"RARS did not reach the bounded stop loop for n={number}"
                        set_subresult(check, "5.A", "ERROR", message)
                        check.status = "ERROR"; check.message = "5.A ERROR; 5.B UNVERIFIED"; return check
                    register = re.search(r"x7\s+0x([0-9a-fA-F]+)", output)
                    if not register:
                        message = f"RARS produced no t2/x7 result for n={number}"
                        set_subresult(check, "5.A", "ERROR", message)
                        check.status = "ERROR"; check.message = "5.A ERROR; 5.B UNVERIFIED"; return check
                    actual = int(register.group(1), 16)
                    check.trace.append({"input": number, "register": "t2/x7", "expected": expected_value, "actual": actual})
                    if actual != expected_value:
                        message = f"RARS result mismatch for n={number}: t2/x7 is {actual}, expected {expected_value}"
                        set_subresult(check, "5.A", "FAIL", message)
                        check.status = "FAIL"; check.message = "5.A FAIL; 5.B UNVERIFIED"; return check
        except (OSError, subprocess.TimeoutExpired) as exc:
            message = f"RARS could not be executed: {exc}"
            set_subresult(check, "5.A", "ERROR", message)
            check.status = "ERROR"; check.message = "5.A ERROR; 5.B UNVERIFIED"; return check
        set_subresult(check, "5.A", "PASS", "RARS execution passed for n=0, 3, and 8", ["t2/x7 results are included in the trace."])
        self._run_factorial_datapath(check, result)
        check.status = aggregate_subresult_status(check.subresults)
        check.message = f"5.A PASS; 5.B {check.subresults['5.B']['status']}"
        return check


def format_summary(result: RunResult) -> str:
    lines = [f"Lab 4 grader: {result.state} ({result.elapsed:.2f}s)"]
    for label, path in result.paths.items():
        lines.append(f"  {label}: {path}")
    for number, check in result.assignments.items():
        lines.append(f"  Assignment {number}: {check.status:<10} {check.message}")
        for subname, sub in check.subresults.items():
            lines.append(f"    {subname}: {sub.get('status', 'ERROR'):<10} {sub.get('message', '')}")
        for diagnostic in check.diagnostics:
            lines.append(f"    {diagnostic}")
    if result.verbose and result.log:
        lines.append("Verbose log:")
        lines.extend(f"  {line}" for line in result.log)
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local autograder for KTH IS1200/IS1500 Lab 4")
    parser.add_argument("--repo", type=Path, help="repository root (defaults to the containing Git checkout)")
    parser.add_argument("--circ", type=Path, help="processor_riscv.circ path")
    parser.add_argument("--asm", type=Path, help="factorial.S/factorial.s path")
    parser.add_argument("--logisim", type=Path, help="Logisim evolution jar path")
    parser.add_argument("--rars", type=Path, help="RARS jar path")
    parser.add_argument("--assignment", "-a", type=int, action="append", choices=ASSIGNMENTS, help="run only this assignment (repeatable)")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--verbose", action="store_true", help="include verbose tool output")
    parser.add_argument("--keep-temp", action="store_true", help="keep temporary generated harness files")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    grader = Grader(repo_root=args.repo, circ_path=args.circ, asm_path=args.asm, logisim_path=args.logisim, rars_path=args.rars, verbose=args.verbose, keep_temp=args.keep_temp)
    selected = args.assignment or ASSIGNMENTS
    result = grader.run(selected)
    print(json.dumps(result.to_dict(), indent=2) if args.json else format_summary(result))
    return 0 if result.state == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
