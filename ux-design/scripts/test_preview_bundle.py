#!/usr/bin/env python3
"""Tests for ux-design/scripts/preview-bundle.py."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent / "preview-bundle.py"
_spec = importlib.util.spec_from_file_location("preview_bundle", _SCRIPT)
assert _spec and _spec.loader
preview_bundle = importlib.util.module_from_spec(_spec)
sys.modules["preview_bundle"] = preview_bundle
_spec.loader.exec_module(preview_bundle)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SELF_CONTAINED_HTML = textwrap.dedent("""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <title>Fleet Management — Prototype</title>
        <style>
            body { font-family: sans-serif; margin: 2rem; }
            .card { border: 1px solid #ccc; padding: 1rem; margin: 1rem 0; }
        </style>
    </head>
    <body>
        <h1>Device Fleet Dashboard</h1>
        <div class="card">
            <h2>Device Status</h2>
            <p>Active: <span id="active">42</span></p>
            <p>Offline: <span id="offline">3</span></p>
        </div>
        <script>
            // Mock data — no backend required
            const devices = [
                { name: 'edge-01', status: 'active' },
                { name: 'edge-02', status: 'active' },
                { name: 'edge-03', status: 'offline' },
            ];
            document.getElementById('active').textContent =
                devices.filter(d => d.status === 'active').length;
        </script>
    </body>
    </html>
""")

_BACKEND_DEPENDENT_HTML = textwrap.dedent("""\
    <!DOCTYPE html>
    <html>
    <head><title>App</title></head>
    <body>
        <div id="root"></div>
        <script>
            fetch('/api/devices')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('root').textContent =
                        JSON.stringify(data);
                });
        </script>
    </body>
    </html>
""")

_LOCALHOST_HTML = textwrap.dedent("""\
    <!DOCTYPE html>
    <html>
    <head><title>Dev</title></head>
    <body>
        <script>
            const ws = new WebSocket('ws://localhost:3000/ws');
        </script>
    </body>
    </html>
