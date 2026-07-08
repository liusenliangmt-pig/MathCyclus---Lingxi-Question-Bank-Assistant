import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def configure_stdio():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")


def run_command(results, name, cmd, cwd):
    start = time.perf_counter()
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        timeout=1200,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    elapsed = round(time.perf_counter() - start, 3)
    results.append(
        {
            "name": name,
            "ok": proc.returncode == 0,
            "elapsed_seconds": elapsed,
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-2500:],
            "stderr_tail": proc.stderr[-2500:],
        }
    )
    return proc


def main():
    configure_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--module-root", default=None)
    parser.add_argument("--python-executable", default=None)
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else Path(__file__).resolve().parents[1]
    module_root = Path(args.module_root).resolve() if args.module_root else project_root
    python = str(Path(args.python_executable).resolve()) if args.python_executable else sys.executable
    results = []

    run_command(
        results,
        "phase1e regression",
        [python, str(project_root / "tests" / "run_phase1e_regression.py"), "--project-root", str(project_root), "--module-root", str(module_root), "--python-executable", python],
        project_root,
    )
    run_command(
        results,
        "phase2a import review smoke",
        [python, str(project_root / "tests" / "physics_phase2a_import_review_smoke.py"), "--project-root", str(project_root), "--module-root", str(module_root)],
        project_root,
    )
    run_command(
        results,
        "phase2a import review page smoke",
        [python, str(project_root / "tests" / "phase2a_import_review_page_smoke.py"), "--project-root", str(project_root), "--module-root", str(module_root)],
        project_root,
    )
    run_command(
        results,
        "phase2a sidebar css smoke",
        [python, str(project_root / "tests" / "phase2a_sidebar_css_smoke.py")],
        project_root,
    )

    ok = all(item["ok"] for item in results)
    summary = {
        "status": "PASS" if ok else "FAIL",
        "project_root": str(project_root),
        "python_executable": python,
        "results": results,
    }
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
