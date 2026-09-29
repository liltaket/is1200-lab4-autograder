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
:root{color-scheme:dark;--paper:#101a22;--sheet:#1b2932;--ink:#edf3f4;--muted:#b0c0c6;--rule:#354851;--rule-strong:#627983;--blue:#8ac7e8;--blue-soft:#244456;--pass:#7cd8ad;--pass-bg:#1a3d31;--fail:#ffa099;--fail-bg:#452d30;--error:#efc982;--error-bg:#473821;--pending:#bdcbd0;--mono:ui-monospace,SFMono-Regular,Consolas,"Liberation Mono",monospace;--sans:system-ui,-apple-system,"Segoe UI",sans-serif}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:14px/1.5 var(--sans)}button,input,summary{font:inherit}button{cursor:pointer}button:disabled{cursor:not-allowed;opacity:.5}button:focus-visible,input:focus-visible,summary:focus-visible{outline:3px solid var(--blue);outline-offset:3px}main{max-width:1120px;margin:auto;padding:28px 28px 54px}
.topline{display:flex;align-items:center;gap:11px;padding-bottom:13px;border-bottom:1px solid var(--rule-strong);font:700 11px var(--mono);letter-spacing:.09em;text-transform:uppercase}.topline .mark{display:block;width:23px;height:23px;flex:none}.topline .right{margin-left:auto;color:var(--muted);font-weight:500;letter-spacing:.04em}.masthead{display:flex;justify-content:space-between;align-items:end;gap:24px;padding:30px 0 27px}h1{font-size:clamp(28px,3vw,40px);line-height:1.08;letter-spacing:-.035em;margin:0 0 7px}h2{font-size:16px;letter-spacing:-.01em;margin:0}.lede{margin:0;color:var(--muted);max-width:66ch}.overall{display:flex;align-items:center;gap:10px;min-width:190px;padding:11px 14px;border:1px solid var(--rule-strong);border-radius:6px;background:var(--sheet)}.overall .state{font:800 15px var(--mono)}.overall .dot{width:9px;height:9px;border-radius:50%;background:var(--pending)}.overall .meta{font:11px var(--mono);color:var(--muted);margin-left:auto}.overall.PASS{border-color:#70aa89;background:var(--pass-bg);color:var(--pass)}.overall.FAIL{border-color:#d59c96;background:var(--fail-bg);color:var(--fail)}.overall.ERROR,.overall.UNVERIFIED{border-color:#d7b278;background:var(--error-bg);color:var(--error)}.overall.RUNNING{border-color:#83afca;background:var(--blue-soft);color:var(--blue)}.overall.PASS .dot{background:var(--pass)}.overall.FAIL .dot{background:var(--fail)}.overall.ERROR .dot,.overall.UNVERIFIED .dot{background:var(--error)}.overall.RUNNING .dot{background:var(--blue);animation:pulse 1.2s ease-in-out infinite}@keyframes pulse{50%{opacity:.3}}
.toolbar{padding:18px 20px 14px;border:1px solid var(--rule);border-radius:8px;background:var(--sheet)}.toolbar-top{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap}.actions{display:flex;gap:7px;flex-wrap:wrap}.button{min-height:38px;border:1px solid var(--rule-strong);border-radius:5px;background:transparent;color:var(--ink);padding:7px 12px;font-weight:650;white-space:nowrap}.button:hover:not(:disabled){background:var(--blue-soft);border-color:var(--blue)}.button.primary{background:#236b94;border-color:#337fa8;color:#fff}.button.primary:hover:not(:disabled){background:#2c7eac}.button.small{font:700 12px var(--mono);min-width:38px;padding:7px 10px}.options{display:flex;gap:16px;align-items:center;flex-wrap:wrap;color:var(--muted);font-size:12px}.options label{display:inline-flex;align-items:center;gap:6px;white-space:nowrap}.options input{accent-color:var(--blue)}.runline{display:flex;align-items:center;gap:12px;margin-top:15px}.runline .caption{font:600 11px var(--mono);text-transform:uppercase;letter-spacing:.05em;white-space:nowrap;color:var(--muted)}.progress{height:4px;flex:1;background:#344750;overflow:hidden}.progress i{display:block;width:100%;height:100%;background:var(--blue);transform:scaleX(0);transform-origin:left center;transition:transform .25s}.runline .count{font:12px var(--mono);color:var(--muted);min-width:43px;text-align:right}.notice{min-height:18px;margin:9px 0 0;color:var(--muted);font-size:12px}.notice.error{color:var(--fail);font-weight:650}
.sectionhead{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin:27px 0 11px}.sectionhead p{margin:0;color:var(--muted);font-size:12px}.checks{border:1px solid var(--rule);border-radius:8px;overflow:hidden;background:var(--sheet)}.check+.check{border-top:1px solid var(--rule)}.check-line{display:grid;grid-template-columns:145px 112px minmax(0,1fr) 64px;align-items:center;gap:16px;padding:15px 18px}.assn h3{font-size:15px;line-height:1.2;margin:0}.assn small{display:block;color:var(--muted);font:11px var(--mono);margin-top:3px}.status{display:inline-flex;align-items:center;gap:6px;font:800 11px var(--mono);letter-spacing:.02em;white-space:nowrap}.status::before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor}.status.PASS{color:var(--pass)}.status.FAIL{color:var(--fail)}.status.ERROR,.status.UNVERIFIED{color:var(--error)}.status.RUNNING{color:var(--blue)}.status.PENDING,.status.IDLE{color:var(--pending)}.check-line .message{margin:0;color:var(--muted);font-size:12px;min-width:0;overflow-wrap:anywhere}.elapsed{text-align:right;font:12px var(--mono);color:var(--muted)}.empty{padding:25px 18px;margin:0;color:var(--muted)}
.check-detail{border-top:1px solid var(--rule);background:#18262f}.check-detail summary{display:inline-block;padding:13px 18px;color:var(--blue);font-size:12px;font-weight:650;cursor:pointer;list-style:none}.check-detail summary::-webkit-details-marker{display:none}.check-detail summary::before{content:"+";display:inline-block;width:15px;font:700 14px var(--mono)}.check-detail[open] summary::before{content:"−"}.check-detail summary:hover{text-decoration:underline}.debug-body{padding:0 18px 17px}.debug-body h4{margin:11px 0 6px;font:700 10px var(--mono);text-transform:uppercase;letter-spacing:.07em;color:var(--muted)}.debug-body pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:300px;overflow:auto;padding:11px 12px;margin:0;background:#0e1b23;color:var(--ink);font:11px/1.55 var(--mono);border:1px solid var(--rule)}.subcheck{display:grid;grid-template-columns:58px 95px minmax(0,1fr);gap:8px;align-items:start;padding:8px 0;border-bottom:1px solid var(--rule);font-size:12px;color:var(--muted)}.subcheck:last-child{border-bottom:0}.subcheck .name{font:700 11px var(--mono);color:var(--ink)}.subcheck pre{grid-column:1/-1}
.more{margin-top:26px}.more h2{margin:0 0 11px}.disclosures{border:1px solid var(--rule);border-radius:8px;overflow:hidden;background:var(--sheet)}.disclosures>details+details{border-top:1px solid var(--rule)}.disclosures>details>summary{display:flex;align-items:center;gap:12px;cursor:pointer;padding:14px 18px;list-style:none}.disclosures>details>summary::-webkit-details-marker{display:none}.disclosures>details>summary::before{content:"+";width:17px;color:var(--blue);font:700 16px var(--mono)}.disclosures>details[open]>summary::before{content:"−"}.disclosures>details>summary:hover{background:#22343f}.disclosures .summary-title{font-weight:650}.disclosures .summary-hint{margin-left:auto;color:var(--muted);font-size:12px}.detail-content{padding:0 18px 18px}.inspector{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 24px;margin:0}.pathitem{padding:10px 0;border-top:1px solid var(--rule)}.pathitem dt{font:700 10px var(--mono);letter-spacing:.07em;text-transform:uppercase;color:var(--muted);margin-bottom:4px}.pathitem dd{margin:0;font:12px/1.5 var(--mono);overflow-wrap:anywhere}.footnote{color:var(--muted);font-size:11px;margin:12px 0 0}.console,.summary{margin:0;padding:14px;min-height:85px;max-height:300px;overflow:auto;background:#0e1b23;color:#e0edf0;font:11px/1.55 var(--mono);white-space:pre-wrap;overflow-wrap:anywhere}.summary{background:#15242d;color:var(--ink);border:1px solid var(--rule)}
@media(max-width:900px){.toolbar-top{align-items:flex-start}.options{width:100%}.check-line{grid-template-columns:130px 100px minmax(0,1fr) 60px;gap:10px}}@media(max-width:700px){main{padding:18px 14px 32px}.topline .right{display:none}.masthead{display:block;padding:24px 0}.overall{display:inline-flex;margin-top:17px}.toolbar{padding:15px}.sectionhead{margin-top:24px}.check-line{grid-template-columns:minmax(0,1fr) auto auto;gap:4px 12px;padding:14px}.assn{grid-column:1}.check-line>.status{grid-column:2}.elapsed{grid-column:3}.check-line .message{grid-column:1/-1;margin-top:5px}.inspector{grid-template-columns:1fr}.disclosures .summary-hint{display:none}.button{min-height:42px}}@media(max-width:520px){.actions{gap:6px}.button.primary{width:100%}.options{gap:10px}.subcheck{grid-template-columns:52px 82px minmax(0,1fr)}.check-detail summary{padding-left:14px}.debug-body{padding-left:14px;padding-right:14px}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}.progress i{transition:none}.overall.RUNNING .dot{animation:none}}
</style>
</head>
<body>
<!-- THESIS: A local verification workbench laid out like an instrument trace sheet. OWN-WORLD: Deep ink surfaces, ruled tables, technical blue controls and explicit result colors. STORY: Select checks, watch progress, inspect evidence and paths. FIRST VIEWPORT: Run controls and compact outcomes lead; evidence and paths are available in disclosures below. FORM: Operator workbench. FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md. -->
<main>
<div class="topline"><img class="mark" src="/logo.svg" alt=""><span>Lab 4 Verify</span><span class="right">IS1200 / IS1500 · LOCAL</span></div>
<header class="masthead"><div><h1>Processor verification</h1><p class="lede">Run local Lab 4 checks and inspect the evidence behind each result. The command line grader is the source of truth.</p></div><div id="overall" class="overall IDLE" role="status" aria-live="polite" aria-atomic="true"><span class="dot" aria-hidden="true"></span><span id="overall-text" class="state">IDLE</span><span id="elapsed" class="meta">0.00s</span></div></header>
<section class="workbench" aria-labelledby="results-heading"><div class="toolbar"><div class="toolbar-top"><div class="actions" aria-label="Run checks"><button class="button primary" onclick="runAll()">Run all tests</button><button class="button small" onclick="runOne(1)" aria-label="Run Assignment 1">A1</button><button class="button small" onclick="runOne(2)" aria-label="Run Assignment 2">A2</button><button class="button small" onclick="runOne(3)" aria-label="Run Assignment 3">A3</button><button class="button small" onclick="runOne(4)" aria-label="Run Assignment 4">A4</button><button class="button small" onclick="runOne(5)" aria-label="Run Assignment 5">A5</button><button class="button" id="retry" onclick="rerunFailed()" disabled>Rerun failed</button></div><div class="options"><label><input id="verbose" type="checkbox">Verbose log</label><label><input id="keep" type="checkbox">Keep temp files</label></div></div><div class="runline"><span class="caption">Run progress</span><div class="progress" role="progressbar" aria-label="Assignment progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><i id="bar"></i></div><span id="progress-count" class="count">0 / 0</span></div><p id="notice" class="notice" role="status" aria-live="polite">Ready to run local checks.</p></div><div class="sectionhead"><h2 id="results-heading">Assignment results</h2><p id="run-count">No run yet</p></div><div id="checks" class="checks" role="list"><p class="empty">Run all tests or select an assignment to begin.</p></div></section>
<section class="more" aria-labelledby="more-heading"><h2 id="more-heading">More from this run</h2><div class="disclosures"><details><summary><span class="summary-title">Inputs &amp; tools</span><span class="summary-hint">Selected source and dependency paths</span></summary><div class="detail-content"><dl id="paths" class="inspector"><div class="pathitem"><dt>Inputs</dt><dd>Paths appear when a run starts.</dd></div></dl><p class="footnote">The grader reads selected source files. Harnesses and variant inputs use temporary copies.</p></div></details><details><summary><span class="summary-title">Run log</span><span class="summary-hint">Live process notes and verbose output</span></summary><div class="detail-content"><pre id="console" class="console">Waiting for a run.</pre></div></details><details><summary><span class="summary-title">Final summary</span><span class="summary-hint">Copyable result text</span></summary><div class="detail-content"><pre id="summary" class="summary">No run yet.</pre></div></details></div></section>
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
  const expanded=new Set([...document.querySelectorAll('#checks details[data-check]')].filter(detail=>detail.open).map(detail=>detail.dataset.check));
  document.getElementById('checks').innerHTML=entries.map(([number,check])=>{
    const subresults=Object.entries(check.subresults||{}).map(([name,item])=>'<div class="subcheck"><span class="name">'+esc(name)+'</span><span class="status '+stateName(item.status)+'">'+esc(item.status||'ERROR')+'</span><span>'+esc(item.message||'')+'</span>'+(item.diagnostics?.length?'<pre>'+esc(item.diagnostics.join('\n'))+'</pre>':'')+'</div>').join('');
    const diagnostics=check.diagnostics?.length?'<h4>Diagnostics</h4><pre>'+esc(check.diagnostics.join('\n'))+'</pre>':'';
    const trace=check.trace?.length?'<h4>Grader trace</h4><pre>'+esc(JSON.stringify(check.trace,null,2))+'</pre>':'';
    const debug=subresults||diagnostics||trace?'<details class="check-detail" data-check="'+esc(number)+'"'+(expanded.has(number)?' open':'')+'><summary>Debug details for A'+esc(number)+'</summary><div class="debug-body">'+(subresults?'<h4>Subchecks</h4>'+subresults:'')+diagnostics+trace+'</div></details>':'';
    return '<article class="check" role="listitem"><div class="check-line"><div class="assn"><h3>A'+esc(number)+'</h3><small>'+esc(labels[number]||'Assignment')+'</small></div><span class="status '+stateName(check.status)+'">'+esc(check.status||'PENDING')+'</span><p class="message">'+esc(check.message||'Awaiting result')+'</p><span class="elapsed">'+seconds(check.elapsed)+'</span></div>'+debug+'</article>';
  }).join('')||'<p class="empty">Run all tests or select an assignment to begin.</p>';
  document.getElementById('retry').disabled=!entries.some(([,check])=>['FAIL','ERROR','UNVERIFIED'].includes(check.status))||current==='RUNNING';
  document.getElementById('console').textContent=(data.log||[]).join('\n')||'Waiting for a run.';
  document.getElementById('summary').textContent=entries.length?'Lab 4 Verify: '+current+' ('+seconds(data.elapsed)+')\n'+entries.map(([number,check])=>'  Assignment '+number+': '+String(check.status||'PENDING').padEnd(10)+' '+(check.message||'')).join('\n'):'No run yet.';
  const notice=document.getElementById('notice');if(!notice.classList.contains('error'))notice.textContent=current==='RUNNING'?'Checks are running. Results update automatically.':current==='IDLE'?'Ready to run local checks.':'Run finished. Open an assignment for debug details.';
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
