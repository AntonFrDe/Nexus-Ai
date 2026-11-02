"""A local stand-in for Ollama and OpenAI-style servers, for tests only. Real HTTP passes through
the real adapter and LiteLLM; only the model behind the socket is fake."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API_KEY = "sk-test-very-secret-value"


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args) -> None:
        pass

    def _send(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self) -> bool:
        return self.headers.get("Authorization") == f"Bearer {API_KEY}"

    def do_GET(self) -> None:
        if self.path == "/api/tags":
            self._send(200, {"models": [{"name": "local-coder:latest"}]})
        elif self.path == "/v1/models":
            if self._authorized():
                self._send(200, {"data": [{"id": "hosted-model"}]})
            else:
                self._send(401, {"error": {"message": "bad key"}})
        else:
            self._send(404, {})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        self.server.requests.append({"path": self.path, "body": body})
        if self.path == "/api/chat" and body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            reply = self.server.reply
            for part in (reply[: len(reply) // 2], reply[len(reply) // 2 :]):
                line = {
                    "model": body["model"],
                    "message": {"role": "assistant", "content": part},
                    "done": False,
                }
                self.wfile.write(json.dumps(line).encode() + b"\n")
            end = {
                "model": body["model"],
                "message": {"role": "assistant", "content": ""},
                "done": True,
                "prompt_eval_count": 4,
                "eval_count": 2,
            }
            self.wfile.write(json.dumps(end).encode() + b"\n")
        elif self.path == "/api/chat":
            self._send(
                200,
                {
                    "model": body["model"],
                    "message": {"role": "assistant", "content": "ready"},
                    "done": True,
                    "prompt_eval_count": 4,
                    "eval_count": 1,
                },
            )
        elif self.path == "/v1/chat/completions":
            if not self._authorized():
                self._send(401, {"error": {"message": f"bad key {API_KEY}", "type": "auth"}})
                return
            self._send(
                200,
                {
                    "id": "1",
                    "object": "chat.completion",
                    "created": 1,
                    "model": body["model"],
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": "ready"},
                        }
                    ],
                    "usage": {"prompt_tokens": 4, "completion_tokens": 1, "total_tokens": 5},
                },
            )
        else:
            self._send(404, {})


def start_fake_provider() -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.requests = []
    server.reply = "ready"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
