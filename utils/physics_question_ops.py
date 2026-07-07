from __future__ import annotations

import hashlib
import os
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from services.file_service import atomic_write_text
from utils.core_config import RuntimeConfig, build_runtime_config
from utils.csv_ops import PHYSICS_PDF_RESERVED_HEADERS, read_csv_index
from utils.init_csv_index import extract_problem_answer_solution, iter_real_question_files, parse_question_record, rebuild_index
from utils.latex_ops import parse_meta_data


ID_FIELD = "ID"
DISCIPLINE_FIELD = "学科"
STAGE_FIELD = "学段"
GRADE_FIELD = "年级"
VOLUME_FIELD = "册别"
CHAPTER_FIELD = "章节"
KNOWLEDGE_POINT_FIELD = "知识点"
QUESTION_TYPE_FIELD = "题型"
DIFFICULTY_FIELD = "难度"
SCORE_FIELD = "分值"
TAGS_FIELD = "标签"
SOURCE_FIELD = "来源"
ENABLED_FIELD = "是否启用"
REMARK_FIELD = "备注"
EXPERIMENT_TYPE_FIELD = "实验类型"
IMAGE_TYPE_FIELD = "图像类型"
UNIT_RULE_FIELD = "单位要求"
HAS_CIRCUIT_FIELD = "是否包含电路图"
HAS_FORCE_FIELD = "是否包含受力图"
HAS_LIGHT_FIELD = "是否包含光路图"
HAS_TABLE_FIELD = "是否包含实验表格"

PROBLEM_FIELD = "题干"
ANSWER_FIELD = "答案"
SOLUTION_FIELD = "解析"

SOURCE_TYPE_FIELD = "来源类型"
REVIEW_STATUS_FIELD = "审核状态"

REL_PATH_FIELD = "相对文件路径"
QUESTION_ID_FIELD = "题目ID"

MANUAL_SOURCE_TYPE = "手动"
REVIEWED_STATUS = "已审核"

PDF_RESERVED_DEFAULTS = {
    SOURCE_TYPE_FIELD: MANUAL_SOURCE_TYPE,
    "来源文件": "",
    "来源页码": "",
    "来源区域坐标": "",
    "导入批次ID": "",
    "识别方式": "",
    "OCR置信度": "",
    REVIEW_STATUS_FIELD: REVIEWED_STATUS,
    "审核备注": "",
    "原始图片路径": "",
}

METADATA_FIELDS = [
    ID_FIELD,
    DISCIPLINE_FIELD,
    STAGE_FIELD,
    GRADE_FIELD,
    VOLUME_FIELD,
    CHAPTER_FIELD,
    KNOWLEDGE_POINT_FIELD,
    QUESTION_TYPE_FIELD,
    DIFFICULTY_FIELD,
    SCORE_FIELD,
    TAGS_FIELD,
    EXPERIMENT_TYPE_FIELD,
    IMAGE_TYPE_FIELD,
    UNIT_RULE_FIELD,
    HAS_CIRCUIT_FIELD,
    HAS_FORCE_FIELD,
    HAS_LIGHT_FIELD,
    HAS_TABLE_FIELD,
    SOURCE_FIELD,
    ENABLED_FIELD,
    REMARK_FIELD,
    *PHYSICS_PDF_RESERVED_HEADERS,
]

REQUIRED_PAYLOAD_FIELDS = [
    ID_FIELD,
    STAGE_FIELD,
    GRADE_FIELD,
    CHAPTER_FIELD,
    KNOWLEDGE_POINT_FIELD,
    QUESTION_TYPE_FIELD,
    DIFFICULTY_FIELD,
    SCORE_FIELD,
    PROBLEM_FIELD,
    ANSWER_FIELD,
    SOLUTION_FIELD,
]

WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class PhysicsQuestionError(ValueError):
    pass


@dataclass(frozen=True)
class PhysicsSaveResult:
    file_path: str
    question_id: str
    index_path: str
    math_index_sha256: str
    physics_count: int


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def get_physics_runtime(base_dir: str | None = None) -> RuntimeConfig:
    return build_runtime_config("physics", base_dir=base_dir)


def get_math_runtime(base_dir: str | None = None) -> RuntimeConfig:
    return build_runtime_config("mathematics", base_dir=base_dir)


