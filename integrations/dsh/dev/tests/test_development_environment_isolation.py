"""AT-B02 negative cases for the isolated development environment.

Run:
    python -m pytest -q integrations/dsh/dev/tests/test_development_environment_isolation.py

The pure-function cases always run; the cases that inspect the real development
root are skipped when `.dsh-dev/` has not been created yet.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))

import dsh_dev as dev  # noqa: E402  (path setup must precede the import)

# The suite entry selects the explicit candidate before any root is inspected.
_CANDIDATE = os.environ.get(dev.CANDIDATE_ENV)
if _CANDIDATE:
    dev.select_candidate(_CANDIDATE)

DEV_ROOT_EXISTS = (dev.DEV_ROOT / "manifest.json").is_file()
requires_dev_root = pytest.mark.skipif(not DEV_ROOT_EXISTS, reason="development root is not set up")


def fake_package(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Build a minimal package + staged install with matching receipts."""
    package = tmp_path / "pkg"
    (package / "src").mkdir(parents=True)
    (package / "lib").mkdir(parents=True)
    (package / "src/index.ts").write_text("export const x = 1;\n")
    (package / "lib/index.js").write_text("export const x = 1;\n")
    (package / "package.json").write_text(json.dumps({
        "name": dev.BUNDLE_NAME, "files": list(dev.STAGE_CONTENT),
    }) + "\n")
    (package / "tsconfig.json").write_text("{}\n")
    receipt = {
        "schema_version": dev.TOOLCHAIN_SCHEMA,
        "package": dev.BUNDLE_NAME,
        "src_present": True,
        "src_inputs": {"src/index.ts": dev.digest_file(package / "src/index.ts")},
        "config_inputs": {
            "package.json": dev.digest_file(package / "package.json"),
            "tsconfig.json": dev.digest_file(package / "tsconfig.json"),
        },
        "outputs": {"lib/index.js": dev.digest_file(package / "lib/index.js")},
        "entry_present": True,
        "patch_present": True,
    }
    dev.write_json(package / "lib/build-receipt.json", receipt)
    staging = tmp_path / "staging"
    (staging / "lib").mkdir(parents=True)
    shutil.copy2(package / "package.json", staging / "package.json")
    shutil.copy2(package / "lib/index.js", staging / "lib/index.js")
    shutil.copy2(package / "lib/build-receipt.json", staging / "lib/build-receipt.json")
    files = {
        rel: {"sha256": dev.digest_file(staging / rel), "size": (staging / rel).stat().st_size}
        for rel in ("package.json", "lib/index.js", "lib/build-receipt.json")
    }
    dev.write_json(tmp_path / "staging.json", {
        "schema_version": 1,
        "bundle": dev.BUNDLE_NAME,
        "staged_path": str(staging),
        "source_package": str(package),
        "build_receipt_sha256": dev.digest_file(package / "lib/build-receipt.json"),
        "src_present": True,
        "entry_present": True,
        "patch_present": True,
        "file_count": len(files),
        "tree_sha256": dev.tree_digest(files),
        "files": files,
    })
    return package, staging, tmp_path / "staging.json"


def use_fake_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    package, staging, staging_receipt = fake_package(tmp_path)
    monkeypatch.setattr(dev, "BUNDLE_PACKAGE", package)
    monkeypatch.setattr(dev, "BUILD_RECEIPT", package / "lib/build-receipt.json")
    monkeypatch.setattr(dev, "BUNDLE_STAGING", staging)
    monkeypatch.setattr(dev, "STAGING_RECEIPT", staging_receipt)
    return package


def test_only_whitelisted_compositions_are_accepted() -> None:
    for composition, bundles in dev.COMPOSITIONS.items():
        dev.validate_composition(composition, list(bundles))
    with pytest.raises(RuntimeError, match="unknown composition"):
        dev.validate_composition("staging", list(dev.COMPOSITIONS["web"]))
    with pytest.raises(RuntimeError, match="requires exactly"):
        dev.validate_composition("web", [*dev.COMPOSITIONS["web"], dev.BUNDLE_NAME])
    with pytest.raises(RuntimeError, match="requires exactly"):
        dev.validate_composition("compat", list(dev.COMPOSITIONS["web"]))
    with pytest.raises(RuntimeError, match="requires exactly"):
        dev.validate_composition("web", list(reversed(dev.COMPOSITIONS["web"])))


def test_a_profile_with_an_unlisted_bundle_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dev, "profile_bundles", lambda composition: ["@deepseek-ai/dsh-base", "some-other-bundle"])
    with pytest.raises(RuntimeError, match="requires exactly"):
        dev.validate_composition("web", dev.profile_bundles("web"))


def test_reserved_ports_are_refused() -> None:
    for port in (0, 3081, 3082, 65535):
        dev.validate_port(port)
    for port in dev.RESERVED_PORTS:
        with pytest.raises(RuntimeError, match="reserved"):
            dev.validate_port(port)
    for port in (-1, 65536):
        with pytest.raises(RuntimeError, match="0..65535"):
            dev.validate_port(port)


