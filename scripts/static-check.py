#!/usr/bin/env python3
"""Parse/compile project Python sources without writing caches outside the project."""
import ast
from pathlib import Path

root = Path(__file__).resolve().parents[1]
paths = sorted(path for name in ("gpt_orchestrator", "scripts", "tests") for path in (root / name).rglob("*.py"))
for path in paths:
    source = path.read_text(encoding="utf-8")
    ast.parse(source, filename=str(path))
    compile(source, str(path), "exec", dont_inherit=True)
print("Syntax/compile checks passed for {} Python files.".format(len(paths)))
