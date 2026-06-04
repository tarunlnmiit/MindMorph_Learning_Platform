# Runs a learner's Python solution against generated unit tests and reports pass/fail.
#
# Uses a tiny self-contained runner (no pytest dependency in the child) so grading works in any
# Python environment. The runner imports the test module, runs every `test_*` function, and prints
# a parseable summary. Module-level `assert`s (when the grader emits bare asserts) execute at import.
#
# SECURITY — READ THIS:
#   This is a HANG-GUARD for a LOCAL, SINGLE-USER prototype. It is NOT a security sandbox.
#   It runs the submitted code in a separate subprocess with a wall-clock timeout (primary guard),
#   a fresh temp working directory, an environment scrubbed of API-key secrets, and best-effort POSIX
#   resource limits (CPU / file size). It CANNOT block network access or filesystem access outside
#   the temp dir, and memory limits (RLIMIT_AS) are unreliable on macOS. The risk is acceptable here
#   because it executes mostly the user's own code on the user's own machine.
#
#   Any hosted or multi-user deployment MUST move grading into the containerized Evaluation Service
#   (architecture §4) with real isolation (gVisor / Firecracker / a locked-down container).

import os
import re
import sys
import signal
import subprocess
import tempfile
from typing import Any, Dict, List

try:
    import resource  # POSIX only
except ImportError:  # pragma: no cover - Windows
    resource = None

DEFAULT_TIMEOUT_SECONDS = 10
# RLIMIT_CPU counts from fork, so interpreter startup eats into this before learner code runs;
# keep it comfortably above the wall-clock timeout (which is the real guard).
_CPU_SECONDS = 15
_MAX_FILE_BYTES = 16 * 1024 * 1024  # 16 MB cap on files the solution can write
_KILL_DRAIN_SECONDS = 5  # bound the post-SIGKILL pipe drain so it can never hang the UI thread

# Substrings that mark an env var as a secret to strip before handing the env to the child.
_SECRET_MARKERS = ("API_KEY", "APIKEY", "TOKEN", "SECRET", "PASSWORD", "GROQ", "OPENROUTER",
                   "SERPER", "APIFY", "GITHUB", "OPENAI", "ANTHROPIC", "LANGCHAIN", "LANGSMITH",
                   "HUGGINGFACE", "HF_")

_SUMMARY_RE = re.compile(r"^MINDMORPH_SUMMARY\s+(\d+)\s+(\d+)\s*$", re.MULTILINE)

# Self-contained runner written into the temp dir. No third-party imports — works without pytest.
_RUNNER_SRC = '''\
import importlib, sys, traceback

passed, failures = 0, []
try:
    mod = importlib.import_module("test_solution")
except BaseException as e:
    # Import-time failure: bad import (e.g. solution missing the required name) or a failing
    # module-level assert. Report as a hard failure with the cause.
    print("MINDMORPH_FAILURE collect: " + "".join(traceback.format_exception_only(type(e), e)).strip())
    print("MINDMORPH_SUMMARY 0 0")
    sys.exit(0)

tests = [(n, getattr(mod, n)) for n in dir(mod) if n.startswith("test") and callable(getattr(mod, n))]
if not tests:
    # No test functions, but the module imported cleanly => any bare module-level asserts passed.
    print("MINDMORPH_SUMMARY 1 1")
    sys.exit(0)

for name, fn in tests:
    try:
        fn()
        passed += 1
    except BaseException as e:
        msg = "".join(traceback.format_exception_only(type(e), e)).strip()
        failures.append(name + ": " + msg)

for f in failures:
    print("MINDMORPH_FAILURE " + f)
print("MINDMORPH_SUMMARY %d %d" % (passed, len(tests)))
'''


def _apply_resource_limits():  # pragma: no cover - runs in the child process
    """Best-effort defense-in-depth in the child before exec. Never raise (would kill the child)."""
    if resource is None:
        return
    for limit, value in ((resource.RLIMIT_CPU, _CPU_SECONDS), (resource.RLIMIT_FSIZE, _MAX_FILE_BYTES)):
        try:
            resource.setrlimit(limit, (value, value))
        except (ValueError, OSError):
            # Platform refused this limit (e.g. macOS quirks) — skip it; timeout remains the guard.
            pass