def normalize_payload(payload: dict, runtime_config: RuntimeConfig) -> dict:
    normalized = {key: _single_line(str(value).strip(), key) for key, value in payload.items() if key not in {PROBLEM_FIELD, ANSWER_FIELD, SOLUTION_FIELD}}
    normalized[PROBLEM_FIELD] = str(payload.get(PROBLEM_FIELD, "")).strip()
    normalized[ANSWER_FIELD] = str(payload.get(ANSWER_FIELD, "")).strip()
    normalized[SOLUTION_FIELD] = str(payload.get(SOLUTION_FIELD, "")).strip()
    normalized[DISCIPLINE_FIELD] = runtime_config.discipline_name
    normalized.setdefault(VOLUME_FIELD, "通用")
    normalized.setdefault(SOURCE_FIELD, "本地原创测试题")
    normalized.setdefault(ENABLED_FIELD, "是")
    normalized.setdefault(REMARK_FIELD, "")
    normalized.setdefault(EXPERIMENT_TYPE_FIELD, "无")
    normalized.setdefault(IMAGE_TYPE_FIELD, "无")
    normalized.setdefault(UNIT_RULE_FIELD, "")
    normalized.setdefault(HAS_CIRCUIT_FIELD, "否")
    normalized.setdefault(HAS_FORCE_FIELD, "否")
    normalized.setdefault(HAS_LIGHT_FIELD, "否")
    normalized.setdefault(HAS_TABLE_FIELD, "否")
    for field, default in PDF_RESERVED_DEFAULTS.items():
        normalized.setdefault(field, default)
    return normalized


def validate_physics_question_payload(payload: dict, runtime_config: RuntimeConfig, original_id: str | None = None) -> dict:
    if runtime_config.discipline_key != "physics":
        raise PhysicsQuestionError("物理题保存接口只能用于 physics 学科。")

    data = normalize_payload(payload, runtime_config)
    missing = [field for field in REQUIRED_PAYLOAD_FIELDS if not str(data.get(field, "")).strip()]
    if missing:
        raise PhysicsQuestionError("缺少必填字段：" + "、".join(missing))

    _validate_safe_filename_component(data[ID_FIELD], "题目ID")

    if data[STAGE_FIELD] not in runtime_config.school_stages:
        raise PhysicsQuestionError(f"学段不在物理配置中：{data[STAGE_FIELD]}")
    if data[GRADE_FIELD] not in runtime_config.grades:
        raise PhysicsQuestionError(f"年级不在物理配置中：{data[GRADE_FIELD]}")
    if data[CHAPTER_FIELD] not in runtime_config.subjects:
        raise PhysicsQuestionError(f"知识板块不在物理配置中：{data[CHAPTER_FIELD]}")
    if data[QUESTION_TYPE_FIELD] not in runtime_config.question_types:
        raise PhysicsQuestionError(f"题型不在物理配置中：{data[QUESTION_TYPE_FIELD]}")
    if data[DIFFICULTY_FIELD] not in runtime_config.difficulty_levels:
        raise PhysicsQuestionError(f"难度不在物理配置中：{data[DIFFICULTY_FIELD]}")

    try:
        score = Decimal(str(data[SCORE_FIELD]))
    except InvalidOperation as exc:
        raise PhysicsQuestionError("分值必须是合法数字。") from exc
    if score < 0:
        raise PhysicsQuestionError("分值必须是非负数。")
    data[SCORE_FIELD] = str(score.normalize()) if score == score.to_integral() else str(score.normalize())

    for field in (PROBLEM_FIELD, ANSWER_FIELD, SOLUTION_FIELD):
        if not str(data.get(field, "")).strip():
            raise PhysicsQuestionError(f"{field}不能为空。")

    for field in METADATA_FIELDS:
        _single_line(str(data.get(field, "")), field)

    existing_ids = collect_existing_physics_ids(runtime_config)
    new_id = data[ID_FIELD]
    if new_id in existing_ids and new_id != (original_id or ""):
        raise PhysicsQuestionError(f"题目ID已存在：{new_id}")

    return data


def build_physics_tex_content(payload: dict, runtime_config: RuntimeConfig) -> str:
    data = normalize_payload(payload, runtime_config)
    lines = ["% === Begin Label Data ==="]
    for field in METADATA_FIELDS:
        lines.append(f"% {field}: {data.get(field, '')}")
    lines.append("% === End  Label Data ===")
    meta = "\n".join(lines)
    return (
        f"{meta}\n\n"
        "\\begin{problem}\n"
        f"{data[PROBLEM_FIELD].strip()}\n"
        "\\end{problem}\n\n"
        "\\begin{answer}\n"
        f"{data[ANSWER_FIELD].strip()}\n"
        "\\end{answer}\n\n"
        "\\begin{solutions}\n"
        f"{data[SOLUTION_FIELD].strip()}\n"
        "\\end{solutions}\n"
    )


