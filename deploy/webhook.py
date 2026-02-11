#!/usr/bin/env python3
"""
Lightweight GitHub webhook listener for auto-deploy.
No external dependencies — uses only Python stdlib.

Usage:
    python3 webhook.py

Environment variables:
    WEBHOOK_SECRET  - GitHub webhook secret (required)
    WEBHOOK_PORT    - Port to listen on (default: 9000)
    DEPLOY_SCRIPT   - Path to deploy script (default: /root/nyokiiaapp/deploy/deploy.sh)
"""

import hashlib
import hmac
import json
import os
import subprocess
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
WEBHOOK_PORT = int(os.environ.get("WEBHOOK_PORT", "9000"))
DEPLOY_SCRIPT = os.environ.get("DEPLOY_SCRIPT", "/root/nyokiiaapp/deploy/deploy.sh")


def verify_signature(payload: bytes, signature: str) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature."""
    if not WEBHOOK_SECRET:
        return True  # Skip verification if no secret set
    if not signature or not signature.startswith("sha256="):
        return False
    expected = hmac.new(
        WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/webhook":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(content_length)

        # Verify signature
        signature = self.headers.get("X-Hub-Signature-256", "")
        if not verify_signature(payload, signature):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Invalid signature")
            print(f"[REJECTED] Invalid signature from {self.client_address[0]}")
            return

        # Check if it's a push event
        event = self.headers.get("X-GitHub-Event", "")
        if event != "push":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(f"Ignored event: {event}".encode())
            return

        # Parse payload to get branch
        try:
            data = json.loads(payload)
            ref = data.get("ref", "")
            branch = ref.replace("refs/heads/", "")
            pusher = data.get("pusher", {}).get("name", "unknown")
        except (json.JSONDecodeError, KeyError):
            branch = "unknown"
            pusher = "unknown"

        print(f"[DEPLOY] Push to '{branch}' by {pusher} — running deploy script...")

        # Send response immediately, then deploy in background
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Deploy triggered")

        # Run deploy script
        try:
            result = subprocess.run(
                ["bash", DEPLOY_SCRIPT],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode == 0:
                print(f"[OK] Deploy completed successfully")
            else:
                print(f"[ERROR] Deploy failed:\n{result.stderr}")
        except subprocess.TimeoutExpired:
            print("[ERROR] Deploy script timed out after 5 minutes")
        except Exception as e:
            print(f"[ERROR] Deploy failed: {e}")

    def do_GET(self):
        """Health check endpoint."""
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default access logs."""
        pass


if __name__ == "__main__":
    if not WEBHOOK_SECRET:
        print("[WARN] WEBHOOK_SECRET not set — signature verification disabled!")

    server = HTTPServer(("0.0.0.0", WEBHOOK_PORT), WebhookHandler)
    print(f"Webhook listener started on port {WEBHOOK_PORT}")
    print(f"Deploy script: {DEPLOY_SCRIPT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()
