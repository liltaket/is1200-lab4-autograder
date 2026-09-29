# Product

<!-- impeccable:product-schema 1 -->

## Name

Lab 4 Verify is the public-facing name. The repository remains `is1200-lab4-autograder`; the interface and documentation use “Lab 4 Verify” consistently.

## Platform

web

## Users

KTH IS1200/IS1500 students working on Lab 4 who want to check their local processor circuit and factorial assembly implementation. They may use a coding agent to install and operate the grader.

## Product Purpose

Run local, repeatable checks for the Lab 4 processor and show actionable results. Success means the student can identify what passed, failed, or could not be verified without mistaking a completed process for a correct submission.

## Positioning

The web UI and command line share one grading engine; the CLI is the source of truth. Temporary harnesses provide processor instrumentation without changing the student's submission.

## Operating Context

The grader runs on the student's Windows computer against a local checkout of the course repository. It invokes Logisim Evolution and RARS and serves its UI only on localhost.

## Capabilities and Constraints

- Checks Assignments 1–5 using the selected `processor_riscv.circ` and `factorial.s` files.
- Distinguishes PASS, FAIL, and ERROR/UNVERIFIED. Missing tools and unsupported harnesses do not produce PASS.
- Uses temporary copies for circuit instrumentation and input variants.
- Requires Python 3.10+, Java 21+ for Logisim Evolution 4.1.0, Logisim Evolution 4.1.0, and a RARS jar for assembly checks.
- Does not edit or upload student source files.

## Evidence on Hand

The current selected source files are in the public course repository `liltaket/IS1200-Lab4`. No external endorsement, benchmark, or certification is claimed.

## Product Principles

- A PASS must be backed by executed checks and matching result counts.
- Make failures and unavailable checks easy to distinguish.
- Keep setup understandable to both students and coding agents.
- Keep instrumentation and temporary artifacts out of submitted files.

## Identity and Voice

- The original `logo.svg` is a compact circuit trace mark. Its stepped route and terminal point suggest the processor checks without implying an observed waveform.
- The interface uses dark ink surfaces (`#101a22`, `#1b2932`), pale text (`#edf3f4`), and technical blue (`#8ac7e8`). Green, red, and amber distinguish PASS, FAIL, and ERROR/UNVERIFIED alongside text labels.
- Copy is concise, factual, and action-oriented. State exactly what ran, what matched, and what could not be verified. Do not claim certification, endorsement, or coverage beyond the executed checks.