def load_physics_question_payload(file_path: str | Path, runtime_config: RuntimeConfig) -> dict:
    resolved = _resolve_existing_file_in_physics_root(file_path, runtime_config)
    content = resolved.read_text(encoding="utf-8")
    meta, clean_content = parse_meta_data(content)
    problem, answer, solution = extract_problem_answer_solution(clean_content)
    payload = dict(PDF_RESERVED_DEFAULTS)
    payload.update({field: meta.get(field, "") for field in METADATA_FIELDS})
    payload[ID_FIELD] = meta.get(ID_FIELD, resolved.stem)
    payload[DISCIPLINE_FIELD] = meta.get(DISCIPLINE_FIELD, runtime_config.discipline_name)
    payload[CHAPTER_FIELD] = meta.get(CHAPTER_FIELD, resolved.parent.name)
    payload[DIFFICULTY_FIELD] = meta.get(DIFFICULTY_FIELD, meta.get("难度星级", ""))
    payload[PROBLEM_FIELD] = problem
    payload[ANSWER_FIELD] = answer
    payload[SOLUTION_FIELD] = solution
    return payload


def save_new_physics_question(payload: dict, runtime_config: RuntimeConfig) -> PhysicsSaveResult:
    math_runtime = get_math_runtime(runtime_config.base_dir)
    math_hash_before = sha256_file(math_runtime.csv_index_path)
    physics_index_backup = _read_optional_bytes(runtime_config.csv_index_path)

    data = validate_physics_question_payload(payload, runtime_config)
    target_path = build_target_path(data, runtime_config)
    if target_path.exists():
        raise PhysicsQuestionError(f"目标文件已存在，不能静默覆盖：{target_path.name}")

    content = build_physics_tex_content(data, runtime_config)
    try:
        _ensure_writable_parent(target_path, runtime_config)
        atomic_write_text(str(target_path), content, encoding="utf-8", backup=False)
        _verify_single_question_file(target_path, runtime_config, data[ID_FIELD])
        _refresh_and_validate_physics_index(runtime_config, math_hash_before)
        return PhysicsSaveResult(
            file_path=str(target_path),
            question_id=data[ID_FIELD],
            index_path=runtime_config.csv_index_path,
            math_index_sha256=math_hash_before,
            physics_count=len(list(iter_real_question_files(runtime_config))),
        )
    except Exception:
        if target_path.exists():
            target_path.unlink()
        _restore_optional_bytes(runtime_config.csv_index_path, physics_index_backup)
        raise


def save_existing_physics_question_edit(file_path: str | Path, payload: dict, runtime_config: RuntimeConfig) -> PhysicsSaveResult:
    old_path = _resolve_existing_file_in_physics_root(file_path, runtime_config)
    old_content = old_path.read_text(encoding="utf-8")
    old_payload = load_physics_question_payload(old_path, runtime_config)
    old_id = old_payload.get(ID_FIELD, old_path.stem)
    math_runtime = get_math_runtime(runtime_config.base_dir)
    math_hash_before = sha256_file(math_runtime.csv_index_path)
    physics_index_backup = _read_optional_bytes(runtime_config.csv_index_path)

    data = validate_physics_question_payload(payload, runtime_config, original_id=old_id)
    new_path = build_target_path(data, runtime_config)
    same_path = old_path.resolve() == new_path.resolve()
    if new_path.exists() and not same_path:
        raise PhysicsQuestionError(f"目标文件已存在，不能静默覆盖：{new_path.name}")

    content = build_physics_tex_content(data, runtime_config)
    temp_path = None
    old_move_backup = None
    try:
        _ensure_writable_parent(new_path, runtime_config)
        if same_path:
            atomic_write_text(str(new_path), content, encoding="utf-8", backup=False)
            _verify_single_question_file(new_path, runtime_config, data[ID_FIELD])
            _refresh_and_validate_physics_index(runtime_config, math_hash_before)
        else:
            temp_path = new_path.with_name(f".{new_path.name}.{uuid.uuid4().hex}.tmp")
            old_move_backup = old_path.with_name(f".{old_path.name}.{uuid.uuid4().hex}.movebak")
            atomic_write_text(str(temp_path), content, encoding="utf-8", backup=False)
            _verify_single_question_file(temp_path, runtime_config, data[ID_FIELD])
            os.replace(old_path, old_move_backup)
            os.replace(temp_path, new_path)
            _verify_single_question_file(new_path, runtime_config, data[ID_FIELD])
            _refresh_and_validate_physics_index(runtime_config, math_hash_before)
            old_move_backup.unlink()

        return PhysicsSaveResult(
            file_path=str(new_path),
            question_id=data[ID_FIELD],
            index_path=runtime_config.csv_index_path,
            math_index_sha256=math_hash_before,
            physics_count=len(list(iter_real_question_files(runtime_config))),
        )
    except Exception:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
        if not same_path and new_path.exists():
            new_path.unlink()
        if old_move_backup is not None and old_move_backup.exists():
            os.replace(old_move_backup, old_path)
        elif not old_path.exists():
            atomic_write_text(str(old_path), old_content, encoding="utf-8", backup=False)
        elif same_path:
            atomic_write_text(str(old_path), old_content, encoding="utf-8", backup=False)
        _restore_optional_bytes(runtime_config.csv_index_path, physics_index_backup)
        raise


