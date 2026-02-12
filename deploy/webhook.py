#!/usr/bin/env python3
"""
Multi-project GitHub webhook auto-deploy listener.
No external dependencies — uses only Python stdlib.

Reads projects.json to know which repos to deploy and where.
One webhook listener handles ALL your projects.

Usage:
    python3 webhook.py

Environment variables:
    WEBHOOK_SECRET  - GitHub webhook secret (shared across all repos)
    WEBHOOK_PORT    - Port to listen on (default: 9000)
    CONFIG_FILE     - Path to projects.json (default: ./projects.json)
"""

import hashlib
import hmac
import json
import os
import subprocess
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
WEBHOOK_PORT = int(os.environ.get("WEBHOOK_PORT", "9000"))
CONFIG_FILE = os.environ.get("CONFIG_FILE", str(Path(__file__).parent / "projects.json"))
DEPLOY_SCRIPT = str(Path(__file__).parent / "deploy.sh")


def load_projects() -> dict:
    """Load project config from JSON file."""
    with open(CONFIG_FILE) as f:
        data = json.load(f)
    return data.get("projects", {})


def verify_signature(payload: bytes, signature: str) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature."""
    if not WEBHOOK_SECRET:
        return True
    if not signature or not signature.startswith("sha256="):
        return False
    expected = hmac.new(
        WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


def run_deploy(repo_name: str, project_cfg: dict):
    """Run deploy in a background thread so webhook responds immediately."""
    app_dir = project_cfg["dir"]
    branch = project_cfg.get("branch", "main")
    compose_file = project_cfg.get("compose_file", "docker-compose.yml")

    print(f"[DEPLOY] Starting deploy for {repo_name} -> {app_dir}")
    try:
        result = subprocess.run(
            ["bash", DEPLOY_SCRIPT, app_dir, branch, compose_file],
            capture_output=True, text=True, timeout=600
        )
        if result.returncode == 0:
            print(f"[OK] {repo_name} deployed successfully")
        else:
            print(f"[ERROR] {repo_name} deploy failed:\n{result.stderr[-500:]}")
    except subprocess.TimeoutExpired:
        print(f"[ERROR] {repo_name} deploy timed out after 10 minutes")
    except Exception as e:
        print(f"[ERROR] {repo_name} deploy failed: {e}")


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

        # Only handle push events
        event = self.headers.get("X-GitHub-Event", "")
        if event != "push":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(f"Ignored event: {event}".encode())
            return

        # Parse payload
        try:
            data = json.loads(payload)
            repo_name = data.get("repository", {}).get("full_name", "")
            ref = data.get("ref", "")
            branch = ref.replace("refs/heads/", "")
            pusher = data.get("pusher", {}).get("name", "unknown")
        except (json.JSONDecodeError, KeyError):
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Bad payload")
            return

        # Find matching project
        projects = load_projects()
        project_cfg = projects.get(repo_name)

        if not project_cfg:
            self.send_response(200)
            self.end_headers()
            msg = f"No config for repo: {repo_name}"
            self.wfile.write(msg.encode())
            print(f"[SKIP] {msg}")
            return

        # Check branch matches
        target_branch = project_cfg.get("branch", "main")
        if branch != target_branch:
            self.send_response(200)
            self.end_headers()
            msg = f"Ignored push to {branch} (watching {target_branch})"
            self.wfile.write(msg.encode())
            print(f"[SKIP] {repo_name}: {msg}")
            return

        print(f"[DEPLOY] {repo_name} push to {branch} by {pusher}")

        # Respond immediately, deploy in background
        self.send_response(200)
        self.end_headers()
        self.wfile.write(f"Deploy triggered for {repo_name}".encode())

        thread = threading.Thread(target=run_deploy, args=(repo_name, project_cfg))
        thread.daemon = True
        thread.start()

    def do_GET(self):
        if self.path == "/health":
            projects = load_projects()
            response = json.dumps({
                "status": "ok",
                "projects": list(projects.keys()),
            })
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(response.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    projects = load_projects()

    if not WEBHOOK_SECRET:
        print("[WARN] WEBHOOK_SECRET not set — signature verification disabled!")

    print(f"Webhook listener started on port {WEBHOOK_PORT}")
    print(f"Config: {CONFIG_FILE}")
    print(f"Projects registered:")
    for name, cfg in projects.items():
        print(f"  - {name} -> {cfg['dir']} (branch: {cfg.get('branch', 'main')})")

    server = HTTPServer(("0.0.0.0", WEBHOOK_PORT), WebhookHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()
