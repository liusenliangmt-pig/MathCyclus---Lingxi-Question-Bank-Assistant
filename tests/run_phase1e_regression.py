import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import time
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")


EXPECTED_MATH_SHA = "250092C5158BA3A2185253AC0F0A141E5AE74C5C668A4CC74B208309EDE84386"
TEMP_DUP_ID = "PHY-TEMP-1E-DUP"
TEMP_INVALID_ID = "PHY-TEMP-1E-INVALID"
TEMP_FAIL_ID = "PHY-TEMP-1E-FAIL"
def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def read_csv_rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def add(results, name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)})


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
    detail = {
        "returncode": proc.returncode,
        "elapsed_seconds": elapsed,
        "stdout_tail": proc.stdout[-2500:],
        "stderr_tail": proc.stderr[-2500:],
    }
    add(results, name, proc.returncode == 0, detail)
    return proc


def import_project(project_root: Path, module_root: Path):
    sys.path.insert(0, str(module_root))
    from utils.core_config import build_runtime_config
    from utils.csv_ops import read_csv_index
    from utils.init_csv_index import iter_real_question_files, rebuild_index
    from utils.latex_ops import parse_meta_data
    from utils.physics_question_ops import (
        ANSWER_FIELD,
        CHAPTER_FIELD,
        DIFFICULTY_FIELD,
        GRADE_FIELD,
        ID_FIELD,
        KNOWLEDGE_POINT_FIELD,
        PROBLEM_FIELD,
        QUESTION_TYPE_FIELD,
        REMARK_FIELD,
        SCORE_FIELD,
        SOLUTION_FIELD,
        SOURCE_FIELD,
        STAGE_FIELD,
        TAGS_FIELD,
        PhysicsQuestionError,
        build_target_path,
        save_existing_physics_question_edit,
        save_new_physics_question,
        validate_physics_index_integrity,
    )
    import utils.physics_question_ops as physics_question_ops

    return {
        "build_runtime_config": build_runtime_config,
        "read_csv_index": read_csv_index,
        "iter_real_question_files": iter_real_question_files,
        "rebuild_index": rebuild_index,
        "parse_meta_data": parse_meta_data,
        "physics_question_ops": physics_question_ops,
        "PhysicsQuestionError": PhysicsQuestionError,
        "build_target_path": build_target_path,
        "save_existing_physics_question_edit": save_existing_physics_question_edit,
        "save_new_physics_question": save_new_physics_question,
        "validate_physics_index_integrity": validate_physics_index_integrity,
        "fields": {
            "ANSWER_FIELD": ANSWER_FIELD,
            "CHAPTER_FIELD": CHAPTER_FIELD,
            "DIFFICULTY_FIELD": DIFFICULTY_FIELD,
            "GRADE_FIELD": GRADE_FIELD,
            "ID_FIELD": ID_FIELD,
            "KNOWLEDGE_POINT_FIELD": KNOWLEDGE_POINT_FIELD,
            "PROBLEM_FIELD": PROBLEM_FIELD,
            "QUESTION_TYPE_FIELD": QUESTION_TYPE_FIELD,
            "REMARK_FIELD": REMARK_FIELD,
            "SCORE_FIELD": SCORE_FIELD,
            "SOLUTION_FIELD": SOLUTION_FIELD,
            "SOURCE_FIELD": SOURCE_FIELD,
            "STAGE_FIELD": STAGE_FIELD,
            "TAGS_FIELD": TAGS_FIELD,
        },
    }


def count_id_in_files(runtime, api, qid):
    count = 0
    for file_path in api["iter_real_question_files"](runtime):
        path = Path(file_path)
        meta, _ = api["parse_meta_data"](path.read_text(encoding="utf-8"))
        if meta.get("ID") == qid:
            count += 1
    return count


