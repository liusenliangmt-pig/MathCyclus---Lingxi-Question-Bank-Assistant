import argparse
import csv
import datetime
import os
import re
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.file_service import atomic_write_csv_rows, atomic_write_text, backup_existing_file
import utils.batch_gen as batch_gen
from utils.core_config import build_runtime_config
from utils.csv_ops import get_csv_headers
from utils.discipline_config import list_discipline_codes, normalize_discipline_code
from utils.latex_ops import parse_meta_data


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Rebuild question index for a specific discipline.")
    parser.add_argument("--discipline", default="mathematics", help="Supported values: mathematics, physics")
    return parser.parse_args(argv)


def validate_discipline_code(discipline_code: str) -> str:
    normalized = normalize_discipline_code(discipline_code)
    supported = list_discipline_codes()
    if normalized not in supported:
        supported_text = ", ".join(supported)
        raise ValueError(f"Unsupported discipline '{discipline_code}'. Supported disciplines: {supported_text}")
    return normalized


def iter_real_question_files(runtime_config):
    records = []
    if not os.path.exists(runtime_config.chapters_dir):
        return records

    for root, dirs, files in os.walk(runtime_config.chapters_dir):
        dirs[:] = [d for d in dirs if "相关图" not in d]
        for file_name in files:
            if not file_name.endswith(".tex"):
                continue
            if file_name.startswith("content_"):
                continue
            if re.search(r" 图\d+\.tex$", file_name):
                continue
            records.append(os.path.join(root, file_name))
    return sorted(records)


def parse_math_filename(file_name: str):
    name_body = os.path.splitext(file_name)[0]
    segments = name_body.split("-")
    if len(segments) < 5:
        raise ValueError(f"文件名分段不足 5 段: {file_name}")

    year = segments[0]
    ptype = segments[1]
    pnum = segments[-2]
    subj = segments[-1]
    pname = "-".join(segments[2:-2])
    return name_body, year, ptype, pname, pnum, subj


def infer_question_type(stem_text: str, pname: str, meta_dict: dict) -> str:
    if str(meta_dict.get("题型", "")).strip():
        return str(meta_dict.get("题型", "")).strip()
    if "\\begin{choices}" in stem_text or "\\choice" in stem_text:
        return "选择题"
    if "\\underline" in stem_text or "空" in pname:
        return "填空题"
    return "解答题"


def extract_problem_answer_solution(clean_content: str):
    prob_match = re.search(
        r"\\begin\{problem\}(?:\[[^\]]*\])?(?:\s*\{[^\}]*\}){0,5}\s*([\s\S]*?)\\end\{problem\}",
        clean_content,
        re.DOTALL,
    )
    if not prob_match:
        raise ValueError("未找到可解析的 problem 环境")

    stem_text = prob_match.group(1).strip()
    sol_match = re.search(r"\\begin\{solutions?\}(.*?)\\end\{solutions?\}", clean_content, re.DOTALL)
    ans_match = re.search(r"\\begin\{answer\}(.*?)\\end\{answer\}", clean_content, re.DOTALL)

    sol_text = sol_match.group(1).strip() if sol_match else ""
    ans_text = ans_match.group(1).strip() if ans_match else ""

    if sol_match and sol_match.group(0) in stem_text:
        stem_text = stem_text.replace(sol_match.group(0), "")
    if ans_match and ans_match.group(0) in stem_text:
        stem_text = stem_text.replace(ans_match.group(0), "")
    stem_text = stem_text.strip()

    return stem_text, ans_text, sol_text


