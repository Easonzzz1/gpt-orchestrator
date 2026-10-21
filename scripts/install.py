#!/usr/bin/env python3
"""Idempotent project-scoped install; no global config or remote install scripts."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELECTED = ("brainstorming", "writing-plans", "executing-plans", "systematic-debugging",
            "test-driven-development", "verification-before-completion")


def install(skills_dir=None):
    lock = json.loads((ROOT / "upstream.lock.json").read_text())
    manifest = json.loads((ROOT / "vendor/superpowers.manifest.json").read_text()) if (ROOT / "vendor/superpowers.manifest.json").exists() else None
    sp = ROOT / "vendor/superpowers"
    if sp.exists():
        if not manifest:
            raise RuntimeError("Existing Superpowers tree has no manifest; refusing to trust or overwrite it")
        for name, expected in manifest["files"].items():
            path = sp / name
            if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise RuntimeError("Superpowers tree differs from lock: " + name)
    else:
        raise RuntimeError("Missing bundled Superpowers skills; obtain a fresh project checkout")
    protocol = ROOT / "integrations/chatgpt-use/delegation.upstream.rs"
    if not protocol.is_file():
        raise RuntimeError("Missing bundled chatgpt-use protocol source")
    protocol_manifest = json.loads((protocol.parent / "manifest.json").read_text())
    for name, expected in protocol_manifest["files"].items():
        if hashlib.sha256((protocol.parent / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError("chatgpt-use reference differs from lock: " + name)
    target = Path(skills_dir).resolve() if skills_dir else ROOT / ".agents/skills"
    target.mkdir(parents=True, exist_ok=True)
    links = {"gpt-orchestrator": ROOT / "gpt-orchestrator"}
    links.update({name: sp / "skills" / name for name in SELECTED})
    for name, source in links.items():
        destination = target / name
        if not (source / "SKILL.md").is_file():
            raise RuntimeError("Missing skill: " + str(source))
        if destination.is_symlink() and destination.resolve() == source.resolve():
            continue
        if destination.exists() or destination.is_symlink():
            raise RuntimeError("Refusing to replace existing skill: " + str(destination))
        destination.symlink_to(source, target_is_directory=True)
    config = ROOT / "config.json"
    if not config.exists():
        with config.open("x") as f:
            f.write((ROOT / "config.example.json").read_text())
        os.chmod(config, 0o600)
    os.chmod(ROOT / "gpt-orchestrator-cli", 0o755)
    print("Installed project skills at " + str(target))
    print("Run ./gpt-orchestrator-cli doctor. Configure model IDs in config.json before Codex execution.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skills-dir", help="Optional existing target project's .agents/skills directory")
    args = parser.parse_args()
    try:
        install(args.skills_dir)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print("Install failed: " + str(exc), file=sys.stderr)
        raise SystemExit(1)
