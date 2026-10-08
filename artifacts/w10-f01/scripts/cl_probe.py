import socket, threading, sys
from verantyx.vera_server import make_handler
from http.server import ThreadingHTTPServer
import verantyx.vera_server as v
class FakeStore: pass
import tempfile, pathlib
from verantyx.cross_store import CrossStore
from verantyx.gap_graph import GapGraph
from verantyx.cognitive_interventions import InterventionLog
from verantyx.tool_call_quarantine import ToolCallQuarantine
t = pathlib.Path(tempfile.mkdtemp())
h = make_handler(CrossStore(), lambda: None, "m", None, GapGraph.load(t/"g.json"), lambda: None, InterventionLog.load(t/"i.json"), lambda: None, ToolCallQuarantine.load(t/"t.json"), lambda: None)
srv = ThreadingHTTPServer(("127.0.0.1", 0), h)
threading.Thread(target=srv.serve_forever, daemon=True).start()
port = srv.server_address[1]
for cl in ("abc", "-1", "2"):
    s = socket.create_connection(("127.0.0.1", port)); s.settimeout(3)
    s.sendall(f"POST /agent/run HTTP/1.1\r\nHost: x\r\nContent-Length: {cl}\r\n\r\n{{}}".encode())
    try:
        d = s.recv(4096)
        print(cl, "->", d.split(b"\r\n")[0].decode() if d else "<closed, no response>")
    except socket.timeout:
        print(cl, "-> <TIMEOUT: connection still open>")
    s.close()
