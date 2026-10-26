#!/usr/bin/env python3
"""Exercise the smoke-test client's process and environment boundaries."""

import json
import os
from pathlib import Path
import queue
import runpy
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

RUNTIME = runpy.run_path(str(Path(__file__).with_name("test-codex-runtime.py")))
AppServer = RUNTIME["AppServer"]
build_test_environment = RUNTIME["build_test_environment"]


class RuntimeClientTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aiw-runtime-client-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        executable = self.root / "codex"
        executable.write_text(f"#!{sys.executable}\n" + '''import json
import os
import sys

for line in sys.stdin:
    request = json.loads(line)
    if "id" not in request:
        continue
    if request["method"] == "initialize":
        print(json.dumps({"id": request["id"], "result": {}}), flush=True)
        continue
    mode = os.environ["AIW_FIXTURE_MODE"]
    if mode == "eof":
        break
    if mode == "malformed":
        print("not JSON", flush=True)
        break
    if mode == "nonobject":
        print("[]", flush=True)
        break
    if mode == "rpc-error":
        response = {"error": {"code": -32601, "message": "fixture method error"}}
    else:
        response = {"result": {"ok": True}}
    print(json.dumps({"id": request["id"], **response}), flush=True)
''')
        executable.chmod(0o755)

    def client(self, mode):
        env = {**os.environ, "PATH": str(self.root) + os.pathsep + os.environ["PATH"],
               "AIW_FIXTURE_MODE": mode}
        log = (self.root / "stderr.log").open("w")
        self.addCleanup(log.close)
        app = AppServer(env, self.root, "http://127.0.0.1", log)
        self.addCleanup(app.close)
        return app

    def assert_reader_failure(self, mode, cause_type):
        app = self.client(mode)
        result = queue.Queue()

        def invoke():
            try:
                result.put(app.call("fixture", {}))
            except Exception as error:
                result.put(error)

        threading.Thread(target=invoke, daemon=True).start()
        try:
            error = result.get(timeout=3)
        except queue.Empty:
            self.fail("RPC caller was not notified promptly when the reader stopped")
        self.assertIsInstance(error, RuntimeError)
        self.assertIsInstance(error.__cause__, cause_type)

    def test_eof_wakes_pending_call(self):
        self.assert_reader_failure("eof", EOFError)

    def test_malformed_json_wakes_pending_call(self):
        self.assert_reader_failure("malformed", json.JSONDecodeError)

    def test_nonobject_json_wakes_pending_call(self):
        self.assert_reader_failure("nonobject", ValueError)

    def test_normal_response_and_rpc_error_are_preserved(self):
        app = self.client("success")
        self.assertEqual(app.call("fixture", {}), {"ok": True})
        app = self.client("rpc-error")
        with self.assertRaisesRegex(RuntimeError, "fixture method error"):
            app.call("fixture", {})

    def test_environment_ignores_proxy_credentials_and_external_config(self):
        proxies = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                   "http_proxy", "https_proxy", "all_proxy")
        credentials = ("OPENAI_API_KEY", "OPENAI_BASE_URL", "CODEX_API_KEY")
        inherited = {key: "external-value" for key in proxies + credentials}
        inherited.update({"NO_PROXY": "external", "no_proxy": "external",
                          "GIT_CONFIG_GLOBAL": "/external/gitconfig",
                          "XDG_CONFIG_HOME": "/external/config"})
        with patch.dict(os.environ, inherited):
            env = build_test_environment(self.root)
        for variable in proxies + credentials:
            self.assertNotIn(variable, env)
        self.assertEqual(env["NO_PROXY"], "127.0.0.1")
        self.assertEqual(env["no_proxy"], "127.0.0.1")
        self.assertEqual(env["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertEqual(env["XDG_CONFIG_HOME"], str(self.root / ".config"))
        self.assertEqual(env["HOME"], str(self.root))
        self.assertEqual(env["CODEX_HOME"], str(self.root / ".codex"))


if __name__ == "__main__":
    unittest.main()
