import os
from http.server import ThreadingHTTPServer

from handler import AppHandler


def run():
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"Python server running: http://{host}:{port}")
    print("Login test accounts: admin / 1234, leader / 1234, staff / 1234")
    server.serve_forever()


if __name__ == "__main__":
    run()
