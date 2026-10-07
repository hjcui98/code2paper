#!/usr/bin/env python3
"""Bootstrap, verify, and run the isolated DSH development instance (no live LLM).

The everyday DSH installation, its home, and this repository's business code are
read-only inputs. Everything this tool creates lives under `.dsh-dev/`, which is
Git-ignored, or under `integrations/dsh/node_modules` (the locked TypeScript
toolchain). Development dependencies are never installed into the frozen runtime
copy.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
DEV = REPO / ".dsh-dev"
RUNTIME = DEV / "runtime"
DSH_HOME = DEV / "home"
WORKSPACE = DEV / "workspace"
RUN_ROOT = DEV / "run"
EVIDENCE_DIR = DEV / "evidence"
POLICY = REPO / "integrations/dsh/dev/offline.patch.yml"
VERSION = "0.1.5-rc.3"
CLI_REL = Path("node_modules/@deepseek-ai/dsh/lib/bin.js")

BUNDLE_PACKAGE = REPO / "integrations/dsh"
BUNDLE_NAME = "@code2paper/dsh-bundle"
BUNDLE_STAGING = DSH_HOME / "profiles/node_modules/@code2paper/dsh-bundle"
BUILD_RECEIPT = BUNDLE_PACKAGE / "lib/build-receipt.json"
STAGING_RECEIPT = DEV / "staging.json"
TOOLCHAIN_RECEIPT = DEV / "toolchain.json"
TOOLCHAIN_SCHEMA = "c2p-dsh-development-toolchain/1"
PYWORKER = DEV / "pyworker"
PYWORKER_LOCK = REPO / "integrations/dsh/dev/pyworker-requirements.lock"
PYWORKER_REQUIREMENTS = ("pydantic", "PyYAML")
STAGE_CONTENT = ("package.json", "lib", "presets", "cordis.patch.yml")
STAGE_SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".pytest_cache", "tests", "dev"}

#: Isolated candidate roots live here; the default development environment keeps
#: using the module-level paths above and is never rewritten by a selection.
CANDIDATE_ROOT = DEV / "candidates"
CANDIDATE_ENV = "C2P_DSH_CANDIDATE"
#: Set by select_candidate(); None means the default (0.1.5) environment.
CANDIDATE: str | None = None
#: Active root for directories this tool creates; the default DEV unless a
#: candidate is selected. Layout/state writes always go through this.
DEV_ROOT = DEV


def upstream_version(candidate_id: str) -> str:
    """The npm package version a candidate id is patched from.

    Candidate ids may carry a local suffix (`0.2.0-rc.1+loop-origin.1`); the
    upstream version and the candidate id are validated separately so a
    patched candidate never pretends to be a different npm release.
    """
    return candidate_id.split("+", 1)[0]


def assert_selection_agreement(explicit: str | None) -> None:
    """Refuse a candidate flag, candidate env, and development root that disagree.

    The npm toolchain and this launcher must name one environment. A development
    root under ``candidates/`` with no version, or a version whose root is a
    different directory, would otherwise stage or test the historical default.
    """
    env_candidate = os.environ.get(CANDIDATE_ENV) or None
    if explicit and env_candidate and explicit != env_candidate:
        raise RuntimeError(
            f"candidate mismatch: --candidate {explicit} but {CANDIDATE_ENV}={env_candidate}",
        )
    selected = explicit or None
    env_root = os.environ.get("C2P_DSH_DEV_ROOT")
    if not env_root:
        return
    root = Path(env_root).resolve()
    if selected:
        expected = (CANDIDATE_ROOT / selected).resolve()
        if root != expected:
            raise RuntimeError(
                f"candidate mismatch: selection {selected} but C2P_DSH_DEV_ROOT={root}",
            )
        return
    if root != DEV.resolve():
        raise RuntimeError(
            f"C2P_DSH_DEV_ROOT={root} is not the default development root and no candidate is selected",
        )


def select_candidate(version: str | None, *, allow_missing: bool = False) -> None:
    """Rebind every derived path to one isolated candidate root.

    The candidate gets its own runtime, home, profile install location, workspace,
    run root, evidence directory, staging/toolchain receipts, worker environment
    and npm cache. Nothing under the default development root or the everyday
    installation is touched, and the historical manifest identity is left alone.
    """
    global CANDIDATE, DEV_ROOT, RUNTIME, DSH_HOME, WORKSPACE, RUN_ROOT, EVIDENCE_DIR
    global BUNDLE_STAGING, STAGING_RECEIPT, TOOLCHAIN_RECEIPT, PYWORKER, VERSION
    if version is None or version == "":
        return
    if version != version.strip() or "/" in version or ".." in version:
        raise RuntimeError(f"invalid candidate version: {version!r}")
    root = CANDIDATE_ROOT / version
    if allow_missing and not root.is_dir():
        # loop-origin-setup creates the root itself; bind the paths now.
        CANDIDATE = version
        VERSION = version
        DEV_ROOT = root
        RUNTIME = root / "runtime"
        DSH_HOME = root / "home"
        WORKSPACE = root / "workspace"
        RUN_ROOT = root / "run"
        EVIDENCE_DIR = root / "evidence"
        BUNDLE_STAGING = DSH_HOME / "profiles/node_modules/@code2paper/dsh-bundle"
        STAGING_RECEIPT = root / "staging.json"
        TOOLCHAIN_RECEIPT = root / "toolchain.json"
        PYWORKER = root / "pyworker"
        return
    require(root.is_dir(), f"candidate root missing: {root} (install it first)")
    CANDIDATE = version
    VERSION = version
    DEV_ROOT = root
    RUNTIME = root / "runtime"
    DSH_HOME = root / "home"
    WORKSPACE = root / "workspace"
    RUN_ROOT = root / "run"
    EVIDENCE_DIR = root / "evidence"
    BUNDLE_STAGING = DSH_HOME / "profiles/node_modules/@code2paper/dsh-bundle"
    STAGING_RECEIPT = root / "staging.json"
    TOOLCHAIN_RECEIPT = root / "toolchain.json"
    PYWORKER = root / "pyworker"


def default_runtime_integrity(verify: bool) -> dict:
    """Report the default runtime's integrity, and never imply it without proof.

    Presence, entry count or mtime are not integrity. The only accepted proof is
    the historical algorithm (`inventory` + `tree_digest`) recomputed and compared
    against the manifest identity, so this stays `not_checked` unless `verify` is
    requested. A missing manifest identity is reported as such rather than being
    silently treated as verified.
    """
    runtime = DEV / "runtime"
    report: dict = {
        "path": str(runtime),
        "present": runtime.is_dir(),
        "selected_as_under_test": str(runtime) == str(RUNTIME),
        "integrity": "not_checked",
        "verified_by": "historical inventory()+tree_digest() vs .dsh-dev/manifest.json",
    }
    manifest_path = DEV / "manifest.json"
    identity = None
    if manifest_path.is_file():
        try:
            identity = json.loads(manifest_path.read_text(encoding="utf-8")).get("runtime_tree_sha256")
        except (OSError, ValueError):
            identity = None
    report["manifest_identity"] = identity
    if not verify:
        return report
    if not runtime.is_dir():
        report["integrity"] = "runtime_missing"
        return report
    if not identity:
        report["integrity"] = "identity_missing"
        return report
    computed = tree_digest(inventory(runtime))
    report["computed_identity"] = computed
    report["integrity"] = "verified" if computed == identity else "drift"
    return report


def link_profile_peers() -> int:
    """Mirror the frozen runtime's packages into the profile install location.

    The staged bundle is installed at ``<home>/profiles/node_modules``; for it to
    resolve DSH/Cordis peers, that directory needs the same package layout the
    runtime has. Every entry is a symlink to the runtime file, so no bytes are
    copied and the runtime stays the single source of truth. Existing entries are
    left alone.
    """
    runtime_modules = RUNTIME / "node_modules"
    require(runtime_modules.is_dir(), f"runtime node_modules missing: {runtime_modules}")
    profiles_modules = DSH_HOME / "profiles/node_modules"
    profiles_modules.mkdir(mode=0o700, parents=True, exist_ok=True)
    created = 0
    for entry in sorted(runtime_modules.iterdir()):
        if entry.name in (".bin", ".package-lock.json"):
            continue
        if entry.is_dir() and entry.name.startswith("@"):
            scope = profiles_modules / entry.name
            scope.mkdir(exist_ok=True)
            for package in sorted(entry.iterdir()):
                link = scope / package.name
                if not link.exists() and not link.is_symlink():
                    link.symlink_to(package)
                    created += 1
            continue
        link = profiles_modules / entry.name
        if not link.exists() and not link.is_symlink():
            link.symlink_to(entry)
            created += 1
    return created


LOOP_ORIGIN_PATCH = REPO / "integrations/dsh/dev/runtime-0.2.0-rc.1/loop-origin/loop-origin.patch.py"
TOOL_CHOICE_CANDIDATE = "0.2.0-rc.1+loop-origin.1+tool-choice.1"
TOOL_CHOICE_PARAMS_CANDIDATE = "0.2.0-rc.1+loop-origin.1+tool-choice.2"
TOOL_CHOICE_CANDIDATES = frozenset({TOOL_CHOICE_CANDIDATE, TOOL_CHOICE_PARAMS_CANDIDATE})
TOOL_CHOICE_PATCH = REPO / "integrations/dsh/dev/runtime-0.2.0-rc.1/tool-choice/tool-choice.patch.py"
TOOL_CHOICE_PARAMS_PATCH = TOOL_CHOICE_PATCH.with_name('native-params.patch.py')
TOOL_CHOICE_TOUCHED = [
    "node_modules/@deepseek-ai/dsh-llm-pi-ai/lib/index.js",
    "node_modules/@deepseek-ai/dsh-llm-pi-ai/lib/types/config.d.ts",
]


LOOP_ORIGIN_TOUCHED = [
    "node_modules/@deepseek-ai/dsh-agent-loop/lib/index.js",
    "node_modules/@deepseek-ai/dsh-agent-loop/lib/types/dispatch-origin.c2p.d.ts",
    "node_modules/@deepseek-ai/dsh-agent-loop/lib/types/index.d.ts",
    "node_modules/@deepseek-ai/dsh-llm/lib/index.js",
    "node_modules/@deepseek-ai/dsh-llm/lib/types/index.d.ts",
]


def verified_pristine_base(expected_identity: str) -> tuple[dict, dict]:
    root = CANDIDATE_ROOT / upstream_version(VERSION)
    require((root / "runtime").is_dir(), "pristine base runtime missing")
    require((root / "manifest.json").is_file(), "pristine base manifest missing")
    manifest = read_json(root / "manifest.json")
    require(manifest.get("source_kind") == "npm-registry-install", "pristine base source identity wrong")
    require(manifest.get("dsh_version") == upstream_version(VERSION), "pristine base version wrong")
    require(bool(expected_identity) and manifest.get("runtime_tree_sha256") == expected_identity,
            "pristine base trusted identity mismatch")
    entries = inventory(root / "runtime")
    require(tree_digest(entries) == expected_identity, "pristine base bytes drifted")
    require(digest_file(root / "runtime/package-lock.json") == manifest.get("package_lock_sha256"),
            "pristine base lock drifted")
    return manifest, entries


def candidate_contract() -> dict:
    name = VERSION if VERSION in TOOL_CHOICE_CANDIDATES else f"{upstream_version(VERSION)}+loop-origin.1"
    path = BUNDLE_PACKAGE / f"compatibility.{name}.json"
    require(path.is_file(), "trusted candidate compatibility input missing")
    return read_json(path)


def expected_runtime_touched() -> list[str]:
    return sorted(LOOP_ORIGIN_TOUCHED + (TOOL_CHOICE_TOUCHED if VERSION in TOOL_CHOICE_CANDIDATES else []))


def activation_inputs() -> dict:
    manifest = read_json(DEV_ROOT / "manifest.json")
    require(manifest.get("dsh_version") == VERSION, "activation candidate identity wrong")
    declared_node = Path(manifest.get("node", ""))
    active_node = shutil.which("node")
    require(active_node is not None and declared_node.is_file(), "activation declared Node executable missing")
    require(digest_file(declared_node) == digest_file(Path(active_node)), "activation declared Node bytes differ")
    require(manifest.get("node_version") == subprocess.check_output([str(declared_node), "--version"], text=True).strip(),
            "activation Node identity wrong")
    entries = inventory(RUNTIME)
    require(bool(entries) and tree_digest(entries) == manifest.get("runtime_tree_sha256"), "activation runtime bytes drifted")
    require(digest_file(RUNTIME / "package-lock.json") == manifest.get("package_lock_sha256"), "activation runtime lock drifted")
    require(read_json(RUNTIME / "node_modules/@deepseek-ai/dsh/package.json").get("version") == upstream_version(VERSION),
            "activation runtime version wrong")
    if "+" in VERSION:
        contract = candidate_contract()["dsh"]
        expected = (contract["patch"]["source"]["build_verification_tree_sha256"]
                    if VERSION.endswith("-built") else contract["runtime_tree_sha256"])
        require(manifest.get("runtime_tree_sha256") == expected, "activation trusted candidate identity mismatch")
    return {"candidate": CANDIDATE, "runtime_tree_sha256": manifest["runtime_tree_sha256"]}


def loop_origin_setup() -> dict:
    """Create the patched loop-origin candidate from the pristine base runtime.

    The base candidate (unpatched 0.2.0-rc.1) is read-only input: its runtime
    identity is verified against its own manifest first, then the tree is
    copied byte-for-byte into the new candidate root and the verified source
    patch is applied. The patched tree gets its own recomputed identity; the
    base and patch identities are recorded in the new manifest.
    """
    require(CANDIDATE is not None, "loop-origin-setup requires --candidate <id>")
    require("+" in VERSION, f"candidate {VERSION!r} is not a patched candidate id")
    require(upstream_version(VERSION) != VERSION, "upstream version must differ from the candidate id")
    patch_script = LOOP_ORIGIN_PATCH
    require(patch_script.is_file(), f"the loop-origin patch script is missing: {patch_script}")
    expected_base = candidate_contract()["dsh"]["base_runtime_tree_sha256"]
    base_manifest, base_entries = verified_pristine_base(expected_base)
    base_runtime = CANDIDATE_ROOT / upstream_version(VERSION) / "runtime"
    require(not DEV_ROOT.exists() or not (DEV_ROOT / "runtime").exists(), f"the candidate root already exists: {DEV_ROOT}")
    DEV_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    shutil.copytree(base_runtime, RUNTIME, symlinks=True)
    require(inventory(RUNTIME) == base_entries, "the copied runtime does not match the base bytes")
    import subprocess
    result = subprocess.run(
        [sys.executable, str(patch_script), str(RUNTIME)],
        text=True, capture_output=True,
    )
    require(result.returncode == 0, f"the loop-origin patch failed: {result.stderr.strip()}")
    if VERSION in TOOL_CHOICE_CANDIDATES:
        extension = candidate_contract()["dsh"]["tool_choice_patch"]
        choice_patch = TOOL_CHOICE_PARAMS_PATCH if VERSION == TOOL_CHOICE_PARAMS_CANDIDATE else TOOL_CHOICE_PATCH
        require(extension["script"] == str(choice_patch.relative_to(REPO)), "tool-choice patch path differs")
        require(digest_file(choice_patch) == extension["script_sha256"], "tool-choice patch source differs")
        if VERSION == TOOL_CHOICE_PARAMS_CANDIDATE:
            require(extension['base_patch_sha256'] == digest_file(TOOL_CHOICE_PATCH), 'tool-choice helper source differs')
        result = subprocess.run([sys.executable, str(choice_patch), str(RUNTIME)], text=True, capture_output=True)
        require(result.returncode == 0, f"the tool-choice patch failed: {result.stderr.strip()}")
    patched_entries = inventory(RUNTIME)
    require(patched_entries != base_entries, "the patched runtime must differ from the base tree")
    touched = sorted(
        path for path in (set(base_entries) | set(patched_entries))
        if base_entries.get(path) != patched_entries.get(path)
    )
    require(
        touched == expected_runtime_touched(),
        f"patched runtime touched unexpected files: {touched!r} != {expected_runtime_touched()!r}",
    )
    require(tree_digest(patched_entries) == candidate_contract()["dsh"]["runtime_tree_sha256"], "patched runtime trusted identity differs")
    for rel in ("agent-loop", "llm"):
        require(
            (RUNTIME / "node_modules/@deepseek-ai" / f"dsh-{rel}" / "lib/index.js").is_file(),
            f"patched runtime missing dsh-{rel}",
        )
    provisioned = provision_candidate()
    manifest = read_json(DEV_ROOT / "manifest.json")
    manifest["base_runtime_tree_sha256"] = base_manifest["runtime_tree_sha256"]
    manifest["patched_runtime_tree_sha256"] = provisioned["runtime_tree_sha256"]
    manifest["loop_origin_patch"] = {
        "script": str(patch_script.relative_to(REPO)),
        "script_sha256": digest_file(patch_script),
        "touched": touched,
    }
    if VERSION in TOOL_CHOICE_CANDIDATES:
        manifest["tool_choice_patch"] = candidate_contract()["dsh"]["tool_choice_patch"]
    write_json(DEV_ROOT / "manifest.json", manifest)
    return {
        "candidate": CANDIDATE,
        "upstream_dsh_version": upstream_version(VERSION),
        "base_runtime_tree_sha256": base_manifest["runtime_tree_sha256"],
        "patched_runtime_tree_sha256": provisioned["runtime_tree_sha256"],
        "patch_script": str(patch_script.relative_to(REPO)),
        "runtime_files": len(patched_entries),
        "profiles": provisioned["profiles"],
    }


def provision_candidate() -> dict:
    """Give one npm-installed candidate its own home, profile rows and manifest.

    The candidate runtime is installed by npm under
    ``.dsh-dev/candidates/<version>/runtime``; this only creates the surrounding
    isolated layout and records the candidate's own identity. It never copies
    everyday settings, credentials or sessions, and never writes the default
    development root or the historical manifest.
    """
    require(CANDIDATE is not None, "provision requires --candidate <version>")
    installed = RUNTIME / "node_modules/@deepseek-ai/dsh/package.json"
    require(installed.is_file(), f"candidate runtime missing: {installed}")
    package = read_json(installed)
    require(
        package.get("version") == upstream_version(VERSION),
        f"candidate runtime is {package.get('version')!r}, expected upstream {upstream_version(VERSION)!r} for candidate {VERSION!r}",
    )
    node = shutil.which("node")
    require(node is not None, "Node is required")
    DEV_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    ensure_layout()
    linked = link_profile_peers()
    entries = inventory(RUNTIME)
    write_json(DEV_ROOT / "runtime-inventory.json", entries)
    manifest_path = DEV_ROOT / "manifest.json"
    if manifest_path.exists():
        manifest = read_json(manifest_path)
    else:
        manifest = {"schema_version": 2, "dsh_version": VERSION, "source_kind": "npm-registry-install"}
    manifest.update({
        "dsh_version": VERSION,
        "upstream_dsh_version": upstream_version(VERSION),
        "source_kind": "local-patched" if "+" in VERSION else "npm-registry-install",
        "runtime_tree_sha256": tree_digest(entries),
        "package_lock_sha256": digest_file(RUNTIME / "package-lock.json"),
        "cli_sha256": digest_file(RUNTIME / CLI_REL),
        "node": node,
        "node_version": subprocess.check_output([node, "--version"], text=True).strip(),
        "profile": PROFILE_NAMES["web"],
        "profiles": dict(PROFILE_NAMES),
        "compositions": {k: list(v) for k, v in COMPOSITIONS.items()},
        "run_root": str(RUN_ROOT),
        "live_enabled": False,
    })
    write_json(manifest_path, manifest)
    return {
        "candidate": CANDIDATE,
        "root": str(DEV_ROOT),
        "runtime_tree_sha256": manifest["runtime_tree_sha256"],
        "profiles": sorted(str(p.name) for p in (DSH_HOME / "profiles").iterdir()),
        "manifest": str(manifest_path),
        "profile_peer_links": linked,
    }


def require_candidate_ready(action: str) -> None:
    """Fail closed when a selected candidate is not provisioned.

    A candidate must never silently fall back to the default development home,
    profile or receipts: that would run one environment's tests against another
    environment's identity.
    """
    if CANDIDATE is None:
        return
    require(
        (RUNTIME / CLI_REL).is_file(),
        f"--candidate {CANDIDATE}: runtime CLI missing at {RUNTIME / CLI_REL}",
    )
    require(
        (DSH_HOME / "profiles").is_dir(),
        f"--candidate {CANDIDATE}: home profile missing at {DSH_HOME / 'profiles'}; "
        f"provision this candidate before '{action}'",
    )


def candidate_status(*, verify_runtime: bool = False) -> dict:
    """Report the selected environment without mutating anything."""
    installed = RUNTIME / "node_modules/@deepseek-ai/dsh/package.json"
    version = None
    if installed.is_file():
        version = json.loads(installed.read_text(encoding="utf-8")).get("version")
    return {
        "candidate": CANDIDATE,
        "expected_version": upstream_version(VERSION),
        "candidate_id": VERSION,
        "upstream_version": upstream_version(VERSION),
        "runtime": str(RUNTIME),
        "runtime_present": RUNTIME.is_dir(),
        "installed_version": version,
        "version_matches": version == VERSION,
        "cli": str(RUNTIME / CLI_REL),
        "cli_present": (RUNTIME / CLI_REL).is_file(),
        "home": str(DSH_HOME),
        "home_present": DSH_HOME.is_dir(),
        "profile": str(DSH_HOME / "profiles"),
        "profile_present": (DSH_HOME / "profiles").is_dir(),
        "workspace": str(WORKSPACE),
        "run_root": str(RUN_ROOT),
        "staging_receipt": str(STAGING_RECEIPT),
        "staging_receipt_present": STAGING_RECEIPT.is_file(),
        "default_runtime": default_runtime_integrity(verify_runtime),
    }

# Fixed composition whitelist. A profile whose bundle list is not exactly one of
# these rows is refused; the compat row additionally requires a staged bundle.
COMPOSITIONS = {
    "web": ("@deepseek-ai/dsh-base", "@deepseek-ai/dsh-web-app"),
    "compat": ("@deepseek-ai/dsh-base", "@deepseek-ai/dsh-web-app", BUNDLE_NAME),
}
PROFILE_NAMES = {"web": "code2paper-dev", "compat": "code2paper-dev-compat"}
RESERVED_PORTS = (3080, 19387, 8006)
SENSITIVE_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL", "PROXY", "AUTH")
INHERITED_ENV = ("HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TERM", "TZ")
OWN_DSH_ENV = ("DSH_HOME", "DSH_TELEMETRY_DISABLED")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def digest_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inventory(root: Path) -> dict[str, dict[str, str | int]]:
    """Use the shared inventory; preserve the development manifest wire."""
    import importlib.util
    source = REPO / "src/code2paper/integrations/dsh/runtime_inventory.py"
    spec = importlib.util.spec_from_file_location("c2p_runtime_inventory", source)
    require(spec is not None and spec.loader is not None, "inventory source unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    runtime_inventory = module.runtime_inventory
    try:
        return runtime_inventory(root)
    except (ValueError, OSError) as error:
        raise RuntimeError(str(error)) from error


def tree_digest(entries: dict) -> str:
    raw = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def safe_dev_root() -> None:
    require(DEV_ROOT.resolve() == DEV_ROOT, f"development root cannot be a symlink: {DEV_ROOT}")
    require(DEV_ROOT != Path.home() / ".dsh", "development and everyday homes overlap")
    for path in (RUNTIME, DSH_HOME, WORKSPACE, RUN_ROOT, DEV_ROOT / "tmp", DEV_ROOT / "cache",
                 DEV_ROOT / "config", DEV_ROOT / "data"):
        require(path.resolve().is_relative_to(DEV_ROOT), f"path escapes development root: {path}")


def ensure_layout() -> None:
    """Create missing development directories and profile rows; never overwrite."""
    safe_dev_root()
    for rel in ("home", "workspace", "tmp", "cache", "config", "data", "evidence", "run", "cache/npm", "cache/pip"):
        path = DEV_ROOT / rel
        if not path.exists():
            path.mkdir(mode=0o700, parents=True)
    npmrc = DEV_ROOT / "config/npmrc"
    if not npmrc.exists():
        npmrc.write_text("audit=false\nfund=false\n")
    for composition in COMPOSITIONS:
        profile = DSH_HOME / "profiles" / PROFILE_NAMES[composition]
        if not profile.exists():
            profile.mkdir(parents=True)
        package = profile / "package.json"
        if not package.exists():
            write_json(package, {
                "name": f"code2paper-dsh-development-profile-{composition}", "private": True,
                "dsh": {"profile": {"bundles": list(COMPOSITIONS[composition]), "patchReload": "startup"}},
            })
        patch = profile / "cordis.patch.yml"
        if not patch.exists():
            patch.write_text("[]\n")
        # The runtime composes the tree from the bundle list plus patch files;
        # this root config starts empty (the shipped initial content).
        cordis = profile / "cordis.yml"
        if not cordis.exists():
            cordis.write_bytes(
                b"# dsh profile root \xe2\x80\x94 an empty entry list. The tree is composed as patches:\n"
                b"# each bundle in package.json's dsh.profile.bundles, then cordis.patch.yml, then any\n"
                b"# --patch overlays. Edit cordis.patch.yml, not this file.\n"
                b"[]\n"
            )


def validate_composition(name: str, bundles) -> None:
    require(name in COMPOSITIONS, f"unknown composition {name!r}; allowed {sorted(COMPOSITIONS)}")
    expected = list(COMPOSITIONS[name])
    require(
        list(bundles) == expected,
        f"composition {name!r} requires exactly {expected}; found {list(bundles)}",
    )


def validate_port(port: int) -> None:
    require(0 <= port <= 65535, "choose a development port within 0..65535 (0 selects a free port)")
    require(
        port not in RESERVED_PORTS,
        f"port {port} is reserved for the everyday instances ({', '.join(str(p) for p in RESERVED_PORTS)})",
    )


def child_env(node: str) -> dict[str, str]:
    # Do not repurpose HOME. Inherit only innocuous launch variables, never API
    # keys, proxies, NODE_OPTIONS/NODE_PATH, or another Harness's DSH_* values.
    env = {key: os.environ[key] for key in INHERITED_ENV if key in os.environ}
    # Propagate the selected development root so npm/toolchain children resolve
    # the same manifest, receipts, caches and frozen peers this launcher selected.
    env["C2P_DSH_DEV_ROOT"] = str(DEV_ROOT)
    env.update({
        "PATH": f"{Path(node).parent}:/usr/bin:/bin",
        "DSH_HOME": str(DSH_HOME),
        "DSH_TELEMETRY_DISABLED": "1",
        "TMPDIR": str(DEV_ROOT / "tmp"),
        "XDG_CACHE_HOME": str(DEV_ROOT / "cache"),
        "XDG_CONFIG_HOME": str(DEV_ROOT / "config"),
        "XDG_DATA_HOME": str(DEV_ROOT / "data"),
        "npm_config_cache": str(DEV_ROOT / "cache/npm"),
        "npm_config_userconfig": str(DEV_ROOT / "config/npmrc"),
        "C2P_DSH_RUN_ROOT": str(RUN_ROOT),
    })
    if CANDIDATE is not None:
        env["C2P_DSH_CANDIDATE"] = CANDIDATE
    for key in env:
        require(not any(marker in key.upper() for marker in SENSITIVE_MARKERS), f"refusing to inherit {key}")
        require(not key.startswith("DSH_") or key in OWN_DSH_ENV, f"refusing to inherit another instance's {key}")
    require(env.get("HOME") == os.environ.get("HOME"), "HOME must not be repurposed for the development instance")
    return env


def require_bwrap() -> str:
    bwrap = shutil.which("bwrap")
    require(bwrap is not None, "bubblewrap is required; no unconfined fallback")
    return bwrap


def profile_bundles(composition: str) -> list[str]:
    profile = DSH_HOME / "profiles" / PROFILE_NAMES[composition] / "package.json"
    require(profile.is_file(), f"profile {PROFILE_NAMES[composition]} is missing; run setup")
    return read_json(profile)["dsh"]["profile"]["bundles"]


def read_manifest(composition: str = "web") -> dict:
    require(composition in COMPOSITIONS, f"unknown composition {composition!r}; allowed {sorted(COMPOSITIONS)}")
    safe_dev_root()
    manifest_path = DEV_ROOT / "manifest.json"
    require(manifest_path.is_file(), f"run setup first (no manifest at {manifest_path})")
    manifest = read_json(manifest_path)
    require(manifest["dsh_version"] == VERSION, "unexpected DSH version")
    patched = upstream_version(VERSION) != VERSION
    actual = read_json(RUNTIME / "node_modules/@deepseek-ai/dsh/package.json")
    if patched:
        # A patched candidate carries its own identity fields; the frozen tree
        # itself keeps the upstream package version.
        require(
            manifest.get("upstream_dsh_version") == upstream_version(VERSION),
            f"manifest upstream version {manifest.get('upstream_dsh_version')!r} does not match candidate {VERSION!r}",
        )
        require(actual["version"] == upstream_version(VERSION), "runtime version drift")
    else:
        # Unpatched manifests (the historical default and plain npm candidates)
        # keep their original format: no new fields are required of them.
        require(actual["version"] == VERSION, "runtime version drift")
    require(digest_file(RUNTIME / "package-lock.json") == manifest["package_lock_sha256"], "runtime lock drift")
    require(digest_file(RUNTIME / CLI_REL) == manifest["cli_sha256"], "runtime CLI drift")
    require(tree_digest(inventory(RUNTIME)) == manifest["runtime_tree_sha256"], "runtime bytes drifted")
    require_bwrap()
    node_version = subprocess.check_output([manifest["node"], "--version"], text=True).strip()
    require(node_version == manifest["node_version"], "Node version changed; revalidate the development runtime")
    validate_composition(composition, profile_bundles(composition))
    return manifest


def validate_readonly_inputs(inputs: list[Path], *, output_root: Path | None = None) -> list[Path]:
    """Validate physical mounts without sealing the owned writable output."""
    result=sorted(set(inputs))
    for source in result:
        require(source.is_absolute() and source.resolve() == source and (source.is_file() or source.is_dir()),
                "operator input must be a canonical existing file or directory")
        require(output_root is None or not source.is_dir() or not output_root.is_relative_to(source),
                "operator readonly directory must not contain the writable output root")
    return result


def validate_qualification_root(parent: Path, output_root: Path | None) -> None:
    require(parent.is_absolute() and parent.resolve() == parent and parent.is_dir()
            and parent.is_relative_to(Path('/tmp')) and parent != Path('/tmp')
            and output_root is not None and output_root.is_absolute() and output_root.resolve() == output_root
            and output_root.parent == parent,
            'qualification root must be the canonical /tmp direct parent of the operator output')


def sandbox_command(manifest: dict, payload: list[str], *, cwd: Path | None = None, offline: bool = False,
                    output_root: Path | None = None, readonly_inputs: list[Path] | None = None,
                    readonly_parent: Path | None = None, shared_backend_root: Path | None = None) -> list[str]:
    """One write boundary for app, tests and worker installation; no fallback.

    ``cwd`` is resolved when the command is built. A default captured at import
    would keep the historical workspace after ``select_candidate``.
    """
    if cwd is None:
        cwd = WORKSPACE
    if shared_backend_root is not None:
        require(not offline and shared_backend_root.is_absolute() and shared_backend_root.is_dir()
                and shared_backend_root.resolve() == shared_backend_root
                and shared_backend_root.name == 'live-backend-admission'
                and shared_backend_root.parent.parent == CANDIDATE_ROOT,
                'shared backend must be an existing canonical candidate admission directory for live only')
        for source in readonly_inputs or []:
            require(not source.is_relative_to(shared_backend_root)
                    and not shared_backend_root.is_relative_to(source),
                    'shared backend write mount must not overlap certificate readonly inputs')
    argv = [
        require_bwrap(), "--die-with-parent", "--new-session", "--unshare-pid",
        "--ro-bind", "/", "/", "--bind", str(DEV_ROOT), str(DEV_ROOT),
        "--ro-bind", str(RUNTIME), str(RUNTIME),
        "--tmpfs", "/tmp", "--proc", "/proc", "--dev", "/dev",
    ]
    if shared_backend_root is not None:
        argv += ['--bind', str(shared_backend_root), str(shared_backend_root)]
    if offline:
        argv.append("--unshare-net")
        # DEV_ROOT stays writable for named development state. Executed Host
        # profiles, staged modules and the existing locked Python environment
        # are immutable inputs, including files outside an enumerated I01 list.
        protected=[DSH_HOME/'profiles']
        if PYWORKER.exists():protected.append(PYWORKER)
        for source in validate_readonly_inputs(protected,output_root=output_root):
            require(source.is_dir(),'offline runtime input must be a directory')
            argv += ['--ro-bind',str(source),str(source)]
    if readonly_parent is not None:
        require(offline,'qualification root requires the offline sandbox')
        validate_qualification_root(readonly_parent,output_root)
        argv += ['--ro-bind',str(readonly_parent),str(readonly_parent)]
    if output_root is not None:
        require(output_root.is_absolute() and output_root.resolve() == output_root
                and output_root.is_dir() and output_root.is_relative_to(Path("/tmp"))
                and output_root != Path("/tmp"), "test output must be a canonical task directory under /tmp")
        argv += ["--bind",str(output_root),str(output_root)]
    for source in validate_readonly_inputs(readonly_inputs or [],output_root=output_root):
        argv += ["--ro-bind",str(source),str(source)]
    return argv + ["--chdir", str(cwd), "--", *payload]


def command(manifest: dict, app_args: list[str], *, composition: str = "web", dump: bool = False) -> list[str]:
    payload = [
        manifest["node"], str(RUNTIME / CLI_REL),
        "--profile", PROFILE_NAMES[composition], "--patch", str(POLICY),
    ]
    if dump:
        payload.append("--dump-config")
    return sandbox_command(manifest, payload + app_args)


def test_command(manifest: dict, files: list[str], *, output_root: Path | None = None,
                 report_path: Path | None = None, readonly_inputs: list[Path] | None = None,
                 readonly_parent: Path | None = None) -> list[str]:
    roots = [(BUNDLE_PACKAGE / rel).resolve() for rel in ("tests", "dev/toolchain")]
    for file in files:
        target = Path(file).resolve()
        require(target.is_file() and target.name.endswith(".test.ts"), f"invalid test file: {target}")
        require(any(target.is_relative_to(root) for root in roots), f"test outside package test roots: {target}")
    require(bool(files), "no compatibility test files")
    reporter_args=[]
    if report_path is not None:
        require(output_root is not None and report_path.is_absolute() and report_path.resolve() == report_path
                and report_path.parent == output_root and not report_path.exists(),
                "machine report must be a new file directly in the fresh output root")
        reporter_args=["--test-reporter=spec",
            "--test-reporter="+str(BUNDLE_PACKAGE / "dev/toolchain/suite-reporter.mjs"),
            "--test-reporter-destination=stdout","--test-reporter-destination="+str(report_path)]
    return sandbox_command(
        manifest, [manifest["node"], "--test", "--test-concurrency=1", *reporter_args, *files],
        cwd=BUNDLE_PACKAGE, offline=True, **({"output_root":output_root} if output_root is not None else {}),
        **({"readonly_inputs":readonly_inputs} if readonly_inputs is not None else {}),
        **({"readonly_parent":readonly_parent} if readonly_parent is not None else {}),
    )


def setup(source: Path | None) -> None:
    safe_dev_root()
    require(not DEV.exists(), f"already exists; use doctor instead: {DEV}")
    if source is None:
        base = Path.home() / ".dsh/profiles/node_modules/@deepseek-ai/dsh-base"
        require(base.is_dir(), "cannot discover existing DSH; pass --from-existing")
        source = base.resolve().parents[2]
    source = source.resolve()
    require(not source.is_relative_to(DEV), "source cannot be the development copy")
    package = read_json(source / "node_modules/@deepseek-ai/dsh/package.json")
    require(package["name"] == "@deepseek-ai/dsh" and package["version"] == VERSION, f"expected installed DSH {VERSION}")
    require((source / "package-lock.json").is_file(), "existing npm installation lock is required")
    node = shutil.which("node")
    require(node is not None, "Node is required")
    require_bwrap()
    entries = inventory(source)
    DEV.mkdir(mode=0o700)
    # copy2 creates independent files, never hardlinks to the everyday runtime.
    shutil.copytree(source, RUNTIME, symlinks=True)
    require(inventory(RUNTIME) == entries, "runtime copy does not match the installed bytes")
    for rel in ("home", "workspace", "tmp", "cache", "config", "data", "evidence", "run"):
        (DEV / rel).mkdir(mode=0o700)
    ensure_layout()
    node_version = subprocess.check_output([node, "--version"], text=True).strip()
    write_json(DEV / "runtime-inventory.json", entries)
    write_json(DEV / "manifest.json", {
        "schema_version": 2, "dsh_version": VERSION,
        "source_installation": str(source), "source_kind": "installed-npm-snapshot",
        "upstream_commit": None, "runtime_tree_sha256": tree_digest(entries),
        "package_lock_sha256": digest_file(RUNTIME / "package-lock.json"),
        "cli_sha256": digest_file(RUNTIME / CLI_REL), "node": node,
        "node_version": node_version, "profile": PROFILE_NAMES["web"],
        "profiles": dict(PROFILE_NAMES), "compositions": {k: list(v) for k, v in COMPOSITIONS.items()},
        "run_root": str(RUN_ROOT),
        "code2paper_head_at_setup": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "live_enabled": False,
    })
    print(f"Created independent DSH {VERSION} runtime: {DEV}")
    print("No everyday settings, credentials, sessions, or local plugins were copied.")


def toolchain_state() -> dict:
    """Verify the locked TypeScript toolchain and that the runtime stayed clean."""
    require(
        TOOLCHAIN_RECEIPT.is_file(),
        "toolchain is not installed; run: npm --prefix integrations/dsh run toolchain:install",
    )
    state = read_json(TOOLCHAIN_RECEIPT)
    require(state.get("schema_version") == TOOLCHAIN_SCHEMA, "unexpected toolchain receipt schema")
    declared = read_json(BUNDLE_PACKAGE / "package.json")["devDependencies"]
    require(state["typescript_version"] == declared["typescript"], "installed TypeScript does not match the lock")
    require(state["types_node_version"] == declared["@types/node"], "installed @types/node does not match the lock")
    require(state["lock_sha256"] == digest_file(BUNDLE_PACKAGE / "package-lock.json"),
            "package-lock.json changed since the toolchain install; reinstall the toolchain")
    # The frozen runtime ships its own dependency tree (including @types/node for
    # DSH's own build inputs); the whole-tree digest check in doctor() proves that
    # tree is byte-identical to the frozen copy. The toolchain's own compiler must
    # never appear there.
    require(
        not (RUNTIME / "node_modules/typescript").exists(),
        "TypeScript was installed into the frozen runtime; development dependencies stay outside it",
    )
    require(
        not (BUNDLE_PACKAGE / "node_modules/typescript").is_symlink(),
        "the toolchain compiler must be a locked local install, not a link into the runtime",
    )
    link = BUNDLE_PACKAGE / "node_modules/@deepseek-ai"
    require(link.is_symlink(), "the DSH/Cordis peer link is missing; reinstall the toolchain")
    require(
        link.resolve() == (RUNTIME / "node_modules/@deepseek-ai").resolve(),
        "the DSH/Cordis peer link does not point at the frozen runtime",
    )
    return state


def stage_bundle() -> dict:
    """Copy the built package to the profile install location and record its bytes."""
    ensure_layout()
    BUNDLE_STAGING.parent.mkdir(parents=True, exist_ok=True)
    with (BUNDLE_STAGING.parent / ".c2p-bundle-stage.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _stage_bundle()


def staged_build_files(receipt: dict, receipt_bytes: bytes) -> dict[str, str]:
    """Expected runtime payload comes from the fixed build, not from copied bytes."""
    return {
        "package.json": receipt["config_inputs"]["package.json"],
        "lib/build-receipt.json": hashlib.sha256(receipt_bytes).hexdigest(),
        **{rel: digest for rel, digest in receipt["outputs"].items() if rel.startswith("lib/")},
        **receipt.get("asset_inputs", {}),
    }


def _stage_bundle() -> dict:
    require(BUILD_RECEIPT.is_file(), "no build receipt; run: npm --prefix integrations/dsh run build")
    receipt_bytes = BUILD_RECEIPT.read_bytes()
    receipt = verify_build_receipt(expected_receipt=receipt_bytes)
    expected = staged_build_files(receipt, receipt_bytes)
    package = read_json(BUNDLE_PACKAGE / "package.json")
    require(set(package.get("files", [])) == set(STAGE_CONTENT), "unexpected bundle files allowlist")
    sources = []
    for entry in STAGE_CONTENT:
        root = BUNDLE_PACKAGE / entry
        candidates = [root, *sorted(root.rglob("*"))] if root.is_dir() else [root]
        for path in candidates:
            rel = path.relative_to(BUNDLE_PACKAGE)
            require(not path.is_symlink(), f"bundle staging cannot copy a symlink: {rel}")
            if any(part in STAGE_SKIP_DIRS for part in rel.parts) or not path.is_file():
                continue
            sources.append((path, rel))
    require({rel.as_posix() for _, rel in sources} == set(expected), "runtime package file set differs from build")
    candidate = Path(tempfile.mkdtemp(prefix=".c2p-stage-candidate-", dir=BUNDLE_STAGING.parent))
    backup = candidate.with_name(candidate.name + "-previous")
    receipt_file = candidate.with_name(candidate.name + "-receipt.json")
    committed = False
    try:
        files: dict[str, dict[str, str | int]] = {}
        for path, rel in sources:
            target = candidate / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if rel.as_posix() == "lib/build-receipt.json":
                target.write_bytes(receipt_bytes)
            else:
                shutil.copy2(path, target)
            digest = digest_file(target)
            require(digest == expected[rel.as_posix()], f"staged bytes differ from fixed build: {rel}")
            files[rel.as_posix()] = {"sha256": digest, "size": target.stat().st_size}
        require(read_json(candidate / "package.json")["name"] == BUNDLE_NAME, "staged package name mismatch")
        # A concurrent build may replace outputs while this copy is in flight.
        # Do not activate a candidate unless it still names the exact initial build.
        verify_build_receipt(expected_receipt=receipt_bytes)
        record = {
            "schema_version": 1, "bundle": BUNDLE_NAME,
            "candidate": CANDIDATE,
            "dev_root": str(DEV_ROOT),
            "staged_path": str(BUNDLE_STAGING), "source_package": str(BUNDLE_PACKAGE),
            "build_receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
            "src_present": bool(receipt.get("src_present")),
            "entry_present": (candidate / "lib/index.js").is_file(),
            "patch_present": (candidate / "cordis.patch.yml").is_file(),
            "file_count": len(files), "tree_sha256": tree_digest(files), "files": files,
        }
        write_json(receipt_file, record)
        if BUNDLE_STAGING.exists():
            BUNDLE_STAGING.rename(backup)
        try:
            candidate.rename(BUNDLE_STAGING)
            os.replace(receipt_file, STAGING_RECEIPT)
        except BaseException:
            if BUNDLE_STAGING.exists():
                shutil.rmtree(BUNDLE_STAGING)
            if backup.exists():
                backup.rename(BUNDLE_STAGING)
            raise
        committed = True
        return record
    finally:
        if candidate.exists():
            shutil.rmtree(candidate)
        if committed and backup.exists():
            shutil.rmtree(backup)
        receipt_file.unlink(missing_ok=True)


def bundle_build_inputs() -> dict[str, str]:
    src = BUNDLE_PACKAGE / "src"
    if not src.is_dir():
        return {}
    return {
        path.relative_to(BUNDLE_PACKAGE).as_posix(): digest_file(path)
        for path in sorted(src.rglob("*.ts")) if path.is_file()
    }


def bundle_asset_inputs() -> dict[str, str]:
    assets = [BUNDLE_PACKAGE / "cordis.patch.yml", *sorted((BUNDLE_PACKAGE / "presets").rglob("*"))]
    return {
        path.relative_to(BUNDLE_PACKAGE).as_posix(): digest_file(path)
        for path in assets if path.is_file()
    }


def verify_build_receipt(*, expected_receipt: bytes | None = None) -> dict:
    """Refuse a build whose inputs or emitted bytes no longer match its receipt."""
    require(BUILD_RECEIPT.is_file(), "no build receipt; run: npm --prefix integrations/dsh run build")
    receipt_bytes = BUILD_RECEIPT.read_bytes()
    if expected_receipt is not None:
        require(receipt_bytes == expected_receipt, "build changed during staging; re-run build then stage")
    receipt = json.loads(receipt_bytes)
    require(
        bundle_build_inputs() == receipt.get("src_inputs", {}),
        "bundle sources changed after the last build; re-run: npm --prefix integrations/dsh run build",
    )
    require(
        bundle_asset_inputs() == receipt.get("asset_inputs", {}),
        "bundle assets changed after the last build; re-run: npm --prefix integrations/dsh run build",
    )
    for rel, digest in receipt.get("config_inputs", {}).items():
        require(
            digest_file(BUNDLE_PACKAGE / rel) == digest,
            f"{rel} changed after the last build; re-run: npm --prefix integrations/dsh run build",
        )
    lib = BUNDLE_PACKAGE / "lib"
    expected = {rel for rel in receipt.get("outputs", {}) if rel.startswith("lib/")} | {"lib/build-receipt.json"}
    actual = {
        path.relative_to(BUNDLE_PACKAGE).as_posix()
        for path in lib.rglob("*") if path.is_file()
    } if lib.is_dir() else set()
    require(actual == expected, f"unexpected files under lib/: {sorted(actual ^ expected)}")
    for rel, digest in receipt.get("outputs", {}).items():
        require(
            digest_file(BUNDLE_PACKAGE / rel) == digest,
            f"emitted bundle bytes drifted from the build receipt: {rel}",
        )
    return receipt


def verify_staging() -> dict:
    require(STAGING_RECEIPT.is_file(), "bundle is not staged; run: python scripts/dsh_dev.py stage")
    receipt = verify_build_receipt()
    receipt_bytes = BUILD_RECEIPT.read_bytes()
    require(json.loads(receipt_bytes) == receipt, "build changed while verifying staging")
    record = read_json(STAGING_RECEIPT)
    require(BUNDLE_STAGING.is_dir(), f"staged bundle directory is missing: {BUNDLE_STAGING}")
    current = {}
    for path in sorted(BUNDLE_STAGING.rglob("*")):
        if path.is_file():
            current[path.relative_to(BUNDLE_STAGING).as_posix()] = {
                "sha256": digest_file(path), "size": path.stat().st_size,
            }
    require(
        tree_digest(current) == record["tree_sha256"],
        "staged bundle bytes drifted from the staging receipt; re-run: python scripts/dsh_dev.py stage",
    )
    require(
        digest_file(BUILD_RECEIPT) == record["build_receipt_sha256"],
        "the bundle was rebuilt after staging; re-run: python scripts/dsh_dev.py stage",
    )
    require(
        {rel: entry["sha256"] for rel, entry in current.items()} == staged_build_files(receipt, receipt_bytes),
        "staged bytes do not match the fixed build generation",
    )
    return {
        "staged_path": record["staged_path"], "file_count": record["file_count"],
        "tree_sha256": record["tree_sha256"], "entry_present": record["entry_present"],
        "patch_present": record["patch_present"], "src_present": record["src_present"],
    }


def require_compat_bundle() -> dict:
    """Refuse the compat composition unless a real, staged bundle entry exists."""
    staged = verify_staging()
    require(
        staged["entry_present"],
        "the staged bundle has no lib/index.js; the compat composition needs the bundle entry "
        "(H01 deliverable). Build and stage after implementing integrations/dsh/src/index.ts",
    )
    require(
        staged["patch_present"],
        "the staged bundle has no cordis.patch.yml; the compat composition cannot be composed",
    )
    return staged


def _default_everyday_installation() -> Path | None:
    """The historical snapshot's everyday path, if that manifest still names one.

    A candidate without its own snapshot may use this only to prove the current
    runtime does not share inodes with that install. It is not a hash baseline.
    """
    manifest_path = DEV / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        recorded = json.loads(manifest_path.read_text(encoding="utf-8")).get("source_installation")
    except (OSError, ValueError):
        return None
    if not isinstance(recorded, str) or recorded == "":
        return None
    return Path(recorded)


def _shared_inodes(source: Path, entries: dict) -> list[str]:
    return [
        rel for rel, entry in entries.items()
        if "sha256" in entry and (source / rel).exists()
        and os.path.samestat((RUNTIME / rel).stat(), (source / rel).stat())
    ]


def _path_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def verify_original_installation(manifest: dict, entries: dict) -> dict:
    """Cheap identity checks that the everyday installation was not overwritten.

    An npm candidate has no everyday snapshot. It must not borrow the default
    runtime's source path, and this check then reports that the comparison
    does not apply.
    """
    source_text = manifest.get("source_installation")
    if not isinstance(source_text, str) or source_text == "":
        everyday = _default_everyday_installation()
        report: dict = {
            "applicable": False,
            "hash_compared": False,
            "reason": "this environment has no everyday installation snapshot",
            "everyday_path": None if everyday is None else str(everyday),
            "everyday_present": bool(everyday is not None and everyday.is_dir()),
            "shared_inodes": 0,
            "write_path": False,
        }
        if everyday is not None and everyday.is_dir():
            shared = _shared_inodes(everyday, entries)
            require(not shared, "runtime shares hardlinks with the everyday installation")
            report["shared_inodes"] = 0
            report["write_path"] = _path_inside(everyday, DEV_ROOT)
        return report
    source = Path(source_text)
    require(source.is_dir(), f"the everyday DSH installation is missing: {source}")
    require(
        digest_file(source / "package-lock.json") == manifest["package_lock_sha256"],
        "the everyday DSH installation lock changed; this environment must not modify it",
    )
    require(
        digest_file(source / CLI_REL) == manifest["cli_sha256"],
        "the everyday DSH installation CLI changed; this environment must not modify it",
    )
    shared = _shared_inodes(source, entries)
    require(not shared, "runtime shares hardlinks with the original installation")
    return {
        "applicable": True, "path": str(source), "lock_matches": True,
        "cli_matches": True, "shared_inodes": 0,
    }


def sandbox_probes(manifest: dict) -> dict:
    """Prove the write boundary from inside bubblewrap."""
    checks = {
        "everyday_home_read_only": ["!", "-w", str(Path.home() / ".dsh")],
        "business_tree_read_only": ["!", "-w", str(REPO)],
        "run_root_writable": ["-w", str(RUN_ROOT)],
        "runtime_read_only": ["!", "-w", str(RUNTIME)],
        "runtime_js_read_only": ["!", "-w", str(RUNTIME / CLI_REL)],
    }
    results = {}
    for name, test_args in checks.items():
        argv = sandbox_command(manifest, ["/usr/bin/test", *test_args])
        subprocess.run(argv, check=True, env=child_env(manifest["node"]))
        results[name] = True
    return results


def parse_requirements_lock(text: str) -> dict[str, str]:
    packages = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9._-]+)==([^\s;]+)", line)
        require(match is not None, f"unparsable lock line: {line}")
        packages[normalize_name(match.group(1))] = match.group(2)
    return packages


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def pyworker_python() -> Path:
    return PYWORKER / "bin/python"


def pyworker_env() -> dict[str, str]:
    """Do not inherit install redirects, Python startup hooks or credentials."""
    return {
        **{key: os.environ[key] for key in INHERITED_ENV if key in os.environ},
        "PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin",
        "TMPDIR": str(DEV_ROOT / "tmp"),
        "XDG_CACHE_HOME": str(DEV_ROOT / "cache"),
        "XDG_CONFIG_HOME": str(DEV_ROOT / "config"),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PIP_CONFIG_FILE": os.devnull,
        "PIP_CACHE_DIR": str(DEV_ROOT / "cache/pip"),
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PIP_NO_INPUT": "1",
    }


def pyworker_state() -> dict:
    """Verify the locked Python worker environment without touching the daily one."""
    require(PYWORKER_LOCK.is_file(), f"the locked requirements file is missing: {PYWORKER_LOCK}")
    require(pyworker_python().is_file(), "python worker environment missing; run: python scripts/dsh_dev.py pyworker-setup")
    lock = parse_requirements_lock(PYWORKER_LOCK.read_text())
    freeze = subprocess.check_output(
        [str(pyworker_python()), "-m", "pip", "freeze", "--disable-pip-version-check"],
        text=True, env=pyworker_env(),
    )
    installed = {}
    for line in freeze.splitlines():
        if "==" not in line:
            continue
        name, _, version = line.partition("==")
        installed[normalize_name(name)] = version.split()[0]
    require(installed == lock, "the worker environment drifted from the lock; re-run pyworker-setup")
    prefix = subprocess.check_output(
        [str(pyworker_python()), "-c", "import sys; print(sys.prefix)"], text=True,
        env=pyworker_env(),
    ).strip()
    require(Path(prefix).resolve() == PYWORKER.resolve(), "the worker interpreter is not the isolated venv")
    import_probe = subprocess.run(
        [str(pyworker_python()), "-c", "import code2paper, pydantic, yaml; print(code2paper.__name__)"],
        env={**child_env(shutil.which("node") or "/usr/bin/node"), "PYTHONPATH": str(REPO / "src")},
        text=True, capture_output=True,
    )
    require(import_probe.returncode == 0, f"worker cannot import the domain package: {import_probe.stderr.strip()}")
    return {
        "path": str(PYWORKER), "packages": len(lock), "lock": str(PYWORKER_LOCK.relative_to(REPO)),
        "daily_interpreter_unchanged": True, "domain_import": import_probe.stdout.strip(),
    }


def pyworker_setup(wheelhouse: Path | None = None) -> dict:
    require(PYWORKER_LOCK.is_file(), f"the locked requirements file is missing: {PYWORKER_LOCK}")
    manifest = read_manifest("web")
    ensure_layout()
    if wheelhouse is not None:
        require(wheelhouse.is_dir() and wheelhouse.resolve() == (DEV_ROOT / "cache/pip/wheels").resolve(),
                "offline wheelhouse must be the selected candidate cache/pip/wheels directory")
    require(PYWORKER.resolve().is_relative_to(DEV_ROOT), "worker environment escapes the selected development root")
    if PYWORKER.exists():
        shutil.rmtree(PYWORKER)
    subprocess.run(
        sandbox_command(manifest, [sys.executable, "-I", "-m", "venv", str(PYWORKER)]),
        check=True, env=pyworker_env(),
    )
    subprocess.run(
        sandbox_command(manifest, [str(pyworker_python()), "-I", "-m", "pip", "install",
         *([] if wheelhouse is None else ["--no-index", "--find-links", str(wheelhouse.resolve())]),
         "--require-hashes", "--no-deps", "--no-user", "--prefix", str(PYWORKER), "-r", str(PYWORKER_LOCK)]),
        check=True, env={**pyworker_env(), "VIRTUAL_ENV": str(PYWORKER)},
    )
    return pyworker_state()


def pyworker_lock() -> None:
    """Regenerate the committed worker lock from the pinned top-level requirements."""
    ensure_layout()
    report = DEV / "tmp/pyworker-report.json"
    spec = [f"{name}=={version}" for name, version in pinned_requirements()]
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--dry-run", "--ignore-installed", "--quiet",
         "--report", str(report), *spec],
        check=True,
        env=pyworker_env(),
    )
    installs = read_json(report)["install"]
    lines = []
    for item in sorted(installs, key=lambda entry: normalize_name(entry["metadata"]["name"])):
        name = item["metadata"]["name"]
        version = item["metadata"]["version"]
        digest = item["download_info"]["archive_info"]["hashes"]["sha256"]
        lines.append(f"{name}=={version} --hash=sha256:{digest}")
    header = [
        "# Code2Paper DSH development Python worker environment (B02).",
        "# Generated by: python scripts/dsh_dev.py pyworker-lock",
        f"# Interpreter: CPython {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        f"# Top-level requirements: {', '.join(spec)}",
        "# Install with: python scripts/dsh_dev.py pyworker-setup",
    ]
    PYWORKER_LOCK.write_text("\n".join(header + lines) + "\n")
    print(PYWORKER_LOCK.read_text())


def pinned_requirements() -> list[tuple[str, str]]:
    """Versions of the daily interpreter's packages, used to pin the worker lock."""
    probe = subprocess.run(
        [sys.executable, "-c",
         "import importlib.metadata as m, sys\n"
         "print('\\n'.join(f'{n}=={m.version(n)}' for n in sys.argv[1:]))",
         *PYWORKER_REQUIREMENTS],
        text=True, capture_output=True, check=True,
    )
    versions = {}
    for line in probe.stdout.splitlines():
        name, _, version = line.partition("==")
        versions[name] = version
    return [(name, versions[name]) for name in PYWORKER_REQUIREMENTS]


