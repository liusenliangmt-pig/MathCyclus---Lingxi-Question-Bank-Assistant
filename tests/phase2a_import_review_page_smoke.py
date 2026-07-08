import argparse
import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path


TEMP_BATCH = "APPTEST-IMPORT-2A"
TEMP_CANDIDATE = "APPTEST-CANDIDATE-2A"
PREVIEW_BATCH = "APPTEST-PREVIEW-2A"
PREVIEW_CANDIDATE = "APPTEST-PREVIEW-CANDIDATE-2A"
BUILTIN_CANDIDATE = "CAND-TEMP-IMPORT-2A-0001"
EXPECTED_MATH_SHA = "250092C5158BA3A2185253AC0F0A141E5AE74C5C668A4CC74B208309EDE84386"


def add(results, name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)})


def read_csv_rows(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def import_project(module_root):
    sys.path.insert(0, str(module_root))
    from utils.core_config import build_runtime_config
    from utils.init_csv_index import iter_real_question_files
    import utils.import_review_ops as import_review_ops

    return {
        "build_runtime_config": build_runtime_config,
        "iter_real_question_files": iter_real_question_files,
        "import_review_ops": import_review_ops,
    }


def batch_dir(project_root, batch_id):
    return Path(project_root) / "data" / "import_staging" / batch_id


def candidate_jsons(project_root, batch_id):
    candidates = batch_dir(project_root, batch_id) / "candidates"
    return sorted(candidates.glob("*.json")) if candidates.exists() else []


def candidate_path(project_root, batch_id, candidate_id):
    return batch_dir(project_root, batch_id) / "candidates" / f"{candidate_id}.json"


def cleanup_batch(project_root, batch_id):
    path = batch_dir(project_root, batch_id)
    staging = (Path(project_root) / "data" / "import_staging").resolve()
    resolved = path.resolve()
    if resolved.exists() and staging in resolved.parents:
        shutil.rmtree(resolved)


def preview_candidate_payload(ops, batch_id):
    data = ops.default_candidate_payload(batch_id, PREVIEW_CANDIDATE)
    data.update(
        {
            "question_id": "PHY-TEMP-PREVIEW-2A-0001",
            "stage": "初中",
            "grade": "八年级",
            "knowledge_block": "机械运动",
            "knowledge_point": "平均速度",
            "question_type": "计算题",
            "difficulty": "1.0",
            "score": "5",
            "source_type": "manual",
            "source_file": "phase2a_preview_fixture.json",
            "recognition_method": "manual",
            "problem": "某同学在 $20\\,\\mathrm{s}$ 内运动了 $100\\,\\mathrm{m}$，求该同学的平均速度。",
            "answer": "$5\\,\\mathrm{m/s}$",
            "solutions": (
                "根据平均速度公式\n"
                "\\[\n"
                "v=\\frac{s}{t},\n"
                "\\]\n"
                "代入 $s=100\\,\\mathrm{m}$、$t=20\\,\\mathrm{s}$，得到\n"
                "\\[\n"
                "v=\\frac{100}{20}=5\\,\\mathrm{m/s}.\n"
                "\\]"
            ),
        }
    )
    return data


def set_text_input_by_label(at, label, value):
    matches = [item for item in at.text_input if str(item.label) == label]
    if not matches:
        raise AssertionError(f"text_input not found: {label}")
    matches[0].input(value)


def click_button_by_label(at, label):
    matches = [item for item in at.button if str(item.label) == label]
    if not matches:
        raise AssertionError(f"button not found: {label}")
    matches[0].click()


def page_text(at):
    buckets = []
    for collection in (at.markdown, at.text, at.info, at.warning, at.error, at.success):
        buckets.extend(str(item.value) for item in collection)
    return "\n".join(buckets)


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

    for batch_id in (TEMP_BATCH, PREVIEW_BATCH, "MANUAL-IMPORT-2A", "BATCH-TEMP-MANUAL-2A-0001"):
        cleanup_batch(project_root, batch_id)

    try:
        from streamlit.testing.v1 import AppTest
    except Exception as exc:
        add(results, "streamlit AppTest import", False, repr(exc))
        print(json.dumps({"status": "FAIL", "results": results}, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    try:
        initial_physics_count = len(list(api["iter_real_question_files"](physics_runtime)))
        initial_physics_rows = len(read_csv_rows(physics_csv))
        add(results, "initial physics source/index count match", initial_physics_count == initial_physics_rows, f"{initial_physics_count}/{initial_physics_rows}")
        add(results, "initial physics index columns 44", len(read_csv_rows(physics_csv)[0]) == 44)
        add(results, "initial math sha", initial_math_sha == EXPECTED_MATH_SHA, initial_math_sha)

        at = AppTest.from_file(str(project_root / "question_bank_app.py"), default_timeout=30)
        at.run()
        if at.exception:
            add(results, "AppTest initial load", False, str(at.exception))
            raise AssertionError(str(at.exception))

        physics_label = "\u7269\u7406"
        import_nav = "\u9898\u5e93\u5bfc\u5165\u4e0e\u5ba1\u6838"
        batch_label = "\u5bfc\u5165\u6279\u6b21ID"
        save_label = "\u4fdd\u5b58\u4e3a\u5f85\u5ba1\u6838\u5019\u9009\u9898"
        create_batch_label = "\u521b\u5efa/\u52a0\u8f7d\u6279\u6b21"
        builtin_label = "\u8f7d\u5165\u5185\u7f6e\u6d4b\u8bd5\u5019\u9009\u9898"
        at.sidebar.selectbox[0].set_value(physics_label)
        at.run()
        radio = at.sidebar.radio[0]
        radio.set_value(next(option for option in radio.options if import_nav in str(option)))
        at.run()
        add(results, "import page initial render no exception", not at.exception, at.exception or "")
        add(results, "import page no candidate json on initial render", not candidate_jsons(project_root, TEMP_BATCH))
        add(results, "import page no batch json on initial render", not batch_dir(project_root, TEMP_BATCH).exists())

        ops.create_import_batch(PREVIEW_BATCH, base_dir=project_root)
        ops.save_import_candidate(PREVIEW_BATCH, preview_candidate_payload(ops, PREVIEW_BATCH), base_dir=project_root)
        preview_path = candidate_path(project_root, PREVIEW_BATCH, PREVIEW_CANDIDATE)
        preview_before_hash = sha256_of(preview_path)
        preview_data = json.loads(preview_path.read_text(encoding="utf-8"))
        add(results, "preview candidate contains display math source", "\\[" in preview_data.get("solutions", ""), preview_data.get("solutions", ""))
        set_text_input_by_label(at, batch_label, PREVIEW_BATCH)
        at.run()
        rendered_markdown = "\n".join(str(item.value) for item in at.markdown)
        formula_preview = "\n".join(
            str(item.value)
            for item in at.markdown
            if "v=\\frac" in str(item.value) or "平均速度公式" in str(item.value)
        )
        edit_values = "\n".join(str(item.value) for item in at.text_area)
        add(
            results,
            "candidate preview converts display math",
            bool(formula_preview) and "\\[" not in formula_preview and "$$" in formula_preview and "v=\\frac{s}{t}," in formula_preview,
            formula_preview or rendered_markdown[-800:],
        )
        add(results, "candidate edit form keeps raw latex", "\\[\nv=\\frac{s}{t}," in edit_values, edit_values[-800:])
        add(results, "candidate json unchanged after preview", sha256_of(preview_path) == preview_before_hash, sha256_of(preview_path))

        set_text_input_by_label(at, batch_label, TEMP_BATCH)
        at.run()
        click_button_by_label(at, save_label)
        at.run()
        text_after_empty = page_text(at)
        add(results, "empty candidate id shows friendly error", "candidate_id" in text_after_empty and "\u4e0d\u80fd\u4e3a\u7a7a" in text_after_empty, text_after_empty[-500:])
        add(results, "empty candidate id creates no json", not batch_dir(project_root, TEMP_BATCH).exists() and not candidate_jsons(project_root, TEMP_BATCH))
        add(results, "formal physics unchanged after empty submit", len(list(api["iter_real_question_files"](physics_runtime))) == initial_physics_count and len(read_csv_rows(physics_csv)) == initial_physics_rows)

        at = AppTest.from_file(str(project_root / "question_bank_app.py"), default_timeout=30)
        at.run()
        at.sidebar.selectbox[0].set_value(physics_label)
        at.run()
        radio = at.sidebar.radio[0]
        radio.set_value(next(option for option in radio.options if import_nav in str(option)))
        at.run()
        set_text_input_by_label(at, batch_label, TEMP_BATCH)
        at.run()
        click_button_by_label(at, create_batch_label)
        at.run()
        add(results, "create batch button creates no candidate", batch_dir(project_root, TEMP_BATCH).exists() and not candidate_jsons(project_root, TEMP_BATCH))

        set_text_input_by_label(at, "candidate_id", TEMP_CANDIDATE)
        at.run()
        click_button_by_label(at, save_label)
        at.run()
        saved_candidates = candidate_jsons(project_root, TEMP_BATCH)
        add(results, "valid candidate save creates one json", len(saved_candidates) == 1, saved_candidates)
        if saved_candidates:
            data = json.loads(saved_candidates[0].read_text(encoding="utf-8"))
            add(results, "valid candidate pending review", data.get("candidate_id") == TEMP_CANDIDATE and data.get("review_status") == ops.PENDING_REVIEW, data)
        add(results, "formal physics unchanged after candidate save", len(list(api["iter_real_question_files"](physics_runtime))) == initial_physics_count and len(read_csv_rows(physics_csv)) == initial_physics_rows)

        cleanup_batch(project_root, TEMP_BATCH)
        at = AppTest.from_file(str(project_root / "question_bank_app.py"), default_timeout=30)
        at.run()
        at.sidebar.selectbox[0].set_value(physics_label)
        at.run()
        radio = at.sidebar.radio[0]
        radio.set_value(next(option for option in radio.options if import_nav in str(option)))
        at.run()
        set_text_input_by_label(at, batch_label, TEMP_BATCH)
        at.run()
        click_button_by_label(at, builtin_label)
        at.run()
        builtin_candidates = candidate_jsons(project_root, TEMP_BATCH)
        add(results, "builtin candidate creates legal id", any(path.stem == BUILTIN_CANDIDATE for path in builtin_candidates), [path.name for path in builtin_candidates])
        at.run()
        add(results, "rerun does not duplicate builtin candidate", len(candidate_jsons(project_root, TEMP_BATCH)) == len(builtin_candidates), [path.name for path in candidate_jsons(project_root, TEMP_BATCH)])

    except Exception as exc:
        add(results, "phase2a import review page smoke unexpected exception", False, repr(exc))
    finally:
        cleanup_batch(project_root, TEMP_BATCH)
        cleanup_batch(project_root, PREVIEW_BATCH)
        cleanup_batch(project_root, "MANUAL-IMPORT-2A")
        cleanup_batch(project_root, "BATCH-TEMP-MANUAL-2A-0001")
        if physics_csv.read_bytes() != initial_physics_bytes:
            physics_csv.write_bytes(initial_physics_bytes)

    final_staging_root = Path(project_root) / "data" / "import_staging"
    allowed_staging = {"README.md", ".gitignore"}
    staging_residuals = [
        str(path.relative_to(final_staging_root))
        for path in final_staging_root.rglob("*")
        if path.is_file()
        and path.name not in allowed_staging
    ]
    add(results, "final physics source count unchanged", len(list(api["iter_real_question_files"](physics_runtime))) == initial_physics_count, len(list(api["iter_real_question_files"](physics_runtime))))
    add(results, "final physics index rows unchanged", len(read_csv_rows(physics_csv)) == initial_physics_rows, len(read_csv_rows(physics_csv)))
    add(results, "final physics index columns 44", len(read_csv_rows(physics_csv)[0]) == 44)
    add(results, "final math sha unchanged", sha256_of(math_csv) == EXPECTED_MATH_SHA, sha256_of(math_csv))
    add(results, "no staging residual data", not staging_residuals, staging_residuals)

    ok = all(item["ok"] for item in results)
    print(json.dumps({"status": "PASS" if ok else "FAIL", "results": results}, ensure_ascii=False, indent=2))
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
