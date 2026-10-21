#!/usr/bin/env python3
"""Codex app-server smoke test; uses a local HTTP fixture, never a live model.

CI pins Codex 0.163.0. Checks real discovery and explicit skill injection.
Command routing and project override resolution are tested separately by
test-codex-adapters.py; this is not a model evaluation of phase execution.
"""

import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = Path(__file__).resolve().parents[2]
REQUESTS = queue.Queue()


class ModelFixture(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        REQUESTS.put(json.loads(body))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        event = {"type": "response.completed", "response": {
            "id": "resp_fixture", "status": "completed", "output": [],
            "usage": {"input_tokens": 1, "output_tokens": 0, "total_tokens": 1},
        }}
        self.wfile.write(f"event: response.completed\ndata: {json.dumps(event)}\n\n".encode())

    def log_message(self, *_args):
        pass


class AppServer:
    def __init__(self, env, cwd, url, stderr):
        self.messages = queue.Queue()
        self.sequence = 0
        self.process = subprocess.Popen([
            "codex", "app-server", "--stdio",
            "-c", 'model_provider="fixture"',
            "-c", 'model="fixture-model"',
            "-c", 'model_providers.fixture.name="Local test fixture"',
            "-c", f"model_providers.fixture.base_url={json.dumps(url)}",
            "-c", 'model_providers.fixture.wire_api="responses"',
            "-c", 'model_providers.fixture.requires_openai_auth=false',
            "-c", 'model_providers.fixture.request_max_retries=0',
            "-c", 'model_providers.fixture.stream_max_retries=0',
        ], env=env, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=stderr, text=True)
        threading.Thread(target=self._read, daemon=True).start()
        try:
            self.call("initialize", {"clientInfo": {"name": "aiw-smoke", "version": "1"}})
            self.send({"method": "initialized"})
        except Exception:
            self.close()
            raise

    def _read(self):
        for line in self.process.stdout:
            self.messages.put(json.loads(line))

    def send(self, message):
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def call(self, method, params):
        self.sequence += 1
        request_id = self.sequence
        self.send({"id": request_id, "method": method, "params": params})
        while True:
            message = self.messages.get(timeout=30)
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message["result"]

    def close(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        self.process.stdin.close()
        self.process.stdout.close()


def main():
    print(subprocess.check_output(["codex", "--version"], text=True).strip())
    with tempfile.TemporaryDirectory(prefix="aiw-codex-runtime-") as root:
        root = Path(root)
        home, project = root / "home", root / "project"
        home.mkdir()
        project.mkdir()
        env = {**os.environ, "HOME": str(home), "CODEX_HOME": str(home / ".codex")}
        # No inherited account credentials or configuration are needed.
        env.pop("OPENAI_API_KEY", None)
        env.pop("OPENAI_BASE_URL", None)
        env.pop("CODEX_API_KEY", None)
        (home / ".codex").mkdir()
        subprocess.run(["git", "init", "-q", str(project)], check=True)
        server = ThreadingHTTPServer(("127.0.0.1", 0), ModelFixture)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            for scope in ("user", "project"):
                args = ["--project", str(project)] if scope == "project" else []
                subprocess.run([
                    "bash", str(REPO / "install.sh"), "codex", "--packages",
                    "bugfix,sizing,docs-writer,report-bug", "--no-update-timer", *args,
                ], env=env, check=True, stdout=subprocess.DEVNULL)
                with (root / "app-server.log").open("w+") as log:
                    app = AppServer(env, project, f"http://127.0.0.1:{server.server_port}/v1", log)
                    try:
                        listing = app.call("skills/list", {"cwds": [str(project)], "forceReload": True})
                        entry = listing["data"][0]
                        assert not entry["errors"], entry["errors"]
                        skills = {skill["name"]: skill for skill in entry["skills"]}
                        expected = {"bugfix", "sizing", "docs-writer", "report-bug",
                                    "bugfix-assess", "sizing-assess", "docs-writer-gather"}
                        assert expected <= skills.keys(), expected - skills.keys()
                        assert "assess" not in skills, "Bare phase name collision"
                        assert len(skills) == len(entry["skills"]), "Duplicate discovery names"
                        for name in ("bugfix-assess", "sizing-assess", "bugfix"):
                            skill = skills[name]
                            assert skill["enabled"], skill
                            thread = app.call("thread/start", {
                                "cwd": str(project), "ephemeral": True,
                                "approvalPolicy": "never", "sandbox": "read-only",
                            })
                            app.call("turn/start", {"threadId": thread["thread"]["id"], "input": [
                                {"type": "skill", "name": name, "path": skill["path"]},
                                {"type": "text", "text": "Invocation fixture context."},
                            ]})
                            payload = REQUESTS.get(timeout=30)
                            # Assert the selected file's body is injected, rather than
                            # merely appearing in the discovery metadata listing.
                            texts = [part["text"] for item in payload["input"]
                                     for part in item.get("content", []) if part.get("type") == "input_text"]
                            content = "\n".join(texts)
                            body = Path(skill["path"]).read_text().split("---", 2)[2].strip()
                            assert body in content, f"Selected skill body not injected: {name}"
                            assert "Invocation fixture context." in content
                        print(f"PASS: {scope} discovery, distinct phases, explicit invocation, top-level entry")
                    except Exception:
                        log.seek(0)
                        print(log.read())
                        raise
                    finally:
                        app.close()
                subprocess.run(["bash", str(REPO / "uninstall.sh"), "codex", "--packages",
                                "bugfix,sizing,docs-writer,report-bug", *args],
                               env=env, check=True, stdout=subprocess.DEVNULL)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