def _child_env(tmp: str) -> Dict[str, str]:
    """Inherit the parent env (so the interpreter finds its own stdlib/site-packages) but strip
    every API-key / token secret, and point PYTHONPATH at the temp dir so `import solution` works."""
    env = {k: v for k, v in os.environ.items()
           if not any(marker in k.upper() for marker in _SECRET_MARKERS)}
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = tmp + (os.pathsep + existing_pp if existing_pp else "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _parse_summary(output: str):
    """Return (passed, total) from the runner's summary line, or None if absent."""
    m = _SUMMARY_RE.search(output or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _extract_failures(output: str) -> List[str]:
    """The runner's per-test failure lines."""
    return [ln[len("MINDMORPH_FAILURE "):].strip()
            for ln in (output or "").splitlines() if ln.startswith("MINDMORPH_FAILURE ")]


def execute_tests(
    solution_code: str,
    test_code: str,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Run `test_code` against `solution_code` in an isolated subprocess (no pytest dependency).

    The tests import the solution as `import solution` / `from solution import ...`.
    Returns: {passed, total, failures, score, stdout, timed_out}. Never raises on test failure.
    """
    if not test_code or not test_code.strip():
        return {"passed": 0, "total": 0, "failures": [], "score": 0.0,
                "stdout": "No unit tests were generated.", "timed_out": False}

    tmp = tempfile.mkdtemp(prefix="mindmorph_grade_")
    try:
        with open(os.path.join(tmp, "solution.py"), "w") as f:
            f.write(solution_code or "")
        with open(os.path.join(tmp, "test_solution.py"), "w") as f:
            f.write(test_code)
        with open(os.path.join(tmp, "_runner.py"), "w") as f:
            f.write(_RUNNER_SRC)

        env = _child_env(tmp)
        stdout, _returncode, timed_out = _run([sys.executable, "_runner.py"], tmp, env, timeout)
        if timed_out:
            return {"passed": 0, "total": 0, "failures": ["Execution timed out (possible infinite loop)."],
                    "score": 0.0, "stdout": (stdout or "")[-4000:], "timed_out": True}

        parsed = _parse_summary(stdout or "")
        if parsed is None:
            # Runner crashed before printing a summary (e.g. syntax error in the solution import).
            return {"passed": 0, "total": 0, "failures": _extract_failures(stdout) or ["Could not run the tests."],
                    "score": 0.0, "stdout": (stdout or "")[-4000:], "timed_out": False}

        passed, total = parsed
        score = (passed / total * 100.0) if total else 0.0
        return {
            "passed": passed,
            "total": total,
            "failures": _extract_failures(stdout),
            "score": score,
            "stdout": (stdout or "")[-4000:],
            "timed_out": False,
        }
    finally:
        _rmtree_quiet(tmp)


def _run(cmd, cwd, env, timeout):
    """Run `cmd` in an isolated subprocess. Returns (stdout, returncode, timed_out)."""
    popen_kwargs: Dict[str, Any] = dict(
        cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env,
    )
    if os.name == "posix":
        # New session => own process group, so a timeout can kill grandchildren too.
        popen_kwargs["start_new_session"] = True
        popen_kwargs["preexec_fn"] = _apply_resource_limits

    proc = subprocess.Popen(cmd, **popen_kwargs)
    try:
        stdout, _ = proc.communicate(timeout=timeout)
        return stdout, proc.returncode, False
    except subprocess.TimeoutExpired:
        _kill_process_tree(proc)
        # Bound the drain: the wall-clock guard already fired, so never wait unbounded here.
        try:
            stdout, _ = proc.communicate(timeout=_KILL_DRAIN_SECONDS)
        except subprocess.TimeoutExpired:
            stdout = ""
        return stdout, proc.returncode, True


def _kill_process_tree(proc: "subprocess.Popen"):
    try:
        if os.name == "posix":
            # start_new_session=True makes the child a session/group leader, so pgid == pid.
            # Use proc.pid directly to avoid an os.getpgid() race if the child already exited.
            os.killpg(proc.pid, signal.SIGKILL)
        else:  # pragma: no cover
            proc.kill()
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except OSError:
            pass


def _rmtree_quiet(path: str):
    import shutil
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


if __name__ == "__main__":
    demo_solution = "def add(a, b):\n    return a + b\n"
    demo_tests = "from solution import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"
    print(execute_tests(demo_solution, demo_tests))
