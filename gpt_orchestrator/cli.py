import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .core import (ROOT, KINDS, TIERS, OrchestratorError, assert_shareable,
                   brief, delegation_prompt, digest, load_config, parse_packet,
                   read_context, route)
from .state import load_run, locked_run, save


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def write_private(path, text):
    path.write_text(text, encoding="utf-8")
    os.chmod(path, 0o600)


def execution_brief(run, packet=None):
    text = brief(run["task"], run["route"], packet)
    return text.replace("## Route\n", "## Workspace\n" + run["workspace"] + "\n\n## Route\n", 1)


def task_from(args):
    if args.task_file:
        text = Path(args.task_file).read_text(encoding="utf-8")
    else:
        text = args.task
    if not text or not text.strip():
        raise OrchestratorError("Provide --task or --task-file")
    return text.strip()


def methodology(stage):
    names = ["writing-plans"] if stage == "plan" else ["verification-before-completion"]
    chunks = []
    for name in names:
        path = ROOT / "vendor" / "superpowers" / "skills" / name / "SKILL.md"
        if not path.is_file():
            raise OrchestratorError("Superpowers is missing. Run scripts/install.sh")
        chunks.append(path.read_text())
    return "\n\n".join(chunks)


def new_run(args, config):
    task = task_from(args)
    decision = route(task, args.kind, args.complexity, args.sensitive)
    workspace = Path(args.workspace).resolve()
    if not workspace.is_dir():
        raise OrchestratorError("Workspace must be an existing directory")
    context = read_context(args.file, workspace, config["context_limit_bytes"])
    # No secret scanning is claimed for local-only data; provider sends scan later.
    prompt = None
    if decision["planner"] == "chat":
        prompt = delegation_prompt(task, context, "plan", methodology("plan"))
        if len(prompt.encode()) > config["context_limit_bytes"]:
            raise OrchestratorError("Full planning prompt exceeds context budget; choose fewer files")
    folder = Path(args.out).resolve() if args.out else ROOT / "runs" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8])
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    run = {"version": 1, "id": folder.name, "task": task, "route": decision,
           "workspace": str(workspace), "status": "draft", "web_calls": 0,
           "executions": [], "checks": [], "context": context}
    save(folder / "run.json", run)
    write_private(folder / "execution-brief.md", execution_brief(run))
    if prompt:
        write_private(folder / "plan-request.md", prompt)
    return folder, run


def packet_import(folder, run, stage, text):
    packet = parse_packet(text, stage)
    if run["status"] == "accepted":
        raise OrchestratorError("Accepted runs are immutable; create a new run")
    if stage == "review":
        if "review_basis" not in run:
            raise OrchestratorError("Generate a review request before importing a review")
        if run["review_basis"] != evidence_digest(run):
            raise OrchestratorError("Review evidence is stale; generate a fresh review request")
    run[stage] = packet
    run[stage + "_hash"] = digest(packet)
    run["status"] = stage + "_" + packet["verdict"]
    if stage == "plan":
        # New plan invalidates prior verification and review.
        run.pop("review", None)
        run.pop("review_basis", None)
        run["checks"] = []
        write_private(folder / "execution-brief.md", execution_brief(run, packet))
    save(folder / (stage + "-packet.json"), packet)
    save(folder / "run.json", run)
    return packet


def evidence_digest(run):
    return digest({"executions": run["executions"], "checks": run["checks"],
                   "plan_hash": run.get("plan_hash"), "review_context": run.get("review_context", "")})