def cleanup_temp_questions(project_root, physics_runtime, api):
    for qid in (TEMP_DUP_ID, TEMP_INVALID_ID, TEMP_FAIL_ID):
        for file_path in list(api["iter_real_question_files"](physics_runtime)):
            path = Path(file_path)
            meta, _ = api["parse_meta_data"](path.read_text(encoding="utf-8"))
            if meta.get("ID") == qid and path.name == f"{qid}.tex":
                path.unlink()
        for artifact in Path(physics_runtime.chapters_dir).rglob(f".{qid}.tex.*"):
            artifact.unlink()
    outputs = project_root / "outputs"
    for child in ("physics_phase1_smoke", "physics_phase1d2_write_smoke", "physics_phase1d2_move_smoke"):
        target = outputs / child
        if target.exists():
            shutil.rmtree(target)
    api["rebuild_index"]("physics", base_dir=str(project_root), sync_artifacts=False, write_report=False)


def baseline_checks(results, project_root, math_runtime, physics_runtime, api):
    math_csv = Path(math_runtime.csv_index_path)
    physics_csv = Path(physics_runtime.csv_index_path)
    math_rows = read_csv_rows(math_csv)
    physics_rows = read_csv_rows(physics_csv)
    math_files = [Path(math_runtime.chapters_dir) / (row.get("相对文件路径") or "") for row in math_rows]
    physics_files = [Path(physics_runtime.chapters_dir) / (row.get("相对文件路径") or "") for row in physics_rows]
    math_ids = [row.get("题目ID", "") for row in math_rows]
    physics_ids = [row.get("题目ID", "") for row in physics_rows]
    real_physics_files = list(api["iter_real_question_files"](physics_runtime))
    expected_physics_count = 8
    add(results, "math index rows 70", len(math_rows) == 70, len(math_rows))
    add(results, "physics source files 8", len(real_physics_files) == expected_physics_count, len(real_physics_files))
    add(results, "physics index rows 8", len(physics_rows) == expected_physics_count, len(physics_rows))
    add(results, "physics index columns 44", len(physics_rows[0]) == 44, len(physics_rows[0]) if physics_rows else 0)
    add(results, "math sha baseline", sha256_of(math_csv) == EXPECTED_MATH_SHA, sha256_of(math_csv))
    add(results, "math paths exist", all(path.exists() for path in math_files), "checked")
    add(results, "physics paths exist", all(path.exists() for path in physics_files), "checked")
    add(results, "math index excludes physics", not any("chapters_physics" in (row.get("相对文件路径", "").replace("\\", "/")) for row in math_rows), "checked")
    add(results, "physics index excludes math", not any("chapters/" in (row.get("相对文件路径", "").replace("\\", "/")) for row in physics_rows), "checked")
    add(results, "math ids unique", len(math_ids) == len(set(math_ids)), "checked")
    add(results, "physics ids unique", len(physics_ids) == len(set(physics_ids)), "checked")
    add(results, "cross ids unique", not (set(math_ids) & set(physics_ids) - {""}), "checked")
    residuals = [
        str(path.relative_to(project_root))
        for path in project_root.rglob("*")
        if path.is_file()
        and ("PHY-TEMP" in path.name or path.name.endswith(".tmp") or "movebak" in path.name)
    ]
    add(results, "no temp residuals", not residuals, residuals[:10])