def doctor(evidence: bool = False) -> dict:
    manifest = read_manifest("web")
    ensure_layout()
    entries = inventory(RUNTIME)
    require(tree_digest(entries) == manifest["runtime_tree_sha256"], "runtime bytes drifted")
    original = verify_original_installation(manifest, entries)
    probes = sandbox_probes(manifest)
    env = child_env(manifest["node"])
    report = {
        "schema_version": "c2p-dsh-development-environment-isolation/1",
        "task": "B02",
        "acceptance_id": "AT-B02",
        "dsh_version": VERSION,
        "node_version": manifest["node_version"],
        "runtime": {
            "path": str(RUNTIME), "files_and_links": len(entries),
            "tree_sha256": manifest["runtime_tree_sha256"], "bytes_match": True,
            "development_dependencies_absent": True,
        },
        "original_installation": original,
        "isolation": {
            **probes,
            "home_preserved": env["HOME"] == os.environ.get("HOME"),
            "api_key_inheritance": "rejected",
            "reserved_ports_refused": list(RESERVED_PORTS),
            "bubblewrap_required": True,
        },
        "compositions": {},
        "run_root": str(RUN_ROOT),
        "toolchain": toolchain_state(),
        "bundle": {"package": str(BUNDLE_PACKAGE.relative_to(REPO)), "staging": "absent"},
        "pyworker": "absent",
    }
    for composition in COMPOSITIONS:
        bundles = profile_bundles(composition)
        validate_composition(composition, bundles)
        report["compositions"][composition] = {
            "profile": PROFILE_NAMES[composition], "bundles": bundles, "whitelisted": True,
        }
    if STAGING_RECEIPT.is_file():
        report["bundle"]["staging"] = verify_staging()
    # The locked worker environment is part of this unit's deliverable, so a
    # missing or drifted worker fails the check instead of being reported as absent.
    report["pyworker"] = pyworker_state()
    report["compat_composition_ready"] = bool(
        isinstance(report["bundle"]["staging"], dict) and report["bundle"]["staging"]["entry_present"]
        and report["bundle"]["staging"]["patch_present"]
    )
    if evidence:
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        write_json(EVIDENCE_DIR / "development-environment-isolation.json", report)
    return report