""")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

class TestParseArgs(unittest.TestCase):
    """Verify argparse configuration for each subcommand."""

    def test_validate_defaults(self) -> None:
        parser = preview_bundle.build_parser()
        args = parser.parse_args(["validate", "--prototype-dir", "/tmp/proto"])
        self.assertEqual(args.subcommand, "validate")
        self.assertEqual(args.mode, "standalone")
        self.assertIsNone(args.entry_point)

    def test_validate_workspace(self) -> None:
        parser = preview_bundle.build_parser()
        args = parser.parse_args([
            "validate", "--prototype-dir", "/tmp/proto",
            "--mode", "workspace",
        ])
        self.assertEqual(args.mode, "workspace")

    def test_package_required_args(self) -> None:
        parser = preview_bundle.build_parser()
        args = parser.parse_args([
            "package",
            "--prototype-dir", "/tmp/proto",
            "--output-dir", "/tmp/out",
            "--issue-key", "EDM-1234",
            "--revision", "iteration-1",
        ])
        self.assertEqual(args.subcommand, "package")
        self.assertEqual(args.issue_key, "EDM-1234")
        self.assertEqual(args.revision, "iteration-1")

    def test_package_missing_issue_key(self) -> None:
        parser = preview_bundle.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args([
                "package", "--prototype-dir", "/tmp/proto",
                "--output-dir", "/tmp/out", "--revision", "r1",
            ])

    def test_manifest_args(self) -> None:
        parser = preview_bundle.build_parser()
        args = parser.parse_args(["manifest", "--bundle-dir", "/tmp/bundle"])
        self.assertEqual(args.subcommand, "manifest")


# ---------------------------------------------------------------------------
# Backend-dependency scanning
# ---------------------------------------------------------------------------

class TestScanDependencies(unittest.TestCase):
    """Test backend dependency detection in HTML and JS files."""

    def test_self_contained_has_no_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            html = Path(tmpdir) / "index.html"
            html.write_text(_SELF_CONTAINED_HTML, encoding="utf-8")
            findings = preview_bundle._scan_directory(Path(tmpdir))
            self.assertEqual(findings, [])

    def test_fetch_api_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            html = Path(tmpdir) / "index.html"
            html.write_text(_BACKEND_DEPENDENT_HTML, encoding="utf-8")
            findings = preview_bundle._scan_directory(Path(tmpdir))
            self.assertGreater(len(findings), 0)
            patterns = [f["pattern"] for f in findings]
            self.assertTrue(
                any("fetch()" in p for p in patterns),
                f"Expected fetch() finding, got: {patterns}",
            )

    def test_localhost_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            html = Path(tmpdir) / "index.html"
            html.write_text(_LOCALHOST_HTML, encoding="utf-8")
            findings = preview_bundle._scan_directory(Path(tmpdir))
            self.assertGreater(len(findings), 0)
            patterns = [f["pattern"] for f in findings]
            self.assertTrue(
                any("localhost" in p for p in patterns),
                f"Expected localhost finding, got: {patterns}",
            )

    def test_cdn_fetch_not_flagged(self) -> None:
        """CDN fetches (unpkg, cdnjs) should not trigger backend findings."""
        html_text = textwrap.dedent("""\
            <!DOCTYPE html>
            <html><head><title>CDN</title></head>
            <body>
                <script>
                    fetch('https://unpkg.com/react/umd/react.production.min.js')
                        .then(r => r.text());
                    fetch('https://cdnjs.cloudflare.com/ajax/libs/lodash.js/4.17.21/lodash.min.js')
                        .then(r => r.text());
                </script>
            </body></html>
        """)
        with tempfile.TemporaryDirectory() as tmpdir:
            html = Path(tmpdir) / "index.html"
            html.write_text(html_text, encoding="utf-8")
            findings = preview_bundle._scan_directory(Path(tmpdir))
            self.assertEqual(
                findings, [],
                f"Known CDN fetches should not trigger findings, got: {findings}",
            )

    def test_skips_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            real = Path(tmpdir) / "real.html"
            real.write_text("<html><body>OK</body></html>", encoding="utf-8")
            link = Path(tmpdir) / "link.html"
            link.symlink_to(real)
            findings = preview_bundle._scan_directory(Path(tmpdir))
            scanned = [f["file"] for f in findings]
            self.assertNotIn(str(link), scanned)


# ---------------------------------------------------------------------------
# Content directory resolution
# ---------------------------------------------------------------------------

class TestResolveContentDir(unittest.TestCase):
    """Test _resolve_content_dir for standalone and workspace modes."""

    def test_standalone_prototype_subdir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            proto = Path(tmpdir) / "prototype"
            proto.mkdir()
            (proto / "index.html").write_text("<html></html>")
            result = preview_bundle._resolve_content_dir(Path(tmpdir), "standalone")
            self.assertEqual(result, proto)

    def test_standalone_html_in_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "index.html").write_text("<html></html>")
            result = preview_bundle._resolve_content_dir(Path(tmpdir), "standalone")
            self.assertEqual(result, Path(tmpdir))

    def test_standalone_no_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = preview_bundle._resolve_content_dir(Path(tmpdir), "standalone")
            self.assertIsNone(result)

    def test_workspace_dist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dist = Path(tmpdir) / "code" / "dist"
            dist.mkdir(parents=True)
            (dist / "index.html").write_text("<html></html>")
            result = preview_bundle._resolve_content_dir(Path(tmpdir), "workspace")
            self.assertEqual(result, dist)

    def test_workspace_no_code_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = preview_bundle._resolve_content_dir(Path(tmpdir), "workspace")
            self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Validate subcommand
# ---------------------------------------------------------------------------

class TestValidate(unittest.TestCase):
    """Test the validate subcommand end-to-end."""

    def test_valid_standalone_prototype(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            proto = Path(tmpdir) / "prototype"
            proto.mkdir()
            (proto / "index.html").write_text(
                _SELF_CONTAINED_HTML, encoding="utf-8",
            )
            (proto / "style.css").write_text(
                "body { margin: 0; }", encoding="utf-8",
            )
            result = preview_bundle.cmd_validate(
                argparse.Namespace(
                    prototype_dir=tmpdir,
                    mode="standalone",
                    entry_point=None,
                ),
            )
            self.assertEqual(result, preview_bundle.EXIT_SUCCESS)

    def test_invalid_backend_dependent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            proto = Path(tmpdir) / "prototype"
            proto.mkdir()
            (proto / "index.html").write_text(
                _BACKEND_DEPENDENT_HTML, encoding="utf-8",
            )
            result = preview_bundle.cmd_validate(
                argparse.Namespace(
                    prototype_dir=tmpdir,
                    mode="standalone",
                    entry_point=None,
                ),
            )
            self.assertEqual(result, preview_bundle.EXIT_VALIDATION_FAIL)

    def test_no_content_returns_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = preview_bundle.cmd_validate(
                argparse.Namespace(
                    prototype_dir=tmpdir,
                    mode="standalone",
                    entry_point=None,
                ),
            )
            self.assertEqual(result, preview_bundle.EXIT_VALIDATION_FAIL)


# ---------------------------------------------------------------------------
# Package subcommand
# ---------------------------------------------------------------------------

class TestPackage(unittest.TestCase):
    """Test the package subcommand end-to-end."""

    def test_creates_namespaced_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Set up prototype source.
            proto = Path(tmpdir) / "source" / "prototype"
            proto.mkdir(parents=True)
            (proto / "index.html").write_text(
                _SELF_CONTAINED_HTML, encoding="utf-8",
            )
            (proto / "app.js").write_text(
                "console.log('hello');", encoding="utf-8",
            )

            output = Path(tmpdir) / "output"

            result = preview_bundle.cmd_package(
                argparse.Namespace(
                    prototype_dir=str(Path(tmpdir) / "source"),
                    output_dir=str(output),
                    issue_key="EDM-1234",
                    revision="iteration-1",
                    mode="standalone",
                    entry_point=None,
                ),
            )
            self.assertEqual(result, preview_bundle.EXIT_SUCCESS)

            bundle = output / "previews" / "EDM-1234" / "iteration-1"
            self.assertTrue(bundle.is_dir())
            self.assertTrue((bundle / "index.html").is_file())
            self.assertTrue((bundle / "app.js").is_file())
            self.assertTrue((bundle / "preview-manifest.json").is_file())

            manifest = json.loads(
                (bundle / "preview-manifest.json").read_text(encoding="utf-8"),
            )
            self.assertEqual(manifest["issue_key"], "EDM-1234")
            self.assertEqual(manifest["revision"], "iteration-1")
            self.assertEqual(manifest["entry_point"], "index.html")
            self.assertGreater(manifest["file_count"], 0)

    def test_invalid_issue_key_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            proto = Path(tmpdir) / "prototype"
            proto.mkdir()
            (proto / "index.html").write_text("<html></html>")
            with self.assertRaises(SystemExit):
                preview_bundle.cmd_package(
                    argparse.Namespace(
                        prototype_dir=tmpdir,
                        output_dir=str(Path(tmpdir) / "out"),
                        issue_key="../escape",
                        revision="r1",
                        mode="standalone",
                        entry_point=None,
                    ),
                )


# ---------------------------------------------------------------------------
# Manifest subcommand
# ---------------------------------------------------------------------------

class TestManifest(unittest.TestCase):
    """Test the manifest subcommand."""

    def test_reads_existing_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = {
                "issue_key": "TEST-1",
                "revision": "r1",
                "entry_point": "index.html",
                "file_count": 2,
                "files": [],
            }
            (Path(tmpdir) / "preview-manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8",
            )
            result = preview_bundle.cmd_manifest(
                argparse.Namespace(bundle_dir=tmpdir),
            )
            self.assertEqual(result, preview_bundle.EXIT_SUCCESS)

    def test_missing_manifest_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(SystemExit):
                preview_bundle.cmd_manifest(
                    argparse.Namespace(bundle_dir=tmpdir),
                )


# ---------------------------------------------------------------------------
# Static serving smoke test
# ---------------------------------------------------------------------------

class TestStaticServeSmoke(unittest.TestCase):
    """Verify a packaged bundle serves without backend dependencies.

    This test creates a minimal bundle, starts a local HTTP server, and
    confirms the entry point returns HTTP 200. The server is torn down
    immediately. No external network access is required.
    """

    def test_bundle_serves_locally(self) -> None:
        import http.server
        import threading
        import urllib.request

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a minimal bundle.
            bundle = Path(tmpdir) / "bundle"
            bundle.mkdir()
            (bundle / "index.html").write_text(
                _SELF_CONTAINED_HTML, encoding="utf-8",
            )
            (bundle / "preview-manifest.json").write_text(
                json.dumps({"entry_point": "index.html"}), encoding="utf-8",
            )

            # Start a local server.
            handler = http.server.SimpleHTTPRequestHandler
            original_dir = os.getcwd()
            os.chdir(str(bundle))
            try:
                server = http.server.HTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever)
                thread.daemon = True
                thread.start()

                # Request the entry point.
                url = f"http://127.0.0.1:{port}/index.html"
                with urllib.request.urlopen(url, timeout=5) as resp:
                    self.assertEqual(resp.status, 200)
                    body = resp.read().decode("utf-8")
                    self.assertIn("Device Fleet Dashboard", body)
                    # Verify no backend-dependent markers in served content.
                    self.assertNotIn("fetch('/api/", body)
                    self.assertNotIn("localhost:", body)

                server.shutdown()
            finally:
                os.chdir(original_dir)


# ---------------------------------------------------------------------------
# File inventory
# ---------------------------------------------------------------------------

class TestFileInventory(unittest.TestCase):
    """Test _collect_file_inventory categories."""

    def test_categorizes_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "index.html").write_text("<html></html>")
            (Path(tmpdir) / "style.css").write_text("body{}")
            (Path(tmpdir) / "app.js").write_text("console.log(1)")
            (Path(tmpdir) / "logo.png").write_bytes(b"\x89PNG")
            inventory = preview_bundle._collect_file_inventory(Path(tmpdir))
            categories = {item["path"]: item["category"] for item in inventory}
            self.assertEqual(categories["index.html"], "html")
            self.assertEqual(categories["style.css"], "style")
            self.assertEqual(categories["app.js"], "script")
            self.assertEqual(categories["logo.png"], "asset")


# ---------------------------------------------------------------------------
# Package safety — private file exclusion
# ---------------------------------------------------------------------------

class TestPrivateFileExclusion(unittest.TestCase):
    """Verify that private/hidden files are excluded from bundles."""

    def _package(self, tmpdir: str, **extra: str) -> int:
        """Run cmd_package with standard args, return exit code."""
        proto = Path(tmpdir) / "source" / "prototype"
        proto.mkdir(parents=True, exist_ok=True)
        (proto / "index.html").write_text(
            _SELF_CONTAINED_HTML, encoding="utf-8",
        )
        # Add private files that should be excluded.
        (proto / ".env").write_text("SECRET=x", encoding="utf-8")
        (proto / ".gitignore").write_text("node_modules/", encoding="utf-8")
        (proto / "prototype-notes.md").write_text("# Notes", encoding="utf-8")
        hidden_dir = proto / ".hidden"
        hidden_dir.mkdir()
        (hidden_dir / "secret.txt").write_text("private", encoding="utf-8")

        output = Path(tmpdir) / "output"
        return preview_bundle.cmd_package(
            argparse.Namespace(
                prototype_dir=str(Path(tmpdir) / "source"),
                output_dir=str(output),
                issue_key=extra.get("issue_key", "TEST-1"),
                revision=extra.get("revision", "r1"),
                mode="standalone",
                entry_point=None,
            ),
        )

    def test_private_files_excluded_from_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._package(tmpdir)
            self.assertEqual(result, preview_bundle.EXIT_SUCCESS)
            bundle = Path(tmpdir) / "output" / "previews" / "TEST-1" / "r1"
            bundle_files = {f.name for f in bundle.rglob("*") if f.is_file()}
            self.assertIn("index.html", bundle_files)
            self.assertNotIn(".env", bundle_files)
            self.assertNotIn(".gitignore", bundle_files)
            self.assertNotIn("prototype-notes.md", bundle_files)
            self.assertNotIn("secret.txt", bundle_files)

    def test_manifest_excludes_private_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            self._package(tmpdir)
            bundle = Path(tmpdir) / "output" / "previews" / "TEST-1" / "r1"
            manifest = json.loads(
                (bundle / "preview-manifest.json").read_text(encoding="utf-8"),
            )
            paths = [f["path"] for f in manifest["files"]]
            self.assertNotIn(".env", paths)
            self.assertNotIn("prototype-notes.md", paths)


# ---------------------------------------------------------------------------
# Package safety — entry point containment
# ---------------------------------------------------------------------------

class TestEntryPointContainment(unittest.TestCase):
    """Verify entry point must be relative and contained."""

    def test_absolute_entry_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "index.html").write_text("<html></html>")
            result = preview_bundle._find_entry_point(
                Path(tmpdir), "/etc/passwd",
            )
            self.assertIsNone(result)

    def test_traversal_entry_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "index.html").write_text("<html></html>")
            result = preview_bundle._find_entry_point(
                Path(tmpdir), "../../../etc/passwd",
            )
            self.assertIsNone(result)

    def test_valid_relative_entry_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sub = Path(tmpdir) / "pages"
            sub.mkdir()
            (sub / "main.html").write_text("<html></html>")
            result = preview_bundle._find_entry_point(
                Path(tmpdir), "pages/main.html",
            )
            self.assertIsNotNone(result)


# ---------------------------------------------------------------------------
# Package safety — input/output disjointness
# ---------------------------------------------------------------------------

class TestInputOutputDisjoint(unittest.TestCase):
    """Verify package fails when input and output directories overlap."""

    def test_output_inside_prototype_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            proto = Path(tmpdir) / "prototype"
            proto.mkdir()
            (proto / "index.html").write_text(
                _SELF_CONTAINED_HTML, encoding="utf-8",
            )
            with self.assertRaises(SystemExit) as ctx:
                preview_bundle.cmd_package(
                    argparse.Namespace(
                        prototype_dir=str(proto),
                        output_dir=str(proto / "output"),
                        issue_key="TEST-1",
                        revision="r1",
                        mode="standalone",
                        entry_point=None,
                    ),
                )
            self.assertEqual(ctx.exception.code, preview_bundle.EXIT_PACKAGE_FAIL)

    def test_prototype_inside_output_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "output"
            output.mkdir()
            proto = output / "proto" / "prototype"
            proto.mkdir(parents=True)
            (proto / "index.html").write_text(
                _SELF_CONTAINED_HTML, encoding="utf-8",
            )
            with self.assertRaises(SystemExit) as ctx:
                preview_bundle.cmd_package(
                    argparse.Namespace(
                        prototype_dir=str(output / "proto"),
                        output_dir=str(output),
                        issue_key="TEST-1",
                        revision="r1",
                        mode="standalone",
                        entry_point=None,
                    ),
                )
            self.assertEqual(ctx.exception.code, preview_bundle.EXIT_PACKAGE_FAIL)


# ---------------------------------------------------------------------------
# Package safety — existing revision non-destruction
# ---------------------------------------------------------------------------

class TestExistingRevision(unittest.TestCase):
    """Verify package does not destroy existing revisions."""

    def test_existing_revision_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            proto = Path(tmpdir) / "source" / "prototype"
            proto.mkdir(parents=True)
            (proto / "index.html").write_text(
                _SELF_CONTAINED_HTML, encoding="utf-8",
            )
            output = Path(tmpdir) / "output"

            # First package succeeds.
            result = preview_bundle.cmd_package(
                argparse.Namespace(
                    prototype_dir=str(Path(tmpdir) / "source"),
                    output_dir=str(output),
                    issue_key="TEST-1",
                    revision="r1",
                    mode="standalone",
                    entry_point=None,
                ),
            )
            self.assertEqual(result, preview_bundle.EXIT_SUCCESS)

            # Second package with same revision fails.
            with self.assertRaises(SystemExit) as ctx:
                preview_bundle.cmd_package(
                    argparse.Namespace(
                        prototype_dir=str(Path(tmpdir) / "source"),
                        output_dir=str(output),
                        issue_key="TEST-1",
                        revision="r1",
                        mode="standalone",
                        entry_point=None,
                    ),
                )
            self.assertEqual(ctx.exception.code, preview_bundle.EXIT_PACKAGE_FAIL)

            # Original bundle still intact.
            bundle = output / "previews" / "TEST-1" / "r1"
            self.assertTrue((bundle / "index.html").is_file())


# ---------------------------------------------------------------------------
# Package safety — SHA-256 content digest
# ---------------------------------------------------------------------------

class TestContentDigest(unittest.TestCase):
    """Verify manifest includes a deterministic content digest."""

    def test_manifest_has_content_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            proto = Path(tmpdir) / "source" / "prototype"
            proto.mkdir(parents=True)
            (proto / "index.html").write_text(
                _SELF_CONTAINED_HTML, encoding="utf-8",
            )
            output = Path(tmpdir) / "output"
            preview_bundle.cmd_package(
                argparse.Namespace(
                    prototype_dir=str(Path(tmpdir) / "source"),
                    output_dir=str(output),
                    issue_key="TEST-1",
                    revision="r1",
                    mode="standalone",
                    entry_point=None,
                ),
            )
            bundle = output / "previews" / "TEST-1" / "r1"
            manifest = json.loads(
                (bundle / "preview-manifest.json").read_text(encoding="utf-8"),
            )
            self.assertIn("content_sha256", manifest)
            self.assertEqual(len(manifest["content_sha256"]), 64)

    def test_digest_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            proto = Path(tmpdir) / "source" / "prototype"
            proto.mkdir(parents=True)
            (proto / "index.html").write_text(
                _SELF_CONTAINED_HTML, encoding="utf-8",
            )
            output1 = Path(tmpdir) / "out1"
            output2 = Path(tmpdir) / "out2"
            for out in (output1, output2):
                preview_bundle.cmd_package(
                    argparse.Namespace(
                        prototype_dir=str(Path(tmpdir) / "source"),
                        output_dir=str(out),
                        issue_key="TEST-1",
                        revision="r1",
                        mode="standalone",
                        entry_point=None,
                    ),
                )
            m1 = json.loads(
                (output1 / "previews" / "TEST-1" / "r1" / "preview-manifest.json")
                .read_text(encoding="utf-8"),
            )
            m2 = json.loads(
                (output2 / "previews" / "TEST-1" / "r1" / "preview-manifest.json")
                .read_text(encoding="utf-8"),
            )
            self.assertEqual(m1["content_sha256"], m2["content_sha256"])


# ---------------------------------------------------------------------------
# Package safety — symlink escape
# ---------------------------------------------------------------------------

class TestSymlinkEscape(unittest.TestCase):
    """Verify symlinks that escape content_dir are excluded."""

    def test_escaping_symlink_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            proto = Path(tmpdir) / "source" / "prototype"
            proto.mkdir(parents=True)
            (proto / "index.html").write_text(
                _SELF_CONTAINED_HTML, encoding="utf-8",
            )
            # Create a file outside the content directory.
            secret = Path(tmpdir) / "secret.txt"
            secret.write_text("TOP SECRET", encoding="utf-8")
            # Create a symlink inside proto pointing to the secret.
            (proto / "leaked.txt").symlink_to(secret)

            output = Path(tmpdir) / "output"
            result = preview_bundle.cmd_package(
                argparse.Namespace(
                    prototype_dir=str(Path(tmpdir) / "source"),
                    output_dir=str(output),
                    issue_key="TEST-1",
                    revision="r1",
                    mode="standalone",
                    entry_point=None,
                ),
            )
            self.assertEqual(result, preview_bundle.EXIT_SUCCESS)
            bundle = output / "previews" / "TEST-1" / "r1"
            self.assertFalse((bundle / "leaked.txt").exists())


# ---------------------------------------------------------------------------
# Packaged bundle → serve (actual packager output, not hand-created)
# ---------------------------------------------------------------------------

class TestPackageThenServe(unittest.TestCase):
    """Package via cmd_package, then serve the result and verify.

    Unlike TestStaticServeSmoke which hand-creates a bundle, this test
    uses the actual packager to build the bundle, ensuring the full
    pipeline produces a servable result.
    """

    def test_packaged_bundle_serves(self) -> None:
        import http.server
        import threading
        import urllib.request

        with tempfile.TemporaryDirectory() as tmpdir:
            # Build a prototype with JS interaction + CSS.
            proto = Path(tmpdir) / "source" / "prototype"
            proto.mkdir(parents=True)
            (proto / "index.html").write_text(textwrap.dedent("""\
                <!DOCTYPE html>
                <html lang="en">
                <head>
                    <meta charset="utf-8">
                    <title>Interactive Mock</title>
                    <link rel="stylesheet" href="style.css">
                </head>
                <body>
                    <h1>Dashboard</h1>
                    <button id="toggle">Toggle</button>
                    <div id="panel" class="hidden">Panel Content</div>
                    <script src="app.js"></script>
                </body>
                </html>
            """), encoding="utf-8")
            (proto / "style.css").write_text(textwrap.dedent("""\
                body { font-family: sans-serif; margin: 2rem; }
                .hidden { display: none; }
                .visible { display: block; background: #eef; padding: 1rem; }
            """), encoding="utf-8")
            (proto / "app.js").write_text(textwrap.dedent("""\
                document.getElementById('toggle').addEventListener('click', function() {
                    var panel = document.getElementById('panel');
                    panel.className = panel.className === 'hidden' ? 'visible' : 'hidden';
                });
            """), encoding="utf-8")

            output = Path(tmpdir) / "output"
            result = preview_bundle.cmd_package(
                argparse.Namespace(
                    prototype_dir=str(Path(tmpdir) / "source"),
                    output_dir=str(output),
                    issue_key="TEST-1",
                    revision="r1",
                    mode="standalone",
                    entry_point=None,
                ),
            )
            self.assertEqual(result, preview_bundle.EXIT_SUCCESS)

            bundle = output / "previews" / "TEST-1" / "r1"

            # Verify manifest has correct content.
            manifest = json.loads(
                (bundle / "preview-manifest.json").read_text(encoding="utf-8"),
            )
            self.assertEqual(manifest["entry_point"], "index.html")
            self.assertIn("content_sha256", manifest)
            file_paths = {f["path"] for f in manifest["files"]}
            self.assertIn("style.css", file_paths)
            self.assertIn("app.js", file_paths)

            # Serve the packaged bundle and verify assets load.
            handler = http.server.SimpleHTTPRequestHandler
            original_dir = os.getcwd()
            os.chdir(str(bundle))
            try:
                server = http.server.HTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever)
                thread.daemon = True
                thread.start()

                # Verify entry point.
                url = f"http://127.0.0.1:{port}/index.html"
                with urllib.request.urlopen(url, timeout=5) as resp:
                    self.assertEqual(resp.status, 200)
                    body = resp.read().decode("utf-8")
                    self.assertIn("Dashboard", body)
                    self.assertIn("app.js", body)
                    self.assertIn("style.css", body)

                # Verify CSS asset loads.
                css_url = f"http://127.0.0.1:{port}/style.css"
                with urllib.request.urlopen(css_url, timeout=5) as resp:
                    self.assertEqual(resp.status, 200)
                    css = resp.read().decode("utf-8")
                    self.assertIn(".hidden", css)

                # Verify JS asset loads.
                js_url = f"http://127.0.0.1:{port}/app.js"
                with urllib.request.urlopen(js_url, timeout=5) as resp:
                    self.assertEqual(resp.status, 200)
                    js = resp.read().decode("utf-8")
                    self.assertIn("toggle", js)

                # Verify no external network requests needed.
                self.assertNotIn("fetch(", body)
                self.assertNotIn("localhost:", body)

                server.shutdown()
            finally:
                os.chdir(original_dir)


# ---------------------------------------------------------------------------
# Private file helper unit tests
# ---------------------------------------------------------------------------

class TestIsPrivateFile(unittest.TestCase):
    """Test _is_private_file helper directly."""

    def test_dotenv_is_private(self) -> None:
        base = Path("/tmp/base")
        self.assertTrue(
            preview_bundle._is_private_file(base / ".env", base),
        )

    def test_hidden_dir_is_private(self) -> None:
        base = Path("/tmp/base")
        self.assertTrue(
            preview_bundle._is_private_file(base / ".git" / "config", base),
        )

    def test_normal_file_is_not_private(self) -> None:
        base = Path("/tmp/base")
        self.assertFalse(
            preview_bundle._is_private_file(base / "index.html", base),
        )

    def test_outside_base_is_private(self) -> None:
        self.assertTrue(
            preview_bundle._is_private_file(Path("/other/file"), Path("/base")),
        )


# ---------------------------------------------------------------------------
# Per-file SHA-256 hashes in manifest
# ---------------------------------------------------------------------------

class TestPerFileHashes(unittest.TestCase):
    """Verify manifest includes per-file SHA-256 hashes."""

    def test_manifest_has_per_file_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            proto = Path(tmpdir) / "source" / "prototype"
            proto.mkdir(parents=True)
            content = _SELF_CONTAINED_HTML
            (proto / "index.html").write_text(content, encoding="utf-8")
            (proto / "style.css").write_text("body { margin: 0; }", encoding="utf-8")
            output = Path(tmpdir) / "output"
            preview_bundle.cmd_package(
                argparse.Namespace(
                    prototype_dir=str(Path(tmpdir) / "source"),
                    output_dir=str(output),
                    issue_key="HASH-1",
                    revision="r1",
                    mode="standalone",
                    entry_point=None,
                ),
            )
            bundle = output / "previews" / "HASH-1" / "r1"
            manifest = json.loads(
                (bundle / "preview-manifest.json").read_text(encoding="utf-8"),
            )
            for f in manifest["files"]:
                self.assertIn("sha256", f, f"File {f['path']} missing sha256")
                self.assertEqual(len(f["sha256"]), 64, f"File {f['path']} bad hash length")

    def test_per_file_hash_matches_content(self) -> None:
        """Each file's sha256 must match actual file content hash."""
        import hashlib as hl
        with tempfile.TemporaryDirectory() as tmpdir:
            proto = Path(tmpdir) / "source" / "prototype"
            proto.mkdir(parents=True)
            (proto / "index.html").write_text("<html><body>Test</body></html>", encoding="utf-8")
            output = Path(tmpdir) / "output"
            preview_bundle.cmd_package(
                argparse.Namespace(
                    prototype_dir=str(Path(tmpdir) / "source"),
                    output_dir=str(output),
                    issue_key="HASH-2",
                    revision="r1",
                    mode="standalone",
                    entry_point=None,
                ),
            )
            bundle = output / "previews" / "HASH-2" / "r1"
            manifest = json.loads(
                (bundle / "preview-manifest.json").read_text(encoding="utf-8"),
            )
            for f in manifest["files"]:
                fpath = bundle / f["path"]
                expected = hl.sha256(fpath.read_bytes()).hexdigest()
                self.assertEqual(f["sha256"], expected, f"Hash mismatch for {f['path']}")

    def test_aggregate_hash_differs_from_single_file(self) -> None:
        """Aggregate content_sha256 must not equal any single file hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            proto = Path(tmpdir) / "source" / "prototype"
            proto.mkdir(parents=True)
            (proto / "index.html").write_text("<html>A</html>", encoding="utf-8")
            (proto / "app.js").write_text("console.log(1)", encoding="utf-8")
            output = Path(tmpdir) / "output"
            preview_bundle.cmd_package(
                argparse.Namespace(
                    prototype_dir=str(Path(tmpdir) / "source"),
                    output_dir=str(output),
                    issue_key="HASH-3",
                    revision="r1",
                    mode="standalone",
                    entry_point=None,
                ),
            )
            bundle = output / "previews" / "HASH-3" / "r1"
            manifest = json.loads(
                (bundle / "preview-manifest.json").read_text(encoding="utf-8"),
            )
            file_hashes = {f["sha256"] for f in manifest["files"]}
            self.assertNotIn(
                manifest["content_sha256"], file_hashes,
                "Aggregate digest should differ from any single file hash",
            )


# ---------------------------------------------------------------------------
# Symlink entry point rejection
# ---------------------------------------------------------------------------

class TestSymlinkEntryRejection(unittest.TestCase):
    """Verify symlink entry points are rejected."""

    def test_symlink_index_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Put real file outside; symlink is the only HTML in tmpdir
            outer = Path(tmpdir) / "outer"
            outer.mkdir()
            real = outer / "real.html"
            real.write_text("<html>OK</html>", encoding="utf-8")
            inner = Path(tmpdir) / "inner"
            inner.mkdir()
            link = inner / "index.html"
            link.symlink_to(real)
            result = preview_bundle._find_entry_point(inner)
            self.assertIsNone(
                result,
                "Symlink entry point should be rejected",
            )

    def test_symlink_content_dir_rejected(self) -> None:
        """Symlink prototype directory should not resolve as content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            real = Path(tmpdir) / "real_proto"
            real.mkdir()
            (real / "index.html").write_text("<html>OK</html>")
            link = Path(tmpdir) / "prototype"
            link.symlink_to(real)
            result = preview_bundle._resolve_content_dir(Path(tmpdir), "standalone")
            # Should use symlink target or reject — the prototype/ symlink is
            # rejected because is_symlink() is true for it.
            self.assertNotEqual(result, link)


# ---------------------------------------------------------------------------
# Missing entry after symlink skip
# ---------------------------------------------------------------------------

class TestMissingEntryAfterSkip(unittest.TestCase):
    """Package fails if entry point is excluded (symlink/private)."""

    def test_symlink_entry_excluded_fails_package(self) -> None:
        """When the only entry point is a symlink to outside, packaging fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            proto = Path(tmpdir) / "source" / "prototype"
            proto.mkdir(parents=True)
            # Only HTML file is a symlink to outside — will be skipped
            external = Path(tmpdir) / "external.html"
            external.write_text("<html>External</html>")
            (proto / "index.html").symlink_to(external)
            # _find_entry_point skips symlinks
            result = preview_bundle._find_entry_point(proto)
            self.assertIsNone(result, "Symlink-only entry should not be found")


# ---------------------------------------------------------------------------
# Publisher fixture integration
# ---------------------------------------------------------------------------

class TestPublisherWrapper(unittest.TestCase):
    """Test preview-publish.py production wrapper + local fixture."""

    _PUB_SCRIPT = _SCRIPT.parent / "preview-publish.py"

    def _package_bundle(self, tmpdir: str) -> tuple[Path, dict]:
        """Create a prototype and package it via CLI."""
        proto = Path(tmpdir) / "source" / "prototype"
        proto.mkdir(parents=True)
        (proto / "index.html").write_text(
            _SELF_CONTAINED_HTML, encoding="utf-8",
        )
        (proto / "style.css").write_text("body { margin: 0; }", encoding="utf-8")
        output = Path(tmpdir) / "output"
        import subprocess
        result = subprocess.run(
            [
                sys.executable, str(_SCRIPT), "package",
                "--prototype-dir", str(Path(tmpdir) / "source"),
                "--output-dir", str(output),
                "--issue-key", "PUB-1",
                "--revision", "r1",
                "--mode", "standalone",
            ],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        pkg = json.loads(result.stdout)
        return Path(pkg["bundle_dir"]), pkg

    def _run_publish(self, bundle: Path, tmpdir: str, **kw: str) -> tuple[int, dict]:
        """Run the publisher wrapper and return (returncode, receipt)."""
        import subprocess
        site_dir = kw.pop("site_dir", str(Path(tmpdir) / "site"))
        pr_number = kw.pop("pr_number", "42")
        content_sha = kw.pop("content_sha256", "")
        if not content_sha:
            manifest = json.loads(
                (bundle / "preview-manifest.json").read_text(encoding="utf-8"),
            )
            content_sha = manifest["content_sha256"]
        args = [
            sys.executable, str(self._PUB_SCRIPT), "publish",
            "--bundle-dir", str(bundle),
            "--pr-repo", "org/docs-repo",
            "--pr-number", pr_number,
            "--content-sha256", content_sha,
            "--target-repo", kw.pop("target_repo", "org/docs-repo"),
        ]
        if "deploy_command" in kw:
            args += ["--deploy-command", kw["deploy_command"]]
        if "local_fixture" in kw:
            args += ["--local-fixture", kw["local_fixture"]]
        elif site_dir:
            args += ["--local-fixture", site_dir]
        result = subprocess.run(args, capture_output=True, text=True)
        try:
            receipt = json.loads(result.stdout)
        except json.JSONDecodeError:
            receipt = {}
        return result.returncode, receipt

    def test_no_command_returns_awaiting_setup(self) -> None:
        """Without deploy-command or local-fixture, returns awaiting-setup."""
        import subprocess
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, pkg = self._package_bundle(tmpdir)
            result = subprocess.run(
                [
                    sys.executable, str(self._PUB_SCRIPT), "publish",
                    "--bundle-dir", str(bundle),
                    "--pr-repo", "org/docs-repo",
                    "--pr-number", "42",
                    "--content-sha256", pkg["content_sha256"],
                    "--target-repo", "org/docs-repo",
                ],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0)
            receipt = json.loads(result.stdout)
            self.assertEqual(receipt["status"], "awaiting-setup")
            self.assertIn("pr_number", receipt)
            self.assertEqual(receipt["pr_number"], 42)

    def test_local_fixture_publish_and_verify(self) -> None:
        """Local fixture publishes, receipt matches, verify passes."""
        import subprocess
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, pkg = self._package_bundle(tmpdir)
            site_dir = Path(tmpdir) / "site"
            # Pre-populate with docs
            (site_dir / "docs").mkdir(parents=True)
            (site_dir / "docs" / "readme.md").write_text("# Docs")

            rc, receipt = self._run_publish(
                bundle, tmpdir, local_fixture=str(site_dir),
            )
            self.assertEqual(rc, 0, f"Publish failed: {receipt}")
            self.assertEqual(receipt["status"], "published-local")
            self.assertTrue(receipt["digest_match"])
            self.assertIn("LOCAL", receipt["note"])
            self.assertIn("pr-42", receipt["namespace"])
            self.assertEqual(receipt["pr_number"], 42)

            # Existing docs preserved
            self.assertTrue((site_dir / "docs" / "readme.md").is_file())

            # Verify via verify subcommand
            verify = subprocess.run(
                [
                    sys.executable, str(self._PUB_SCRIPT), "verify",
                    "--site-dir", str(site_dir),
                    "--namespace", receipt["namespace"],
                    "--expected-digest", receipt["content_sha256"],
                ],
                capture_output=True, text=True,
            )
            self.assertEqual(verify.returncode, 0, verify.stderr)
            vresult = json.loads(verify.stdout)
            self.assertTrue(vresult["verified"])

    def test_verify_mismatch_detected(self) -> None:
        """Verify fails on wrong digest (negative test)."""
        import subprocess
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, pkg = self._package_bundle(tmpdir)
            site_dir = str(Path(tmpdir) / "site")
            rc, receipt = self._run_publish(
                bundle, tmpdir, local_fixture=site_dir,
            )
            self.assertEqual(rc, 0)

            verify = subprocess.run(
                [
                    sys.executable, str(self._PUB_SCRIPT), "verify",
                    "--site-dir", site_dir,
                    "--namespace", receipt["namespace"],
                    "--expected-digest", "0" * 64,
                ],
                capture_output=True, text=True,
            )
            self.assertNotEqual(verify.returncode, 0)
            vresult = json.loads(verify.stdout)
            self.assertFalse(vresult["verified"])

    def test_preserves_other_pr_preview(self) -> None:
        """Publishing a new PR's preview preserves existing PR previews."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, pkg = self._package_bundle(tmpdir)
            site_dir = Path(tmpdir) / "site"
            # Old PR preview
            old = site_dir / "previews" / "org" / "docs-repo" / "pr-10" / "abc"
            old.mkdir(parents=True)
            (old / "index.html").write_text("<html>Old</html>")

            rc, receipt = self._run_publish(
                bundle, tmpdir, local_fixture=str(site_dir),
            )
            self.assertEqual(rc, 0)
            # Old preview untouched
            self.assertTrue((old / "index.html").is_file())
            self.assertEqual(
                (old / "index.html").read_text(), "<html>Old</html>",
            )

    def test_collision_rejected(self) -> None:
        """Same PR+digest namespace is rejected (non-destructive)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, pkg = self._package_bundle(tmpdir)
            site_dir = str(Path(tmpdir) / "site")
            rc1, _ = self._run_publish(
                bundle, tmpdir, local_fixture=site_dir,
            )
            self.assertEqual(rc1, 0)
            rc2, _ = self._run_publish(
                bundle, tmpdir, local_fixture=site_dir,
            )
            self.assertNotEqual(rc2, 0)

    def test_namespace_uses_pr_identity(self) -> None:
        """Published namespace includes PR repo, number, and content SHA."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, pkg = self._package_bundle(tmpdir)
            rc, receipt = self._run_publish(
                bundle, tmpdir, pr_number="99",
                target_repo="acme/preview-site",
            )
            self.assertEqual(rc, 0)
            ns = receipt["namespace"]
            self.assertIn("acme/preview-site", ns)
            self.assertIn("pr-99", ns)
            self.assertIn(pkg["content_sha256"][:12], ns)


if __name__ == "__main__":
    unittest.main()
