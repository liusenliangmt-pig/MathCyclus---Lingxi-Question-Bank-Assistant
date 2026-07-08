import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path


TEMP_ID = "PHY-TEMP-1D2-0001"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_result(results, name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--module-root", default=None)
    args = parser.parse_args()

    default_root = Path(__file__).resolve().parents[1]
    project_root = Path(args.project_root).resolve() if args.project_root else default_root
    module_root = Path(args.module_root).resolve() if args.module_root else project_root
    sys.path.insert(0, str(module_root))

    from utils.core_config import build_runtime_config
    from utils.init_csv_index import iter_real_question_files, rebuild_index
    from utils.csv_ops import read_csv_index
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
        load_physics_question_payload,
        save_existing_physics_question_edit,
        save_new_physics_question,
        validate_physics_index_integrity,
    )
    import utils.physics_question_ops as physics_question_ops
    import question_bank_app

    results = []
    physics_runtime = build_runtime_config("physics", base_dir=str(project_root))
    math_runtime = build_runtime_config("mathematics", base_dir=str(project_root))
    physics_csv = Path(physics_runtime.csv_index_path)
    math_csv = Path(math_runtime.csv_index_path)
    physics_csv_before = physics_csv.read_bytes()
    math_hash_before = sha256_of(math_csv)
    temp_path = Path(physics_runtime.chapters_dir) / "初中" / "力与运动" / f"{TEMP_ID}.tex"
    created_path = None
    initial_physics_count = 0
    outputs_dir = project_root / "outputs" / "physics_phase1d2_write_smoke"

    try:
        initial_files = list(iter_real_question_files(physics_runtime))
        initial_physics_count = len(initial_files)
        initial_math_rows = read_csv_index(runtime_config=math_runtime)
        initial_index_rows = read_csv_index(runtime_config=physics_runtime)
        add_result(results, "initial physics source/index count match", initial_physics_count == len(initial_index_rows), f"source={initial_physics_count}; index={len(initial_index_rows)}")
        add_result(results, "initial math count 70", len(initial_math_rows) == 70, f"count={len(initial_math_rows)}")
        add_result(results, "temp file absent before test", not temp_path.exists(), str(temp_path))
        if temp_path.exists():
            raise RuntimeError(f"Temp file already exists before test: {temp_path}")

        payload = {
            ID_FIELD: TEMP_ID,
            STAGE_FIELD: "初中",
            GRADE_FIELD: "八年级",
            CHAPTER_FIELD: "力与运动",
            KNOWLEDGE_POINT_FIELD: "二力平衡",
            QUESTION_TYPE_FIELD: "计算题",
            DIFFICULTY_FIELD: "1.0",
            SCORE_FIELD: "6",
            TAGS_FIELD: "1D-2测试",
            SOURCE_FIELD: "本地原创测试题",
            REMARK_FIELD: "1D-2临时写入测试题",
            PROBLEM_FIELD: "一个物体受到两个方向相反、大小均为 $5\\,\\mathrm{N}$ 的水平拉力。求物体所受合力的大小。",
            ANSWER_FIELD: "合力大小为 $0\\,\\mathrm{N}$。",
            SOLUTION_FIELD: "两个力方向相反且大小相等，合力为 $F=5\\,\\mathrm{N}-5\\,\\mathrm{N}=0\\,\\mathrm{N}$。",
        }

        original_rebuild_index = physics_question_ops.rebuild_index

        def fail_rebuild_index(*_args, **_kwargs):
            raise RuntimeError("simulated physics index refresh failure")

        physics_question_ops.rebuild_index = fail_rebuild_index
        try:
            try:
                save_new_physics_question(payload, physics_runtime)
                rollback_failed = False
            except RuntimeError:
                rollback_failed = True
        finally:
            physics_question_ops.rebuild_index = original_rebuild_index

        add_result(results, "simulated save failure raised", rollback_failed, "simulated index refresh failure")
        add_result(results, "rollback removed temp file", not temp_path.exists(), str(temp_path))
        add_result(results, "rollback restored physics csv", physics_csv.read_bytes() == physics_csv_before, "restored")
        add_result(results, "rollback kept math hash", sha256_of(math_csv) == math_hash_before, sha256_of(math_csv))

        save_result = save_new_physics_question(payload, physics_runtime)
        created_path = Path(save_result.file_path)
        add_result(results, "new physics save success", created_path.exists(), created_path)
        add_result(results, "new file under chapters_physics", "chapters_physics" in str(created_path), created_path)
        after_create_count = len(list(iter_real_question_files(physics_runtime)))
        add_result(results, "physics count increments after create", after_create_count == initial_physics_count + 1, f"count={after_create_count}")
        add_result(results, "math hash unchanged after create", sha256_of(math_csv) == math_hash_before, sha256_of(math_csv))

        question_bank_app.get_active_runtime_config = lambda: physics_runtime
        question_bank_app.APP_ROOT = str(project_root)
        question_bank_app.st.cache_data.clear()
        runtime_rows = question_bank_app._get_runtime_question_rows(physics_runtime)
        search_rows = question_bank_app._filter_runtime_rows(runtime_rows, keyword=TEMP_ID)
        add_result(results, "new question searchable", len(search_rows) == 1, f"count={len(search_rows)}")
        detail_payload = load_physics_question_payload(created_path, physics_runtime)
        add_result(results, "new question detail non-empty", all(detail_payload.get(field, "").strip() for field in (PROBLEM_FIELD, ANSWER_FIELD, SOLUTION_FIELD)), "problem/answer/solution checked")

        edited_payload = dict(detail_payload)
        edited_payload[SCORE_FIELD] = "7"
        edited_payload[REMARK_FIELD] = "1D-2临时写入测试题-已编辑"
        edit_result = save_existing_physics_question_edit(created_path, edited_payload, physics_runtime)
        edited_path = Path(edit_result.file_path)
        edited_detail = load_physics_question_payload(edited_path, physics_runtime)
        rows_after_edit = read_csv_index(runtime_config=physics_runtime)
        edited_index_row = next((row for row in rows_after_edit if row.get("题目ID") == TEMP_ID), {})
        add_result(results, "edit save success", edited_detail.get(SCORE_FIELD) == "7", edited_detail.get(SCORE_FIELD))
        add_result(results, "edit reflected in index", edited_index_row.get("分值") == "7" and edited_index_row.get("备注") == "1D-2临时写入测试题-已编辑", edited_index_row)
        add_result(results, "math hash unchanged after edit", sha256_of(math_csv) == math_hash_before, sha256_of(math_csv))
        validate_physics_index_integrity(physics_runtime, expected_math_sha256=math_hash_before)
        add_result(results, "index integrity after edit", True, "ok")

    finally:
        if created_path and created_path.exists() and created_path.name == f"{TEMP_ID}.tex":
            created_path.unlink()
        elif temp_path.exists():
            temp_path.unlink()
        rebuild_index("physics", base_dir=str(project_root), sync_artifacts=False, write_report=False)
        restored_count = len(list(iter_real_question_files(physics_runtime)))
        physics_csv.write_bytes(physics_csv_before)
        if outputs_dir.exists():
            shutil.rmtree(outputs_dir)
        add_result(results, "cleanup physics count restored", restored_count == initial_physics_count, f"count={restored_count}; expected={initial_physics_count}")
        add_result(results, "cleanup math hash unchanged", sha256_of(math_csv) == math_hash_before, sha256_of(math_csv))
        add_result(results, "cleanup temp file removed", not temp_path.exists(), str(temp_path))
        add_result(results, "cleanup physics csv restored", physics_csv.read_bytes() == physics_csv_before, "restored")
        add_result(results, "cleanup outputs absent", not outputs_dir.exists(), str(outputs_dir))

    print(json.dumps({"results": results}, ensure_ascii=False, indent=2))
    if not all(item["ok"] for item in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