def activate_candidate() -> dict:
    """Switch the development peer link to this candidate without reinstalling npm dependencies."""
    require(CANDIDATE is not None, "activate requires --candidate <id>")
    require((DEV_ROOT / "manifest.json").is_file(), f"manifest.json missing for candidate {CANDIDATE}")
    node = shutil.which("node")
    require(node is not None, "Node is required")
    env = child_env(node)
    toolchain_script = BUNDLE_PACKAGE / "dev/toolchain/toolchain.mjs"
    result = subprocess.run(
        [node, str(toolchain_script), "activate"],
        cwd=BUNDLE_PACKAGE,
        env=env,
        text=True,
        capture_output=True,
    )
    require(
        result.returncode == 0,
        f"toolchain activate failed: {result.stderr.strip() or result.stdout.strip()}",
    )
    link = BUNDLE_PACKAGE / "node_modules/@deepseek-ai"
    return {
        "candidate": CANDIDATE,
        "dev_root": str(DEV_ROOT),
        "peer_link": str(link.resolve()),
        "status": "activated",
    }


def audit_candidate_delivery() -> dict:
    """Verify runtime manifest, staging, build receipt, peer link, and candidate consistency."""
    require(CANDIDATE is not None, "audit requires --candidate <id>")
    manifest_path = DEV_ROOT / "manifest.json"
    require(manifest_path.is_file(), f"manifest missing: {manifest_path}")
    manifest = read_json(manifest_path)

    require(manifest.get("dsh_version") == VERSION, "audit candidate identity wrong")
    require(digest_file(RUNTIME / "package-lock.json") == manifest.get("package_lock_sha256"), "audit runtime lock drifted")

    # 1. Whole-tree runtime integrity check
    entries = inventory(RUNTIME)
    tree_hash = tree_digest(entries)
    require(
        tree_hash == manifest.get("runtime_tree_sha256"),
        f"runtime tree drifted: actual {tree_hash} != manifest {manifest.get('runtime_tree_sha256')}",
    )

    # Patched audits require both the pristine input and an independent trusted
    # declaration; absence cannot erase the diff obligation.
    if "+" in VERSION:
        contract = candidate_contract()["dsh"]
        expected_base = contract["base_runtime_tree_sha256"]
        require(manifest.get("base_runtime_tree_sha256") == expected_base, "candidate base identity mismatch")
        _, base_entries = verified_pristine_base(expected_base)
        actual_touched = sorted(p for p in set(base_entries) | set(entries) if base_entries.get(p) != entries.get(p))
        require(actual_touched == expected_runtime_touched(), f"runtime touched unexpected files: {actual_touched!r}")
        require(manifest.get("loop_origin_patch", {}).get("touched") == actual_touched, "manifest declared touched drifted")
        require(contract["patch"]["touched"] == actual_touched, "compatibility declared touched drifted")
        expected_tree = (contract["patch"]["source"]["build_verification_tree_sha256"]
                         if VERSION.endswith("-built") else contract["runtime_tree_sha256"])
        require(tree_hash == expected_tree, "candidate trusted runtime identity mismatch")
        if VERSION in TOOL_CHOICE_CANDIDATES:
            extension = contract["tool_choice_patch"]
            require(manifest.get("tool_choice_patch") == extension, "tool-choice manifest binding differs")
            choice_patch = TOOL_CHOICE_PARAMS_PATCH if VERSION == TOOL_CHOICE_PARAMS_CANDIDATE else TOOL_CHOICE_PATCH
            require(digest_file(choice_patch) == extension["script_sha256"], "tool-choice patch source drifted")
            if VERSION == TOOL_CHOICE_PARAMS_CANDIDATE:
                require(extension['base_patch_sha256'] == digest_file(TOOL_CHOICE_PATCH), 'tool-choice helper source drifted')

    # 3. Staging and build receipt check
    require(STAGING_RECEIPT.is_file(), f"staging receipt missing: {STAGING_RECEIPT}")
    staging = verify_staging()
    staged_receipt_file = BUNDLE_STAGING / "lib/build-receipt.json"
    require(staged_receipt_file.is_file(), f"staged build receipt missing: {staged_receipt_file}")
    staged_receipt = read_json(staged_receipt_file)
    require(
        staged_receipt.get("frozen_runtime", {}).get("runtime_tree_sha256") == manifest["runtime_tree_sha256"],
        f"cross-candidate receipt detected: staged receipt frozen runtime {staged_receipt.get('frozen_runtime', {}).get('runtime_tree_sha256')} != candidate {manifest['runtime_tree_sha256']}",
    )

    # 4. Peer link check
    link = BUNDLE_PACKAGE / "node_modules/@deepseek-ai"
    require(link.is_symlink(), "peer link is missing or not a symlink")
    require(
        link.resolve() == (RUNTIME / "node_modules/@deepseek-ai").resolve(),
        f"peer link points to wrong runtime: actual {link.resolve()} != candidate {RUNTIME / 'node_modules/@deepseek-ai'}",
    )

    return {
        "candidate": CANDIDATE,
        "runtime_tree_sha256": tree_hash,
        "staged_build_receipt_sha256": digest_file(staged_receipt_file),
        "staging_tree_sha256": staging["tree_sha256"],
        "peer_link_target": str(link.resolve()),
        "status": "PASS",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate",
        default=os.environ.get(CANDIDATE_ENV),
        help=(
            "use the isolated root .dsh-dev/candidates/<version> instead of the "
            f"default development environment (env {CANDIDATE_ENV})"
        ),
    )
    commands = parser.add_subparsers(dest="action", required=True)
    candidate_parser = commands.add_parser(
        "candidate", help="report the selected environment without mutating it",
    )
    candidate_parser.add_argument(
        "--verify-runtime", action="store_true",
        help="recompute the default runtime identity with the historical algorithm",
    )
    candidate_parser.add_argument(
        "--provision", action="store_true",
        help="create the selected candidate's isolated layout, profile rows and manifest",
    )
    setup_parser = commands.add_parser("setup", help="copy the existing installed npm runtime once")
    setup_parser.add_argument("--from-existing", type=Path)
    doctor_parser = commands.add_parser("doctor", help="verify frozen bytes, toolchain, staging and isolation")
    doctor_parser.add_argument("--evidence", action="store_true", help="also write the evidence JSON")
    stage = commands.add_parser("stage", help="stage the built bundle at the profile install location")
    stage.add_argument("--check", action="store_true", help="verify existing build/staging without replacing it")
    config = commands.add_parser("config", help="dump the isolated composed configuration")
    config.add_argument("--composition", choices=sorted(COMPOSITIONS), default="web")
    web = commands.add_parser("web", help="run the isolated Web UI in the foreground; Ctrl-C stops it")
    web.add_argument("--port", type=int, default=3081)
    compat = commands.add_parser("compat", help="run the isolated Web UI with the Code2Paper compat composition")
    compat.add_argument("--port", type=int, default=3082)
    loop_origin = commands.add_parser(
        "loop-origin-setup",
        help="create the patched loop-origin candidate from the pristine base runtime",
    )
    commands.add_parser("activation-inputs", help="verify activation runtime inputs without writes")
    commands.add_parser("activate", help="switch toolchain peer link to the selected candidate")
    commands.add_parser("audit", help="verify runtime manifest, staging, build receipt and peer link")
    worker_setup = commands.add_parser("pyworker-setup", help="create the locked Python worker virtual environment")
    worker_setup.add_argument("--wheelhouse", type=Path, help="offline selected candidate cache/pip/wheels; original lock hashes required")
    commands.add_parser("pyworker-lock", help="regenerate the committed worker lock file")
    tests = commands.add_parser("test", help="run compatibility test files in the offline sandbox")
    tests.add_argument("--output-root",type=Path,help="fresh task directory under /tmp, retained across isolated runs")
    tests.add_argument("--report-path",type=Path,help="new Node machine report directly in --output-root")
    tests.add_argument("--operator-package",action="store_true",help="private single-Host CLI preparation; waits for a real offline receipt")
    tests.add_argument('--qualification-root',type=Path,help='read-only proof parent for private operator preparation')
    tests.add_argument("--coverage-receipt",type=Path,help="private normal CLI proof with an existing final certificate locator")
    tests.add_argument('--core-reuse-readonly',type=Path,help='read-only evidence for fresh offline qualification; grants no admission')
    tests.add_argument("files", nargs="+")
    writer = commands.add_parser("writer",help="explicit experimental Writer in the offline sandbox")
    writer.add_argument("--experimental-dsh",action="store_true",required=True)
    writer.add_argument("--task-root",type=Path,required=True,help="original prepared /tmp task directory")
    writer.add_argument("--output-root",type=Path,required=True,help="fresh output child of task-root")
    writer.add_argument("--bootstrap",type=Path,required=True)
    writer.add_argument("--launch-file",type=Path,required=True)
    writer.add_argument("--offline-receipt",type=Path,required=True)
    writer.add_argument("--parallel-agents",choices=("false","true"),default="false")
    args = parser.parse_args()
    assert_selection_agreement(args.candidate)
    select_candidate(args.candidate, allow_missing=args.action == "loop-origin-setup")
    if args.action not in ("candidate", "pyworker-lock", "loop-origin-setup", "activation-inputs"):
        require_candidate_ready(args.action)
    if args.action == "candidate":
        if args.provision:
            print(json.dumps(provision_candidate(), ensure_ascii=False, indent=2))
        else:
            print(json.dumps(
                candidate_status(verify_runtime=args.verify_runtime), ensure_ascii=False, indent=2,
            ))
    elif args.action == "setup":
        setup(args.from_existing)
    elif args.action == "loop-origin-setup":
        print(json.dumps(loop_origin_setup(), ensure_ascii=False, indent=2))
    elif args.action == "activation-inputs":
        print(json.dumps(activation_inputs(), indent=2))
    elif args.action == "activate":
        print(json.dumps(activate_candidate(), ensure_ascii=False, indent=2))
    elif args.action == "audit":
        print(json.dumps(audit_candidate_delivery(), ensure_ascii=False, indent=2))
    elif args.action == "doctor":
        print(json.dumps(doctor(evidence=args.evidence), ensure_ascii=False, indent=2))
    elif args.action == "stage":
        print(json.dumps(verify_staging() if args.check else stage_bundle(), ensure_ascii=False, indent=2))
    elif args.action == "pyworker-setup":
        print(json.dumps(pyworker_setup(args.wheelhouse), ensure_ascii=False, indent=2))
    elif args.action == "pyworker-lock":
        pyworker_lock()
    elif args.action == "test":
        readonly_inputs=[]
        if args.core_reuse_readonly is not None:
            require(args.operator_package,'core evidence transport requires offline operator preparation')
            sys.path.insert(0,str(REPO/'src'))
            from code2paper.agentic.digest import digest_bytes
            from code2paper.integrations.dsh.core_reuse import reuse_readonly_paths
            raw=args.core_reuse_readonly.read_bytes()
            readonly_inputs=reuse_readonly_paths({'path':str(args.core_reuse_readonly),
                'bytes_digest':digest_bytes(raw),'byte_length':len(raw)})
        if args.qualification_root is not None:
            require(args.operator_package,'qualification root requires operator preparation')
            validate_qualification_root(args.qualification_root,args.output_root)
        require(not (args.operator_package and args.coverage_receipt is not None),
                "operator qualification and normal CLI proof are mutually exclusive")
        if args.coverage_receipt is not None:
            require(args.coverage_receipt.is_absolute() and args.coverage_receipt.resolve() == args.coverage_receipt
                    and args.coverage_receipt.is_file(), "coverage receipt must be a canonical existing file")
            sys.path.insert(0,str(REPO/'src'))
            from code2paper.integrations.dsh.offline_inputs import coverage_readonly_inputs
            try:
                _,readonly_inputs=coverage_readonly_inputs(args.coverage_receipt,candidate=CANDIDATE,engine_root=REPO)
            except Exception:
                raise RuntimeError('coverage_receipt_rejected') from None
        if args.operator_package or args.coverage_receipt is not None:
            require(CANDIDATE is not None and args.output_root is not None
                    and len(args.files) == 1
                    and Path(args.files[0]).resolve() == (BUNDLE_PACKAGE/'tests/host-provider.test.ts').resolve(),
                    'operator preparation requires the explicit candidate, fresh output and single actual Host fixture')
        manifest = read_manifest("web")
        verify_staging()
        toolchain_state()
        output_root=args.output_root
        if output_root is not None:
            require(output_root.is_absolute() and output_root.resolve() == output_root
                    and output_root.is_relative_to(Path("/tmp")) and output_root != Path("/tmp"),
                    "test output must be a canonical task directory under /tmp")
            validate_readonly_inputs(readonly_inputs,output_root=output_root)
            output_root.mkdir(parents=True,exist_ok=False)
        argv = test_command(manifest, args.files,output_root=output_root,
            **({"report_path":args.report_path} if args.report_path is not None else {}),
            **({"readonly_inputs":readonly_inputs} if readonly_inputs else {}),
            **({"readonly_parent":args.qualification_root} if args.qualification_root is not None else {}))
        environment=child_env(manifest["node"])
        environment['C2P_DSH_OFFLINE_EXECUTION']='1'
        if args.operator_package:environment['C2P_STAGE04_TEST_OPERATOR_PACKAGE']='1'
        if args.coverage_receipt is not None:environment['C2P_STAGE04_TEST_COVERAGE_RECEIPT']=str(args.coverage_receipt)
        if output_root is not None: environment["C2P_DSH_RUN_ROOT"]=str(output_root)
        os.execve(argv[0], argv, environment)
    elif args.action == "writer":
        require(CANDIDATE is not None,"writer requires an explicit candidate")
        # Parent verifies the certificate and immutable target transport only.
        # Fresh-target authority belongs to the normal CLI inside unshare-net.
        sys.path.insert(0,str(REPO/'src'))
        from code2paper.integrations.dsh.offline_inputs import coverage_readonly_inputs
        from code2paper.integrations.dsh.host_admission import _read, _bootstrap_spec
        from code2paper.integrations.dsh.target_admission import _launch
        from code2paper.agentic.authoring_execution_identity import validate_execution_composition
        from code2paper.integrations.dsh.protocol import strict_json_loads
        require(args.parallel_agents == 'false','parallel_execution_unsupported')
        try:
            _,inputs=coverage_readonly_inputs(args.offline_receipt,candidate=CANDIDATE,engine_root=REPO)
            bootstrap=strict_json_loads(_read(args.bootstrap),max_bytes=32 << 20)
            spec=_bootstrap_spec(bootstrap,REPO)
            composition=validate_execution_composition(spec,bootstrap['composition'],engine_root=REPO)
            _launch(bootstrap,spec,composition,args.launch_file)
            worker_python=spec.files['test_worker_launcher']
            require(worker_python.is_file(),'writer frozen Python launcher unavailable')
        except Exception:
            raise RuntimeError('writer_admission_rejected') from None
        task_root=args.task_root;output_root=args.output_root
        require(task_root.is_absolute() and task_root.resolve() == task_root and task_root.is_dir()
                and task_root.is_relative_to(Path('/tmp')) and task_root != Path('/tmp'),
                'writer task root must be a canonical prepared /tmp directory')
        require(output_root.is_absolute() and output_root.resolve() == output_root and output_root.parent == task_root,
                'writer output must be a fresh direct child of task root')
        require(Path(bootstrap['artifact_root']).resolve().is_relative_to(task_root)
                and args.bootstrap.resolve().is_relative_to(task_root) and args.launch_file.resolve().is_relative_to(task_root),
                'writer bootstrap, launch and original run must belong to task root')
        inputs.extend([args.bootstrap,args.launch_file,
            *(path.resolve() for path in spec.files.values()),*(path.resolve() for path in spec.trees.values())])
        inputs=validate_readonly_inputs(inputs,output_root=task_root)
        manifest=read_manifest('web');verify_staging();toolchain_state()
        output_root.mkdir(exist_ok=False)
        executable=DSH_HOME/'profiles/node_modules/@code2paper/dsh-bundle/lib/cli.js'
        payload=[manifest['node'],str(executable),'run','--experimental-dsh','--candidate',CANDIDATE,
            '--python',str(worker_python),'--engine-root',str(REPO),
            '--bootstrap',str(args.bootstrap),'--offline-receipt',str(args.offline_receipt),
            '--launch-file',str(args.launch_file),'--parallel-agents',args.parallel_agents]
        argv=sandbox_command(manifest,payload,cwd=BUNDLE_PACKAGE,offline=True,output_root=task_root,
            readonly_inputs=sorted(set(inputs)))
        environment=child_env(manifest['node']);environment['C2P_DSH_OFFLINE_EXECUTION']='1'
        environment['C2P_DSH_RUN_ROOT']=str(output_root)
        os.execve(argv[0],argv,environment)
    else:
        composition = "compat" if args.action == "compat" else getattr(args, "composition", "web")
        manifest = read_manifest(composition)
        # Fail closed before launching anything when the compat row cannot load.
        if composition == "compat":
            require_compat_bundle()
        if args.action in ("web", "compat"):
            validate_port(args.port)
            app_args = ["--host", "127.0.0.1", "--port", str(args.port), "--no-open"]
        else:
            app_args = []
        argv = command(manifest, app_args, composition=composition, dump=args.action == "config")
        os.execve(argv[0], argv, child_env(manifest["node"]))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"dsh-dev: {exc}", file=sys.stderr)
        sys.exit(1)