def regression_app_test(results, project_root):
    try:
        from streamlit.testing.v1 import AppTest
    except Exception as exc:
        add(results, "streamlit AppTest import", False, repr(exc))
        return

    PHYSICS = "\u7269\u7406"
    MATH = "\u6570\u5b66"
    ADV = "\u4e09\u7ea7\u67e5\u627e"
    FULL = "\u5168\u6587\u5185\u5bb9"
    QID = "\u9898\u76eeID"
    SUBJECT = "\u77e5\u8bc6\u677f\u5757"
    TAG = "\u6807\u7b7e"
    FIRST = "\u4e00\u7ea7\u5173\u952e\u8bcd"

    def field_boxes(at):
        return [
            sb for sb in at.selectbox
            if QID in [str(x) for x in sb.options]
            and SUBJECT in [str(x) for x in sb.options]
            and TAG in [str(x) for x in sb.options]
        ]

    def values(*element_lists):
        items = []
        for element_list in element_lists:
            items.extend(list(element_list))
        return [str(item.value) for item in items]

    at = AppTest.from_file(str(project_root / "question_bank_app.py"), default_timeout=25)
    at.run()
    if at.exception:
        add(results, "AppTest initial load", False, str(at.exception))
        return
    add(results, "math default loads", any("70" in text for text in values(at.markdown, at.text, at.metric)), "loaded")

    at.sidebar.selectbox[0].set_value(PHYSICS)
    at.run()
    if at.exception:
        add(results, "AppTest switch physics", False, str(at.exception))
        return

    radio = at.sidebar.radio[0]
    radio.set_value(next(opt for opt in radio.options if ADV in str(opt)))
    at.run()
    boxes = field_boxes(at)
    boxes[0].set_value(QID)
    boxes[1].set_value(SUBJECT)
    boxes[2].set_value(TAG)
    at.run()
    physics_fields = [field_boxes(at)[i].value for i in range(3)]
    add(results, "physics advanced fields persist after rerun", physics_fields == [QID, SUBJECT, TAG], physics_fields)

    for item in at.text_input:
        if item.label == FIRST:
            item.input("PHY-JH-0003")
    at.run()
    next(btn for btn in at.button if "\u67e5" in str(btn.label)).click()
    at.run()
    success_text = "\n".join(str(x.value) for x in at.success)
    page_text = "\n".join(values(at.markdown, at.text)) + "\n" + success_text
    add(results, "physics search by id returns one", "\u627e\u5230 1" in page_text and "PHY-JH-0003" in page_text, page_text[-500:])
    physics_fields_after = [field_boxes(at)[i].value for i in range(3)]
    add(results, "physics advanced fields persist after search", physics_fields_after == [QID, SUBJECT, TAG], physics_fields_after)

    at.sidebar.selectbox[0].set_value(MATH)
    at.run()
    radio = at.sidebar.radio[0]
    radio.set_value(next(opt for opt in radio.options if ADV in str(opt)))
    at.run()
    math_fields = [field_boxes(at)[i].value for i in range(3)]
    add(results, "math advanced fields isolated", math_fields == [FULL, FULL, FULL], math_fields)


