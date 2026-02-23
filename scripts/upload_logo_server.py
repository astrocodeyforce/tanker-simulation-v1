#!/usr/bin/env python3
"""Tiny one-shot upload server – saves logo then exits."""
import http.server, cgi, os, sys

SAVE_DIR = "/opt/sim-lab/truck-tanker-sim-env/data/assets"
os.makedirs(SAVE_DIR, exist_ok=True)

HTML = b"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Upload Bull &amp; Bear Logo</title>
<style>
  body{background:#1a1a2e;color:#eee;font-family:sans-serif;display:flex;
       justify-content:center;align-items:center;height:100vh;margin:0}
  .box{background:#16213e;padding:40px 60px;border-radius:16px;text-align:center;
       box-shadow:0 8px 32px rgba(0,0,0,.4)}
  h1{margin-bottom:8px} .sub{color:#888;margin-bottom:24px}
  input[type=file]{margin:16px 0}
  button{background:#8b1e1e;color:#fff;border:none;padding:14px 40px;
         border-radius:8px;font-size:18px;cursor:pointer}
  button:hover{background:#a52a2a}
</style></head><body>
<div class="box">
  <h1>Bull &amp; Bear Logo Upload</h1>
  <p class="sub">Select your logo image, then click Upload</p>
  <form method="POST" enctype="multipart/form-data">
    <input type="file" name="logo" accept="image/*" required><br>
    <button type="submit">Upload Logo</button>
  </form>
</div></body></html>"""

DONE = b"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Done</title>
<style>
  body{background:#1a1a2e;color:#eee;font-family:sans-serif;display:flex;
       justify-content:center;align-items:center;height:100vh;margin:0}
  .box{background:#16213e;padding:40px 60px;border-radius:16px;text-align:center}
  h1{color:#4caf50}
</style></head><body>
<div class="box"><h1>Logo Uploaded!</h1>
<p>Refresh your Streamlit dashboard to see it.</p>
<p>This upload server will shut down automatically.</p>
</div></body></html>"""

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type","text/html")
        self.end_headers()
        self.wfile.write(HTML)

    def do_POST(self):
        ct = self.headers.get("Content-Type","")
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers,
                                environ={"REQUEST_METHOD":"POST",
                                         "CONTENT_TYPE":ct})
        f = form["logo"]
        ext = os.path.splitext(f.filename)[1].lower() or ".png"
        # Remove old logos
        for old in os.listdir(SAVE_DIR):
            if old.startswith("logo."):
                os.remove(os.path.join(SAVE_DIR, old))
        dest = os.path.join(SAVE_DIR, f"logo{ext}")
        with open(dest, "wb") as out:
            out.write(f.file.read())
        size = os.path.getsize(dest)
        print(f"[OK] Saved {dest}  ({size:,} bytes)")
        self.send_response(200)
        self.send_header("Content-Type","text/html")
        self.end_headers()
        self.wfile.write(DONE)
        # Schedule shutdown
        import threading
        threading.Timer(1.0, lambda: os._exit(0)).start()

    def log_message(self, fmt, *a):
        print(fmt % a)

print(f"Upload server running on http://0.0.0.0:9090")
print(f"Waiting for logo upload...")
http.server.HTTPServer(("0.0.0.0", 9090), Handler).serve_forever()
