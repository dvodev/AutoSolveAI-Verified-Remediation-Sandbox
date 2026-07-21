"""Dependency-free HTTP UI/API for the hackathon demo."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .engine import RemediationEngine
from .ui import HTML as MODERN_HTML


HTML = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Verified Remediation Sandbox</title>
<style>body{font:16px system-ui;background:#0b1020;color:#edf2ff;max-width:1000px;margin:40px auto;padding:0 20px}button{background:#6ee7b7;border:0;border-radius:8px;padding:12px 16px;margin:4px;font-weight:700;cursor:pointer}.card{background:#151d35;border:1px solid #293655;border-radius:14px;padding:20px;margin:18px 0}pre{white-space:pre-wrap;background:#080c18;padding:14px;border-radius:8px;overflow:auto}.pill{display:inline-block;padding:5px 9px;border-radius:999px;background:#33405f}.ok{color:#6ee7b7}.bad{color:#fb7185}</style></head>
<body><h1>AutoSolve AI · Verified Remediation Command Center</h1>
<p>Controlled synthetic incident. No production hosts, credentials, or integrations.</p>
<div class="card"><label>Scenario <select id="scenario"><option value="stale_heartbeat">Stale heartbeat</option><option value="missing_process">Missing process</option><option value="healthy_signal">Healthy signal (no-op)</option></select></label> <label>Mode <select id="mode"><option value="approval">Approval required</option><option value="shadow">Shadow mode</option></select></label><br><button onclick="run('alert')">1 · Simulate alert</button><button onclick="run('plan')">2 · Generate GPT plan</button><button onclick="run('approve')">3 · Approve</button><button onclick="run('execute')">4 · Execute + verify</button><button onclick="run('replay')">Replay audit</button><button onclick="run('rollback')">Rollback</button></div>
<div id="view" class="card"><em>Start the demo.</em></div>
<script>
let runId=null;
async function call(path,method='GET',body){const r=await fetch(path,{method,headers:{'content-type':'application/json'},body:body?JSON.stringify(body):undefined});const x=await r.json();if(!r.ok)throw Error(x.error||r.status);return x}
async function run(action){try{if(action==='alert'){const x=await call('/api/alerts','POST',{scenario:document.querySelector('#scenario').value,mode:document.querySelector('#mode').value});runId=x.run_id}else if(action==='plan'){await call('/api/runs/'+runId+'/plan','POST')}else if(action==='approve'){await call('/api/runs/'+runId+'/approve','POST')}else if(action==='replay'){const x=await call('/api/runs/'+runId+'/replay');document.querySelector('#view').innerHTML='<h2>Audit replay</h2><pre>'+JSON.stringify(x,null,2)+'</pre>';return}else if(action==='rollback'){await call('/api/runs/'+runId+'/rollback','POST')}else{await call('/api/runs/'+runId+'/execute','POST')}const s=await call('/api/state');render(s)}catch(e){document.querySelector('#view').innerHTML='<p class="bad">'+e+'</p>'}}
function render(s){const r=s.runs.at(-1);const verified=r?.status==='verified';document.querySelector('#view').innerHTML='<h2>Status: <span class="pill '+(verified?'ok':'')+'">'+(r?.status||'idle')+'</span></h2><p>Capabilities are loaded from a manifest; the plan cannot name anything outside it.</p><pre>'+JSON.stringify(r||s,null,2)+'</pre>'}
</script></body></html>"""

# Keep the HTTP handler dependency-free, but serve the maintained UI module
# rather than the original prototype markup above.
HTML = MODERN_HTML


class Handler(BaseHTTPRequestHandler):
    engine: RemediationEngine

    def _json(self, status: int, payload: object) -> None:
        data = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        try:
            value = json.loads(self.rfile.read(length) or b"{}")
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}

    def do_GET(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        if route == "/":
            data = HTML.encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
        elif route == "/api/state":
            self._json(200, self.engine.state())
        elif route == "/api/capabilities":
            self._json(200, self.engine.capabilities)
        elif route == "/api/workflow":
            from .orchestrator import RemediationOrchestrator
            self._json(200, RemediationOrchestrator(self.engine).workflow())
        elif route == "/api/connectors":
            from .orchestrator import RemediationOrchestrator
            self._json(200, RemediationOrchestrator(self.engine).workflow()["adapter_health"])
        elif route == "/api/scenarios":
            from .scenarios import SCENARIOS
            self._json(200, SCENARIOS)
        elif route == "/api/audit/verify":
            self._json(200, self.engine.events.verify_chain())
        elif route == "/api/audit":
            self._json(200, self.engine.events.all())
        elif route == "/metrics":
            data = self.engine.metrics.prometheus().encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "text/plain; version=0.0.4"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
        elif route.startswith("/api/runs/") and route.endswith("/report"):
            from .reporting import build_report
            run = self.engine.runs.get(route.split("/")[3])
            if not run:
                self._json(404, {"error": "run_not_found"})
            else:
                self._json(200, build_report(run, audit_chain=self.engine.events.verify_chain()).as_dict())
        elif route.startswith("/api/runs/") and route.endswith("/replay"):
            self._json(200, self.engine.replay(route.split("/")[3]))
        else:
            self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        try:
            if route == "/api/alerts":
                result = self.engine.create_alert(self._body() or None)
            elif route.startswith("/api/runs/") and route.endswith("/plan"):
                result = self.engine.plan(route.split("/")[3])
            elif route.startswith("/api/runs/") and route.endswith("/approve"):
                result = self.engine.approve(route.split("/")[3])
            elif route.startswith("/api/runs/") and route.endswith("/execute"):
                result = self.engine.execute(route.split("/")[3])
            elif route.startswith("/api/runs/") and route.endswith("/rollback"):
                result = self.engine.rollback(route.split("/")[3])
            else:
                self._json(404, {"error": "not_found"}); return
            self._json(200, result)
        except (KeyError, ValueError, RuntimeError) as exc:
            self._json(400, {"error": str(exc)})

    def log_message(self, fmt: str, *args: object) -> None:
        return


def main() -> None:
    engine = RemediationEngine(os.getenv("SANDBOX_DATA_DIR", "data"))
    Handler.engine = engine
    host = os.getenv("SANDBOX_HOST", "127.0.0.1")
    port = int(os.getenv("SANDBOX_PORT", "8787"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Verified Remediation Sandbox listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        engine.close(); server.server_close()


if __name__ == "__main__":
    main()
