import csv
import datetime
import os
import re

from .core_config import CHAPTERS_DIR, CSV_INDEX_PATH, RuntimeConfig, build_runtime_config
from .latex_ops import parse_meta_data
from services.file_service import atomic_write_csv_rows

MATH_CSV_HEADERS = [
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

PHYSICS_APPENDED_HEADERS = [
    "学科",
    "学段",
    "年级",
    "册别",
    "知识点",
    "分值",
    "实验类型",
    "图像类型",
    "单位要求",
    "是否包含电路图",
    "是否包含受力图",
    "是否包含光路图",
    "是否包含实验表格",
    "来源",
]


def get_csv_headers(discipline_code: str = "mathematics"):
    if (discipline_code or "mathematics").strip().lower() == "physics":
        return MATH_CSV_HEADERS + PHYSICS_APPENDED_HEADERS
    return list(MATH_CSV_HEADERS)


def resolve_runtime_config(runtime_config: RuntimeConfig | None = None, discipline_code: str | None = None, base_dir: str | None = None) -> RuntimeConfig:
    if runtime_config is not None:
        return runtime_config
    return build_runtime_config(discipline_code, base_dir=base_dir)


def resolve_csv_path(csv_path: str | None = None, runtime_config: RuntimeConfig | None = None, discipline_code: str | None = None, base_dir: str | None = None) -> str:
    if csv_path:
        return csv_path
    if runtime_config is not None or discipline_code is not None or base_dir is not None:
        return resolve_runtime_config(runtime_config=runtime_config, discipline_code=discipline_code, base_dir=base_dir).csv_index_path
    return CSV_INDEX_PATH


def read_csv_index(csv_path: str | None = None, runtime_config: RuntimeConfig | None = None, discipline_code: str | None = None, base_dir: str | None = None):
    """Read the whole CSV index into memory."""
    resolved_csv_path = resolve_csv_path(csv_path=csv_path, runtime_config=runtime_config, discipline_code=discipline_code, base_dir=base_dir)
    if not os.path.exists(resolved_csv_path):
        return []
    data = []
    with open(resolved_csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data


def write_csv_index(data, csv_path: str | None = None, headers=None, runtime_config: RuntimeConfig | None = None, discipline_code: str | None = None, base_dir: str | None = None, backup: bool = True):
    """Write the full CSV index using utf-8-sig for Excel compatibility."""
    resolved_runtime = resolve_runtime_config(runtime_config=runtime_config, discipline_code=discipline_code, base_dir=base_dir)
    resolved_headers = headers or get_csv_headers(resolved_runtime.discipline_key)
    resolved_csv_path = resolve_csv_path(csv_path=csv_path, runtime_config=resolved_runtime)
    rows = normalize_csv_rows(data, headers=resolved_headers)
    issues = validate_csv_rows(rows, headers=resolved_headers)
    if issues:
        preview = "; ".join(
            f"row {issue.get('行号')}: {issue.get('字段')} {issue.get('问题')}"
            for issue in issues[:5]
        )
        raise ValueError(f"CSV index validation failed before write: {preview}")
    atomic_write_csv_rows(resolved_csv_path, resolved_headers, rows, backup=backup)


def normalize_csv_rows(data, headers=None):
    """Return rows containing exactly the managed CSV headers."""
    resolved_headers = headers or list(MATH_CSV_HEADERS)
    normalized = []
    for row in data:
        normalized.append({field: row.get(field, "") for field in resolved_headers})
    return normalized


def find_duplicate_ids(data, id_field: str = "题目ID"):
    """Read-only duplicate ID detection."""
    seen = {}
    duplicates = []
    for row_num, row in enumerate(data, start=2):
        qid = str(row.get(id_field, "")).strip()
        if not qid:
            continue
        if qid in seen:
            duplicates.append({"题目ID": qid, "首次行号": seen[qid], "重复行号": row_num})
        else:
            seen[qid] = row_num
    return duplicates


def validate_csv_rows(data, required_fields=None, headers=None):
    """Read-only validation for missing required fields and duplicate IDs."""
    resolved_headers = headers or list(MATH_CSV_HEADERS)
    if required_fields is None:
        required_fields = resolved_headers[:3]

    issues = []
    for row_num, row in enumerate(data, start=2):
        for field in required_fields:
            if not str(row.get(field, "")).strip():
                issues.append({"行号": row_num, "字段": field, "问题": "缺少必填值"})

    for duplicate in find_duplicate_ids(data):
        issues.append({"行号": duplicate["重复行号"], "字段": "题目ID", "问题": f"重复ID：{duplicate['题目ID']}"})

    return issues


def get_next_id(csv_path: str | None = None):
    """Get the next numeric global ID from the default mathematics index."""
    data = read_csv_index(csv_path=csv_path)
    max_id = 0
    for row in data:
        if row.get("题目ID") and str(row["题目ID"]).isdigit():
            max_id = max(max_id, int(row["题目ID"]))
    return max_id + 1


def _parse_tex_content(content, pname):
    """Parse tex content to extract stem, answer, solutions and metadata."""
    meta, clean_content = parse_meta_data(content)

    has_tikz = "是" if "\\begin{tikzpicture}" in clean_content else "否"

    prob_match = re.search(
        r"\\begin\{problem\}(?:\[[^\]]*\])?(?:\s*\{[^\}]*\}){0,5}\s*([\s\S]*?)\\end\{problem\}",
        clean_content,
        re.DOTALL,
    )
    stem_text = prob_match.group(1).strip() if prob_match else ""

    sol_match = re.search(r"\\begin\{solutions?\}(.*?)\\end\{solutions?\}", clean_content, re.DOTALL)
    sol_text = sol_match.group(1).strip() if sol_match else ""

    ans_match = re.search(r"\\begin\{answer\}(.*?)\\end\{answer\}", clean_content, re.DOTALL)
    ans_text = ans_match.group(1).strip() if ans_match else ""

    has_solution = "是" if sol_text else "否"

    if sol_match and sol_match.group(0) in stem_text:
        stem_text = stem_text.replace(sol_match.group(0), "")
    if ans_match and ans_match.group(0) in stem_text:
        stem_text = stem_text.replace(ans_match.group(0), "")
    stem_text = stem_text.strip()

    if meta.get("题型", "").strip():
        q_type = meta.get("题型", "").strip()
    elif "\\begin{choices}" in stem_text or "\\choice" in stem_text:
        q_type = "选择题"
    elif "\\underline" in stem_text or "空" in pname:
        q_type = "填空题"
    else:
        q_type = "解答题"

    return has_tikz, q_type, has_solution, stem_text, ans_text, sol_text, meta


def add_to_csv_index(file_path, content, year, ptype, pname, pnum, subj, runtime_config: RuntimeConfig | None = None, headers=None):
    """Append a new question into the current discipline CSV."""
    resolved_runtime = resolve_runtime_config(runtime_config=runtime_config)
    resolved_headers = headers or get_csv_headers(resolved_runtime.discipline_key)
    data = read_csv_index(runtime_config=resolved_runtime)

    name_body = os.path.basename(file_path).replace(".tex", "")
    rel_path = os.path.relpath(file_path, resolved_runtime.chapters_dir)

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    has_tikz, q_type, has_solution, stem_text, ans_text, sol_text, meta = _parse_tex_content(content, pname)

    new_id = meta.get("ID")
    if not new_id and resolved_runtime.discipline_key == "mathematics":
        new_id = str(get_next_id())

    new_row = {
        "题目ID": new_id or "",
        "文件名称": name_body,
        "相对文件路径": rel_path,
        "年份": year,
        "试卷类型": ptype,
        "试卷名称": pname,
        "原卷题号": pnum,
        "知识板块": subj,
        "标签": meta.get("标签", ""),
        "包含TikZ绘图": has_tikz,
        "题型": q_type,
        "难度星级": meta.get("难度星级", meta.get("难度", "")),
        "包含解析": has_solution,
        "组卷引用次数": meta.get("组卷引用次数", "0"),
        "备注": meta.get("备注", ""),
        "初次录入的时间": now_str,
        "最后修改时间": now_str,
        "题干": stem_text,
        "答案": ans_text,
        "解析": sol_text,
        "学科": meta.get("学科", resolved_runtime.discipline_name),
        "学段": meta.get("学段", ""),
        "年级": meta.get("年级", ""),
        "册别": meta.get("册别", ""),
        "知识点": meta.get("知识点", ""),
        "分值": meta.get("分值", ""),
        "实验类型": meta.get("实验类型", ""),
        "图像类型": meta.get("图像类型", ""),
        "单位要求": meta.get("单位要求", ""),
        "是否包含电路图": meta.get("是否包含电路图", ""),
        "是否包含受力图": meta.get("是否包含受力图", ""),
        "是否包含光路图": meta.get("是否包含光路图", ""),
        "是否包含实验表格": meta.get("是否包含实验表格", ""),
        "来源": meta.get("来源", ""),
    }

    data.append(new_row)
    write_csv_index(data, runtime_config=resolved_runtime, headers=resolved_headers)
    return new_id


def update_csv_index_for_edit(old_file_path, new_file_path, new_content, new_year, new_ptype, new_pname, new_pnum, new_subj, runtime_config: RuntimeConfig | None = None, headers=None):
    """Update CSV metadata after editing a question file."""
    resolved_runtime = resolve_runtime_config(runtime_config=runtime_config)
    resolved_headers = headers or get_csv_headers(resolved_runtime.discipline_key)
    data = read_csv_index(runtime_config=resolved_runtime)
    old_name_body = os.path.basename(old_file_path).replace(".tex", "")
    new_name_body = os.path.basename(new_file_path).replace(".tex", "")
    new_rel_path = os.path.relpath(new_file_path, resolved_runtime.chapters_dir)

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    has_tikz, q_type, has_solution, stem_text, ans_text, sol_text, meta = _parse_tex_content(new_content, new_pname)

    found = False
    for row in data:
        if row.get("文件名称") == old_name_body:
            row["文件名称"] = new_name_body
            row["相对文件路径"] = new_rel_path
            row["年份"] = new_year
            row["试卷类型"] = new_ptype
            row["试卷名称"] = new_pname
            row["原卷题号"] = new_pnum
            row["知识板块"] = new_subj
            row["标签"] = meta.get("标签", "")
            row["包含TikZ绘图"] = has_tikz
            row["题型"] = q_type
            row["难度星级"] = meta.get("难度星级", meta.get("难度", ""))
            row["包含解析"] = has_solution
            row["组卷引用次数"] = meta.get("组卷引用次数", row.get("组卷引用次数", "0"))
            row["备注"] = meta.get("备注", "")
            row["最后修改时间"] = now_str
            row["题干"] = stem_text
            row["答案"] = ans_text
            row["解析"] = sol_text
            row["学科"] = meta.get("学科", row.get("学科", resolved_runtime.discipline_name))
            row["学段"] = meta.get("学段", row.get("学段", ""))
            row["年级"] = meta.get("年级", row.get("年级", ""))
            row["册别"] = meta.get("册别", row.get("册别", ""))
            row["知识点"] = meta.get("知识点", row.get("知识点", ""))
            row["分值"] = meta.get("分值", row.get("分值", ""))
            row["实验类型"] = meta.get("实验类型", row.get("实验类型", ""))
            row["图像类型"] = meta.get("图像类型", row.get("图像类型", ""))
            row["单位要求"] = meta.get("单位要求", row.get("单位要求", ""))
            row["是否包含电路图"] = meta.get("是否包含电路图", row.get("是否包含电路图", ""))
            row["是否包含受力图"] = meta.get("是否包含受力图", row.get("是否包含受力图", ""))
            row["是否包含光路图"] = meta.get("是否包含光路图", row.get("是否包含光路图", ""))
            row["是否包含实验表格"] = meta.get("是否包含实验表格", row.get("是否包含实验表格", ""))
            row["来源"] = meta.get("来源", row.get("来源", ""))
            found = True
            break

    if not found:
        add_to_csv_index(new_file_path, new_content, new_year, new_ptype, new_pname, new_pnum, new_subj, runtime_config=resolved_runtime, headers=resolved_headers)
    else:
        write_csv_index(data, runtime_config=resolved_runtime, headers=resolved_headers)
