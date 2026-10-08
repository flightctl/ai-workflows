"""Tests for compute-hash.py gap_id and content_hash computation."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

# Allow importing the module under test from this directory.
sys.path.insert(0, os.path.dirname(__file__))
from importlib import import_module

compute_hash = import_module("compute-hash")


class TestComputeGapId(unittest.TestCase):
    """Unit tests for gap_id computation."""

    def test_basic_gap_id(self) -> None:
        """Gap ID matches the documented formula."""
        category = "field"
        data_element = "device health score"
        endpoint = "GET /api/v1/devices"
        raw = f"{category}|{data_element}|{endpoint}"
        expected_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        expected = f"field-{expected_hash}"

        result = compute_hash.compute_gap_id(category, data_element, endpoint)
        self.assertEqual(result, expected)

    def test_na_endpoint_default(self) -> None:
        """When endpoint is N/A, the hash is computed with 'N/A'."""
        result = compute_hash.compute_gap_id("data", "fleet count", "N/A")
        self.assertTrue(result.startswith("data-"))
        self.assertEqual(len(result), len("data-") + 12)

    def test_category_slug_lowercased(self) -> None:
        """Category is lowercased and spaces are replaced with hyphens."""
        result = compute_hash.compute_gap_id("Shape Mismatch", "nested tree", "GET /api/v1/tree")
        self.assertTrue(result.startswith("shape-mismatch-"))

    def test_deterministic(self) -> None:
        """Same inputs always produce the same gap_id."""
        args = ("field", "device count", "GET /api/v1/devices")
        self.assertEqual(
            compute_hash.compute_gap_id(*args),
            compute_hash.compute_gap_id(*args),
        )

    def test_different_inputs_differ(self) -> None:
        """Different inputs produce different gap_ids."""
        id1 = compute_hash.compute_gap_id("field", "health", "GET /api/v1/a")
        id2 = compute_hash.compute_gap_id("field", "health", "GET /api/v1/b")
        self.assertNotEqual(id1, id2)


class TestComputeContentHash(unittest.TestCase):
    """Unit tests for content_hash computation."""

    def _make_fields(self, **overrides: str) -> dict[str, str]:
        base = {
            "affected_components": "DeviceList, DeviceDetailPanel",
            "category": "field",
            "current_state": "Endpoint returns devices without health score",
            "prd_requirements": "FR-1",
            "severity": "high",
            "suggested_approach": "Add healthScore to response",
            "title": "Missing device health score",
            "ui_design_section": "ui-design-EDM-1234.md#Component Architecture > DeviceList",
            "ui_need": "data-display: show device health score",
            "whats_missing": "healthScore field not in response",
        }
        base.update(overrides)
        return base

    def test_basic_content_hash(self) -> None:
        """Content hash matches manual SHA-256 of sorted JSON."""
        fields = self._make_fields()
        payload = json.dumps(fields, sort_keys=True, ensure_ascii=False)
        expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        result = compute_hash.compute_content_hash(fields)
        self.assertEqual(result, expected)

    def test_whitespace_trimming(self) -> None:
        """Leading/trailing whitespace is trimmed before hashing."""
        clean = self._make_fields()
        padded = self._make_fields(title="  Missing device health score  ")
        self.assertEqual(
            compute_hash.compute_content_hash(clean),
            compute_hash.compute_content_hash(padded),
        )

    def test_field_order_irrelevant(self) -> None:
        """Field insertion order does not affect the hash (sorted keys)."""
        import collections

        fields_ordered = collections.OrderedDict(
            [("title", "T"), ("category", "C"), ("severity", "S")]
        )
        fields_reversed = collections.OrderedDict(
            [("severity", "S"), ("category", "C"), ("title", "T")]
        )
        self.assertEqual(
            compute_hash.compute_content_hash(dict(fields_ordered)),
            compute_hash.compute_content_hash(dict(fields_reversed)),
        )

    def test_deterministic(self) -> None:
        """Same fields always produce the same hash."""
        fields = self._make_fields()
        self.assertEqual(
            compute_hash.compute_content_hash(fields),
            compute_hash.compute_content_hash(fields),
        )

    def test_content_change_detected(self) -> None:
        """A change to any field produces a different hash."""
        original = self._make_fields()
        modified = self._make_fields(severity="critical")
        self.assertNotEqual(
            compute_hash.compute_content_hash(original),
            compute_hash.compute_content_hash(modified),
        )


class TestCLI(unittest.TestCase):
    """Integration tests for the CLI interface."""

    SCRIPT = os.path.join(os.path.dirname(__file__), "compute-hash.py")

    def _run(self, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, self.SCRIPT, *args],
            capture_output=True,
            text=True,
            input=stdin,
        )

    def test_gap_id_cli(self) -> None:
        r = self._run("gap-id", "--category", "field", "--data-element", "health", "--endpoint", "GET /api/v1/x")
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.stdout.strip().startswith("field-"))

    def test_gap_id_default_endpoint(self) -> None:
        r = self._run("gap-id", "--category", "data", "--data-element", "fleet count")
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.stdout.strip().startswith("data-"))

    def test_content_hash_json_stdin(self) -> None:
        fields = {"title": "T", "category": "C", "severity": "S"}
        r = self._run("content-hash", "--json-stdin", stdin=json.dumps(fields))
        self.assertEqual(r.returncode, 0)
        self.assertEqual(len(r.stdout.strip()), 64)  # SHA-256 hex length

    def test_content_hash_json_file(self) -> None:
        fields = {"title": "T", "category": "C"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(fields, f)
            f.flush()
            path = f.name
        try:
            r = self._run("content-hash", "--json-file", path)
            self.assertEqual(r.returncode, 0)
            self.assertEqual(len(r.stdout.strip()), 64)
        finally:
            os.unlink(path)

    def test_no_command_exits_1(self) -> None:
        r = self._run()
        self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main()