def test_api_keys_proxies_and_other_harness_env_are_not_inherited(monkeypatch: pytest.MonkeyPatch) -> None:
    secrets = {
        "DEEPSEEK_API_KEY": "sk-should-not-leak",
        "OPENAI_API_KEY": "sk-should-not-leak",
        "ANTHROPIC_AUTH_TOKEN": "token-should-not-leak",
        "HTTPS_PROXY": "http://proxy.invalid:3128",
        "NODE_OPTIONS": "--require=/tmp/inject.js",
        "NODE_PATH": "/tmp/modules",
        "DSH_SESSION_SECRET": "should-not-leak",
        "PYTHONPATH": "/tmp/leak",
    }
    for key, value in secrets.items():
        monkeypatch.setenv(key, value)
    # Another Harness instance's DSH_HOME must be replaced, never inherited.
    monkeypatch.setenv("DSH_HOME", "/home/someone/.dsh")
    env = dev.child_env("/usr/bin/node")
    for key in secrets:
        assert key not in env, f"{key} must not be inherited by the development instance"
    assert env["DSH_HOME"] == str(dev.DSH_HOME), "DSH_HOME must point at the development home"
    assert env["HOME"] == os.environ["HOME"], "HOME must keep its everyday value"
    assert env["C2P_DSH_RUN_ROOT"] == str(dev.RUN_ROOT)
    assert env["PATH"].startswith("/usr/bin")


def test_bubblewrap_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dev.shutil, "which", lambda name: None if name == "bwrap" else "/usr/bin/node")
    with pytest.raises(RuntimeError, match="bubblewrap is required"):
        dev.require_bwrap()
    if DEV_ROOT_EXISTS:
        with pytest.raises(RuntimeError, match="bubblewrap is required"):
            dev.read_manifest("web")


def test_bundle_drift_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    package = use_fake_root(monkeypatch, tmp_path)
    assert dev.verify_staging()["entry_present"] is True

    (package.parent / "staging/lib/index.js").write_text("export const x = 2;\n")
    with pytest.raises(RuntimeError, match="staged bundle bytes drifted"):
        dev.verify_staging()
    shutil.copy2(package / "lib/index.js", package.parent / "staging/lib/index.js")

    (package / "src/index.ts").write_text("export const x = 3;\n")
    with pytest.raises(RuntimeError, match="sources changed after the last build"):
        dev.verify_staging()

    (package / "src/index.ts").write_text("export const x = 1;\n")
    assert dev.verify_staging()["entry_present"] is True
    (package / "lib/index.js").write_text("export const x = 4;\n")
    with pytest.raises(RuntimeError, match="emitted bundle bytes drifted"):
        dev.verify_staging()


def test_rebuild_after_staging_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    package = use_fake_root(monkeypatch, tmp_path)
    receipt = json.loads((package / "lib/build-receipt.json").read_text())
    receipt["outputs_digest"] = "rebuilt"
    dev.write_json(package / "lib/build-receipt.json", receipt)
    with pytest.raises(RuntimeError, match="rebuilt after staging"):
        dev.verify_staging()


