# Interface design

## Direction

The local UI is a verification workbench informed by a logic-analyzer report: compact, ruled tables make each check and state easy to scan, while the inspector keeps tool paths and run context close by. The layout does not invent waveforms or execution traces; it renders only data reported by the grader.

## Visual system

- Deep ink surfaces and pale text form the dark interface. Technical blue marks the primary action and active progress.
- PASS uses green, FAIL uses red, and ERROR/UNVERIFIED uses amber. Text labels accompany color.
- System sans-serif handles interface copy. Monospace is reserved for paths, times, logs, and traces.
- Fine dividers structure the results table and tool inspector. Use spacing and typography for hierarchy instead of nested card grids.

## Interaction

- Run all tests is the primary action; assignments 1–5 and rerun-failed remain available as secondary controls.
- Overall and assignment status come from the shared CLI grading engine.
- Diagnostics expand in place. The UI polls the JSON status endpoint during a run and does not derive PASS from process completion.
- The layout collapses to a single column on narrow screens. Keyboard focus and reduced-motion preferences remain visible and respected.

## Product constraints

- Keep the listener on localhost by default.
- Preserve the distinction between FAIL and ERROR/UNVERIFIED.
- Never display a synthetic trace as observed data.
- Keep student sources read-only; temporary instrumentation belongs in generated copies.
