import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parents[1]))

from grader import (
    build_logisim_command,
    build_parser,
    copy_vector_for_logisim,
    discover_inputs,
    aggregate_subresult_status,
    build_datapath_harness,
    build_factorial_datapath_vector,
    Grader,
    parse_logisim_result,
    validate_assembly,
    validate_vector_file,
)


class GraderLogicTests(unittest.TestCase):
    def test_discovers_nested_lab4_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            circ_source = root / "Bruno" / "circuits" / "processor_riscv.circ"
            asm_source = root / "Bruno" / "Assembly" / "Lab 4" / "factorial.s"
            circ_source.parent.mkdir(parents=True)
            asm_source.parent.mkdir(parents=True)
            circ_source.write_text("<project />", encoding="utf-8")
            asm_source.write_text("addi t0, zero, 3\n", encoding="utf-8")
            circ, asm = discover_inputs(root)
            self.assertEqual(circ, circ_source)
            self.assertEqual(asm, asm_source)

    def test_vector_parser_accepts_comments_and_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vectors.txt"
            path.write_text("# comment\nA B\n1 2\n", encoding="utf-8")
            self.assertEqual(validate_vector_file(path), (True, "Parsed 1 vectors from vectors.txt", []))

    def test_assembly_validation_requires_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "factorial.s"
            path.write_text("addi t2, zero, 1\n", encoding="utf-8")
            ok, _message, diagnostics = validate_assembly(path)
            self.assertFalse(ok)
            self.assertTrue(diagnostics)

    def test_current_factorial_passes_strict_static_validation(self):
        source = """addi t0, zero, 3
addi t2, zero, 1
beq t0, zero, stop
outer:
add t1, zero, t0
addi ra, zero, 0
inner:
beq t1, zero, done_mul
add ra, ra, t2
addi t1, t1, -1
beq zero, zero, inner
done_mul:
addi t2, ra, 0
addi t0, t0, -1
beq t0, zero, stop
beq zero, zero, outer
stop:
beq zero, zero, stop
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "factorial.s"
            path.write_text(source, encoding="utf-8")
            ok, message, diagnostics = validate_assembly(path)
            self.assertTrue(ok, (message, diagnostics))

    def test_logisim_result_requires_counts_and_handles_failed_zero(self):
        self.assertEqual(parse_logisim_result("Tests: 25\nPassed: 25\nFailed: 0"), ("PASS", "Logisim reported 25 executed vector(s) and zero failures"))
        self.assertEqual(parse_logisim_result("Failed: 0" )[0], "ERROR")
        self.assertEqual(parse_logisim_result("Tests: 25\nPassed: 24\nFailed: 1")[0], "FAIL")
        mixed = "Tests: 23\nPassed: 23\nFailed: 0\nTests: 1\nPassed: 0\nFailed: 1"
        self.assertEqual(parse_logisim_result(mixed)[0], "FAIL")
        self.assertEqual(parse_logisim_result("Passed: 24\nFailed: 0", expected_count=25)[0], "ERROR")

    def test_logisim_command_uses_documented_argument_order(self):
        command = build_logisim_command(Path("logisim.jar"), "RegisterFile", Path("vectors.txt"), Path("processor.circ"))
        self.assertEqual(command[4:], ["RegisterFile", "vectors.txt", "processor.circ"])

    def test_registerfile_vector_metadata_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "registerfile_tests_v2.txt"
            destination = Path(directory) / "copied.txt"
            source.write_text("A B <set> <seq>\n0 1 1 1\n", encoding="utf-8")
            copy_vector_for_logisim(source, destination)
            self.assertEqual(destination.read_bytes(), source.read_bytes())
            self.assertIn(b"<set> <seq>", destination.read_bytes())

    def test_assignment5_subresult_aggregation_keeps_unverified_as_error(self):
        self.assertEqual(aggregate_subresult_status({"5.A": {"status": "PASS"}, "5.B": {"status": "ERROR"}}), "ERROR")
        self.assertEqual(aggregate_subresult_status({"5.A": {"status": "PASS"}, "5.B": {"status": "PASS"}}), "PASS")

    def test_datapath_harness_is_temporary_and_instruments_expected_pins(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "processor.circ"
            source.write_text('''<project><circuit name="Datapath">
<comp lib="0" loc="(70,390)" name="Clock" />
<comp lib="5" loc="(360,520)" name="ROM"><a name="contents" val="old" /></comp>
</circuit></project>''', encoding="utf-8")
            original = source.read_bytes()
            destination = Path(directory) / "harness.circ"
            build_datapath_harness(source, destination)
            text = destination.read_text(encoding="utf-8")
            self.assertIn('label" val="CLK_TEST', text)
            self.assertIn('label" val="PCdbg', text)
            self.assertIn("00400293 00228393 005383b3", text)
            self.assertEqual(source.read_bytes(), original)

    def test_factorial_datapath_vector_preserves_state_sequence_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "factorial.txt"
            build_factorial_datapath_vector(destination, 6, cycles=4)
            lines = destination.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], "CLK_TEST t2[32] <set> <seq>")
            self.assertEqual(lines[-2], "1 0x00000006 1 4")
            self.assertEqual(lines[-1], "0 <DC> 1 5")

    def test_missing_logisim_remains_unverified(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            circ = repo / "processor_riscv.circ"
            circ.write_text("<project />", encoding="utf-8")
            result = Grader(repo_root=repo, circ_path=circ, logisim_path=repo / "does-not-exist.jar").run([1])
            self.assertEqual(result.assignments["1"].status, "ERROR")
            self.assertIn("UNVERIFIED", result.assignments["1"].message)

    def test_cli_parser_help_shape(self):
        parser = build_parser()
        args = parser.parse_args(["--assignment", "5", "--json", "--verbose"])
        self.assertEqual(args.assignment, [5])
        self.assertTrue(args.json)
        self.assertTrue(args.verbose)


if __name__ == "__main__":
    unittest.main()