def build_target_path(payload: dict, runtime_config: RuntimeConfig) -> Path:
    stage = _validate_safe_filename_component(payload[STAGE_FIELD], STAGE_FIELD)
    chapter = _validate_safe_filename_component(payload[CHAPTER_FIELD], CHAPTER_FIELD)
    question_id = _validate_safe_filename_component(payload[ID_FIELD], ID_FIELD)
    root = Path(runtime_config.chapters_dir).resolve(strict=True)
    target = root / stage / chapter / f"{question_id}.tex"
    return _resolve_path_inside_root(target, root)


def collect_existing_physics_ids(runtime_config: RuntimeConfig) -> set[str]:
    ids = {str(row.get(QUESTION_ID_FIELD, "")).strip() for row in read_csv_index(runtime_config=runtime_config)}
    ids.discard("")
    for file_path in iter_real_question_files(runtime_config):
        try:
            content = Path(file_path).read_text(encoding="utf-8")
            meta, _ = parse_meta_data(content)
            qid = str(meta.get(ID_FIELD, "")).strip() or Path(file_path).stem
            if qid:
                ids.add(qid)
        except Exception:
            continue
    return ids


def validate_physics_index_integrity(runtime_config: RuntimeConfig, expected_math_sha256: str | None = None) -> None:
    math_runtime = get_math_runtime(runtime_config.base_dir)
    if expected_math_sha256 and sha256_file(math_runtime.csv_index_path) != expected_math_sha256:
        raise PhysicsQuestionError("数学索引 SHA-256 发生变化，已阻止本次物理保存。")

    physics_files = list(iter_real_question_files(runtime_config))
    physics_rows = read_csv_index(runtime_config=runtime_config)
    if len(physics_rows) != len(physics_files):
        raise PhysicsQuestionError(f"物理索引行数与真实题目数不一致：索引 {len(physics_rows)}，文件 {len(physics_files)}。")

    seen_ids = set()
    seen_paths = set()
    root = Path(runtime_config.chapters_dir).resolve(strict=True)
    for row in physics_rows:
        qid = str(row.get(QUESTION_ID_FIELD, "")).strip()
        if not qid:
            raise PhysicsQuestionError("物理索引中存在空题目ID。")
        if qid in seen_ids:
            raise PhysicsQuestionError(f"物理索引中存在重复题目ID：{qid}")
        seen_ids.add(qid)

        rel_path = str(row.get(REL_PATH_FIELD, "")).strip()
        if not rel_path:
            raise PhysicsQuestionError("物理索引中存在空路径。")
        normalized_rel_path = os.path.normcase(os.path.normpath(rel_path))
        if normalized_rel_path in seen_paths:
            raise PhysicsQuestionError(f"物理索引中存在重复相对路径：{rel_path}")
        seen_paths.add(normalized_rel_path)
        if "chapters/" in rel_path.replace("\\", "/"):
            raise PhysicsQuestionError(f"物理索引中出现数学路径：{rel_path}")
        _resolve_path_inside_root(root / rel_path, root)
        if not (root / rel_path).exists():
            raise PhysicsQuestionError(f"物理索引路径不存在：{rel_path}")

    for row in read_csv_index(runtime_config=math_runtime):
        rel_path = str(row.get(REL_PATH_FIELD, "")).strip()
        if "chapters_physics" in rel_path.replace("\\", "/"):
            raise PhysicsQuestionError(f"数学索引中出现物理路径：{rel_path}")