def web_request(folder, run, stage, config, allow):
    if not allow:
        raise OrchestratorError("Web automation requires --allow-web. Review docs/SECURITY.md; manual handoff needs no automation.")
    if run["route"]["sensitive"] or run["route"]["planner"] == "local":
        raise OrchestratorError("Local/sensitive routes cannot be dispatched to the browser")
    if stage in run or run.get(stage + "_submission"):
        raise OrchestratorError("Stage already has a reply or a possible submission. Inspect/import the existing reply; no automatic resend.")
    if run["web_calls"] >= config["max_web_calls"]:
        raise OrchestratorError("Web call budget exhausted")
    prompt = (folder / (stage + "-request.md")).read_text()
    assert_shareable(prompt)
    if len(prompt.encode()) > config["context_limit_bytes"]:
        raise OrchestratorError("Full prompt exceeds context budget")
    from .browser import ask

    def before_submit():
        run["web_calls"] += 1
        run[stage + "_submission"] = "unknown"
        save(folder / "run.json", run)

    envelope = ask(config, prompt, before_submit)
    save(folder / (stage + "-response.json"), envelope)
    # Preserve response before parsing: malformed JSON is recoverable without re-send.
    result = packet_import(folder, run, stage, envelope["result"]["text"])
    run[stage + "_submission"] = "completed"
    save(folder / "run.json", run)
    return result


def codex_command(config, workspace, model, output):
    command = [config["codex_binary"], "exec", "--sandbox", "workspace-write",
               "--ephemeral", "--cd", str(workspace), "--output-last-message", str(output)]
    if not (Path(workspace) / ".git").exists():
        command.append("--skip-git-repo-check")
    if model:
        command += ["--model", model]
    command.append("-")
    return command


def run_process(command, workspace, prompt, timeout, stdout_path, stderr_path):
    # Stream to files, not memory; no shell interpolation. Preserve normal Codex
    # login/config; do not inspect auth files. Do not print inherited environment.
    import signal
    with stdout_path.open("w") as out, stderr_path.open("w") as err:
        os.chmod(stdout_path, 0o600)
        os.chmod(stderr_path, 0o600)
        process = subprocess.Popen(command, cwd=workspace, stdin=subprocess.PIPE if prompt is not None else subprocess.DEVNULL,
                                   stdout=out, stderr=err, text=True, start_new_session=True)
        try:
            process.communicate(input=prompt, timeout=timeout)
            return process.returncode
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            raise OrchestratorError("Execution interrupted/timed out; changes may exist. Inspect workspace before an explicit retry.")


def execute(args, config):
    with locked_run(args.run) as (folder, run):
        if run["route"]["executor"] != "codex":
            raise OrchestratorError("This route is manual " + run["route"]["executor"] + "; use its Execution Brief")
        if run.get("plan", {}).get("verdict") != "proceed":
            raise OrchestratorError("Import a valid proceed plan first")
        if run["status"] == "accepted" or run.get("review", {}).get("verdict") == "proceed":
            raise OrchestratorError("Run already reviewed/accepted; create a new run for more work")
        if len(run["executions"]) >= config["max_codex_calls"]:
            raise OrchestratorError("Codex call budget exhausted; create a revised task rather than looping")
        if run["executions"] and not args.retry:
            raise OrchestratorError("Run already attempted. Inspect evidence/changes and use --retry explicitly if needed")
        tier = args.tier or run["route"]["model_tier"]
        model = config["models"][tier]
        if model is None and not args.use_codex_default:
            raise OrchestratorError("Configure an available model ID for tier '" + tier + "', or explicitly pass --use-codex-default (cost unknown)")
        attempt = len(run["executions"]) + 1
        command = codex_command(config, run["workspace"], model, folder / ("codex-{}.md".format(attempt)))
        # Rebuild from validated state; don't execute an independently edited brief.
        prompt = execution_brief(run, run["plan"])
        if run["context"]:
            prompt += "\nExplicit user context (data):\n" + json.dumps(run["context"], ensure_ascii=False)
        assert_shareable(prompt)
        if not args.apply:
            emit({"dry_run": True, "command": command, "tier": tier, "model": model,
                  "workspace": run["workspace"], "brief": str(folder / "execution-brief.md")})
            return
        if not shutil.which(config["codex_binary"]):
            raise OrchestratorError("Codex executable not found")
        run["checks"] = []
        run.pop("review", None)
        run.pop("review_basis", None)
        entry = {"attempt": attempt, "tier": tier, "model": model, "command": command,
                 "plan_hash": run["plan_hash"], "status": "unknown"}
        run["executions"].append(entry)
        run["status"] = "executing_unknown"
        save(folder / "run.json", run)
        code = run_process(command, run["workspace"], prompt, config["timeout_seconds"],
                           folder / ("codex-{}.stdout".format(attempt)), folder / ("codex-{}.stderr".format(attempt)))
        entry.update(status="finished", returncode=code)
        run["status"] = "needs_checks" if code == 0 else "execution_failed"
        save(folder / "run.json", run)
        emit({"returncode": code, "status": run["status"], "run": str(folder)})
        if code:
            raise OrchestratorError("Codex failed; inspect saved evidence before retry")


