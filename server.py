"""Lightweight proxy that forwards OpenAI-compatible requests to Z.AI Coding Plan API."""
import os
import json
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler

ZAI_CODING_BASE = "https://api.z.ai/api/coding/paas/v4"
ZAI_API_KEY = os.environ.get("ZAI_API_KEY", "")

class ProxyHandler(BaseHTTPRequestHandler):
    
    def _forward_request(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b''
        
        # Strip /v1 prefix if present (Letta sends /v1/chat/completions)
        path = self.path
        if path.startswith("/v1"):
            path = path[3:]  # Remove /v1 prefix
        
        target_url = ZAI_CODING_BASE + path
        
        req = urllib.request.Request(target_url, data=body if body else None, method="POST")
        req.add_header("Authorization", f"Bearer {ZAI_API_KEY}")
        req.add_header("Content-Type", self.headers.get("Content-Type", "application/json"))
        
        try:
            payload = json.loads(body) if body else {}
            is_stream = payload.get("stream", False)
            
            with urllib.request.urlopen(req, timeout=120) as resp:
                if is_stream:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "keep-alive")
                    self.end_headers()
                    while True:
                        chunk = resp.read(4096)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
                else:
                    response_body = resp.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(response_body)
                    
        except urllib.error.HTTPError as e:
            error_body = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(error_body)
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def do_POST(self):
        self._forward_request()
    
    def do_GET(self):
        if "/models" in self.path:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            models = {
                "object": "list",
                "data": [
                    {"id": "glm-5.2", "object": "model", "owned_by": "zai"},
                    {"id": "glm-5.1", "object": "model", "owned_by": "zai"},
                    {"id": "glm-5-turbo", "object": "model", "owned_by": "zai"},
                    {"id": "glm-4.7", "object": "model", "owned_by": "zai"}
                ]
            }
            self.wfile.write(json.dumps(models).encode())
        else:
            self._forward_request()
    
    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), ProxyHandler)
    print(f"Z.AI Coding proxy running on port {port}")
    server.serve_forever()
