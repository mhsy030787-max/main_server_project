from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
import json

from auth.routes import handle_api_get, handle_api_post
from http_utils import json_bytes
from static_files import serve_static_file


class AppHandler(BaseHTTPRequestHandler):
    def end_headers(self):
        origin = self.headers.get("Origin")
        allowed_origins = {
            "http://127.0.0.1:5500",
            "http://localhost:5500",
            "http://127.0.0.1:5501",
            "http://localhost:5501",
        }
        if origin in allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/api/"):
            handle_api_get(self)
            return

        serve_static_file(self)

    def do_POST(self):
        if self.path.startswith("/api/"):
            handle_api_post(self)
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def read_json_body(self):
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length).decode("utf-8")
        if not raw_body:
            return {}

        try:
            return json.loads(raw_body)
        except json.JSONDecodeError:
            return {}

    def send_json(self, data, status=HTTPStatus.OK, headers=None):
        body = json_bytes(data)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)
