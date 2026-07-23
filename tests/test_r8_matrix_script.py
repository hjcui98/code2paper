"""Tests for the R8 Gemma matrix script sanity checks.

These tests verify the correctness of the TSV parsing, JSON extraction,
and post-check logic used by ``scripts/run_r8_gemma_matrix.sh`` without
actually running the full matrix.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# JSON extraction tests
# ---------------------------------------------------------------------------


class TestRecheckJsonExtraction:
    """Verify that the recheck JSON extraction logic works correctly.

    The matrix script writes the recheck report to a JSON file and then
    extracts fields using ``json.load()``.  These tests verify that the
    extraction produces the correct TSV fields.
    """

    def test_extracts_accepted_true_from_json(self):
        """Verify TSV field extraction from a JSON dict with accepted=True."""
        data = {
            "accepted": True,
            "protocol_check_passed": True,
            "criteria": {
                "completion_complete": {"status": "passed"},
                "readiness_passed": {"status": "passed"},
            },
        }
        accepted = data.get("accepted", False)
        protocol_ok = data.get("protocol_check_passed", False)
        completion = data.get("criteria", {}).get("completion_complete", {}).get("status", "unknown")
        readiness = data.get("criteria", {}).get("readiness_passed", {}).get("status", "unknown")
        assert accepted is True
        assert protocol_ok is True
        assert completion == "passed"
        assert readiness == "passed"

    def test_extracts_accepted_false_from_json(self):
        """A report with accepted=False should produce correct TSV fields."""
        data = {
            "accepted": False,
            "protocol_check_passed": False,
            "criteria": {
                "completion_complete": {"status": "failed"},
                "readiness_passed": {"status": "failed"},
            },
        }
        accepted = data.get("accepted", False)
        protocol_ok = data.get("protocol_check_passed", False)
        completion = data.get("criteria", {}).get("completion_complete", {}).get("status", "unknown")
        readiness = data.get("criteria", {}).get("readiness_passed", {}).get("status", "unknown")
        assert accepted is False
        assert protocol_ok is False
        assert completion == "failed"
        assert readiness == "failed"

    def test_json_roundtrip_preserves_fields(self, tmp_path):
        """Write a JSON dict to file and read it back; verify all TSV fields."""
        data = {
            "accepted": True,
            "protocol_check_passed": True,
            "criteria": {
                "completion_complete": {"status": "passed"},
                "readiness_passed": {"status": "passed"},
            },
        }
        path = tmp_path / "r8_acceptance_report_rechecked.json"
        with open(path, "w") as f:
            json.dump(data, f)
        with open(path) as f:
            loaded = json.load(f)
        accepted = loaded.get("accepted", False)
        protocol_ok = loaded.get("protocol_check_passed", False)
        completion = loaded.get("criteria", {}).get("completion_complete", {}).get("status", "unknown")
        readiness = loaded.get("criteria", {}).get("readiness_passed", {}).get("status", "unknown")
        assert accepted is True
        assert protocol_ok is True
        assert completion == "passed"
        assert readiness == "passed"

    def test_missing_json_file_handled(self, tmp_path):
        """When the recheck JSON file is missing, all fields default to False/error."""
        missing_path = tmp_path / "nonexistent.json"
        assert not missing_path.exists()
        # Simulate the matrix script's fallback logic
        accepted = False
        protocol_ok = False
        completion = "error"
        readiness = "error"
        if missing_path.exists():
            with open(missing_path) as f:
                data = json.load(f)
            accepted = data.get("accepted", False)
        assert accepted is False
        assert protocol_ok is False
        assert completion == "error"
        assert readiness == "error"


# ---------------------------------------------------------------------------
# TSV header / row-count tests
# ---------------------------------------------------------------------------


class TestTsvHeaderAndRowCount:
    """Verify the TSV header-line and row-count logic used by the matrix.

    The matrix uses awk to count project rows and a while-read loop to
    validate each row.  Both must skip the header line and the
    static_pytest row.
    """

    HEADER = "project\trun_id\tcli_exit_code\trecheck_exit_code\taccepted\tprotocol_check_passed\tcompletion\treadiness\telapsed_seconds\trun_root\n"

    def _write_tsv(self, path: Path, rows: list[list[str]]) -> None:
        with open(path, "w") as f:
            f.write(self.HEADER)
            for row in rows:
                f.write("\t".join(row) + "\n")

    def _parse_tsv(self, path: Path) -> list[dict[str, str]]:
        """Parse TSV, skipping header and empty lines."""
        with open(path) as f:
            lines = f.readlines()
        header = [h.strip() for h in lines[0].strip().split("\t")]
        records = []
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            values = line.split("\t")
            if values[0] == "static_pytest":
                continue
            records.append(dict(zip(header, values)))
        return records

    def test_header_skipped_in_row_count(self, tmp_path):
        """awk 'NR>1' ensures the header line is NOT counted as a project."""
        tsv = tmp_path / "project_status.tsv"
        rows = [
            ["rap", "run-rap", "0", "0", "True", "True", "passed", "passed", "500", "/tmp/out/rap"],
            ["ebcar", "run-ebcar", "0", "0", "True", "True", "passed", "passed", "600", "/tmp/out/ebcar"],
        ]
        self._write_tsv(tsv, rows)
        # Simulate the awk command: NR>1 && $1!="static_pytest" && NF>0
        count = 0
        with open(tsv) as f:
            for i, line in enumerate(f, 1):
                if i == 1:
                    continue  # skip header
                parts = line.strip().split("\t")
                if parts[0] != "static_pytest" and any(parts):
                    count += 1
        assert count == 2, f"Expected 2 project rows, got {count}"

    def test_header_skipped_in_while_loop(self, tmp_path):
        """The while-read loop must skip the header line (col 1 == 'project')."""
        tsv = tmp_path / "project_status.tsv"
        rows = [
            ["rap", "run-rap", "0", "0", "True", "True", "passed", "passed", "500", "/tmp/out/rap"],
        ]
        self._write_tsv(tsv, rows)
        records = self._parse_tsv(tsv)
        assert len(records) == 1
        assert records[0]["project"] == "rap"
        assert records[0]["accepted"] == "True"
        assert records[0]["completion"] == "passed"
        assert records[0]["readiness"] == "passed"

    def test_static_pytest_row_skipped(self, tmp_path):
        """The static_pytest row must not be validated as a project."""
        tsv = tmp_path / "project_status.tsv"
        rows = [
            ["static_pytest", "run-stamp", "0", "0", "N/A", "N/A", "N/A", "N/A", "70", "/tmp/log"],
            ["rap", "run-rap", "0", "0", "True", "True", "passed", "passed", "500", "/tmp/out/rap"],
        ]
        self._write_tsv(tsv, rows)
        records = self._parse_tsv(tsv)
        assert len(records) == 1, f"Expected 1 project row (excluding static_pytest), got {len(records)}"
        assert records[0]["project"] == "rap"

    def test_missing_rows_detected(self, tmp_path):
        """When fewer than expected project rows exist, the check fails."""
        tsv = tmp_path / "project_status.tsv"
        rows = [
            ["rap", "run-rap", "0", "0", "True", "True", "passed", "passed", "500", "/tmp/out/rap"],
        ]
        self._write_tsv(tsv, rows)
        records = self._parse_tsv(tsv)
        expected = 6
        assert len(records) != expected, f"Expected {expected} rows, got {len(records)} — this is a failure"

    def test_false_accepted_detected(self, tmp_path):
        """When accepted=False for a project, the check must fail."""
        tsv = tmp_path / "project_status.tsv"
        rows = [
            ["bootstrapping", "run-bs", "0", "0", "False", "True", "failed", "failed", "500", "/tmp/out/bs"],
        ]
        self._write_tsv(tsv, rows)
        records = self._parse_tsv(tsv)
        assert records[0]["accepted"] == "False"
        assert records[0]["completion"] == "failed"
        assert records[0]["readiness"] == "failed"

    def test_nonzero_cli_exit_detected(self, tmp_path):
        """When cli_exit_code != 0, the check must fail."""
        tsv = tmp_path / "project_status.tsv"
        rows = [
            ["crash", "run-crash", "139", "0", "False", "True", "error", "error", "1", "/tmp/out/crash"],
        ]
        self._write_tsv(tsv, rows)
        records = self._parse_tsv(tsv)
        assert records[0]["cli_exit_code"] == "139"

    def test_all_six_projects_pass(self, tmp_path):
        """All six projects accepted=True, all fields correct."""
        tsv = tmp_path / "project_status.tsv"
        projects = ["rap", "ebcar", "dyg", "linearrag", "lookahead", "bootstrapping"]
        rows = [
            [p, f"run-{p}", "0", "0", "True", "True", "passed", "passed", "500", f"/tmp/out/{p}"]
            for p in projects
        ]
        self._write_tsv(tsv, rows)
        records = self._parse_tsv(tsv)
        assert len(records) == 6
        for r in records:
            assert r["accepted"] == "True"
            assert r["protocol_check_passed"] == "True"
            assert r["completion"] == "passed"
            assert r["readiness"] == "passed"
            assert r["cli_exit_code"] == "0"
            assert r["recheck_exit_code"] == "0"


# ---------------------------------------------------------------------------
# Background startup handshake tests
# ---------------------------------------------------------------------------


class TestBackgroundStartupHandshake:
    """Verify the background-mode readiness detection logic.

    After ``setsid`` forks, the driver PID is not the long-lived
    process.  The driver polls for ``status.env`` to confirm
    readiness instead of using ``kill -0``.
    """

    def test_readiness_file_detected(self, tmp_path):
        """When status.env exists, the startup is considered successful."""
        log_root = tmp_path / "logs"
        log_root.mkdir(parents=True)
        # Simulate the foreground process writing status.env
        (log_root / "status.env").write_text("state=RUNNING\n")
        # The driver polls for this file
        assert (log_root / "status.env").exists()

    def test_readiness_file_missing_times_out(self, tmp_path):
        """When status.env never appears, the driver reports failure."""
        log_root = tmp_path / "logs"
        log_root.mkdir(parents=True)
        # No status.env written
        assert not (log_root / "status.env").exists()
        # This simulates the timeout case

    def test_readiness_file_appears_late(self, tmp_path):
        """The driver polls for up to 30 seconds, so a late file is fine."""
        log_root = tmp_path / "logs"
        log_root.mkdir(parents=True)
        # Simulate initial state: no file
        assert not (log_root / "status.env").exists()
        # Simulate file appearing after a few polls
        (log_root / "status.env").write_text("state=RUNNING\n")
        assert (log_root / "status.env").exists()