# Lab 4 Verify interface design

## Brand

“Lab 4 Verify” is the product name in the browser title, workbench header, and README. The compact `logo.svg` is an original circuit trace mark with a stepped route and terminal point. Use the same SVG at small sizes for the in-app mark and favicon; keep its viewBox intact so it scales cleanly. The mark signals a technical checker, not measured data.

## Direction

The local UI is a verification workbench informed by a logic-analyzer report: compact, ruled tables make each check and state easy to scan, while the inspector keeps tool paths and run context close by. The layout does not invent waveforms or execution traces; it renders only data reported by the grader.

## Visual system

- Dark ink `#101a22` and sheet `#1b2932` are the page and workbench surfaces. Pale `#edf3f4` is the primary text, with muted `#b0c0c6` for secondary copy. Rules use `#354851` and `#627983`.
- Technical blue `#8ac7e8` marks links and active progress. The primary button uses `#236b94` with white text. The SVG shares the blue accent.
- PASS uses green `#7cd8ad`, FAIL uses red `#ffa099`, and ERROR/UNVERIFIED uses amber `#efc982`. Text labels accompany color; no status depends on color alone.
- System sans-serif handles interface copy. Monospace is reserved for paths, times, logs, and traces.
- Fine dividers structure the results table and tool inspector. Use spacing and typography for hierarchy instead of nested card grids.

## Voice

- Name controls by action: “Run all tests,” individual assignment buttons, and “Rerun failed.”
- Describe evidence directly. PASS means an executed check matched; ERROR means the grader could not verify the check.
- Keep limitations visible and specific. The 5.B harness checks final `t2` at a bounded sample point; it does not show an intermediate trace.

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
