"""Local read-only UI server for the WSP source explorer.

The default app requires only Python >= 3.8 standard library and contains
verbatim published source excerpts. No model inference or remote API calls.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import traceback

from .data import ROOT, FILES, facts, lookup, model_catalog, source_lines, statistics, SCENARIOS
from .associate import evaluate, released_subset_memory

WEB = (ROOT/"web").resolve()
DOCS = (ROOT/"docs").resolve()
ASSETS = (ROOT/"assets").resolve()
MAX_POST = 14_000


class WspHandler(BaseHTTPRequestHandler):
    server_version="WspEducationalLab/1.0"
    def log_message(self, format_string, *args):
        return

    def answer(self, data, status=200, content_type="application/json; charset=utf-8", docs=False):
        self.send_response(status)
        self.send_header("Content-Type",content_type)
        self.send_header("Content-Length",str(len(data)))
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("X-Frame-Options","DENY")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("Cache-Control","no-store")
        if docs:
            policy=("default-src 'none'; style-src 'unsafe-inline'; "
                    "img-src data: 'self'; object-src 'none'; base-uri 'none'")
        else:
            policy=("default-src 'self'; script-src 'self'; style-src 'self'; "
                    "img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'")
        self.send_header("Content-Security-Policy",policy)
        self.end_headers()
        self.wfile.write(data)

    def json_reply(self, obj, status=200):
        self.answer(json.dumps(obj,ensure_ascii=False,allow_nan=False).encode("utf-8"),status)

    def do_GET(self):
        uri = urlsplit(self.path)
        try:
            if uri.path.startswith("/api/"):
                q=parse_qs(uri.query)
                def param(name,default=""):
                    return q.get(name,[default])[0]
                if uri.path=="/api/catalog":
                    self.json_reply({
                        "statistics":statistics(),
                        "scenarios":list(SCENARIOS),
                        "models":model_catalog(),
                        "memory":released_subset_memory().public_metadata(),
                        "files":[{"path":"kb/"+p,"label":p} for p in FILES]
                    })
                elif uri.path=="/api/facts":
                    self.json_reply({"facts":lookup(
                        query=param("q"),file=param("file"),kind=param("kind"),
                        limit=int(param("limit","70")))
                    })
                elif uri.path=="/api/source":
                    self.json_reply(source_lines(
                        param("file"),focus=int(param("line","1")),
                        context=int(param("context","64"))))
                else:
                    self.json_reply({"error":"APIがありません"},404)
                return

            if uri.path=="/":
                path=WEB/"index.html"
            elif uri.path.startswith("/web/"):
                path=WEB/uri.path[len("/web/"):]
            elif uri.path.startswith("/docs/"):
                path=DOCS/uri.path[len("/docs/"):]
            elif uri.path.startswith("/assets/"):
                path=ASSETS/uri.path[len("/assets/"):]
            else:
                self.json_reply({"error":"ページがありません"},404)
                return
            path=path.resolve()
            if (path!=WEB/"index.html" and
                WEB not in path.parents and
                DOCS not in path.parents and
                ASSETS not in path.parents):
                self.json_reply({"error":"アクセスは禁止されています"},403)
                return
            if not path.is_file():
                self.json_reply({"error":"ファイルがありません"},404)
                return
            extension=path.suffix.lower()
            mimetypes={
                ".html":"text/html; charset=utf-8", ".css":"text/css; charset=utf-8",
                ".js":"application/javascript; charset=utf-8",
                ".json":"application/json; charset=utf-8",
                ".png":"image/png",".svg":"image/svg+xml"
            }
            if extension not in mimetypes:
                self.json_reply({"error":"不正なファイル形式です"},403)
                return
            self.answer(path.read_bytes(),content_type=mimetypes[extension],
                        docs=DOCS in path.parents and extension==".html")
        except (ValueError,TypeError) as exc:
            self.json_reply({"error":str(exc)},400)
        except Exception:
            traceback.print_exc()
            self.json_reply({"error":"内部エラー。ターミナルの内容を確認してください"},500)

    def do_POST(self):
        try:
            size=int(self.headers.get("Content-Length","0"))
            if size<=0 or size>MAX_POST:
                raise ValueError("送信サイズの上限を超えました")
            if not self.headers.get("Content-Type","").startswith("application/json"):
                raise ValueError("JSON形式で送信してください")
            data=json.loads(self.rfile.read(size).decode("utf-8"))
            if not isinstance(data,dict):
                raise ValueError("JSONオブジェクトが必要です")
            path=urlsplit(self.path).path
            if path=="/api/evaluate":
                self.json_reply(evaluate(
                    data.get("question"),data.get("options"),
                    data.get("disabled",[]),data.get("custom","")))
            else:
                self.json_reply({"error":"APIがありません"},404)
        except (ValueError,TypeError) as exc:
            self.json_reply({"error":str(exc)},400)
        except Exception:
            traceback.print_exc()
            self.json_reply({"error":"評価エラー。ターミナルを確認してください"},500)


def serve(port=0):
    server=ThreadingHTTPServer(("127.0.0.1",port),WspHandler)
    server.daemon_threads=True
    return "http://127.0.0.1:%d/"%server.server_address[1],server
