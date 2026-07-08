import argparse
import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path


TEMP_BATCH = "BATCH-TEMP-IMPORT-2A"
TEMP_CANDIDATE = "CAND-TEMP-IMPORT-2A"
TEMP_REJECT_CANDIDATE = "CAND-TEMP-REJECT-2A"
TEMP_FAIL_CANDIDATE = "CAND-TEMP-FAIL-2A"
TEMP_QID = "PHY-TEMP-IMPORT-2A-0001"
TEMP_REJECT_QID = "PHY-TEMP-IMPORT-2A-REJECT"
TEMP_FAIL_QID = "PHY-TEMP-IMPORT-2A-FAIL"
EXPECTED_MATH_SHA = "250092C5158BA3A2185253AC0F0A141E5AE74C5C668A4CC74B208309EDE84386"


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def read_csv_rows(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def add(results, name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)})


def import_project(module_root):
    sys.path.insert(0, str(module_root))
    from utils.core_config import build_runtime_config
    from utils.init_csv_index import iter_real_question_files, rebuild_index
    from utils.latex_ops import parse_meta_data
    import utils.physics_question_ops as physics_question_ops
    import utils.import_review_ops as import_review_ops

    return {
        "build_runtime_config": build_runtime_config,
        "iter_real_question_files": iter_real_question_files,
        "rebuild_index": rebuild_index,
        "parse_meta_data": parse_meta_data,
        "physics_question_ops": physics_question_ops,
        "import_review_ops": import_review_ops,
    }


def count_id_in_files(runtime, api, qid):
    count = 0
    paths = []
    for file_path in api["iter_real_question_files"](runtime):
        path = Path(file_path)
        meta, _ = api["parse_meta_data"](path.read_text(encoding="utf-8"))
        if meta.get("ID") == qid:
            count += 1
            paths.append(path)
    return count, paths


def candidate_payload(ops, runtime, candidate_id=TEMP_CANDIDATE, qid=TEMP_QID):
    data = ops.default_candidate_payload(TEMP_BATCH, candidate_id)
    data.update(
        {
            "question_id": qid,
            "stage": "初中",
            "grade": "八年级",
            "knowledge_block": "力与运动",
            "knowledge_point": "二力平衡",
            "question_type": "计算题",
            "difficulty": runtime.difficulty_levels[0] if runtime.difficulty_levels else "1.0",
            "score": "5",
            "tags": "2A导入审核测试",
            "source": "本地导入候选题",
            "remark": "2A候选题框架测试",
            "source_type": "manual",
            "source_file": "phase2a_builtin_sample.json",
            "source_page": "1",
            "source_region": "N/A",
            "recognition_method": "manual",
            "problem": "一个物体受到两个方向相反、大小均为 $3\\,\\mathrm{N}$ 的水平力。求合力大小。",
            "answer": "$0\\,\\mathrm{N}$。",
            "solutions": "两力大小相等、方向相反，合力为 $3\\,\\mathrm{N}-3\\,\\mathrm{N}=0\\,\\mathrm{N}$。",
        }
    )
    return data


