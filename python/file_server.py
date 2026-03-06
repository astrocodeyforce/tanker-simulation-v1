#!/usr/bin/env python3
"""
Simple HTTP file server for SIM-LAB downloadable files.

Serves /work/data/downloads/ on port 8502 with:
  - Directory listing with clickable links
  - Proper MIME types for PDF, PNG, CSV, etc.
  - CORS headers for browser access

Access:  http://<host>:8502/
"""

import os
import html
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn

SERVE_DIR = os.environ.get("SERVE_DIR", "/work/data/downloads")
PORT = int(os.environ.get("PORT", "8502"))


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle each request in a new thread — prevents single-request blocking."""
    daemon_threads = True


class DownloadHandler(SimpleHTTPRequestHandler):
    """Handler with directory listing, CORS, and forced download headers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SERVE_DIR, **kwargs)

    def end_headers(self):
        # Allow cross-origin access (useful if dashboard fetches links)
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def list_directory(self, path):
        """Generate a styled HTML directory listing."""
        try:
            entries = sorted(os.listdir(path))
        except OSError:
            self.send_error(404, "Directory not found")
            return None

        # Build HTML
        display_path = urllib.parse.unquote(self.path)
        title = f"SIM-LAB Downloads — {display_path}"

        items_html = []
        for name in entries:
            fullpath = os.path.join(path, name)
            display_name = name + ("/" if os.path.isdir(fullpath) else "")
            link = urllib.parse.quote(name, errors="surrogatepass")
            if os.path.isdir(fullpath):
                link += "/"
            size = ""
            if os.path.isfile(fullpath):
                sz = os.path.getsize(fullpath)
                if sz < 1024:
                    size = f"{sz} B"
                elif sz < 1024 * 1024:
                    size = f"{sz / 1024:.1f} KB"
                else:
                    size = f"{sz / (1024 * 1024):.1f} MB"
            items_html.append(
                f'<tr><td><a href="{link}">{html.escape(display_name)}</a></td>'
                f'<td style="text-align:right;padding-left:2em;color:#888">{size}</td></tr>'
            )

        body = f"""<!DOCTYPE html>
<html>
<head><title>{html.escape(title)}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         max-width: 800px; margin: 40px auto; padding: 0 20px; color: #333; }}
  h1 {{ color: #1a5276; border-bottom: 2px solid #1a5276; padding-bottom: 10px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  tr:hover {{ background: #f0f0f0; }}
  td {{ padding: 8px 4px; }}
  a {{ color: #2874a6; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .footer {{ margin-top: 30px; color: #999; font-size: 0.85em; }}
</style></head>
<body>
<h1>&#128230; SIM-LAB Downloads</h1>
<table>{"".join(items_html) if items_html else "<tr><td><em>No files yet.</em></td></tr>"}</table>
<p class="footer">Serve directory: {html.escape(SERVE_DIR)}</p>
</body></html>"""

        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()

        from io import BytesIO
        return BytesIO(encoded)


if __name__ == "__main__":
    print(f"[file_server] Serving {SERVE_DIR} on port {PORT}")
    print(f"[file_server] http://0.0.0.0:{PORT}/")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), DownloadHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[file_server] Shutting down.")
        server.shutdown()