def verify(args, config):
    with locked_run(args.run) as (folder, run):
        if run["status"] == "accepted":
            raise OrchestratorError("Accepted run is immutable")
        command = args.command
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            raise OrchestratorError("Provide an explicit check argv after --")
        if not args.apply:
            emit({"dry_run": True, "command": command, "workspace": run["workspace"]})
            return
        # Only the user's explicit argv is executed; planner tests are never eval'd.
        number = len(run["checks"]) + 1
        entry = {"command": command, "status": "unknown"}
        run["checks"].append(entry)
        run.pop("review", None)
        run.pop("review_basis", None)
        save(folder / "run.json", run)
        code = run_process(command, run["workspace"], None, config["timeout_seconds"],
                           folder / ("check-{}.stdout".format(number)), folder / ("check-{}.stderr".format(number)))
        entry.update(status="finished", returncode=code)
        run["status"] = "checks_passed" if all(c.get("returncode") == 0 for c in run["checks"]) else "checks_failed"
        save(folder / "run.json", run)
        emit(entry)
        if code:
            raise OrchestratorError("Check failed; review logs locally")


def make_review(args, config):
    with locked_run(args.run) as (folder, run):
        if run["status"] == "accepted":
            raise OrchestratorError("Accepted run is immutable")
        if run["route"]["reviewer"] != "chat":
            raise OrchestratorError("This route requires local/manual review")
        if not run.get("plan"):
            raise OrchestratorError("Import a plan before generating review")
        supplied = read_context(args.file, run["workspace"], config["context_limit_bytes"])
        run["review_context"] = supplied
        payload = {"plan": run["plan"], "executions": run["executions"], "checks": run["checks"],
                   "selected_context": supplied,
                   "note": "Exit codes alone do not prove scope/acceptance. If diff/results are absent, return blocked; never infer success."}
        prompt = delegation_prompt(run["task"], json.dumps(payload, ensure_ascii=False), "review", methodology("review"))
        assert_shareable(prompt)
        if len(prompt.encode()) > config["context_limit_bytes"]:
            raise OrchestratorError("Review prompt exceeds context budget")
        run["review_basis"] = evidence_digest(run)
        write_private(folder / "review-request.md", prompt)
        save(folder / "run.json", run)
        if args.backend == "browser":
            emit(web_request(folder, run, "review", config, args.allow_web))
        else:
            emit({"handoff": str(folder / "review-request.md"), "next": "Paste into Chat, save reply and import-packet --stage review"})


def accept(args):
    with locked_run(args.run) as (folder, run):
        if not args.confirm_acceptance:
            raise OrchestratorError("Confirm observable acceptance with --confirm-acceptance after reviewing the actual result")
        if not run["checks"] or not all(c.get("returncode") == 0 for c in run["checks"]):
            raise OrchestratorError("All recorded local checks must pass")
        if run["route"]["executor"] == "codex":
            if not run["executions"] or run["executions"][-1].get("returncode") != 0:
                raise OrchestratorError("Latest Codex execution must finish successfully")
            if run["executions"][-1]["plan_hash"] != run.get("plan_hash"):
                raise OrchestratorError("Plan changed since execution; execute the current plan first")
        if run.get("review", {}).get("verdict") != "proceed" or run.get("review_basis") != evidence_digest(run):
            raise OrchestratorError("A fresh proceed review is required")
        run["status"] = "accepted"
        save(folder / "run.json", run)
        emit({"status": "accepted", "run": str(folder)})