def exception_recovery_checks(results, project_root, math_runtime, physics_runtime, api):
    fields = api["fields"]
    math_csv = Path(math_runtime.csv_index_path)
    physics_csv = Path(physics_runtime.csv_index_path)
    math_bytes = math_csv.read_bytes()
    physics_bytes = physics_csv.read_bytes()
    math_hash_before = sha256_of(math_csv)
    base_payload = {
        fields["ID_FIELD"]: TEMP_FAIL_ID,
        fields["STAGE_FIELD"]: "初中",
        fields["GRADE_FIELD"]: "八年级",
        fields["CHAPTER_FIELD"]: "力与运动",
        fields["KNOWLEDGE_POINT_FIELD"]: "事务测试",
        fields["QUESTION_TYPE_FIELD"]: "计算题",
        fields["DIFFICULTY_FIELD"]: "1.0",
        fields["SCORE_FIELD"]: "5",
        fields["TAGS_FIELD"]: "1E测试",
        fields["SOURCE_FIELD"]: "本地原创测试题",
        fields["REMARK_FIELD"]: "1E异常恢复测试",
        fields["PROBLEM_FIELD"]: "物体以 $1\\,\\mathrm{m/s}$ 匀速运动 $2\\,\\mathrm{s}$，求路程。",
        fields["ANSWER_FIELD"]: "$2\\,\\mathrm{m}$。",
        fields["SOLUTION_FIELD"]: "$s=vt=1\\,\\mathrm{m/s}\\times2\\,\\mathrm{s}=2\\,\\mathrm{m}$。",
    }

    try:
        existing = api["read_csv_index"](runtime_config=physics_runtime)[0]
        dup_payload = dict(base_payload)
        dup_payload[fields["ID_FIELD"]] = existing["题目ID"]
        try:
            api["save_new_physics_question"](dup_payload, physics_runtime)
            add(results, "duplicate physics id blocked", False, "save succeeded unexpectedly")
        except Exception as exc:
            add(results, "duplicate physics id blocked", True, type(exc).__name__)

        missing_payload = dict(base_payload)
        missing_payload[fields["ID_FIELD"]] = TEMP_INVALID_ID
        missing_payload[fields["ANSWER_FIELD"]] = ""
        try:
            api["save_new_physics_question"](missing_payload, physics_runtime)
            add(results, "missing answer blocked", False, "save succeeded unexpectedly")
        except Exception as exc:
            add(results, "missing answer blocked", True, type(exc).__name__)

        bad_path_payload = dict(base_payload)
        bad_path_payload[fields["ID_FIELD"]] = "..\\bad"
        try:
            api["build_target_path"](bad_path_payload, physics_runtime)
            add(results, "illegal path blocked", False, "path accepted unexpectedly")
        except Exception as exc:
            add(results, "illegal path blocked", True, type(exc).__name__)

        original_rebuild = api["physics_question_ops"].rebuild_index

        def fail_rebuild(*_args, **_kwargs):
            raise RuntimeError("simulated phase1e index failure")

        api["physics_question_ops"].rebuild_index = fail_rebuild
        try:
            try:
                api["save_new_physics_question"](base_payload, physics_runtime)
                add(results, "index failure rolls back new file", False, "save succeeded unexpectedly")
            except RuntimeError:
                file_count = count_id_in_files(physics_runtime, api, TEMP_FAIL_ID)
                add(results, "index failure rolls back new file", file_count == 0 and sha256_of(math_csv) == math_hash_before, f"file_count={file_count}")
        finally:
            api["physics_question_ops"].rebuild_index = original_rebuild

        save_result = api["save_new_physics_question"](base_payload, physics_runtime)
        old_path = Path(save_result.file_path)
        move_payload = dict(base_payload)
        move_payload[fields["CHAPTER_FIELD"]] = "光现象"
        move_payload[fields["KNOWLEDGE_POINT_FIELD"]] = "移动失败恢复"
        api["physics_question_ops"].rebuild_index = fail_rebuild
        try:
            try:
                api["save_existing_physics_question_edit"](old_path, move_payload, physics_runtime)
                add(results, "move failure restores old file", False, "move succeeded unexpectedly")
            except RuntimeError:
                new_path = Path(physics_runtime.chapters_dir) / "初中" / "光现象" / f"{TEMP_FAIL_ID}.tex"
                ok = old_path.exists() and not new_path.exists() and count_id_in_files(physics_runtime, api, TEMP_FAIL_ID) == 1
                add(results, "move failure restores old file", ok, f"old={old_path.exists()} new={new_path.exists()}")
        finally:
            api["physics_question_ops"].rebuild_index = original_rebuild

        original_rebuild = api["physics_question_ops"].rebuild_index

        def corrupt_math_during_rebuild(*args, **kwargs):
            result = original_rebuild(*args, **kwargs)
            math_csv.write_bytes(math_bytes + b"\n# phase1e hash corruption")
            return result

        api["physics_question_ops"].rebuild_index = corrupt_math_during_rebuild
        try:
            hash_payload = dict(base_payload)
            hash_payload[fields["ID_FIELD"]] = TEMP_DUP_ID
            try:
                api["save_new_physics_question"](hash_payload, physics_runtime)
                add(results, "math hash mismatch blocks physics write", False, "save succeeded unexpectedly")
            except Exception as exc:
                file_count = count_id_in_files(physics_runtime, api, TEMP_DUP_ID)
                add(results, "math hash mismatch blocks physics write", file_count == 0, f"{type(exc).__name__}; file_count={file_count}")
        finally:
            api["physics_question_ops"].rebuild_index = original_rebuild
            math_csv.write_bytes(math_bytes)

    finally:
        math_csv.write_bytes(math_bytes)
        physics_csv.write_bytes(physics_bytes)
        cleanup_temp_questions(project_root, physics_runtime, api)
        math_csv.write_bytes(math_bytes)
        physics_csv.write_bytes(physics_bytes)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--module-root", default=None)
    parser.add_argument("--python-executable", default=None)
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else Path(__file__).resolve().parents[1]
    module_root = Path(args.module_root).resolve() if args.module_root else project_root
    child_python = str(Path(args.python_executable).resolve()) if args.python_executable else sys.executable
    api = import_project(project_root, module_root)
    math_runtime = api["build_runtime_config"]("mathematics", base_dir=str(project_root))
    physics_runtime = api["build_runtime_config"]("physics", base_dir=str(project_root))
    math_csv = Path(math_runtime.csv_index_path)
    physics_csv = Path(physics_runtime.csv_index_path)
    initial_math_bytes = math_csv.read_bytes()
    initial_physics_bytes = physics_csv.read_bytes()
    initial_math_sha = sha256_of(math_csv)
    initial_physics_sha = sha256_of(physics_csv)
    results = []

    py_files = [
        "question_bank_app.py",
        "utils/discipline_config.py",
        "utils/core_config.py",
        "utils/csv_ops.py",
        "utils/init_csv_index.py",
        "utils/physics_question_ops.py",
        "tests/physics_phase1_smoke.py",
        "tests/physics_phase1d2_write_smoke.py",
        "tests/physics_phase1d2_move_smoke.py",
        "tests/run_phase1e_regression.py",
    ]

    try:
        cleanup_temp_questions(project_root, physics_runtime, api)
        baseline_checks(results, project_root, math_runtime, physics_runtime, api)
        run_command(results, "py_compile", [child_python, "-m", "py_compile", *py_files], project_root)
        run_command(results, "physics_phase1_smoke", [child_python, "tests/physics_phase1_smoke.py"], project_root)
        run_command(results, "physics_phase1d2_write_smoke", [child_python, "tests/physics_phase1d2_write_smoke.py"], project_root)
        run_command(results, "physics_phase1d2_move_smoke", [child_python, "tests/physics_phase1d2_move_smoke.py"], project_root)
        exception_recovery_checks(results, project_root, math_runtime, physics_runtime, api)
        regression_app_test(results, project_root)
    except Exception as exc:
        add(results, "phase1e runner unexpected exception", False, f"{type(exc).__name__}: {exc}")
    finally:
        try:
            cleanup_temp_questions(project_root, physics_runtime, api)
            if math_csv.read_bytes() != initial_math_bytes:
                math_csv.write_bytes(initial_math_bytes)
                add(results, "restore math index bytes", True, "restored original bytes")
            if physics_csv.read_bytes() != initial_physics_bytes:
                physics_csv.write_bytes(initial_physics_bytes)
                add(results, "restore physics index bytes", True, "restored original bytes")
            math_runtime = api["build_runtime_config"]("mathematics", base_dir=str(project_root))
            physics_runtime = api["build_runtime_config"]("physics", base_dir=str(project_root))
            baseline_checks(results, project_root, math_runtime, physics_runtime, api)
            api["validate_physics_index_integrity"](physics_runtime, expected_math_sha256=EXPECTED_MATH_SHA.lower())
            add(results, "validate physics index integrity", True, "ok")
        except Exception as exc:
            add(results, "final cleanup/integrity", False, f"{type(exc).__name__}: {exc}")

    final_math_bytes = math_csv.read_bytes()
    final_physics_rows = read_csv_rows(physics_csv)
    final_temp_residuals = [
        str(path.relative_to(project_root))
        for path in project_root.rglob("*")
        if path.is_file()
        and ("PHY-TEMP" in path.name or path.name.endswith(".tmp") or "movebak" in path.name)
    ]
    add(results, "math index bytes unchanged", final_math_bytes == initial_math_bytes, sha256_of(math_csv))
    add(results, "initial math sha recorded", initial_math_sha == EXPECTED_MATH_SHA, initial_math_sha)
    add(results, "physics index restored to initial bytes", physics_csv.read_bytes() == initial_physics_bytes, sha256_of(physics_csv))
    add(results, "no final temp residuals", not final_temp_residuals, final_temp_residuals[:10])

    ok = all(item["ok"] for item in results)
    summary = {
        "status": "PASS" if ok else "FAIL",
        "project_root": str(project_root),
        "python_executable": child_python,
        "initial_math_sha": initial_math_sha,
        "initial_physics_sha": initial_physics_sha,
        "results": results,
        "math_sha": sha256_of(math_csv),
        "physics_sha": sha256_of(physics_csv),
        "math_rows": len(read_csv_rows(math_csv)),
        "physics_rows": len(final_physics_rows),
        "physics_columns": len(final_physics_rows[0]) if final_physics_rows else 0,
    }
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