def cleanup(project_root, physics_runtime, api, restore_physics_bytes=None):
    ops = api["import_review_ops"]
    try:
        ops.cleanup_test_import_batch(TEMP_BATCH, base_dir=project_root)
    except Exception:
        pass
    for qid in (TEMP_QID, TEMP_REJECT_QID, TEMP_FAIL_QID):
        _count, paths = count_id_in_files(physics_runtime, api, qid)
        for path in paths:
            if path.name == f"{qid}.tex":
                path.unlink()
    if restore_physics_bytes is not None:
        Path(physics_runtime.csv_index_path).write_bytes(restore_physics_bytes)
    else:
        api["rebuild_index"]("physics", base_dir=str(project_root), sync_artifacts=False, write_report=False)
    outputs = Path(project_root) / "outputs" / "physics_phase2a_import_review_smoke"
    if outputs.exists():
        shutil.rmtree(outputs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--module-root", default=None)
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else Path(__file__).resolve().parents[1]
    module_root = Path(args.module_root).resolve() if args.module_root else project_root
    api = import_project(module_root)
    ops = api["import_review_ops"]
    physics_runtime = api["build_runtime_config"]("physics", base_dir=str(project_root))
    math_runtime = api["build_runtime_config"]("mathematics", base_dir=str(project_root))
    physics_csv = Path(physics_runtime.csv_index_path)
    math_csv = Path(math_runtime.csv_index_path)
    initial_physics_bytes = physics_csv.read_bytes()
    initial_math_sha = sha256_of(math_csv)
    results = []

    cleanup(project_root, physics_runtime, api, restore_physics_bytes=initial_physics_bytes)

    try:
        initial_physics_count = len(list(api["iter_real_question_files"](physics_runtime)))
        initial_physics_rows = len(read_csv_rows(physics_csv))
        add(results, "initial physics source/index count match", initial_physics_count == initial_physics_rows, f"{initial_physics_count}/{initial_physics_rows}")
        add(results, "initial math sha", initial_math_sha == EXPECTED_MATH_SHA, initial_math_sha)

        for bad in ("../bad", "C:\\bad", "bad/name", "CON"):
            try:
                ops.create_import_batch(bad, base_dir=project_root)
                add(results, f"bad batch id rejected {bad}", False, "accepted")
            except Exception as exc:
                add(results, f"bad batch id rejected {bad}", True, type(exc).__name__)
            try:
                ops.candidate_path(TEMP_BATCH, bad, base_dir=project_root)
                add(results, f"bad candidate id rejected {bad}", False, "accepted")
            except Exception as exc:
                add(results, f"bad candidate id rejected {bad}", True, type(exc).__name__)

        batch = ops.create_import_batch(TEMP_BATCH, base_dir=project_root)
        add(results, "create fixed batch", batch["batch_id"] == TEMP_BATCH)

        candidate = ops.save_import_candidate(TEMP_BATCH, candidate_payload(ops, physics_runtime), base_dir=project_root)
        add(results, "candidate pending after create", candidate["review_status"] == ops.PENDING_REVIEW)
        add(results, "formal physics unchanged after candidate create", len(list(api["iter_real_question_files"](physics_runtime))) == initial_physics_count)
        add(results, "physics index unchanged after candidate create", len(read_csv_rows(physics_csv)) == initial_physics_rows)

        before_updated = candidate["updated_at"]
        updated = ops.update_import_candidate(TEMP_BATCH, TEMP_CANDIDATE, {"score": "6", "remark": "updated in smoke"}, base_dir=project_root)
        add(results, "candidate edit persisted", updated["score"] == "6" and updated["remark"] == "updated in smoke")
        add(results, "candidate updated_at changed", updated["updated_at"] >= before_updated and updated["created_at"] == candidate["created_at"])
        add(
            results,
            "formal unchanged after edit",
            len(list(api["iter_real_question_files"](physics_runtime))) == initial_physics_count
            and len(read_csv_rows(physics_csv)) == initial_physics_rows,
        )

        reject_candidate = ops.save_import_candidate(
            TEMP_BATCH,
            candidate_payload(ops, physics_runtime, TEMP_REJECT_CANDIDATE, TEMP_REJECT_QID),
            base_dir=project_root,
        )
        rejected = ops.reject_import_candidate(TEMP_BATCH, reject_candidate["candidate_id"], "not ready", base_dir=project_root)
        add(results, "candidate rejected", rejected["review_status"] == ops.REJECTED and "rejected_at" in rejected)
        try:
            ops.approve_import_candidate(TEMP_BATCH, reject_candidate["candidate_id"], runtime_config=physics_runtime, base_dir=project_root)
            add(results, "rejected candidate cannot approve", False, "approved")
        except Exception as exc:
            add(results, "rejected candidate cannot approve", True, type(exc).__name__)

        bad_json_path = ops.candidate_path(TEMP_BATCH, "BROKEN-TEMP-2A", base_dir=project_root)
        bad_json_path.parent.mkdir(parents=True, exist_ok=True)
        bad_json_path.write_text("{not valid json", encoding="utf-8")
        try:
            ops.get_import_candidate(TEMP_BATCH, "BROKEN-TEMP-2A", base_dir=project_root)
            add(results, "broken json rejected", False, "loaded")
        except Exception as exc:
            add(results, "broken json rejected", True, type(exc).__name__)
        bad_json_path.unlink()

        failing = ops.save_import_candidate(
            TEMP_BATCH,
            candidate_payload(ops, physics_runtime, TEMP_FAIL_CANDIDATE, TEMP_FAIL_QID),
            base_dir=project_root,
        )
        original_rebuild = api["physics_question_ops"].rebuild_index

        def fail_rebuild(*_args, **_kwargs):
            raise RuntimeError("simulated phase2a index refresh failure")

        api["physics_question_ops"].rebuild_index = fail_rebuild
        try:
            try:
                ops.approve_import_candidate(TEMP_BATCH, failing["candidate_id"], runtime_config=physics_runtime, base_dir=project_root)
                add(results, "approval failure raised", False, "approved")
            except Exception as exc:
                failed_after = ops.get_import_candidate(TEMP_BATCH, failing["candidate_id"], base_dir=project_root)
                file_count, _paths = count_id_in_files(physics_runtime, api, TEMP_FAIL_QID)
                ok = failed_after["review_status"] == ops.PENDING_REVIEW and failed_after.get("approval_error") and file_count == 0
                add(results, "approval failure keeps pending and records error", ok, f"{type(exc).__name__}; file_count={file_count}")
        finally:
            api["physics_question_ops"].rebuild_index = original_rebuild

        approved_result = ops.approve_import_candidate(TEMP_BATCH, TEMP_CANDIDATE, runtime_config=physics_runtime, base_dir=project_root)
        add(results, "approve imports one formal file", Path(approved_result.official_file_path).exists(), approved_result.official_file_path)
        add(results, "physics source count increments after approve", len(list(api["iter_real_question_files"](physics_runtime))) == initial_physics_count + 1)
        physics_rows = read_csv_rows(physics_csv)
        row = next((r for r in physics_rows if r.get("题目ID") == TEMP_QID), None)
        add(results, "physics index increments with 44 columns", len(physics_rows) == initial_physics_rows + 1 and len(physics_rows[0]) == 44)
        add(results, "formal source fields mapped", bool(row) and row.get("来源类型") == "manual" and row.get("来源文件") == "phase2a_builtin_sample.json" and row.get("来源页码") == "1" and row.get("导入批次ID") == TEMP_BATCH and row.get("审核状态") == "已通过", row or {})
        add(results, "formal problem answer solution present", bool(row) and row.get("题干") and row.get("答案") and row.get("解析"))
        add(results, "math sha unchanged after approve", sha256_of(math_csv) == EXPECTED_MATH_SHA, sha256_of(math_csv))

        approved_candidate = ops.get_import_candidate(TEMP_BATCH, TEMP_CANDIDATE, base_dir=project_root)
        add(results, "candidate approved metadata recorded", approved_candidate["review_status"] == ops.APPROVED and approved_candidate.get("approved_at") and approved_candidate.get("official_question_id") == TEMP_QID and approved_candidate.get("official_file_path"))
        try:
            ops.approve_import_candidate(TEMP_BATCH, TEMP_CANDIDATE, runtime_config=physics_runtime, base_dir=project_root)
            add(results, "approved candidate cannot approve twice", False, "approved")
        except Exception as exc:
            file_count, _paths = count_id_in_files(physics_runtime, api, TEMP_QID)
            add(results, "approved candidate cannot approve twice", file_count == 1, f"{type(exc).__name__}; count={file_count}")

        duplicate = dict(candidate_payload(ops, physics_runtime, "CAND-TEMP-DUP-ID-2A", TEMP_QID))
        ops.save_import_candidate(TEMP_BATCH, duplicate, base_dir=project_root)
        try:
            ops.approve_import_candidate(TEMP_BATCH, duplicate["candidate_id"], runtime_config=physics_runtime, base_dir=project_root)
            add(results, "duplicate official id blocked", False, "approved")
        except Exception as exc:
            file_count, _paths = count_id_in_files(physics_runtime, api, TEMP_QID)
            dup_after = ops.get_import_candidate(TEMP_BATCH, duplicate["candidate_id"], base_dir=project_root)
            add(results, "duplicate official id blocked", file_count == 1 and dup_after.get("approval_error"), f"{type(exc).__name__}; count={file_count}")

    finally:
        cleanup(project_root, physics_runtime, api, restore_physics_bytes=initial_physics_bytes)

    final_staging_root = Path(project_root) / "data" / "import_staging"
    allowed_staging = {"README.md", ".gitignore"}
    staging_residuals = [
        str(path.relative_to(final_staging_root))
        for path in final_staging_root.rglob("*")
        if path.is_file()
        and path.name not in allowed_staging
    ]
    final_temp_files = [
        str(path.relative_to(project_root))
        for path in Path(project_root).rglob("*")
        if path.is_file()
        and ("PHY-TEMP" in path.name or path.name.endswith(".tmp") or path.name.endswith(".movebak"))
    ]
    add(results, "cleanup physics source count restored", len(list(api["iter_real_question_files"](physics_runtime))) == initial_physics_count)
    add(results, "cleanup physics index restored rows 44 columns", len(read_csv_rows(physics_csv)) == initial_physics_rows and len(read_csv_rows(physics_csv)[0]) == 44)
    add(results, "cleanup math rows still 70", len(read_csv_rows(math_csv)) == 70)
    add(results, "cleanup math sha unchanged", sha256_of(math_csv) == EXPECTED_MATH_SHA, sha256_of(math_csv))
    add(results, "no staging residual data", not staging_residuals, staging_residuals)
    add(results, "no temp formal residuals", not final_temp_files, final_temp_files)

    ok = all(item["ok"] for item in results)
    print(json.dumps({"status": "PASS" if ok else "FAIL", "results": results}, ensure_ascii=False, indent=2))
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
