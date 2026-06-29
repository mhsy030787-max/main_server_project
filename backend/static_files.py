from http import HTTPStatus
from urllib.parse import unquote

from settings import BASE_DIR, UI_DIR


def get_content_type(file_path):
    suffix = file_path.suffix.lower()
    if suffix == ".html":
        return "text/html; charset=utf-8"
    if suffix == ".css":
        return "text/css; charset=utf-8"
    if suffix == ".js":
        return "text/javascript; charset=utf-8"
    return "application/octet-stream"


def serve_static_file(handler):
    path = unquote(handler.path.split("?", 1)[0])
    if path in ("", "/"):
        path = "/UI/login_ui.html"

    if path.startswith("/UI/"):
        file_path = (BASE_DIR / path.lstrip("/")).resolve()
    else:
        file_path = (UI_DIR / path.lstrip("/")).resolve()

    if not str(file_path).startswith(str(BASE_DIR)) or not file_path.is_file():
        handler.send_error(HTTPStatus.NOT_FOUND)
        return

    content_type = get_content_type(file_path)
    body = file_path.read_bytes()
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)