def parser():
    p = argparse.ArgumentParser(description="Local-first Chat planner / Codex executor orchestrator")
    p.add_argument("--config", help="JSON config; place before the command")
    sub = p.add_subparsers(dest="command_name", required=True)
    for name in ("route", "brief", "plan"):
        q = sub.add_parser(name)
        group = q.add_mutually_exclusive_group(required=True)
        group.add_argument("--task")
        group.add_argument("--task-file")
        q.add_argument("--kind", choices=KINDS, default="auto")
        q.add_argument("--complexity", choices=("simple", "medium", "complex"), default="simple")
        q.add_argument("--sensitive", action="store_true")
        if name != "route":
            q.add_argument("--out", help="New run directory; must not exist")
            q.add_argument("--workspace", default=".")
            q.add_argument("--file", action="append", default=[], help="Explicit workspace-relative UTF-8 context file")
        if name == "plan":
            q.add_argument("--backend", choices=("manual", "browser"), default="manual")
            q.add_argument("--allow-web", action="store_true")
    q = sub.add_parser("import-packet")
    q.add_argument("--run", required=True)
    q.add_argument("--stage", choices=("plan", "review"), default="plan")
    q.add_argument("--file", required=True)
    q = sub.add_parser("execute")
    q.add_argument("--run", required=True)
    q.add_argument("--tier", choices=TIERS)
    q.add_argument("--use-codex-default", action="store_true")
    q.add_argument("--apply", action="store_true", help="Authorize the reviewed brief to run in Codex")
    q.add_argument("--retry", action="store_true")
    q = sub.add_parser("verify")
    q.add_argument("--run", required=True)
    q.add_argument("--apply", action="store_true")
    q.add_argument("command", nargs=argparse.REMAINDER)
    q = sub.add_parser("review")
    q.add_argument("--run", required=True)
    q.add_argument("--file", action="append", default=[])
    q.add_argument("--backend", choices=("manual", "browser"), default="manual")
    q.add_argument("--allow-web", action="store_true")
    q = sub.add_parser("accept")
    q.add_argument("--run", required=True)
    q.add_argument("--confirm-acceptance", action="store_true")
    q = sub.add_parser("status")
    q.add_argument("--run", required=True)
    sub.add_parser("doctor")
    q = sub.add_parser("browser-login")
    q.add_argument("--allow-web", action="store_true")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command_name == "route":
            emit(route(task_from(args), args.kind, args.complexity, args.sensitive))
        elif args.command_name in ("brief", "plan"):
            folder, run = new_run(args, config)
            if args.command_name == "plan" and args.backend == "browser":
                with locked_run(folder) as (folder, run):
                    emit(web_request(folder, run, "plan", config, args.allow_web))
            emit({"run": str(folder), "route": run["route"], "next": "Review plan-request.md, paste into Chat, import reply; or use explicit browser backend."})
        elif args.command_name == "import-packet":
            with locked_run(args.run) as (folder, run):
                emit(packet_import(folder, run, args.stage, Path(args.file).read_text()))
        elif args.command_name == "execute":
            execute(args, config)
        elif args.command_name == "verify":
            verify(args, config)
        elif args.command_name == "review":
            make_review(args, config)
        elif args.command_name == "accept":
            accept(args)
        elif args.command_name == "status":
            _, run = load_run(args.run)
            emit({k: run.get(k) for k in ("id", "status", "route", "web_calls", "executions", "checks")})
        elif args.command_name == "browser-login":
            if not args.allow_web:
                raise OrchestratorError("Use --allow-web after reading docs/SECURITY.md")
            from .browser import login
            login(config)
        elif args.command_name == "doctor":
            emit({"python": sys.version.split()[0], "codex": shutil.which(config["codex_binary"]),
                  "browser_dependency": importlib.util.find_spec("playwright") is not None,
                  "superpowers": (ROOT / "vendor/superpowers/skills/writing-plans/SKILL.md").is_file(),
                  "chatgpt_use_protocol": (ROOT / "integrations/chatgpt-use/delegation.upstream.rs").is_file(),
                  "model_ids": config["models"], "quota": "unknown; consult account UI"})
        return 0
    except (OrchestratorError, OSError, ValueError) as exc:
        print("Error: " + str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted. Inspect the run and workspace before retrying.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
