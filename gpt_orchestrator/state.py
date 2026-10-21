import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from .core import OrchestratorError


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(prefix=".write-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def load_run(folder):
    path = Path(folder).resolve()
    value = json.loads((path / "run.json").read_text())
    if value.get("version") != 1:
        raise OrchestratorError("Unsupported run version")
    return path, value


@contextmanager
def locked_run(folder):
    import fcntl
    path = Path(folder).resolve()
    with (path / ".lock").open("a+") as f:
        os.chmod(f.name, 0o600)
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise OrchestratorError("Run is busy")
        _, run = load_run(path)
        yield path, run
