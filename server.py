"""Lightweight proxy that forwards OpenAI-compatible requests to Z.AI Coding Plan API."""
import os
import json
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler

ZAI_CODING_URL = "https://api.z.ai/api/coding/paas/v4"
ZAI_API_KEY = os.environ.get("ZAI_API_KEY", "")

class ProxyHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        # Forward to Z.AI Coding endpoint
        target_url = ZAI_CODING_URL + self.path
        
        req = urllib.request.Request(target_url, data=body, method="POST")
        req.add_header("Authorization", f"Bearer {ZAI_API_KEY}")
        req.add_header("Content-Type", self.headers.get("Content-Type", "application/json"))
        
        try:
            # Handle streaming vs non-streaming
            payload = json.loads(body)
            is_stream = payload.get("stream", False)
            
            with urllib.request.urlopen(req, timeout=120) as resp:
                if is_stream:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "keep-alive")
                    self.end_headers()
                    
                    # Forward SSE chunks
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
    
    def do_GET(self):
        """Handle model listing requests."""
        if "/models" in self.path:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            models = {
                "object": "list",
                "data": [
                    {"id": "glm-5.2", "object": "model", "owned_by": "zai"},
                    {"id": "glm-5-turbo", "object": "model", "owned_by": "zai"},
                    {"id": "glm-4.7", "object": "model", "owned_by": "zai"}
                ]
            }
            self.wfile.write(json.dumps(models).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress logs

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), ProxyHandler)
    print(f"Z.AI Coding proxy running on port {port}")
    server.serve_forever()
