"""Exercise compatibility-test discovery against temporary package trees."""

import json
from pathlib import Path
import subprocess

import pytest


REPO = Path(__file__).resolve().parents[4]
DISCOVERY = REPO / "integrations/dsh/dev/toolchain/compat-tests.mjs"


def discovered_tests(package: Path) -> list[str]:
    result = subprocess.run([
        "node", "--input-type=module", "--eval",
        "const { discoverCompatTests } = await import(process.argv[1]); "
        "console.log(JSON.stringify(await discoverCompatTests(process.argv[2])));",
        DISCOVERY.as_uri(), str(package),
    ], text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


@pytest.mark.parametrize("include_task_tests", [False, True])
def test_discovers_dev_and_nested_task_tests_with_optional_task_directory(
    tmp_path: Path, include_task_tests: bool,
) -> None:
    expected = [tmp_path / "dev/toolchain/staging.test.ts"]
    if include_task_tests:
        expected.append(tmp_path / "tests/nested/loader.test.ts")
    for file in expected:
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("import 'node:test';\n")
    ignored = tmp_path / "dev/toolchain/build/emitted.test.ts"
    ignored.parent.mkdir()
    ignored.write_text("throw new Error('must not execute build output');\n")
    assert discovered_tests(tmp_path) == sorted(str(file) for file in expected)


def test_a_discovered_task_failure_produces_a_nonzero_node_exit(tmp_path: Path) -> None:
    file = tmp_path / "tests/nested/failure.test.ts"
    marker = tmp_path / "executed"
    file.parent.mkdir(parents=True)
    file.write_text(
        "import { test } from 'node:test';\n"
        "import { writeFileSync } from 'node:fs';\n"
        "test('discovery failure sentinel', () => { "
        f"writeFileSync({json.dumps(str(marker))}, 'executed'); "
        "throw new Error('discovered-sentinel'); });\n"
    )
    result = subprocess.run(
        ["node", "--test", *discovered_tests(tmp_path)], text=True, capture_output=True,
    )
    assert result.returncode != 0
    assert marker.read_text() == "executed"