def test_stage_copies_runtime_payload_without_dev_tests_or_dependencies(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    package = use_fake_root(monkeypatch, tmp_path)
    monkeypatch.setattr(dev, "ensure_layout", lambda: None)
    for rel in ("dev/probe.js", "tests/nested/fixture.test.ts", "node_modules/@deepseek-ai/cordis/index.js"):
        file = package / rel
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("must not be staged\n")
    record = dev.stage_bundle()
    assert set(record["files"]) == {"package.json", "lib/index.js", "lib/build-receipt.json"}
    assert dev.verify_staging()["entry_present"] is True


def test_stage_refuses_stale_build_before_replacing_previous_install(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    package = use_fake_root(monkeypatch, tmp_path)
    monkeypatch.setattr(dev, "ensure_layout", lambda: None)
    prior = (dev.BUNDLE_STAGING / "lib/index.js").read_bytes()
    (package / "src/index.ts").write_text("export const x = 99;\n")
    with pytest.raises(RuntimeError, match="sources changed after the last build"):
        dev.stage_bundle()
    assert (dev.BUNDLE_STAGING / "lib/index.js").read_bytes() == prior


def test_bundle_asset_changes_require_a_new_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    package = use_fake_root(monkeypatch, tmp_path)
    (package / "cordis.patch.yml").write_text("[]\n")
    with pytest.raises(RuntimeError, match="assets changed after the last build"):
        dev.verify_build_receipt()


def test_stage_rejects_a_build_interleaved_with_copy_and_preserves_old_install(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    package = use_fake_root(monkeypatch, tmp_path)
    monkeypatch.setattr(dev, "ensure_layout", lambda: None)
    old_stage = (dev.BUNDLE_STAGING / "lib/index.js").read_bytes()
    old_record = dev.STAGING_RECEIPT.read_bytes()
    copy = dev.shutil.copy2

    def interleaved_copy(source, target):
        result = copy(source, target)
        if Path(source) == package / "lib/index.js":
            (package / "src/index.ts").write_text("export const x = 2;\n")
            (package / "lib/index.js").write_text("export const x = 2;\n")
            receipt = dev.read_json(dev.BUILD_RECEIPT)
            receipt["src_inputs"]["src/index.ts"] = dev.digest_file(package / "src/index.ts")
            receipt["outputs"]["lib/index.js"] = dev.digest_file(package / "lib/index.js")
            dev.write_json(dev.BUILD_RECEIPT, receipt)
        return result

    monkeypatch.setattr(dev.shutil, "copy2", interleaved_copy)
    with pytest.raises(RuntimeError, match="build changed during staging"):
        dev.stage_bundle()
    assert (dev.BUNDLE_STAGING / "lib/index.js").read_bytes() == old_stage
    assert dev.STAGING_RECEIPT.read_bytes() == old_record


def test_compat_composition_requires_a_staged_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dev, "verify_staging", lambda: {
        "staged_path": "x", "file_count": 0, "tree_sha256": "0",
        "entry_present": False, "patch_present": False, "src_present": False,
    })
    with pytest.raises(RuntimeError, match="no lib/index.js"):
        dev.require_compat_bundle()
    monkeypatch.setattr(dev, "verify_staging", lambda: {
        "staged_path": "x", "file_count": 0, "tree_sha256": "0",
        "entry_present": True, "patch_present": False, "src_present": True,
    })
    with pytest.raises(RuntimeError, match="no cordis.patch.yml"):
        dev.require_compat_bundle()


@requires_dev_root
def test_frozen_runtime_has_no_development_dependencies() -> None:
    state = dev.toolchain_state()
    assert state["peer_packages_vendored"] is False
    assert not (dev.RUNTIME / "node_modules/typescript").exists()
    assert (dev.BUNDLE_PACKAGE / "node_modules/@deepseek-ai").is_symlink()
    report = dev.verify_original_installation(dev.read_manifest("web"), dev.inventory(dev.RUNTIME))
    assert report["shared_inodes"] == 0
    if report["applicable"]:
        assert report["lock_matches"] is True and report["cli_matches"] is True
    else:
        assert report["hash_compared"] is False
        assert report["write_path"] is False
        assert "everyday installation snapshot" in report["reason"]


@requires_dev_root
def test_run_root_is_inside_the_development_root_and_writable() -> None:
    dev.ensure_layout()
    assert dev.RUN_ROOT.is_dir()
    assert dev.RUN_ROOT.resolve().is_relative_to(dev.DEV)
    assert os.access(dev.RUN_ROOT, os.W_OK)


@requires_dev_root
def test_python_worker_environment_matches_its_lock() -> None:
    state = dev.pyworker_state()
    assert state["packages"] == len(dev.parse_requirements_lock(dev.PYWORKER_LOCK.read_text()))
    assert state["domain_import"] == "code2paper"
    assert Path(state["path"]).resolve() == dev.PYWORKER.resolve()


def test_python_worker_drift_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    if not dev.pyworker_python().is_file():
        pytest.skip("worker environment is not created yet")
    lock = dev.PYWORKER_LOCK.read_text().replace("pydantic==2.12.3", "pydantic==0.0.1")
    drifted = tmp_path / "pyworker-requirements.lock"
    drifted.write_text(lock)
    monkeypatch.setattr(dev, "PYWORKER_LOCK", drifted)
    with pytest.raises(RuntimeError, match="drifted from the lock"):
        dev.pyworker_state()


def test_unpatched_manifests_keep_the_original_format(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Old manifests (the historical default and plain npm candidates) load unchanged.

    The patched-candidate identity fields (`upstream_dsh_version` and friends)
    are required only of patched candidate ids (acceptance LO-3); an unpatched
    manifest must never gain a mandatory new field. Both plain versions load
    with the original field set under a runtime whose package version equals
    the plain candidate version.
    """
    monkeypatch.setattr(dev, "DEV", tmp_path)
    monkeypatch.setattr(dev, "DEV_ROOT", tmp_path)
    for name, rel in [("RUNTIME", "runtime"), ("DSH_HOME", "home"), ("WORKSPACE", "workspace"), ("RUN_ROOT", "run")]:
        monkeypatch.setattr(dev, name, tmp_path / rel)
    for plain in ["0.1.5-rc.3", "0.2.0-rc.1"]:
        monkeypatch.setattr(dev, "VERSION", plain)
        for rel, text in [(dev.CLI_REL, "cli"), (Path("package-lock.json"), "lock"),
                          (Path("node_modules/@deepseek-ai/dsh/package.json"), json.dumps({"version": plain})),
                          (Path("node_modules/other/lib.js"), "original")]:
            file = dev.RUNTIME / rel
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text)
        profile_dir = dev.DSH_HOME / "profiles" / "code2paper-dev"
        profile_dir.mkdir(parents=True, exist_ok=True)
        (profile_dir / "package.json").write_text(json.dumps({
            "dsh": {"profile": {"bundles": ["@deepseek-ai/dsh-base", "@deepseek-ai/dsh-web-app"]}},
        }))
        bundle_dir = dev.DSH_HOME / "profiles" / "node_modules" / "@code2paper" / "dsh-bundle"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        (bundle_dir / "package.json").write_text(json.dumps({"name": "@code2paper/dsh-bundle"}))
        node = shutil.which("node")
        assert node is not None
        node_version = subprocess.check_output([node, "--version"], text=True).strip()
        dev.write_json(tmp_path / "manifest.json", {
            "dsh_version": plain,
            "node": node,
            "node_version": node_version,
            "package_lock_sha256": dev.digest_file(dev.RUNTIME / "package-lock.json"),
            "cli_sha256": dev.digest_file(dev.RUNTIME / dev.CLI_REL),
            "runtime_tree_sha256": dev.tree_digest(dev.inventory(dev.RUNTIME)),
        })
        loaded = dev.read_manifest("web")
        assert loaded["dsh_version"] == plain


def test_non_cli_runtime_drift_is_refused_before_launch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(dev, "DEV", tmp_path)
    monkeypatch.setattr(dev, "DEV_ROOT", tmp_path)
    for name, rel in [("RUNTIME", "runtime"), ("DSH_HOME", "home"), ("WORKSPACE", "workspace"), ("RUN_ROOT", "run")]:
        monkeypatch.setattr(dev, name, tmp_path / rel)
    for rel, text in [(dev.CLI_REL, "cli"), (Path("package-lock.json"), "lock"),
                      (Path("node_modules/@deepseek-ai/dsh/package.json"),
                       json.dumps({"version": dev.upstream_version(dev.VERSION)})),
                      (Path("node_modules/other/lib.js"), "original")]:
        file = dev.RUNTIME / rel
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)
    dev.write_json(tmp_path / "manifest.json", {
        "dsh_version": dev.VERSION,
        "upstream_dsh_version": dev.upstream_version(dev.VERSION),
        "package_lock_sha256": dev.digest_file(dev.RUNTIME / "package-lock.json"),
        "cli_sha256": dev.digest_file(dev.RUNTIME / dev.CLI_REL),
        "runtime_tree_sha256": dev.tree_digest(dev.inventory(dev.RUNTIME)),
    })
    (dev.RUNTIME / "node_modules/other/lib.js").write_text("drift")
    with pytest.raises(RuntimeError, match="runtime bytes drifted"):
        dev.read_manifest("web")


def test_worker_install_uses_scrubbed_env_and_sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for key in ["PIP_TARGET", "PIP_PREFIX", "PIP_CONFIG_FILE", "PYTHONPATH", "PYTHONHOME", "OPENAI_API_KEY", "HTTPS_PROXY"]:
        monkeypatch.setenv(key, "b02-synthetic-marker")
    monkeypatch.setattr(dev, "DEV", tmp_path)
    monkeypatch.setattr(dev, "DEV_ROOT", tmp_path)
    monkeypatch.setattr(dev, "PYWORKER", tmp_path / "worker")
    monkeypatch.setattr(dev, "ensure_layout", lambda: None)
    monkeypatch.setattr(dev, "read_manifest", lambda _: {"node": "/usr/bin/node"})
    monkeypatch.setattr(dev, "pyworker_state", lambda: {"fixture": True})
    calls = []
    monkeypatch.setattr(dev.subprocess, "run", lambda argv, **kwargs: calls.append((argv, kwargs)))
    assert dev.pyworker_setup() == {"fixture": True}
    assert len(calls) == 2
    for argv, kwargs in calls:
        assert argv[0] == dev.require_bwrap()
        env = kwargs["env"]
        assert env["HOME"] == os.environ["HOME"]
        assert env["PIP_CONFIG_FILE"] == os.devnull
        assert not any(value == "b02-synthetic-marker" for value in env.values())
        assert ["--ro-bind", str(dev.RUNTIME), str(dev.RUNTIME)] == argv[argv.index(str(dev.RUNTIME)) - 1:argv.index(str(dev.RUNTIME)) + 2]
    install = calls[1][0]
    assert install[install.index("--prefix") + 1] == str(dev.PYWORKER)
    assert "--no-user" in install


@requires_dev_root
def test_cli_chdir_follows_the_selected_workspace() -> None:
    argv = dev.sandbox_command({"node": "/usr/bin/node"}, ["true"])
    assert argv[argv.index("--chdir") + 1] == str(dev.WORKSPACE)


def test_scoped_output_bind_retains_network_isolation_and_rejects_broad_or_linked_paths(tmp_path) -> None:
    root=tmp_path / "task-output";root.mkdir()
    argv=dev.sandbox_command({"node":"/usr/bin/node"},["true"],offline=True,output_root=root)
    assert "--unshare-net" in argv
    profiles=dev.DSH_HOME/'profiles'
    index=argv.index(str(profiles));assert argv[index-1:index+2] == ['--ro-bind',str(profiles),str(profiles)]
    assert index > argv.index(str(dev.DEV_ROOT))
    if dev.PYWORKER.exists():
        index=argv.index(str(dev.PYWORKER));assert argv[index-1] == '--ro-bind'
    index=argv.index(str(root));assert argv[index-1] == "--bind" and argv[index+1] == str(root)
    with pytest.raises(RuntimeError,match="canonical task directory"):
        dev.sandbox_command({},["true"],output_root=Path("/tmp"))
    link=tmp_path / "linked-output";link.symlink_to(root,target_is_directory=True)
    with pytest.raises(RuntimeError,match="canonical task directory"):
        dev.sandbox_command({},["true"],output_root=link)


def test_operator_inputs_are_readonly_after_task_bind_and_must_be_canonical(tmp_path):
    task=tmp_path/'task';task.mkdir()
    source=task/'receipt.json';source.write_text('{}')
    argv=dev.sandbox_command({},['true'],offline=True,output_root=task,readonly_inputs=[source])
    writable=argv.index(str(task));readonly=argv.index(str(source))
    assert argv[writable-1] == '--bind' and argv[readonly-1] == '--ro-bind' and readonly>writable
    assert '--unshare-net' in argv
    for invalid in (tmp_path/'missing.json',):
        with pytest.raises(RuntimeError,match='canonical existing file or directory'):
            dev.sandbox_command({},['true'],readonly_inputs=[invalid])
    linked=tmp_path/'linked.json';linked.symlink_to(source)
    with pytest.raises(RuntimeError,match='canonical existing file or directory'):
        dev.sandbox_command({},['true'],readonly_inputs=[linked])
    tree=tmp_path/'frozen-tree';tree.mkdir()
    argv=dev.sandbox_command({},['true'],output_root=task,readonly_inputs=[tree])
    index=argv.index(str(tree));assert argv[index-1] == '--ro-bind'
    for ancestor in (task,tmp_path):
        with pytest.raises(RuntimeError,match='must not contain the writable output'):
            dev.sandbox_command({},['true'],output_root=task,readonly_inputs=[ancestor])


def test_offline_runtime_protection_cannot_be_overridden_by_output_bind(monkeypatch,tmp_path):
    home=tmp_path/'home';profiles=home/'profiles';profiles.mkdir(parents=True)
    worker=tmp_path/'worker';worker.mkdir()
    monkeypatch.setattr(dev,'DSH_HOME',home)
    monkeypatch.setattr(dev,'PYWORKER',worker)
    for parent in (profiles,worker):
        output=parent/'output';output.mkdir()
        with pytest.raises(RuntimeError,match='must not contain the writable output'):
            dev.sandbox_command({},['true'],offline=True,output_root=output)
    # Setup/install commands retain their original writable development bind.
    argv=dev.sandbox_command({},['true'],offline=False)
    assert str(profiles) not in argv and str(worker) not in argv
    index=argv.index(str(dev.DEV_ROOT));assert argv[index-1] == '--bind'


def test_qualification_parent_mount_is_narrow_and_precedes_writable_child(tmp_path):
    parent=tmp_path/'proof';parent.mkdir();output=parent/'operator';output.mkdir()
    argv=dev.sandbox_command({},['true'],offline=True,output_root=output,readonly_parent=parent)
    parent_index=argv.index(str(parent));child_index=argv.index(str(output))
    assert argv[parent_index-1] == '--ro-bind' and argv[child_index-1] == '--bind'
    assert parent_index < child_index
    for invalid in (Path('/tmp'),tmp_path,output,tmp_path/'missing'):
        with pytest.raises(RuntimeError,match='canonical /tmp direct parent'):
            dev.validate_qualification_root(invalid,output)
    link=tmp_path/'linked';link.symlink_to(parent,target_is_directory=True)
    with pytest.raises(RuntimeError,match='canonical /tmp direct parent'):
        dev.validate_qualification_root(link,link/'operator')
    with pytest.raises(RuntimeError,match='offline sandbox'):
        dev.sandbox_command({},['true'],output_root=output,readonly_parent=parent)
    # General closure mounts still cannot introduce a writable-descendant escape.
    with pytest.raises(RuntimeError,match='must not contain the writable output'):
        dev.sandbox_command({},['true'],offline=True,output_root=output,readonly_inputs=[parent])


def test_actual_qualification_parent_exposes_later_core_proof_without_writes(tmp_path):
    """Real mount timing only; no certificate or qualification is declared."""
    parent=tmp_path/'managed-proof';parent.mkdir();output=parent/'operator';output.mkdir()
    hidden=tmp_path/'unrelated-proof';hidden.write_text('hidden')
    proof=parent/'later-core-report.json';ready=output/'ready';result=output/'mount-result.json'
    code="""
import errno,json,sys,time
from pathlib import Path
parent,output,hidden=map(Path,sys.argv[1:]);proof=parent/'later-core-report.json'
assert not proof.exists(),'proof must be created after the sandbox starts'
(output/'ready').write_text('ready')
deadline=time.monotonic()+15
while not proof.exists():
    assert time.monotonic()<deadline,'parent never published the core proof'
    time.sleep(.01)
assert proof.read_text()=='parent-created original core report'
for action in (lambda:proof.open('ab'),lambda:proof.unlink(),lambda:(parent/'forbidden').mkdir()):
    try:action()
    except OSError as error:assert error.errno==errno.EROFS,error.errno
    else:raise AssertionError('qualification parent is writable')
assert not hidden.exists(),'unrelated /tmp evidence leaked'
(output/'mount-result.json').write_text(json.dumps({'later_proof_read':True,'parent_readonly':True,'output_writable':True}))
"""
    payload=[str(dev.PYWORKER/'bin/python'),'-c',code,str(parent),str(output),str(hidden)]
    argv=dev.sandbox_command({},payload,cwd=REPO,offline=True,output_root=output,readonly_parent=parent)
    process=subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        deadline=time.monotonic()+15
        while not ready.exists() and process.poll() is None and time.monotonic()<deadline:time.sleep(.01)
        if not ready.exists():
            if process.poll() is None:process.kill()
            stdout,stderr=process.communicate(timeout=5)
            pytest.fail(f'sandbox did not reach the real parent/child mount boundary: {stdout} {stderr}')
        proof.write_text('parent-created original core report')
        stdout,stderr=process.communicate(timeout=20)
        assert process.returncode==0,(stdout,stderr)
        assert json.loads(result.read_text())=={'later_proof_read':True,'parent_readonly':True,'output_writable':True}
        assert proof.read_text()=='parent-created original core report'
        assert not (parent/'forbidden').exists()
    finally:
        if process.poll() is None:process.kill()
        process.communicate(timeout=5)


def test_actual_operator_mounts_protect_inputs_inside_writable_task_root(tmp_path):
    """Physical outer-writer boundary; this does not claim a Writer run."""
    manifest=dev.read_manifest("web")
    task=tmp_path/'operator-mounts';task.mkdir()
    inputs=[task/name for name in ('bootstrap.json','launch.json','receipt.json','report.json','output.log')]
    for source in inputs:source.write_text('frozen operator input')
    # These inputs live outside the writable bind and would disappear under
    # the inner /tmp tmpfs without the explicitly validated closure mounts.
    frozen=tmp_path/'qualified-closure';frozen.mkdir()
    (frozen/'nested').mkdir();(frozen/'nested/dependency.json').write_text('original closure')
    certificate=tmp_path/'external-certificate.json';certificate.write_text('original certificate')
    hidden=tmp_path/'unrelated.json';hidden.write_text('must remain hidden')
    profiles=dev.DSH_HOME/'profiles'
    actual_inputs=[profiles/dev.PROFILE_NAMES['compat']/'package.json',
        profiles/dev.PROFILE_NAMES['compat']/'cordis.patch.yml',
        dev.BUNDLE_STAGING/'lib/cli.js',dev.BUNDLE_STAGING/'lib/kernel-client.js',
        dev.PYWORKER/'pyvenv.cfg']
    assert all(source.is_file() for source in actual_inputs)
    probe=task/'mount-probe.json'
    code="""
import errno,json,os,sys
from pathlib import Path
inputs=json.loads(sys.argv[1]);result={'readonly_inputs':[]}
for name in inputs:
    path=Path(name)
    assert path.read_text() == 'frozen operator input'
    try:
        with path.open('ab') as stream:stream.write(b'forbidden')
    except OSError as error:
        assert error.errno == errno.EROFS, (name,error.errno)
        result['readonly_inputs'].append(name)
    else:raise AssertionError('operator input writable: '+name)
assert not os.access(sys.argv[3],os.W_OK)
assert not os.access(sys.argv[4],os.W_OK)
interfaces=[line.split(':')[0].strip() for line in Path('/proc/net/dev').read_text().splitlines()[2:] if ':' in line]
assert interfaces == ['lo'],interfaces
assert Path(sys.argv[5]).read_text() == 'original certificate'
tree=Path(sys.argv[6]);assert (tree/'nested/dependency.json').read_text() == 'original closure'
for path in (Path(sys.argv[5]),tree/'nested/dependency.json',tree/'new.json'):
    try:path.write_text('forbidden')
    except OSError as error:assert error.errno == errno.EROFS,(str(path),error.errno)
    else:raise AssertionError('external closure writable: '+str(path))
try:(tree/'nested/dependency.json').unlink()
except OSError as error:assert error.errno == errno.EROFS,error.errno
else:raise AssertionError('external closure deletable')
assert not Path(sys.argv[7]).exists(),'unrelated /tmp input leaked'
actual_inputs=json.loads(sys.argv[8]);observed=[]
for name in actual_inputs:
    path=Path(name);assert path.is_file();original=path.read_bytes()
    try:
        with path.open('ab') as stream:stream.write(b'forbidden')
    except OSError as error:assert error.errno == errno.EROFS,(name,error.errno)
    else:raise AssertionError('executed runtime input writable: '+name)
    assert path.read_bytes() == original
    observed.append(name)
unknown=Path(sys.argv[9])/'review035-unregistered-profile-file'
assert not unknown.exists()
try:unknown.write_text('forbidden unregistered module')
except OSError as error:assert error.errno == errno.EROFS,error.errno
else:raise AssertionError('unregistered profile file can be created')
result.update(runtime_readonly=True,source_readonly=True,interfaces=interfaces,executed_inputs_readonly=observed)
Path(sys.argv[2]).write_text(json.dumps(result))
"""
    payload=[str(dev.DEV_ROOT/'pyworker/bin/python'),'-c',code,json.dumps([str(p) for p in inputs]),
        str(probe),str(dev.RUNTIME),str(REPO),str(certificate),str(frozen),str(hidden),
        json.dumps([str(source) for source in actual_inputs]),str(profiles)]
    argv=dev.sandbox_command(manifest,payload,cwd=REPO,offline=True,output_root=task,readonly_inputs=[*inputs,certificate,frozen])
    ran=subprocess.run(argv,env=dev.child_env(manifest['node']),capture_output=True,text=True,timeout=30)
    assert ran.returncode == 0,ran.stderr
    observed=json.loads(probe.read_text())
    assert observed['readonly_inputs'] == [str(p) for p in inputs]
    assert observed['runtime_readonly'] and observed['source_readonly'] and observed['interfaces'] == ['lo']
    assert observed['executed_inputs_readonly'] == [str(source) for source in actual_inputs]
    assert all(p.read_text() == 'frozen operator input' for p in inputs)
    assert certificate.read_text() == 'original certificate'
    assert (frozen/'nested/dependency.json').read_text() == 'original closure'


def test_actual_app_sandbox_keeps_runtime_readonly_and_run_root_writable() -> None:
    manifest = dev.read_manifest("web")
    result = dev.sandbox_probes(manifest)
    assert result["runtime_read_only"] and result["runtime_js_read_only"] and result["run_root_writable"]


def test_smoke_candidate_selection_and_evidence_routing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """AT-B02/D3: smoke launcher honors candidate selection, enforces agreement, routes evidence."""
    import dsh_dev_smoke as smoke
    # Positive checks use the complete plan's current staging. Negative flag
    # conflicts below deliberately change the environment independently.
    candidate_id = os.environ.get(dev.CANDIDATE_ENV, "0.2.0-rc.1+loop-origin.1")

    # Category 3: flag and env conflict -> refuse
    monkeypatch.delenv("C2P_DSH_DEV_ROOT", raising=False)
    monkeypatch.setenv(dev.CANDIDATE_ENV, "0.2.0-rc.1+loop-origin.1")
    monkeypatch.setattr(sys, "argv", ["dsh_dev_smoke.py", "--candidate", "0.2.0-rc.1"])
    with pytest.raises(RuntimeError, match="candidate mismatch"):
        smoke.main()

    # Category 4: missing / invalid candidate -> refuse
    monkeypatch.delenv(dev.CANDIDATE_ENV, raising=False)
    monkeypatch.delenv("C2P_DSH_DEV_ROOT", raising=False)
    monkeypatch.setattr(sys, "argv", ["dsh_dev_smoke.py", "--candidate", "non-existent-candidate"])
    with pytest.raises(RuntimeError, match="candidate root missing"):
        smoke.main()

    # Category 1 & 2: valid candidate selection (flag or env)
    cand_root = dev.CANDIDATE_ROOT / candidate_id
    if cand_root.is_dir():
        default_evidence = dev.DEV / "evidence"
        before_default = {p.name: p.read_bytes() for p in default_evidence.glob("*smoke*") if p.is_file()}
        candidate_evidence = tmp_path / "candidate-default-evidence"
        real_select = dev.select_candidate
        def selected(version):
            real_select(version)
            monkeypatch.setattr(dev, "EVIDENCE_DIR", candidate_evidence)
        monkeypatch.setattr(dev, "select_candidate", selected)
        launches = []
        launch_envs = []

        class DummyProc:
            stdout = ["dsh web: http://127.0.0.1:9999/\n"]
            returncode = 0
            def poll(self): return 0
            def terminate(self): pass
            def wait(self, timeout=None): pass
            def kill(self): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass

        real_popen = subprocess.Popen

        def fake_popen(cmd, *args, **kwargs):
            if any("dsh" in str(c) for c in (cmd if isinstance(cmd, (list, tuple)) else [cmd])):
                launches.append(cmd)
                launch_envs.append(kwargs["env"])
                return DummyProc()
            return real_popen(cmd, *args, **kwargs)

        class DummyResponse:
            status = 200
            def read(self): return b'<html><head><script src="app.js"></script></head><body>ok</body></html>'
            def __enter__(self): return self
            def __exit__(self, *args): pass

        class DummyOpener:
            def open(self, *args, **kwargs): return DummyResponse()

        monkeypatch.setattr(smoke.urllib.request, "build_opener", lambda *args, **kwargs: DummyOpener())
        monkeypatch.setattr(smoke.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(smoke.socket, "socket", lambda *args, **kwargs: type("DummySocket", (), {
            "__enter__": lambda self: self,
            "__exit__": lambda self, *args: None,
            "settimeout": lambda self, t: None,
            "connect_ex": lambda self, addr: 1,
        })())

        custom_evidence = tmp_path / "smoke_ev"
        monkeypatch.setattr(sys, "argv", [
            "dsh_dev_smoke.py", "--candidate", candidate_id, "--evidence-dir", str(custom_evidence)
        ])
        ret = smoke.main()
        assert ret == 0
        assert (custom_evidence / "web-smoke.json").is_file()
        obj = json.loads((custom_evidence / "web-smoke.json").read_text())
        record = dev.read_json(dev.STAGING_RECEIPT)
        assert obj["candidate"] == candidate_id
        assert obj["runtime_tree_sha256"] == dev.read_json(cand_root / "manifest.json")["runtime_tree_sha256"]
        assert obj["staging_tree_sha256"] == record["tree_sha256"]
        assert obj["staged_build_receipt_sha256"] == record["build_receipt_sha256"]
        assert obj["passed"]
        assert str(cand_root / "runtime" / dev.CLI_REL) in launches[-1]
        assert launch_envs[-1]["DSH_HOME"] == str(cand_root / "home")
        # Environment-only selection uses the candidate's default evidence path.
        monkeypatch.setenv(dev.CANDIDATE_ENV, candidate_id)
        monkeypatch.setattr(sys, "argv", ["dsh_dev_smoke.py", "--composition", "compat"])
        assert smoke.main() == 0
        actual = json.loads((candidate_evidence / "compat-smoke.json").read_text())
        assert actual["candidate"] == candidate_id
        assert actual["staging_tree_sha256"] == record["tree_sha256"]
        assert actual["staged_build_receipt_sha256"] == record["build_receipt_sha256"]
        assert actual["composition"] == "compat"
        assert str(cand_root / "runtime" / dev.CLI_REL) in launches[-1]
        assert before_default == {p.name: p.read_bytes() for p in default_evidence.glob("*smoke*") if p.is_file()}


        # No selection preserves the historical web entry and explicitly uses
        # runtime-only scope when that environment has no current staged bundle.
        import importlib.util
        spec = importlib.util.spec_from_file_location("default_smoke_dev", REPO / "scripts/dsh_dev.py")
        historical = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(historical)
        monkeypatch.setattr(smoke, "dev", historical)
        monkeypatch.setattr(historical, "STAGING_RECEIPT", tmp_path / "absent-stage.json")
        monkeypatch.setattr(historical, "EVIDENCE_DIR", tmp_path / "historical-default-evidence")
        monkeypatch.delenv(dev.CANDIDATE_ENV, raising=False)
        monkeypatch.setattr(sys, "argv", ["dsh_dev_smoke.py"])
        assert smoke.main() == 0
        actual = json.loads((historical.EVIDENCE_DIR / "web-smoke.json").read_text())
        assert actual["candidate"] is None
        assert actual["staging_proof_scope"] == "web_runtime_only"
        assert str(historical.RUNTIME / historical.CLI_REL) in launches[-1]
        assert launch_envs[-1]["DSH_HOME"] == str(historical.DSH_HOME)


def test_node_machine_report_route_requires_fresh_scoped_file(monkeypatch, tmp_path):
    calls=[]
    def sandbox(manifest,payload,**kwargs):
        calls.append((payload,kwargs))
        return payload
    monkeypatch.setattr(dev,'sandbox_command',sandbox)
    root=tmp_path/'output';root.mkdir()
    report=root/'node-events.jsonl'
    test=str(dev.BUNDLE_PACKAGE/'tests/host.test.ts')
    closure=tmp_path/'closure';closure.mkdir()
    argv=dev.test_command({'node':'/usr/bin/node'},[test],output_root=root,report_path=report,
        readonly_inputs=[closure],readonly_parent=tmp_path)
    assert '--test-reporter-destination='+str(report) in argv
    assert '--test-reporter=spec' in argv
    assert calls[0][1]['offline'] is True
    assert calls[0][1]['output_root'] == root
    assert calls[0][1]['readonly_inputs'] == [closure]
    assert calls[0][1]['readonly_parent'] == tmp_path
    with pytest.raises(RuntimeError,match='machine report'):
        dev.test_command({'node':'/usr/bin/node'},[test],report_path=report)
    with pytest.raises(RuntimeError,match='machine report'):
        dev.test_command({'node':'/usr/bin/node'},[test],output_root=root,report_path=tmp_path/'outside.jsonl')
    report.write_text('old report')
    with pytest.raises(RuntimeError,match='machine report'):
        dev.test_command({'node':'/usr/bin/node'},[test],output_root=root,report_path=report)


def test_writer_parent_transports_frozen_python_without_granting_target_admission(monkeypatch,tmp_path):
    """UNIT launch routing only; no certificate or execution succeeds here."""
    from types import SimpleNamespace
    from code2paper.integrations.dsh import offline_inputs,host_admission,target_admission
    from code2paper.agentic import authoring_execution_identity
    task=tmp_path/'target';task.mkdir()
    output=task/'output';bootstrap=task/'bootstrap.json';launch=task/'launch.json'
    bootstrap.write_text(json.dumps({'artifact_root':str(task/'run'),'composition':{}}))
    launch.write_text('{}')
    frozen_python=task/'python-worker-guard';frozen_python.write_text('UNIT frozen launcher')
    config=task/'config.yml';config.write_text('UNIT config')
    receipt=tmp_path/'receipt.json';receipt.write_text('UNIT coverage boundary, never a passed certificate')
    closure=tmp_path/'qualified-run';closure.mkdir()
    calls=[]
    def coverage(path,**kwargs):
        calls.append(('coverage',path,kwargs))
        assert not output.exists()
        return {},[receipt,closure]
    def forbidden(*args,**kwargs):pytest.fail('parent must not grant fresh-target admission')
    monkeypatch.setattr(offline_inputs,'coverage_readonly_inputs',coverage)
    monkeypatch.setattr(host_admission,'validate_host_admission',forbidden)
    monkeypatch.setattr(target_admission,'validate_target_admission',forbidden)
    spec=SimpleNamespace(files={'test_worker_launcher':frozen_python,'config':config},trees={})
    monkeypatch.setattr(host_admission,'_bootstrap_spec',lambda *args:spec)
    monkeypatch.setattr(authoring_execution_identity,'validate_execution_composition',lambda *args,**kwargs:{})
    monkeypatch.setattr(target_admission,'_launch',lambda *args:({},b'{}'))
    monkeypatch.setattr(dev,'assert_selection_agreement',lambda *args:None)
    monkeypatch.setattr(dev,'select_candidate',lambda *args,**kwargs:None)
    monkeypatch.setattr(dev,'CANDIDATE','unit-candidate')
    monkeypatch.setattr(dev,'require_candidate_ready',lambda *args:None)
    monkeypatch.setattr(dev,'read_manifest',lambda *args:{'node':'/unit/node'})
    monkeypatch.setattr(dev,'verify_staging',lambda:None)
    monkeypatch.setattr(dev,'toolchain_state',lambda:None)
    monkeypatch.setattr(dev,'child_env',lambda *args:{})
    def sandbox(manifest,payload,**kwargs):
        calls.append(('sandbox',payload,kwargs));return ['/unit/bwrap',*payload]
    monkeypatch.setattr(dev,'sandbox_command',sandbox)
    class LaunchIntercepted(Exception):pass
    def execute(*args):raise LaunchIntercepted()
    monkeypatch.setattr(dev.os,'execve',execute)
    monkeypatch.setattr(sys,'argv',['dsh_dev.py','--candidate','unit-candidate','writer','--experimental-dsh',
        '--task-root',str(task),'--output-root',str(output),'--bootstrap',str(bootstrap),
        '--launch-file',str(launch),'--offline-receipt',str(receipt)])
    with pytest.raises(LaunchIntercepted):dev.main()
    payload,bindings=calls[-1][1:]
    assert payload[payload.index('--python')+1] == str(frozen_python)
    assert payload[2:4] == ['run','--experimental-dsh']
    assert bindings['offline'] is True and bindings['output_root'] == task
    assert set(bindings['readonly_inputs']) == {receipt,closure,bootstrap,launch,frozen_python,config}
    assert calls[0][0] == 'coverage' and output.is_dir()