def parse_question_record(file_path: str, runtime_config):
    file_name = os.path.basename(file_path)
    name_body = os.path.splitext(file_name)[0]

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as exc:
        raise ValueError(f"读取失败: {exc}") from exc

    meta_dict, clean_content = parse_meta_data(content)
    stem_text, ans_text, sol_text = extract_problem_answer_solution(clean_content)
    has_tikz = "是" if "\\begin{tikzpicture}" in clean_content else "否"
    has_solution = "是" if sol_text else "否"

    if runtime_config.discipline_key == "mathematics":
        _, year, ptype, pname, pnum, subj = parse_math_filename(file_name)
        qid = str(meta_dict.get("ID", "")).strip()
        discipline_name = meta_dict.get("学科", "")
        school_stage = meta_dict.get("学段", "")
        grade = meta_dict.get("年级", "")
        volume = meta_dict.get("册别", "")
        knowledge_point = meta_dict.get("知识点", "")
        score = meta_dict.get("分值", "")
        experiment_type = meta_dict.get("实验类型", "")
        image_type = meta_dict.get("图像类型", "")
        unit_rule = meta_dict.get("单位要求", "")
        has_circuit = meta_dict.get("是否包含电路图", "")
        has_force = meta_dict.get("是否包含受力图", "")
        has_light = meta_dict.get("是否包含光路图", "")
        has_table = meta_dict.get("是否包含实验表格", "")
        source = meta_dict.get("来源", "")
    else:
        year = str(meta_dict.get("年份", "")).strip()
        ptype = str(meta_dict.get("试卷类型", "")).strip()
        pname = str(meta_dict.get("试卷名称", "")).strip()
        pnum = str(meta_dict.get("原卷题号", "")).strip()
        subj = str(meta_dict.get("章节", "")).strip() or os.path.basename(os.path.dirname(file_path))
        qid = str(meta_dict.get("ID", "")).strip() or name_body
        discipline_name = str(meta_dict.get("学科", runtime_config.discipline_name)).strip()
        school_stage = str(meta_dict.get("学段", "")).strip()
        grade = str(meta_dict.get("年级", "")).strip()
        volume = str(meta_dict.get("册别", "")).strip()
        knowledge_point = str(meta_dict.get("知识点", "")).strip()
        score = str(meta_dict.get("分值", "")).strip()
        experiment_type = str(meta_dict.get("实验类型", "")).strip()
        image_type = str(meta_dict.get("图像类型", "")).strip()
        unit_rule = str(meta_dict.get("单位要求", "")).strip()
        has_circuit = str(meta_dict.get("是否包含电路图", "")).strip()
        has_force = str(meta_dict.get("是否包含受力图", "")).strip()
        has_light = str(meta_dict.get("是否包含光路图", "")).strip()
        has_table = str(meta_dict.get("是否包含实验表格", "")).strip()
        source = str(meta_dict.get("来源", "")).strip()

    q_type = infer_question_type(stem_text, pname, meta_dict)
    stat = os.stat(file_path)
    created_time = datetime.datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
    modified_time = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    rel_path = os.path.relpath(file_path, runtime_config.chapters_dir)

    return {
        "题目ID": qid,
        "文件名称": name_body,
        "相对文件路径": rel_path,
        "年份": year,
        "试卷类型": ptype,
        "试卷名称": pname,
        "原卷题号": pnum,
        "知识板块": subj,
        "标签": meta_dict.get("标签", ""),
        "包含TikZ绘图": has_tikz,
        "题型": q_type,
        "难度星级": meta_dict.get("难度星级", meta_dict.get("难度", "")),
        "包含解析": has_solution,
        "组卷引用次数": meta_dict.get("组卷引用次数", "0"),
        "备注": meta_dict.get("备注", ""),
        "初次录入的时间": created_time,
        "最后修改时间": modified_time,
        "题干": stem_text,
        "答案": ans_text,
        "解析": sol_text,
        "学科": discipline_name,
        "学段": school_stage,
        "年级": grade,
        "册别": volume,
        "知识点": knowledge_point,
        "分值": score,
        "实验类型": experiment_type,
        "图像类型": image_type,
        "单位要求": unit_rule,
        "是否包含电路图": has_circuit,
        "是否包含受力图": has_force,
        "是否包含光路图": has_light,
        "是否包含实验表格": has_table,
        "来源": source,
    }


def normalize_rel_path(rel_path: str):
    return os.path.normcase(os.path.normpath((rel_path or "").replace("/", os.sep).replace("\\", os.sep)))


def read_existing_csv_rows(csv_path: str):
    if not os.path.exists(csv_path):
        return []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def assign_missing_ids(rows, discipline_code: str):
    if discipline_code != "mathematics":
        return

    max_id = 0
    for row in rows:
        qid = str(row.get("题目ID", "")).strip()
        if qid.isdigit():
            max_id = max(max_id, int(qid))

    for row in rows:
        qid = str(row.get("题目ID", "")).strip()
        if not qid:
            max_id += 1
            row["题目ID"] = str(max_id)


def sort_rows(rows, discipline_code: str):
    if discipline_code == "mathematics":
        rows.sort(key=lambda row: int(row["题目ID"]) if str(row.get("题目ID", "")).isdigit() else 999999999)
    else:
        rows.sort(key=lambda row: str(row.get("题目ID", "")))


def sync_main_tex(base_dir: str, chapter_order, title: str):
    main_tex_path = os.path.join(base_dir, "main.tex")
    if not os.path.exists(main_tex_path):
        raise FileNotFoundError(f"main.tex 不存在: {main_tex_path}")

    with open(main_tex_path, "r", encoding="utf-8") as f:
        content = f.read()

    content = re.sub(r"\\title\{.*?\}", rf"\\title{{{title}}}", content, count=1)

    generated_block = []
    for subject in chapter_order:
        generated_block.append(rf"\chapter{{{subject}}}")
        generated_block.append(rf"\input{{chapters/{subject}/content_{subject}}}")
        generated_block.append("")
    generated_text = "\n".join(generated_block).rstrip()

    first_chapter_idx = content.find(r"\chapter{")
    end_document_idx = content.rfind(r"\end{document}")
    if first_chapter_idx == -1 or end_document_idx == -1 or first_chapter_idx >= end_document_idx:
        raise ValueError("main.tex 中未找到可替换的章节区域")

    new_content = content[:first_chapter_idx].rstrip() + "\n\n" + generated_text + "\n\n" + content[end_document_idx:]
    atomic_write_text(main_tex_path, new_content, backup=False)


