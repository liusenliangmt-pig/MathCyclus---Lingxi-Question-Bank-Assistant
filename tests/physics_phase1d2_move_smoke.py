import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path


TEMP_ID = "PHY-TEMP-MOVE-1D2"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_result(results, name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)})


def count_id_in_index(rows, qid):
    return sum(1 for row in rows if row.get("题目ID") == qid)


def count_id_in_files(files, qid):
    from utils.latex_ops import parse_meta_data

    count = 0
    for file_path in files:
        content = Path(file_path).read_text(encoding="utf-8")
        meta, _ = parse_meta_data(content)
        if meta.get("ID") == qid:
            count += 1
    return count


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

    results = []
    physics_runtime = build_runtime_config("physics", base_dir=str(project_root))
    math_runtime = build_runtime_config("mathematics", base_dir=str(project_root))
    physics_csv = Path(physics_runtime.csv_index_path)
    math_csv = Path(math_runtime.csv_index_path)
    physics_csv_before = physics_csv.read_bytes()
    math_hash_before = sha256_of(math_csv)
    old_path = Path(physics_runtime.chapters_dir) / "初中" / "力与运动" / f"{TEMP_ID}.tex"
    new_path = Path(physics_runtime.chapters_dir) / "初中" / "光现象" / f"{TEMP_ID}.tex"
    outputs_dir = project_root / "outputs" / "physics_phase1d2_move_smoke"

    try:
        add_result(results, "initial physics count 8", len(list(iter_real_question_files(physics_runtime))) == 8, "checked")
        add_result(results, "initial math count 70", len(read_csv_index(runtime_config=math_runtime)) == 70, "checked")
        add_result(results, "temp paths absent before test", not old_path.exists() and not new_path.exists(), f"old={old_path}; new={new_path}")
        if old_path.exists() or new_path.exists():
            raise RuntimeError("Temp move test file already exists before test.")

        payload = {
            ID_FIELD: TEMP_ID,
            STAGE_FIELD: "初中",
            GRADE_FIELD: "八年级",
            CHAPTER_FIELD: "力与运动",
            KNOWLEDGE_POINT_FIELD: "匀速运动路程",
            QUESTION_TYPE_FIELD: "计算题",
            DIFFICULTY_FIELD: "1.0",
            SCORE_FIELD: "5",
            TAGS_FIELD: "1D-2移动测试",
            SOURCE_FIELD: "本地原创测试题",
            REMARK_FIELD: "1D-2移动事务测试题",
            PROBLEM_FIELD: "小车以 $2\\,\\mathrm{m/s}$ 的速度匀速运动 $3\\,\\mathrm{s}$，求通过的路程。",
            ANSWER_FIELD: "路程为 $6\\,\\mathrm{m}$。",
            SOLUTION_FIELD: "匀速运动路程 $s=vt=2\\,\\mathrm{m/s}\\times 3\\,\\mathrm{s}=6\\,\\mathrm{m}$。",
        }
        save_new_physics_question(payload, physics_runtime)
        add_result(results, "create source temp question", old_path.exists(), old_path)

        move_payload = load_physics_question_payload(old_path, physics_runtime)
        move_payload[CHAPTER_FIELD] = "光现象"
        move_payload[KNOWLEDGE_POINT_FIELD] = "光的直线传播"
        move_payload[REMARK_FIELD] = "1D-2移动事务测试题-移动后"

        original_rebuild_index = physics_question_ops.rebuild_index

        pre_failure_state = {}

        def fail_rebuild_index(*_args, **_kwargs):
            files_during_failure = list(iter_real_question_files(physics_runtime))
            pre_failure_state["old_exists"] = old_path.exists()
            pre_failure_state["new_exists"] = new_path.exists()
            pre_failure_state["temp_id_file_count"] = count_id_in_files(files_during_failure, TEMP_ID)
            raise RuntimeError("simulated move index refresh failure")

        physics_question_ops.rebuild_index = fail_rebuild_index
        try:
            try:
                save_existing_physics_question_edit(old_path, move_payload, physics_runtime)
                rollback_failed = False
            except RuntimeError:
                rollback_failed = True
        finally:
            physics_question_ops.rebuild_index = original_rebuild_index

        add_result(results, "simulated move failure raised", rollback_failed, "simulated move index refresh failure")
        add_result(results, "no duplicate tex during failed move", pre_failure_state.get("temp_id_file_count") == 1, pre_failure_state)
        add_result(results, "rollback old path restored", old_path.exists(), old_path)
        add_result(results, "rollback new path absent", not new_path.exists(), new_path)
        add_result(results, "rollback physics csv restored to post-create state", count_id_in_index(read_csv_index(runtime_config=physics_runtime), TEMP_ID) == 1, "one index row")
        add_result(results, "rollback math hash unchanged", sha256_of(math_csv) == math_hash_before, sha256_of(math_csv))

        save_existing_physics_question_edit(old_path, move_payload, physics_runtime)
        files_after_move = list(iter_real_question_files(physics_runtime))
        rows_after_move = read_csv_index(runtime_config=physics_runtime)
        add_result(results, "final old path absent", not old_path.exists(), old_path)
        add_result(results, "final new path exists", new_path.exists(), new_path)
        add_result(results, "final only one temp tex file", count_id_in_files(files_after_move, TEMP_ID) == 1, f"count={count_id_in_files(files_after_move, TEMP_ID)}")
        add_result(results, "final one index row for id", count_id_in_index(rows_after_move, TEMP_ID) == 1, f"count={count_id_in_index(rows_after_move, TEMP_ID)}")
        validate_physics_index_integrity(physics_runtime, expected_math_sha256=math_hash_before)
        add_result(results, "final index integrity", True, "ok")

    finally:
        for candidate in (old_path, new_path):
            if candidate.exists() and candidate.name == f"{TEMP_ID}.tex":
                candidate.unlink()
        for parent in (old_path.parent, new_path.parent):
            for artifact in parent.glob(f".{TEMP_ID}.tex.*"):
                artifact.unlink()
        rebuild_index("physics", base_dir=str(project_root), sync_artifacts=False, write_report=False)
        restored_count = len(list(iter_real_question_files(physics_runtime)))
        physics_csv.write_bytes(physics_csv_before)
        if outputs_dir.exists():
            shutil.rmtree(outputs_dir)
        add_result(results, "cleanup physics count restored 8", restored_count == 8, f"count={restored_count}")
        add_result(results, "cleanup math hash unchanged", sha256_of(math_csv) == math_hash_before, sha256_of(math_csv))
        add_result(results, "cleanup temp old/new removed", not old_path.exists() and not new_path.exists(), f"old={old_path.exists()}; new={new_path.exists()}")
        add_result(results, "cleanup physics csv restored", physics_csv.read_bytes() == physics_csv_before, "restored")
        add_result(results, "cleanup outputs absent", not outputs_dir.exists(), str(outputs_dir))

    print(json.dumps({"results": results}, ensure_ascii=False, indent=2))
    if not all(item["ok"] for item in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

