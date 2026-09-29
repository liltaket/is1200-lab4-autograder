# IS1200 / IS1500 Lab 4 local autograder

A local verification tool for the Lab 4 processor circuit and factorial assembly. The command line engine in `grader.py` is the source of truth; `app.py` presents the same results in a browser on your computer. Both report `PASS`, `FAIL`, and `ERROR` separately so an unavailable tool is not mistaken for a passing submission.

The grader reads the selected student files. It creates temporary vector copies, circuit harnesses, and assembly variants for its checks; it does not edit the submitted circuit or assembly source.

## Requirements

| Tool | Required version or form | Used for |
| --- | --- | --- |
| Windows | Windows 11 | Setup steps below |
| Python | 3.10 or newer | Grader and local web UI; standard library only |
| Java | 21 or newer | Running Logisim Evolution 4.1.0 and RARS |
| Logisim Evolution | 4.1.0 all-in-one JAR | Circuit vector checks |
| RARS | RARS JAR | Assembly and factorial checks |
| Git | Current Git for Windows | Cloning the repositories |

Logisim Evolution 4.1.0 requires Java 21. Keep the Logisim and RARS JARs as local files; the grader invokes them through Java. The UI itself does not download dependencies. See the [official Logisim Java requirements](https://github.com/logisim-evolution/logisim-evolution/blob/main/docs/developers.md).

## Windows 11: install and run

1. Install Git for Windows, Python 3.10 or newer, and Java 21 or newer. Open a **new PowerShell window** and check the commands:

   ```powershell
   git --version
   py -3 --version
   java -version
   ```

   If the Python launcher `py` is unavailable, use the `python` command in the examples below after checking `python --version`.

2. Clone the Lab 4 repository, or open PowerShell in your existing Lab 4 checkout. A new checkout can be created with:

   ```powershell
   git clone https://github.com/liltaket/IS1200-Lab4.git
   Set-Location .\IS1200-Lab4
   ```

3. Install this autograder inside that checkout. From the **Lab 4 repository root**:

   ```powershell
   New-Item -ItemType Directory -Force .\tools | Out-Null
   git clone https://github.com/liltaket/is1200-lab4-autograder.git .\tools\lab4-autograder
   ```

   If `tools\lab4-autograder` already exists, update that checkout instead of cloning over it. Keep your circuit, assembly, and test files in their existing locations.

4. Download the [Logisim Evolution **4.1.0 all-in-one JAR**](https://github.com/logisim-evolution/logisim-evolution/releases/download/v4.1.0/logisim-evolution-4.1.0-all.jar) and a [RARS JAR from its official releases](https://github.com/TheThirdOne/rars/releases). Place both in the Lab 4 repository's `tools` folder, for example:

   ```text
   IS1200-Lab4\tools\logisim-evolution-4.1.0-all.jar
   IS1200-Lab4\tools\rars1_6.jar
   ```

   The grader searches `tools` and common local installation folders. To use JARs in other locations, pass `--logisim` and `--rars` to the CLI as shown below.

5. Start the local interface:

   ```powershell
   Set-Location .\tools\lab4-autograder
   py -3 -X utf8 app.py
   ```

   The interface opens at `http://127.0.0.1:8000` by default. If your browser does not open automatically, enter that address manually. Keep PowerShell open while using the interface; press `Ctrl+C` to stop the server.

Choose **Run all tests** or an individual assignment. The result table shows status, elapsed time, and expandable diagnostics. The input and tool inspector shows the exact selected paths. **Rerun failed** repeats assignments marked `FAIL`, `ERROR`, or `UNVERIFIED`. The verbose option includes more tool output; keep-temp retains generated harness copies for inspection.

## Command line use

From `tools\lab4-autograder`:

```powershell
py -3 -X utf8 grader.py
py -3 -X utf8 grader.py --assignment 5 --json
py -3 -X utf8 grader.py --logisim "C:\path\to\logisim-evolution-4.1.0-all.jar" --rars "C:\path\to\rars.jar"
```

Use `py -3 -X utf8 grader.py --help` for all options, including `--circ`, `--asm`, and `--repo` when automatic file discovery selects the wrong inputs. The CLI prints selected absolute paths and returns a nonzero exit code when the run does not pass.

The browser UI reads the same grader engine through `GET /api/status` and starts a run through `POST /api/run`. For example, the JSON body `{"assignments":[4,5],"verbose":true,"keep_temp":true}` selects two assignments.

## What the results mean

- **PASS:** The executed check produced the expected result.
- **FAIL:** The check ran and found a mismatch.
- **ERROR / UNVERIFIED:** The check could not establish a result, such as when a required JAR or Java is unavailable. A process exit by itself never creates a PASS.

Assignments 1–3 run the supplied circuit vectors. Assignment 4 runs a reference program in a temporary Datapath copy with clock and PC observation pins; its vectors check PC and `t2` values. Assignment 5 separates the RARS assembly check (5.A) from the Datapath run (5.B). Check 5.A tests factorial inputs 0, 3, and 8. Check 5.B assembles the **current selected source**, loads its words into a temporary Datapath ROM, and checks the final `t2` value at a bounded sample point. **5.B checks final `t2` only; it does not independently verify every intermediate register or PC state.** Interpret it alongside 5.A and Assignment 4. Inputs above 8 are outside the bounded 5.B harness range and remain unverified.

## Copy-paste prompt for a coding agent

Give the following prompt to an agent with access to your Windows computer. It should inspect your checkout and report the paths it used before making changes.

```text
Set up and start the local IS1200/IS1500 Lab 4 autograder on my Windows 11 computer.

1. Locate my existing IS1200-Lab4 repository. If there are several candidates, show me their paths and identify the one containing my current processor_riscv.circ and factorial.s files. Do not overwrite or edit either student source file or any Lab 4 test vectors.
2. In the selected Lab 4 repository, install or update https://github.com/liltaket/is1200-lab4-autograder.git at tools/lab4-autograder. Preserve unrelated local files and changes. If that destination has local changes or is not the expected checkout, inspect and explain before replacing anything.
3. Verify Python 3.10+, Java 21+, the Logisim Evolution 4.1.0 all-in-one JAR, and a RARS JAR. Check the local tools folder and normal installation locations. Report each dependency's version or path. Do not claim a check passed when a dependency is missing; tell me exactly what to install or where to place it.
4. From tools/lab4-autograder, run the CLI help command to verify Python can load the grader. Then start app.py bound to localhost (127.0.0.1), open http://127.0.0.1:8000, and tell me which repository, circuit, assembly, Logisim, RARS, and Java paths the grader selected. Keep the server available for me to use.
5. If a dependency or startup step fails, report the error and the next concrete step. Do not modify my circuit or assembly to make a check pass.
```

## Local code checks

From `tools\lab4-autograder`:

```powershell
py -3 -X utf8 -m unittest discover -s tests -v
```

These Python tests check grading and harness logic. Circuit and assembly results still require Logisim Evolution, RARS, and the selected student files.
