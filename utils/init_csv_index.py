import csv
import datetime
import os
import re
import sys

# 确保能正确导入同一目录和上级目录的模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.file_service import atomic_write_csv_rows, atomic_write_text, backup_existing_file
from utils.core_config import (
    BASE_DIR,
    CHAPTERS_DIR,
    CSV_INDEX_PATH,
    EXPORT_TEMPLATE_SUBJECT_NAME,
    MAIN_TEX_CHAPTER_ORDER,
    MAIN_TEX_TITLE,
)
from utils.latex_ops import parse_meta_data
import utils.batch_gen as batch_gen

CSV_HEADERS = [
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

REPORT_PATH = os.path.join(BASE_DIR, "index_rebuild_report.md")
MAIN_TEX_PATH = os.path.join(BASE_DIR, "main.tex")
EXAM_TEMPLATE_PATH = os.path.join(
    BASE_DIR,
    "Test Paper Group",
    "主题模板",
    "试卷类模板",
    "试卷类模板.tex",
)


def iter_real_question_files():
    records = []
    if not os.path.exists(CHAPTERS_DIR):
        return records

    for root, dirs, files in os.walk(CHAPTERS_DIR):
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


def parse_filename(file_name: str):
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


def parse_question_record(file_path: str):
    file_name = os.path.basename(file_path)
    name_body, year, ptype, pname, pnum, subj = parse_filename(file_name)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as exc:
        raise ValueError(f"读取失败: {exc}") from exc

    meta_dict, clean_content = parse_meta_data(content)
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

    has_tikz = "是" if "\\begin{tikzpicture}" in clean_content else "否"
    has_solution = "是" if sol_text else "否"

    if "\\begin{choices}" in stem_text or "\\choice" in stem_text:
        q_type = "选择题"
    elif "\\underline" in stem_text or "空" in pname:
        q_type = "填空题"
    else:
        q_type = "解答题"

    stat = os.stat(file_path)
    created_time = datetime.datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
    modified_time = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    rel_path = os.path.relpath(file_path, CHAPTERS_DIR)

    return {
        "题目ID": str(meta_dict.get("ID", "")).strip(),
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
        "难度星级": meta_dict.get("难度星级", ""),
        "包含解析": has_solution,
        "组卷引用次数": meta_dict.get("组卷引用次数", "0"),
        "备注": meta_dict.get("备注", ""),
        "初次录入的时间": created_time,
        "最后修改时间": modified_time,
        "题干": stem_text,
        "答案": ans_text,
        "解析": sol_text,
    }


def normalize_rel_path(rel_path: str):
    return os.path.normcase(os.path.normpath((rel_path or "").replace("/", os.sep).replace("\\", os.sep)))


def read_existing_csv_rows():
    if not os.path.exists(CSV_INDEX_PATH):
        return []
    with open(CSV_INDEX_PATH, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def assign_missing_ids(rows):
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


def sort_rows(rows):
    rows.sort(key=lambda row: int(row["题目ID"]) if str(row.get("题目ID", "")).isdigit() else 999999999)


def sync_main_tex():
    if not os.path.exists(MAIN_TEX_PATH):
        raise FileNotFoundError(f"main.tex 不存在: {MAIN_TEX_PATH}")

    with open(MAIN_TEX_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    content = re.sub(r"\\title\{.*?\}", rf"\\title{{{MAIN_TEX_TITLE}}}", content, count=1)

    generated_block = []
    for subject in MAIN_TEX_CHAPTER_ORDER:
        generated_block.append(rf"\chapter{{{subject}}}")
        generated_block.append(rf"\input{{chapters/{subject}/content_{subject}}}")
        generated_block.append("")
    generated_text = "\n".join(generated_block).rstrip()

    first_chapter_idx = content.find(r"\chapter{")
    end_document_idx = content.rfind(r"\end{document}")
    if first_chapter_idx == -1 or end_document_idx == -1 or first_chapter_idx >= end_document_idx:
        raise ValueError("main.tex 中未找到可替换的章节区域")

    new_content = content[:first_chapter_idx].rstrip() + "\n\n" + generated_text + "\n\n" + content[end_document_idx:]
    atomic_write_text(MAIN_TEX_PATH, new_content, backup=False)


def sync_exam_template_subject():
    if not os.path.exists(EXAM_TEMPLATE_PATH):
        raise FileNotFoundError(f"试卷模板不存在: {EXAM_TEMPLATE_PATH}")

    with open(EXAM_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    updated = re.sub(
        r"\\subject\{.*?\}",
        rf"\\subject{{{EXPORT_TEMPLATE_SUBJECT_NAME}}}",
        content,
        count=1,
    )
    atomic_write_text(EXAM_TEMPLATE_PATH, updated, backup=False)


def build_report(
    real_question_count: int,
    old_index_count: int,
    deleted_invalid_count: int,
    rebuilt_index_count: int,
    parse_issues,
    csv_backup_path: str,
):
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

    lines.append("")
    lines.append("## 说明")
    lines.append("")
    lines.append("- 本次重建以 `chapters/` 中真实存在的单题 `.tex` 文件为唯一数据源。")
    lines.append("- `content_*.tex` 已按真实存在的题目文件重新生成。")
    lines.append("- 未删除任何真实题目文件。")
    lines.append("")

    atomic_write_text(REPORT_PATH, "\n".join(lines), backup=False)


def main():
    real_files = iter_real_question_files()
    existing_rows = read_existing_csv_rows()
    old_index_count = len(existing_rows)
    real_question_count = len(real_files)
    real_rel_paths = {
        normalize_rel_path(os.path.relpath(path, CHAPTERS_DIR))
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
            rows.append(parse_question_record(file_path))
        except Exception as exc:
            parse_issues.append({"path": file_path, "error": str(exc)})

    if parse_issues:
        build_report(
            real_question_count=real_question_count,
            old_index_count=old_index_count,
            deleted_invalid_count=deleted_invalid_count,
            rebuilt_index_count=0,
            parse_issues=parse_issues,
            csv_backup_path="",
        )
        raise SystemExit("发现无法解析的真实题目文件，已停止重建。请先处理 index_rebuild_report.md 中列出的问题。")

    assign_missing_ids(rows)
    sort_rows(rows)

    csv_backup_path = backup_existing_file(CSV_INDEX_PATH) if os.path.exists(CSV_INDEX_PATH) else ""
    atomic_write_csv_rows(CSV_INDEX_PATH, CSV_HEADERS, rows, backup=False)

    batch_gen.update_chapter_contents()
    sync_main_tex()
    sync_exam_template_subject()

    build_report(
        real_question_count=real_question_count,
        old_index_count=old_index_count,
        deleted_invalid_count=deleted_invalid_count,
        rebuilt_index_count=len(rows),
        parse_issues=parse_issues,
        csv_backup_path=csv_backup_path,
    )

    print(f"真实题目数量: {real_question_count}")
    print(f"原索引记录数量: {old_index_count}")
    print(f"删除的失效记录数量: {deleted_invalid_count}")
    print(f"重建后的索引数量: {len(rows)}")
    print(f"报告文件: {REPORT_PATH}")


if __name__ == "__main__":
    main()
