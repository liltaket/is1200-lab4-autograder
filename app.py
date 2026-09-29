"""Small standard-library localhost UI for Lab 4 Verify."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from grader import ASSIGNMENTS, Grader, RunResult, find_repo_root


ROOT = find_repo_root(Path(__file__))
state_lock = threading.Lock()
state = RunResult(state="IDLE", paths={})
worker: threading.Thread | None = None


def update_state(result: RunResult, _line: str = "") -> None:
    global state
    with state_lock:
        state = result


def start_run(assignments: tuple[int, ...], options: dict | None = None) -> bool:
    global worker, state
    options = options or {}
    with state_lock:
        if worker and worker.is_alive():
            return False
        grader = Grader(
            repo_root=Path(options.get("repo", ROOT)),
            circ_path=Path(options["circ"]) if options.get("circ") else None,
            asm_path=Path(options["asm"]) if options.get("asm") else None,
            logisim_path=Path(options["logisim"]) if options.get("logisim") else None,
            rars_path=Path(options["rars"]) if options.get("rars") else None,
            verbose=bool(options.get("verbose")),
            keep_temp=bool(options.get("keep_temp")),
            on_update=update_state,
        )
        state = RunResult(state="RUNNING", paths=grader._paths(), verbose=grader.verbose, keep_temp=grader.keep_temp)

        def run() -> None:
            grader.run(assignments)

        worker = threading.Thread(target=run, name="lab4-grader", daemon=True)
        worker.start()
        return True


HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lab 4 Verify · Local autograder</title>
<meta name="theme-color" content="#101a22">
<link rel="icon" type="image/svg+xml" href="/logo.svg">
<style>
:root{color-scheme:dark;--paper:#101a22;--sheet:#1b2932;--ink:#edf3f4;--muted:#b0c0c6;--rule:#354851;--rule-strong:#627983;--blue:#8ac7e8;--blue-soft:#244456;--pass:#7cd8ad;--pass-bg:#1a3d31;--fail:#ffa099;--fail-bg:#452d30;--error:#efc982;--error-bg:#473821;--pending:#bdcbd0;--pending-bg:#2b3a43;--mono:ui-monospace,SFMono-Regular,Consolas,"Liberation Mono",monospace;--sans:system-ui,-apple-system,"Segoe UI",sans-serif}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:14px/1.45 var(--sans)}button,input,summary{font:inherit}button{cursor:pointer}button:disabled{cursor:not-allowed;opacity:.52}button:focus-visible,input:focus-visible,summary:focus-visible{outline:3px solid #247fb3;outline-offset:3px}main{max-width:1320px;margin:auto;padding:30px 32px 44px}.topline{display:flex;align-items:center;gap:12px;padding-bottom:13px;border-bottom:2px solid var(--ink);font:700 11px var(--mono);letter-spacing:.1em;text-transform:uppercase}.topline .mark{display:block;width:23px;height:23px;flex:none}.topline .right{margin-left:auto;color:var(--muted);font-weight:500;letter-spacing:.04em}.masthead{display:flex;justify-content:space-between;align-items:end;gap:24px;padding:25px 0 24px}h1{font-size:clamp(28px,3vw,41px);line-height:1.07;letter-spacing:-.035em;margin:0 0 8px;font-weight:700}h2{font-size:16px;letter-spacing:-.015em;margin:0}.lede{margin:0;color:var(--muted);max-width:64ch}.overall{display:flex;align-items:center;gap:12px;min-width:205px;padding:13px 16px;border:1px solid var(--rule-strong);background:var(--sheet)}.overall .state{font:800 16px var(--mono);letter-spacing:.03em}.overall .dot{width:11px;height:11px;border-radius:50%;background:var(--pending)}.overall .meta{font:11px var(--mono);color:var(--muted);margin-left:auto}.overall.PASS{border-color:#70aa89;background:var(--pass-bg);color:var(--pass)}.overall.FAIL{border-color:#d59c96;background:var(--fail-bg);color:var(--fail)}.overall.ERROR,.overall.UNVERIFIED{border-color:#d7b278;background:var(--error-bg);color:var(--error)}.overall.RUNNING{border-color:#83afca;background:var(--blue-soft);color:var(--blue)}.overall.PASS .dot{background:var(--pass)}.overall.FAIL .dot{background:var(--fail)}.overall.ERROR .dot,.overall.UNVERIFIED .dot{background:var(--error)}.overall.RUNNING .dot{background:var(--blue);animation:pulse 1.2s ease-in-out infinite}@keyframes pulse{50%{opacity:.3}}
.workbench{display:grid;grid-template-columns:minmax(0,1fr) 314px;border:1px solid var(--rule-strong);background:var(--sheet)}.maincol{min-width:0}.sidecol{border-left:1px solid var(--rule)}.toolbar{padding:18px 20px;border-bottom:1px solid var(--rule);background:#202f38}.toolbar-top{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap}.actions{display:flex;gap:7px;flex-wrap:wrap}.button{min-height:38px;border:1px solid var(--rule-strong);background:var(--sheet);color:var(--ink);padding:7px 12px;font-weight:650;white-space:nowrap}.button:hover:not(:disabled){background:var(--blue-soft);border-color:var(--blue)}.button.primary{background:#236b94;border-color:#337fa8;color:#fff}.button.primary:hover:not(:disabled){background:#2c7eac}.button.small{font:700 12px var(--mono);min-width:38px;padding:7px 10px}.options{display:flex;gap:16px;align-items:center;flex-wrap:wrap;color:var(--muted);font-size:12px}.options label{display:inline-flex;align-items:center;gap:6px;white-space:nowrap}.options input{accent-color:var(--blue)}.runline{display:flex;align-items:center;gap:12px;margin-top:16px}.runline .caption{font:600 11px var(--mono);text-transform:uppercase;letter-spacing:.06em;white-space:nowrap;color:var(--muted)}.progress{height:4px;flex:1;background:#344750;overflow:hidden}.progress i{display:block;width:100%;height:100%;background:var(--blue);transform:scaleX(0);transform-origin:left center;transition:transform .25s}.runline .count{font:12px var(--mono);color:var(--muted);min-width:43px;text-align:right}.notice{min-height:19px;margin:10px 0 0;color:var(--muted);font-size:12px}.notice.error{color:var(--fail);font-weight:650}.sectionhead{display:flex;justify-content:space-between;align-items:baseline;gap:12px;padding:17px 20px 12px}.sectionhead p{margin:0;color:var(--muted);font-size:12px}.legend{display:flex;gap:12px;flex-wrap:wrap;padding:0 20px 14px;color:var(--muted);font-size:11px}.legend strong{font:700 11px var(--mono);margin-right:3px}.legend .p{color:var(--pass)}.legend .f{color:var(--fail)}.legend .e{color:var(--error)}
.results{width:100%;border-collapse:collapse;table-layout:fixed}.results th{text-align:left;background:#263741;border-top:1px solid var(--rule);border-bottom:1px solid var(--rule-strong);padding:8px 20px;font:700 10px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}.results th:nth-child(1){width:27%}.results th:nth-child(2){width:18%}.results th:nth-child(3){width:12%;text-align:right}.results th:nth-child(4){width:43%}.results td{border-bottom:1px solid var(--rule);padding:12px 20px;vertical-align:top}.results tr:last-child td{border-bottom:0}.results .assn{font-weight:700}.results .assn small{display:block;color:var(--muted);font:11px var(--mono);margin-top:2px}.results .elapsed{text-align:right;font:12px var(--mono);color:var(--muted);padding-top:15px}.status{display:inline-flex;align-items:center;gap:5px;font:800 11px var(--mono);letter-spacing:.03em}.status::before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor}.status.PASS{color:var(--pass)}.status.FAIL{color:var(--fail)}.status.ERROR,.status.UNVERIFIED{color:var(--error)}.status.RUNNING{color:var(--blue)}.status.PENDING,.status.IDLE{color:var(--pending)}.resultmsg{color:var(--muted);font-size:12px;line-height:1.4}.resultmsg .message{display:block}.resultmsg details{margin-top:6px}.resultmsg summary{color:var(--blue);cursor:pointer;font-weight:650;list-style-position:inside}.resultmsg summary:hover{text-decoration:underline}.resultmsg pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:280px;overflow:auto;padding:10px 11px;background:#14232c;color:var(--ink);font:11px/1.5 var(--mono);border:1px solid var(--rule);margin:7px 0 0}.empty{padding:27px 20px;color:var(--muted)}
.sidehead{padding:19px 18px 12px;border-bottom:1px solid var(--rule)}.sidehead p{margin:3px 0 0;color:var(--muted);font-size:12px}.inspector{padding:4px 18px 15px}.pathitem{padding:12px 0;border-bottom:1px solid var(--rule)}.pathitem:last-child{border:0}.pathitem dt{font:700 10px var(--mono);letter-spacing:.07em;text-transform:uppercase;color:var(--muted);margin-bottom:4px}.pathitem dd{margin:0;font:12px/1.45 var(--mono);overflow-wrap:anywhere}.footnote{border-top:1px solid var(--rule);padding:13px 18px;color:var(--muted);font-size:11px;line-height:1.5}.lower{display:grid;grid-template-columns:minmax(0,1fr) 314px;gap:0;margin-top:20px;border:1px solid var(--rule-strong);background:var(--sheet)}.lower section{min-width:0}.lower section+section{border-left:1px solid var(--rule)}.lower .sectionhead{padding:15px 18px 11px}.console,.summary{margin:0 18px 18px;padding:14px;min-height:138px;max-height:240px;overflow:auto;background:#0e1b23;color:#e0edf0;font:11px/1.55 var(--mono);white-space:pre-wrap;overflow-wrap:anywhere}.summary{background:#15242d;color:var(--ink);border:1px solid var(--rule)}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
@media(max-width:1080px){.workbench{grid-template-columns:minmax(0,1fr) 280px}.lower{grid-template-columns:minmax(0,1fr) 280px}.toolbar-top{align-items:flex-start}.options{width:100%}}@media(max-width:760px){main{padding:18px 14px 28px}.topline .right{display:none}.masthead{display:block;padding:22px 0}.overall{display:inline-flex;margin-top:19px}.workbench,.lower{display:block}.sidecol,.lower section+section{border-left:0;border-top:1px solid var(--rule)}.toolbar{padding:15px}.sectionhead{padding:16px 15px 12px}.legend{padding:0 15px 12px}.results th,.results td{padding-left:12px;padding-right:10px}.results th:nth-child(1){width:27%}.results th:nth-child(2){width:20%}.results th:nth-child(3){width:14%}.results th:nth-child(4){width:39%}.results .assn small{display:none}.results .assn{font-size:12px}.resultmsg{font-size:11px}.button{min-height:42px}.console,.summary{margin:0 15px 15px}}@media(max-width:520px){.results th:nth-child(3),.results td:nth-child(3){display:none}.results th:nth-child(1){width:30%}.results th:nth-child(2){width:23%}.results th:nth-child(4){width:47%}.results td{padding-top:13px;padding-bottom:13px}.resultmsg .message{max-height:2.9em;overflow:hidden}.toolbar-top{gap:12px}.actions{gap:6px}.button.primary{width:100%}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}.progress i{transition:none}.overall.RUNNING .dot{animation:none}}
</style>
</head>
<body>
<!-- THESIS: A local verification workbench laid out like an instrument trace sheet. OWN-WORLD: Deep ink surfaces, ruled tables, technical blue controls and explicit result colors. STORY: Select checks, watch progress, inspect evidence and paths. FIRST VIEWPORT: Run controls sit above one compact results table, with input paths at its side. FORM: Operator workbench. FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md. -->
<main>
<div class="topline"><img class="mark" src="/logo.svg" alt=""><span>Lab 4 Verify</span><span class="right">IS1200 / IS1500 · LOCAL</span></div>
<header class="masthead"><div><h1>Processor verification</h1><p class="lede">Run the local Lab 4 checks and inspect the evidence behind each result. The command line grader is the source of truth.</p></div><div id="overall" class="overall IDLE" role="status" aria-live="polite" aria-atomic="true"><span class="dot" aria-hidden="true"></span><span id="overall-text" class="state">IDLE</span><span id="elapsed" class="meta">0.00s</span></div></header>
<div class="workbench"><div class="maincol"><div class="toolbar"><div class="toolbar-top"><div class="actions" aria-label="Run checks"><button class="button primary" onclick="runAll()">Run all tests</button><button class="button small" onclick="runOne(1)" aria-label="Run Assignment 1">A1</button><button class="button small" onclick="runOne(2)" aria-label="Run Assignment 2">A2</button><button class="button small" onclick="runOne(3)" aria-label="Run Assignment 3">A3</button><button class="button small" onclick="runOne(4)" aria-label="Run Assignment 4">A4</button><button class="button small" onclick="runOne(5)" aria-label="Run Assignment 5">A5</button><button class="button" id="retry" onclick="rerunFailed()" disabled>Rerun failed</button></div><div class="options"><label><input id="verbose" type="checkbox">Verbose log</label><label><input id="keep" type="checkbox">Keep temp files</label></div></div><div class="runline"><span class="caption">Run progress</span><div class="progress" role="progressbar" aria-label="Assignment progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><i id="bar"></i></div><span id="progress-count" class="count">0 / 0</span></div><p id="notice" class="notice" role="status" aria-live="polite">Ready to run local checks.</p></div><div class="sectionhead"><h2>Assignment results</h2><p id="run-count">No run yet</p></div><div class="legend"><span><strong class="p">PASS</strong> checks matched</span><span><strong class="f">FAIL</strong> result mismatch</span><span><strong class="e">ERROR</strong> could not verify</span></div><table class="results"><thead><tr><th scope="col">Check</th><th scope="col">Status</th><th scope="col">Time</th><th scope="col">Evidence / diagnostics</th></tr></thead><tbody id="checks"><tr><td class="empty" colspan="4">Run all tests or select an assignment to begin.</td></tr></tbody></table></div><aside class="sidecol" aria-labelledby="inspector-heading"><div class="sidehead"><h2 id="inspector-heading">Input &amp; tool inspector</h2><p>Paths selected by the grader for this run.</p></div><dl id="paths" class="inspector"><div class="pathitem"><dt>Inputs</dt><dd>Paths appear when a run starts.</dd></div></dl><div class="footnote">The grader reads your selected source files. Test harnesses and variant inputs are generated in temporary locations.</div></aside></div>
<div class="lower"><section aria-labelledby="console-heading"><div class="sectionhead"><h2 id="console-heading">Run log</h2><p>Live process notes</p></div><pre id="console" class="console">Waiting for a run.</pre></section><section aria-labelledby="summary-heading"><div class="sectionhead"><h2 id="summary-heading">Final summary</h2><p>Copyable text</p></div><pre id="summary" class="summary">No run yet.</pre></section></div>
</main>
<script>
let last={assignments:{}};
let polling=false;
const labels={1:'ALU',2:'Register file',3:'Control unit',4:'Datapath',5:'Factorial'};
const validStates=new Set(['IDLE','PENDING','RUNNING','PASS','FAIL','ERROR','UNVERIFIED']);
function esc(value){return String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]))}
function stateName(value){return validStates.has(value)?value:'ERROR'}
function seconds(value){return Number(value||0).toFixed(2)+'s'}
function render(data){
  last=data;const current=stateName(data.state||'IDLE');const overall=document.getElementById('overall');
  overall.className='overall '+current;document.getElementById('overall-text').textContent=current;document.getElementById('elapsed').textContent=seconds(data.elapsed);
  const entries=Object.entries(data.assignments||{});const done=entries.filter(([,check])=>!['PENDING','RUNNING'].includes(check.status)).length;
  const progress=entries.length?Math.round(done/entries.length*100):0;document.getElementById('bar').style.transform='scaleX('+progress/100+')';document.querySelector('.progress').setAttribute('aria-valuenow',progress);
  document.getElementById('progress-count').textContent=done+' / '+entries.length;document.getElementById('run-count').textContent=entries.length?entries.length+' selected · '+done+' complete':'No run yet';
  document.getElementById('paths').innerHTML=Object.entries(data.paths||{}).map(([name,path])=>'<div class="pathitem"><dt>'+esc(name)+'</dt><dd>'+esc(path)+'</dd></div>').join('')||'<div class="pathitem"><dt>Inputs</dt><dd>Paths appear when a run starts.</dd></div>';
  document.getElementById('checks').innerHTML=entries.map(([number,check])=>{
    const subresults=Object.entries(check.subresults||{}).map(([name,item])=>name+': '+(item.status||'ERROR')+' — '+(item.message||'')+(item.diagnostics?.length?'\n'+item.diagnostics.join('\n'):''));
    const details=[...subresults,...(check.diagnostics||[])];if(check.trace?.length)details.push('Trace:\n'+JSON.stringify(check.trace,null,2));
    const summary=check.message||'';const diagnostic=details.length?'<details><summary>View diagnostics</summary><pre>'+esc(details.join('\n\n'))+'</pre></details>':'';
    return '<tr><td class="assn">A'+esc(number)+'<small>'+esc(labels[number]||'Assignment')+'</small></td><td><span class="status '+stateName(check.status)+'">'+esc(check.status||'PENDING')+'</span></td><td class="elapsed">'+seconds(check.elapsed)+'</td><td class="resultmsg"><span class="message">'+esc(summary||'Awaiting result')+'</span>'+diagnostic+'</td></tr>';
  }).join('')||'<tr><td class="empty" colspan="4">Run all tests or select an assignment to begin.</td></tr>';
  document.getElementById('retry').disabled=!entries.some(([,check])=>['FAIL','ERROR','UNVERIFIED'].includes(check.status))||current==='RUNNING';
  document.getElementById('console').textContent=(data.log||[]).join('\n')||'Waiting for a run.';
  document.getElementById('summary').textContent=entries.length?'Lab 4 Verify: '+current+' ('+seconds(data.elapsed)+')\n'+entries.map(([number,check])=>'  Assignment '+number+': '+String(check.status||'PENDING').padEnd(10)+' '+(check.message||'')).join('\n'):'No run yet.';
  const notice=document.getElementById('notice');if(!notice.classList.contains('error'))notice.textContent=current==='RUNNING'?'Checks are running. Results update automatically.':current==='IDLE'?'Ready to run local checks.':'Run finished. Expand a row for diagnostics and trace data.';
}
async function run(assignments){
  const notice=document.getElementById('notice');notice.classList.remove('error');notice.textContent='Starting selected checks…';
  const body={assignments,verbose:document.getElementById('verbose').checked,keep_temp:document.getElementById('keep').checked};
  try{const response=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!response.ok){const payload=await response.json().catch(()=>({}));throw new Error(payload.error||'Could not start the run ('+response.status+').')}await poll()}
  catch(error){notice.classList.add('error');notice.textContent=error.message||'Could not start the run.'}
}
function runAll(){run([1,2,3,4,5])}function runOne(number){run([number])}
function rerunFailed(){const selected=Object.entries(last.assignments||{}).filter(([,check])=>['FAIL','ERROR','UNVERIFIED'].includes(check.status)).map(([number])=>Number(number));if(selected.length)run(selected)}
async function poll(){if(polling)return;polling=true;try{const response=await fetch('/api/status');if(!response.ok)throw new Error('Status request failed');render(await response.json())}catch(error){const notice=document.getElementById('notice');notice.classList.add('error');notice.textContent='Could not refresh status. The local server may have stopped.'}finally{polling=false}}
setInterval(()=>{if(last.state==='RUNNING')poll()},550);poll();
</script>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, payload: bytes, content_type: str = "application/json", status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/api/status":
            with state_lock:
                payload = json.dumps(state.to_dict()).encode()
            self._send(payload)
            return
        if urlparse(self.path).path == "/":
            self._send(HTML.encode(), "text/html; charset=utf-8")
            return
        if urlparse(self.path).path == "/logo.svg":
            self._send(Path(__file__).with_name("logo.svg").read_bytes(), "image/svg+xml")
            return
        self._send(b"Not found", status=404)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/run":
            self._send(b"Not found", status=404)
            return
        try:
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        except Exception:
            data = {}
        assignments = tuple(int(x) for x in data.get("assignments", ASSIGNMENTS) if int(x) in ASSIGNMENTS)
        if not start_run(assignments or ASSIGNMENTS, data):
            self._send(json.dumps({"error": "A run is already in progress"}).encode(), status=409)
            return
        self._send(json.dumps({"started": True}).encode(), status=202)

    def log_message(self, fmt: str, *args) -> None:
        return


def main() -> None:
    import argparse
    import webbrowser

    parser = argparse.ArgumentParser(description="Start the IS1200 Lab 4 local grader UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    print(f"Lab 4 Verify: http://{args.host}:{args.port}")
    threading.Timer(0.35, lambda: webbrowser.open(f"http://{args.host}:{args.port}")).start()
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
