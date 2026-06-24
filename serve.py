#!/usr/bin/env python3
"""Serve the repo and save exported WebM clips to clips/."""

import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
CLIPS_DIR = REPO_ROOT / "clips"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(REPO_ROOT), **kwargs)

    def do_POST(self):
        if self.path != "/api/clips":
            self.send_error(404)
            return

        filename = self.headers.get("X-Filename", "clip.webm")
        filename = Path(re.sub(r"[^\w.\-]", "_", filename)).name
        if not filename.endswith(".webm"):
            filename += ".webm"

        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length)

        CLIPS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = CLIPS_DIR / filename
        out_path.write_bytes(data)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(f'{{"path":"clips/{filename}"}}'.encode())

    def log_message(self, format, *args):
        if args and args[0].startswith("POST /api/clips"):
            print(f"Saved clip: {args[0]}")
        else:
            super().log_message(format, *args)


def main():
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("localhost", 8000), Handler)
    print(f"Serving {REPO_ROOT} at http://localhost:8000/")
    print(f"Clips saved to {CLIPS_DIR}")
    print("Open http://localhost:8000/website/index.html")
    server.serve_forever()


if __name__ == "__main__":
    main()
