import argparse
import csv
import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


MATH_BASE_FIELDS = [
    "题目ID",
    "文件名称",
    "相对文件路径",
    "年份",
    "试卷类型",
    "试卷名称",
    "原卷题号",
    "知识板块",
    "标签",
    "包含TikZ绘图",
    "题型",
    "难度星级",
    "包含解析",
    "组卷引用次数",
    "备注",
    "初次录入的时间",
    "最后修改时间",
    "题干",
    "答案",
    "解析",
]


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv_rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def assert_check(results: list, name: str, condition: bool, detail: str):
    results.append({"name": name, "ok": condition, "detail": detail})
    if not condition:
        raise AssertionError(f"{name}: {detail}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--module-root", required=True)
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    module_root = Path(args.module_root).resolve()
    sys.path.insert(0, str(module_root))

    discipline_config = importlib.import_module("utils.discipline_config")
    core_config = importlib.import_module("utils.core_config")
    csv_ops = importlib.import_module("utils.csv_ops")
    init_csv_index = importlib.import_module("utils.init_csv_index")

    results = []

    math_runtime = core_config.build_runtime_config("mathematics", base_dir=str(project_root))
    physics_runtime = core_config.build_runtime_config("physics", base_dir=str(project_root))
    math_csv_path = Path(math_runtime.csv_index_path)
    physics_csv_path = Path(physics_runtime.csv_index_path)

    math_hash_before = sha256_of(math_csv_path)

    assert_check(
        results,
        "physics config path",
        physics_runtime.chapters_dir.endswith("chapters_physics"),
        physics_runtime.chapters_dir,
    )

    physics_source_files = init_csv_index.iter_real_question_files(physics_runtime)
    assert_check(
        results,
        "physics source count",
        len(physics_source_files) == 8,
        f"count={len(physics_source_files)}",
    )

    math_rows_before = csv_ops.read_csv_index()
    assert_check(
        results,
        "math read_csv_index compatibility",
        len(math_rows_before) == 70,
        f"count={len(math_rows_before)}",
    )
    missing_math_fields = [field for field in MATH_BASE_FIELDS if field not in (math_rows_before[0].keys() if math_rows_before else [])]
    assert_check(
        results,
        "math base fields exist",
        not missing_math_fields,
        ",".join(missing_math_fields) if missing_math_fields else "all fields present",
    )

    rebuild_result = init_csv_index.rebuild_index("physics", base_dir=str(project_root), sync_artifacts=False, write_report=False)
    assert_check(
        results,
        "physics rebuild target csv",
        rebuild_result["csv_path"] == str(physics_csv_path),
        rebuild_result["csv_path"],
    )

    physics_rows = read_csv_rows(physics_csv_path)
    assert_check(
        results,
        "physics csv row count",
        len(physics_rows) == 8,
        f"count={len(physics_rows)}",
    )

    physics_ids = [str(row.get("题目ID", "")).strip() for row in physics_rows]
    assert_check(
        results,
        "physics duplicate ids",
        len(set(physics_ids)) == 8,
        f"unique={len(set(physics_ids))}",
    )

    missing_paths = []
    empty_blocks = []
    math_path_leaks = []
    for row in physics_rows:
        rel_path = str(row.get("相对文件路径", "")).strip()
        abs_path = physics_csv_path.parent.parent / "chapters_physics" / rel_path
        if not abs_path.exists():
            missing_paths.append(rel_path)
        if "chapters" in rel_path.replace("\\", "/").split("/"):
            math_path_leaks.append(rel_path)
        for field in ("题干", "答案", "解析"):
            if not str(row.get(field, "")).strip():
                empty_blocks.append(f"{row.get('题目ID')}:{field}")

    assert_check(
        results,
        "physics indexed paths exist",
        not missing_paths,
        "\n".join(missing_paths) if missing_paths else "all exist",
    )
    assert_check(
        results,
        "physics stem answer solution non-empty",
        not empty_blocks,
        "\n".join(empty_blocks) if empty_blocks else "all non-empty",
    )
    assert_check(
        results,
        "physics index excludes math chapters path",
        not math_path_leaks,
        "\n".join(math_path_leaks) if math_path_leaks else "no math path leak",
    )

    math_rows_after = csv_ops.read_csv_index()
    assert_check(
        results,
        "math index still 70 rows",
        len(math_rows_after) == 70,
        f"count={len(math_rows_after)}",
    )

    math_physics_leaks = []
    for row in math_rows_after:
        rel_path = str(row.get("相对文件路径", "")).strip().replace("\\", "/")
        if "chapters_physics" in rel_path:
            math_physics_leaks.append(rel_path)
    assert_check(
        results,
        "math index excludes chapters_physics",
        not math_physics_leaks,
        "\n".join(math_physics_leaks) if math_physics_leaks else "no physics path leak",
    )

    math_hash_after = sha256_of(math_csv_path)
    assert_check(
        results,
        "math csv sha256 unchanged",
        math_hash_before == math_hash_after,
        f"before={math_hash_before} after={math_hash_after}",
    )

    cli = [
        sys.executable,
        str(module_root / "utils" / "init_csv_index.py"),
        "--discipline",
        "chemistry",
    ]
    completed = subprocess.run(cli, capture_output=True, text=True, encoding="utf-8", errors="replace")
    combined_output = (completed.stdout or "") + "\n" + (completed.stderr or "")
    assert_check(
        results,
        "invalid discipline non-zero exit",
        completed.returncode != 0,
        f"returncode={completed.returncode}",
    )
    assert_check(
        results,
        "invalid discipline supported values",
        ("mathematics" in combined_output) and ("physics" in combined_output),
        combined_output.strip(),
    )

    print(json.dumps({"results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