def _refresh_and_validate_physics_index(runtime_config: RuntimeConfig, math_hash_before: str) -> None:
    result = rebuild_index("physics", base_dir=runtime_config.base_dir, sync_artifacts=False, write_report=False)
    if result.get("csv_path") != runtime_config.csv_index_path:
        raise PhysicsQuestionError("物理索引刷新目标路径异常。")
    validate_physics_index_integrity(runtime_config, expected_math_sha256=math_hash_before)


def _verify_single_question_file(path: Path, runtime_config: RuntimeConfig, expected_id: str) -> None:
    record = parse_question_record(str(path), runtime_config)
    if str(record.get(QUESTION_ID_FIELD, "")).strip() != expected_id:
        raise PhysicsQuestionError("保存后的题目ID回读不一致。")
    for field in ("题干", "答案", "解析"):
        if not str(record.get(field, "")).strip():
            raise PhysicsQuestionError(f"保存后的{field}为空。")


def _resolve_existing_file_in_physics_root(file_path: str | Path, runtime_config: RuntimeConfig) -> Path:
    root = Path(runtime_config.chapters_dir).resolve(strict=True)
    candidate = Path(file_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = _resolve_path_inside_root(candidate, root)
    if not resolved.exists() or not resolved.is_file():
        raise PhysicsQuestionError(f"物理题文件不存在：{resolved}")
    return resolved


def _resolve_path_inside_root(path: Path, root: Path) -> Path:
    if path.is_absolute():
        resolved = path.resolve(strict=False)
    else:
        resolved = (root / path).resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PhysicsQuestionError(f"目标路径不在物理题库目录内：{resolved}") from exc
    _reject_symlink_chain(root, resolved.parent)
    return resolved


def _reject_symlink_chain(root: Path, parent: Path) -> None:
    current = root
    if current.is_symlink():
        raise PhysicsQuestionError(f"物理题库根目录不能是软链接：{root}")
    try:
        relative_parts = parent.resolve(strict=False).relative_to(root).parts
    except ValueError as exc:
        raise PhysicsQuestionError(f"目标目录不在物理题库目录内：{parent}") from exc
    for part in relative_parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise PhysicsQuestionError(f"目标路径包含软链接目录：{current}")


def _ensure_writable_parent(path: Path, runtime_config: RuntimeConfig) -> None:
    root = Path(runtime_config.chapters_dir).resolve(strict=True)
    _resolve_path_inside_root(path, root)
    _reject_symlink_chain(root, path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)


def _validate_safe_filename_component(value: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise PhysicsQuestionError(f"{field_name}不能为空。")
    if text in {".", ".."} or ".." in text:
        raise PhysicsQuestionError(f"{field_name}不能包含路径跳转：{text}")
    if any(sep in text for sep in ("/", "\\")) or ":" in text:
        raise PhysicsQuestionError(f"{field_name}不能包含路径分隔符或盘符：{text}")
    if Path(text).is_absolute():
        raise PhysicsQuestionError(f"{field_name}不能是绝对路径：{text}")
    if not re.fullmatch(r"[A-Za-z0-9_\-\u4e00-\u9fff]+", text):
        raise PhysicsQuestionError(f"{field_name}只能包含中文、英文、数字、短横线和下划线：{text}")
    if text.upper() in WINDOWS_RESERVED_NAMES:
        raise PhysicsQuestionError(f"{field_name}不能使用 Windows 保留名称：{text}")
    return text


def _single_line(value: str, field_name: str) -> str:
    text = str(value or "")
    if "\n" in text or "\r" in text:
        raise PhysicsQuestionError(f"{field_name}不能包含换行。")
    if "% ===" in text:
        raise PhysicsQuestionError(f"{field_name}不能包含 Label Data 控制标记。")
    return text


def _read_optional_bytes(path: str | Path) -> bytes | None:
    p = Path(path)
    return p.read_bytes() if p.exists() else None


def _restore_optional_bytes(path: str | Path, data: bytes | None) -> None:
    p = Path(path)
    if data is None:
        if p.exists():
            p.unlink()
    else:
        p.write_bytes(data)