def sync_exam_template_subject(base_dir: str, subject_name: str):
    template_path = os.path.join(
        base_dir,
        "Test Paper Group",
        "主题模板",
        "试卷类模板",
        "试卷类模板.tex",
    )
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"试卷模板不存在: {template_path}")

    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()

    updated = re.sub(r"\\subject\{.*?\}", rf"\\subject{{{subject_name}}}", content, count=1)
    atomic_write_text(template_path, updated, backup=False)


def build_report(base_dir: str, real_question_count: int, old_index_count: int, deleted_invalid_count: int, rebuilt_index_count: int, parse_issues, csv_backup_path: str):
    report_path = os.path.join(base_dir, "index_rebuild_report.md")
    lines = [
        "# Index Rebuild Report",
        "",
        f"- 扫描时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 扫描到的真实题目数量：{real_question_count}",
        f"- 原索引记录数量：{old_index_count}",
        f"- 删除的失效记录数量：{deleted_invalid_count}",
        f"- 重建后的索引数量：{rebuilt_index_count}",
        f"- CSV 备份文件：{csv_backup_path or '无（原文件不存在）'}",
        "",
        "## 无法解析的题目文件",
        "",
    ]
    if not parse_issues:
        lines.append("- 无")
    else:
        for issue in parse_issues:
            lines.append(f"- `{issue['path']}`：{issue['error']}")

    lines.extend(
        [
            "",
            "## 说明",
            "",
            "- 本次重建以真实存在的单题 `.tex` 文件为唯一数据源。",
            "- 未删除任何真实题目文件。",
            "",
        ]
    )
    atomic_write_text(report_path, "\n".join(lines), backup=False)


def rebuild_index(discipline_code: str = "mathematics", base_dir: str | None = None, sync_artifacts: bool | None = None, write_report: bool | None = None):
    normalized = validate_discipline_code(discipline_code)
    runtime_config = build_runtime_config(normalized, base_dir=base_dir)
    headers = get_csv_headers(normalized)

    if sync_artifacts is None:
        sync_artifacts = normalized == "mathematics"
    if write_report is None:
        write_report = normalized == "mathematics"

    real_files = iter_real_question_files(runtime_config)
    existing_rows = read_existing_csv_rows(runtime_config.csv_index_path)
    old_index_count = len(existing_rows)
    real_question_count = len(real_files)
    real_rel_paths = {
        normalize_rel_path(os.path.relpath(path, runtime_config.chapters_dir))
        for path in real_files
    }
    deleted_invalid_count = sum(
        1
        for row in existing_rows
        if normalize_rel_path(row.get("相对文件路径", "")) not in real_rel_paths
    )

    rows = []
    parse_issues = []
    for file_path in real_files:
        try:
            rows.append(parse_question_record(file_path, runtime_config))
        except Exception as exc:
            parse_issues.append({"path": file_path, "error": str(exc)})

    if parse_issues:
        if write_report:
            build_report(
                base_dir=runtime_config.base_dir,
                real_question_count=real_question_count,
                old_index_count=old_index_count,
                deleted_invalid_count=deleted_invalid_count,
                rebuilt_index_count=0,
                parse_issues=parse_issues,
                csv_backup_path="",
            )
        raise SystemExit("发现无法解析的真实题目文件，已停止重建。")

    assign_missing_ids(rows, normalized)
    sort_rows(rows, normalized)

    csv_backup_path = backup_existing_file(runtime_config.csv_index_path) if os.path.exists(runtime_config.csv_index_path) else ""
    atomic_write_csv_rows(runtime_config.csv_index_path, headers, [{field: row.get(field, "") for field in headers} for row in rows], backup=False)

    if normalized == "mathematics" and sync_artifacts:
        batch_gen.update_chapter_contents()
        sync_main_tex(runtime_config.base_dir, runtime_config.main_tex_chapter_order, runtime_config.main_tex_title)
        sync_exam_template_subject(runtime_config.base_dir, runtime_config.export_template_subject_name)

    if write_report:
        build_report(
            base_dir=runtime_config.base_dir,
            real_question_count=real_question_count,
            old_index_count=old_index_count,
            deleted_invalid_count=deleted_invalid_count,
            rebuilt_index_count=len(rows),
            parse_issues=parse_issues,
            csv_backup_path=csv_backup_path,
        )

    return {
        "discipline": normalized,
        "csv_path": runtime_config.csv_index_path,
        "headers": headers,
        "real_question_count": real_question_count,
        "old_index_count": old_index_count,
        "deleted_invalid_count": deleted_invalid_count,
        "rebuilt_index_count": len(rows),
        "csv_backup_path": csv_backup_path,
    }


def main(argv=None):
    args = parse_args(argv)
    try:
        result = rebuild_index(args.discipline)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(f"discipline: {result['discipline']}")
    print(f"csv_path: {result['csv_path']}")
    print(f"real_question_count: {result['real_question_count']}")
    print(f"old_index_count: {result['old_index_count']}")
    print(f"deleted_invalid_count: {result['deleted_invalid_count']}")
    print(f"rebuilt_index_count: {result['rebuilt_index_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
