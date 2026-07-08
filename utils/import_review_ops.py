from __future__ import annotations

import datetime
import json
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from utils.core_config import RuntimeConfig, build_runtime_config
from utils.physics_question_ops import (
    ANSWER_FIELD,
    CHAPTER_FIELD,
    DIFFICULTY_FIELD,
    ENABLED_FIELD,
    EXPERIMENT_TYPE_FIELD,
    GRADE_FIELD,
    HAS_CIRCUIT_FIELD,
    HAS_FORCE_FIELD,
    HAS_LIGHT_FIELD,
    HAS_TABLE_FIELD,
    ID_FIELD,
    IMAGE_TYPE_FIELD,
    KNOWLEDGE_POINT_FIELD,
    PROBLEM_FIELD,
    QUESTION_TYPE_FIELD,
    REMARK_FIELD,
    SCORE_FIELD,
    SOLUTION_FIELD,
    SOURCE_FIELD,
    STAGE_FIELD,
    TAGS_FIELD,
    UNIT_RULE_FIELD,
    VOLUME_FIELD,
    PhysicsQuestionError,
    collect_existing_physics_ids,
    save_new_physics_question,
    validate_physics_index_integrity,
    validate_physics_question_payload,
)


SCHEMA_VERSION = 1
STAGING_DIRNAME = "data/import_staging"
PENDING_REVIEW = "pending_review"
APPROVED = "approved"
REJECTED = "rejected"
REVIEW_STATUS_LABELS = {
    PENDING_REVIEW: "待审核",
    APPROVED: "已通过",
    REJECTED: "已驳回",
}
APPROVED_PHYSICS_REVIEW_STATUS = "已通过"
ALLOWED_REVIEW_STATUSES = {PENDING_REVIEW, APPROVED, REJECTED}

SOURCE_TYPE_FIELD = "source_type"
SOURCE_FILE_FIELD = "source_file"
SOURCE_PAGE_FIELD = "source_page"
SOURCE_REGION_FIELD = "source_region"
IMPORT_BATCH_ID_FIELD = "import_batch_id"
RECOGNITION_METHOD_FIELD = "recognition_method"
OCR_CONFIDENCE_FIELD = "ocr_confidence"
ORIGINAL_IMAGE_PATH_FIELD = "original_image_path"
REVIEW_NOTES_FIELD = "review_notes"

PDF_FIELD_MAPPING = {
    SOURCE_TYPE_FIELD: "来源类型",
    SOURCE_FILE_FIELD: "来源文件",
    SOURCE_PAGE_FIELD: "来源页码",
    SOURCE_REGION_FIELD: "来源区域坐标",
    IMPORT_BATCH_ID_FIELD: "导入批次ID",
    RECOGNITION_METHOD_FIELD: "识别方式",
    OCR_CONFIDENCE_FIELD: "OCR置信度",
    "review_status": "审核状态",
    REVIEW_NOTES_FIELD: "审核备注",
    ORIGINAL_IMAGE_PATH_FIELD: "原始图片路径",
}

BASE_FIELDS = (
    "candidate_id",
    "discipline",
    "review_status",
    REVIEW_NOTES_FIELD,
    "created_at",
    "updated_at",
)
SOURCE_FIELDS = (
    SOURCE_TYPE_FIELD,
    SOURCE_FILE_FIELD,
    SOURCE_PAGE_FIELD,
    SOURCE_REGION_FIELD,
    IMPORT_BATCH_ID_FIELD,
    RECOGNITION_METHOD_FIELD,
    OCR_CONFIDENCE_FIELD,
    ORIGINAL_IMAGE_PATH_FIELD,
)
QUESTION_FIELDS = (
    "question_id",
    "stage",
    "grade",
    "volume",
    "knowledge_block",
    "knowledge_point",
    "question_type",
    "difficulty",
    "score",
    "tags",
    "source",
    "remark",
    "experiment_type",
    "image_type",
    "unit_requirement",
    "has_circuit_diagram",
    "has_force_diagram",
    "has_optical_diagram",
    "has_experiment_table",
    "enabled",
    "problem",
    "answer",
    "solutions",
)
REQUIRED_CANDIDATE_FIELDS = (
    "candidate_id",
    "discipline",
    "review_status",
    "question_id",
    "stage",
    "grade",
    "knowledge_block",
    "knowledge_point",
    "question_type",
    "difficulty",
    "score",
    "problem",
    "answer",
    "solutions",
)
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class ImportReviewError(ValueError):
    pass


@dataclass(frozen=True)
class ApprovalResult:
    candidate_id: str
    question_id: str
    official_file_path: str
    review_status: str


def now_iso() -> str:
    return datetime.datetime.now().replace(microsecond=0).isoformat(sep=" ")


def get_staging_root(base_dir: str | Path | None = None) -> Path:
    root = Path(base_dir or Path(__file__).resolve().parents[1]) / STAGING_DIRNAME
    return root.resolve()


def validate_safe_id(value: str, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ImportReviewError(f"{label}不能为空。")
    if not SAFE_ID_RE.fullmatch(text):
        raise ImportReviewError(f"{label}只能包含英文字母、数字、短横线和下划线：{text}")
    if text.upper() in WINDOWS_RESERVED_NAMES:
        raise ImportReviewError(f"{label}不能使用 Windows 保留名称：{text}")
    if ".." in text or ":" in text or "/" in text or "\\" in text:
        raise ImportReviewError(f"{label}包含非法路径字符：{text}")
    if Path(text).is_absolute():
        raise ImportReviewError(f"{label}不能是绝对路径：{text}")
    return text


def ensure_inside_staging(path: str | Path, staging_root: str | Path) -> Path:
    root = Path(staging_root).resolve()
    resolved = Path(path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ImportReviewError(f"暂存路径越界：{resolved}") from exc
    return resolved


def batch_dir(batch_id: str, base_dir: str | Path | None = None) -> Path:
    safe_batch_id = validate_safe_id(batch_id, "batch_id")
    root = get_staging_root(base_dir)
    return ensure_inside_staging(root / safe_batch_id, root)


def candidate_path(batch_id: str, candidate_id: str, base_dir: str | Path | None = None) -> Path:
    safe_candidate_id = validate_safe_id(candidate_id, "candidate_id")
    root = get_staging_root(base_dir)
    path = batch_dir(batch_id, base_dir) / "candidates" / f"{safe_candidate_id}.json"
    return ensure_inside_staging(path, root)


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def _load_json(path: Path, expected_kind: str) -> dict:
    if not path.exists():
        raise ImportReviewError(f"{expected_kind}不存在：{path}")
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ImportReviewError(f"{expected_kind} JSON损坏：{path}；{exc}") from exc
    if not isinstance(data, dict):
        raise ImportReviewError(f"{expected_kind} JSON格式错误：根节点必须是对象。")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ImportReviewError(f"{expected_kind} schema_version 不支持：{data.get('schema_version')}")
    return data


def create_import_batch(batch_id: str, base_dir: str | Path | None = None, source_type: str = "manual") -> dict:
    safe_batch_id = validate_safe_id(batch_id, "batch_id")
    directory = batch_dir(safe_batch_id, base_dir)
    path = directory / "batch.json"
    if path.exists():
        return load_import_batch(safe_batch_id, base_dir)
    timestamp = now_iso()
    data = {
        "schema_version": SCHEMA_VERSION,
        "batch_id": safe_batch_id,
        "source_type": source_type,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    _atomic_write_json(path, data)
    (directory / "candidates").mkdir(parents=True, exist_ok=True)
    (directory / "assets").mkdir(parents=True, exist_ok=True)
    return data


def load_import_batch(batch_id: str, base_dir: str | Path | None = None) -> dict:
    data = _load_json(batch_dir(batch_id, base_dir) / "batch.json", "导入批次")
    if data.get("batch_id") != validate_safe_id(batch_id, "batch_id"):
        raise ImportReviewError("导入批次ID与路径不一致。")
    return data


def default_candidate_payload(batch_id: str, candidate_id: str) -> dict:
    timestamp = now_iso()
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": validate_safe_id(candidate_id, "candidate_id"),
        "discipline": "physics",
        "review_status": PENDING_REVIEW,
        REVIEW_NOTES_FIELD: "",
        "created_at": timestamp,
        "updated_at": timestamp,
        SOURCE_TYPE_FIELD: "manual",
        SOURCE_FILE_FIELD: "",
        SOURCE_PAGE_FIELD: "",
        SOURCE_REGION_FIELD: "",
        IMPORT_BATCH_ID_FIELD: validate_safe_id(batch_id, "batch_id"),
        RECOGNITION_METHOD_FIELD: "manual",
        OCR_CONFIDENCE_FIELD: "",
        ORIGINAL_IMAGE_PATH_FIELD: "",
        "question_id": "",
        "stage": "",
        "grade": "",
        "volume": "通用",
        "knowledge_block": "",
        "knowledge_point": "",
        "question_type": "",
        "difficulty": "",
        "score": "",
        "tags": "",
        "source": "本地导入候选题",
        "remark": "",
        "experiment_type": "无",
        "image_type": "无",
        "unit_requirement": "",
        "has_circuit_diagram": "否",
        "has_force_diagram": "否",
        "has_optical_diagram": "否",
        "has_experiment_table": "否",
        "enabled": "是",
        "problem": "",
        "answer": "",
        "solutions": "",
    }


def normalize_candidate(candidate: dict, batch_id: str | None = None, candidate_id: str | None = None, keep_created_at: str | None = None) -> dict:
    data = dict(default_candidate_payload(batch_id or candidate.get(IMPORT_BATCH_ID_FIELD, ""), candidate_id or candidate.get("candidate_id", "")))
    data.update(candidate)
    data["schema_version"] = SCHEMA_VERSION
    data["candidate_id"] = validate_safe_id(data.get("candidate_id", ""), "candidate_id")
    data[IMPORT_BATCH_ID_FIELD] = validate_safe_id(data.get(IMPORT_BATCH_ID_FIELD, batch_id or ""), "batch_id")
    if batch_id and data[IMPORT_BATCH_ID_FIELD] != validate_safe_id(batch_id, "batch_id"):
        raise ImportReviewError("候选题所属批次与保存路径不一致。")
    if data.get("discipline") != "physics":
        raise ImportReviewError("当前阶段仅支持 physics 候选题。")
    if data.get("review_status") not in ALLOWED_REVIEW_STATUSES:
        raise ImportReviewError(f"候选题审核状态非法：{data.get('review_status')}")
    if keep_created_at:
        data["created_at"] = keep_created_at
    elif not data.get("created_at"):
        data["created_at"] = now_iso()
    data["updated_at"] = now_iso()
    return data


def validate_import_candidate(candidate: dict, runtime_config: RuntimeConfig | None = None) -> dict:
    runtime = runtime_config or build_runtime_config("physics")
    data = normalize_candidate(candidate)
    missing = [field for field in REQUIRED_CANDIDATE_FIELDS if not str(data.get(field, "")).strip()]
    if missing:
        raise ImportReviewError("候选题缺少必填字段：" + "、".join(missing))
    to_physics_payload(data, runtime, official_review_status=APPROVED_PHYSICS_REVIEW_STATUS)
    validate_physics_question_payload(to_physics_payload(data, runtime, official_review_status=APPROVED_PHYSICS_REVIEW_STATUS), runtime)
    return data


def save_import_candidate(batch_id: str, candidate: dict, base_dir: str | Path | None = None) -> dict:
    create_import_batch(batch_id, base_dir)
    data = normalize_candidate(candidate, batch_id=batch_id, candidate_id=candidate.get("candidate_id"))
    path = candidate_path(batch_id, data["candidate_id"], base_dir)
    if path.exists():
        raise ImportReviewError(f"候选题已存在，不能静默覆盖：{data['candidate_id']}")
    _atomic_write_json(path, data)
    _touch_batch(batch_id, base_dir)
    return data


def update_import_candidate(batch_id: str, candidate_id: str, updates: dict, base_dir: str | Path | None = None) -> dict:
    current = get_import_candidate(batch_id, candidate_id, base_dir)
    if current.get("review_status") == APPROVED:
        raise ImportReviewError("已通过候选题不能继续编辑。")
    if "review_status" in updates and updates["review_status"] != current.get("review_status"):
        raise ImportReviewError("review_status 只能通过审核服务接口变更。")
    merged = dict(current)
    merged.update(updates)
    merged["candidate_id"] = current["candidate_id"]
    merged[IMPORT_BATCH_ID_FIELD] = current[IMPORT_BATCH_ID_FIELD]
    data = normalize_candidate(merged, batch_id=batch_id, candidate_id=candidate_id, keep_created_at=current.get("created_at"))
    _atomic_write_json(candidate_path(batch_id, candidate_id, base_dir), data)
    _touch_batch(batch_id, base_dir)
    return data


def list_import_candidates(batch_id: str, base_dir: str | Path | None = None, status: str | None = None) -> list[dict]:
    load_import_batch(batch_id, base_dir)
    candidates_dir = batch_dir(batch_id, base_dir) / "candidates"
    if not candidates_dir.exists():
        return []
    rows = []
    for path in sorted(candidates_dir.glob("*.json")):
        data = _load_json(path, "候选题")
        if data.get(IMPORT_BATCH_ID_FIELD) != validate_safe_id(batch_id, "batch_id"):
            raise ImportReviewError(f"候选题批次字段与路径不一致：{path.name}")
        if status is None or data.get("review_status") == status:
            rows.append(data)
    return rows


def get_import_candidate(batch_id: str, candidate_id: str, base_dir: str | Path | None = None) -> dict:
    data = _load_json(candidate_path(batch_id, candidate_id, base_dir), "候选题")
    if data.get("candidate_id") != validate_safe_id(candidate_id, "candidate_id"):
        raise ImportReviewError("候选题ID与路径不一致。")
    if data.get(IMPORT_BATCH_ID_FIELD) != validate_safe_id(batch_id, "batch_id"):
        raise ImportReviewError("候选题批次ID与路径不一致。")
    return data


def reject_import_candidate(batch_id: str, candidate_id: str, review_notes: str, base_dir: str | Path | None = None) -> dict:
    current = get_import_candidate(batch_id, candidate_id, base_dir)
    if current.get("review_status") != PENDING_REVIEW:
        raise ImportReviewError("只有待审核候选题可以驳回。")
    current["review_status"] = REJECTED
    current[REVIEW_NOTES_FIELD] = str(review_notes or "").strip()
    current["rejected_at"] = now_iso()
    current["updated_at"] = now_iso()
    _atomic_write_json(candidate_path(batch_id, candidate_id, base_dir), current)
    _touch_batch(batch_id, base_dir)
    return current


def restore_candidate_to_pending(batch_id: str, candidate_id: str, base_dir: str | Path | None = None) -> dict:
    current = get_import_candidate(batch_id, candidate_id, base_dir)
    if current.get("review_status") != REJECTED:
        raise ImportReviewError("只有已驳回候选题可以恢复为待审核。")
    current["review_status"] = PENDING_REVIEW
    current["updated_at"] = now_iso()
    _atomic_write_json(candidate_path(batch_id, candidate_id, base_dir), current)
    _touch_batch(batch_id, base_dir)
    return current


def approve_import_candidate(
    batch_id: str,
    candidate_id: str,
    runtime_config: RuntimeConfig | None = None,
    base_dir: str | Path | None = None,
) -> ApprovalResult:
    runtime = runtime_config or build_runtime_config("physics", base_dir=str(base_dir) if base_dir else None)
    with _candidate_lock(batch_id, candidate_id, base_dir):
        current = get_import_candidate(batch_id, candidate_id, base_dir)
        if current.get("review_status") == APPROVED:
            raise ImportReviewError("该候选题已通过并入库，不能重复审批。")
        if current.get("review_status") == REJECTED:
            raise ImportReviewError("已驳回候选题不能直接入库，请先显式恢复为待审核。")
        if current.get("review_status") != PENDING_REVIEW:
            raise ImportReviewError(f"候选题状态不是待审核：{current.get('review_status')}")
        if current.get("official_question_id"):
            raise ImportReviewError("候选题已记录正式题目ID，不能重复入库。")

        question_id = str(current.get("question_id", "")).strip()
        existing_ids = collect_existing_physics_ids(runtime)
        if question_id in existing_ids:
            current["approval_error"] = "正式题目ID已存在，可能已入库但候选状态未恢复，请人工核查。"
            current["updated_at"] = now_iso()
            _atomic_write_json(candidate_path(batch_id, candidate_id, base_dir), current)
            raise ImportReviewError(current["approval_error"])

        payload = to_physics_payload(current, runtime, official_review_status=APPROVED_PHYSICS_REVIEW_STATUS)
        try:
            validate_import_candidate(current, runtime)
            result = save_new_physics_question(payload, runtime)
            validate_physics_index_integrity(runtime)
        except Exception as exc:
            latest = get_import_candidate(batch_id, candidate_id, base_dir)
            latest["approval_error"] = str(exc)
            latest["updated_at"] = now_iso()
            _atomic_write_json(candidate_path(batch_id, candidate_id, base_dir), latest)
            raise

        approved = get_import_candidate(batch_id, candidate_id, base_dir)
        approved["review_status"] = APPROVED
        approved["approved_at"] = now_iso()
        approved["official_question_id"] = result.question_id
        approved["official_file_path"] = result.file_path
        approved["approval_error"] = ""
        approved["updated_at"] = now_iso()
        _atomic_write_json(candidate_path(batch_id, candidate_id, base_dir), approved)
        _touch_batch(batch_id, base_dir)
        return ApprovalResult(
            candidate_id=candidate_id,
            question_id=result.question_id,
            official_file_path=result.file_path,
            review_status=APPROVED,
        )


def to_physics_payload(candidate: dict, runtime_config: RuntimeConfig, official_review_status: str) -> dict:
    return {
        ID_FIELD: candidate.get("question_id", ""),
        STAGE_FIELD: candidate.get("stage", ""),
        GRADE_FIELD: candidate.get("grade", ""),
        VOLUME_FIELD: candidate.get("volume", "通用"),
        CHAPTER_FIELD: candidate.get("knowledge_block", ""),
        KNOWLEDGE_POINT_FIELD: candidate.get("knowledge_point", ""),
        QUESTION_TYPE_FIELD: candidate.get("question_type", ""),
        DIFFICULTY_FIELD: candidate.get("difficulty", ""),
        SCORE_FIELD: candidate.get("score", ""),
        TAGS_FIELD: candidate.get("tags", ""),
        SOURCE_FIELD: candidate.get("source", "本地导入候选题"),
        ENABLED_FIELD: candidate.get("enabled", "是"),
        REMARK_FIELD: candidate.get("remark", ""),
        EXPERIMENT_TYPE_FIELD: candidate.get("experiment_type", "无"),
        IMAGE_TYPE_FIELD: candidate.get("image_type", "无"),
        UNIT_RULE_FIELD: candidate.get("unit_requirement", ""),
        HAS_CIRCUIT_FIELD: candidate.get("has_circuit_diagram", "否"),
        HAS_FORCE_FIELD: candidate.get("has_force_diagram", "否"),
        HAS_LIGHT_FIELD: candidate.get("has_optical_diagram", "否"),
        HAS_TABLE_FIELD: candidate.get("has_experiment_table", "否"),
        PROBLEM_FIELD: candidate.get("problem", ""),
        ANSWER_FIELD: candidate.get("answer", ""),
        SOLUTION_FIELD: candidate.get("solutions", ""),
        PDF_FIELD_MAPPING[SOURCE_TYPE_FIELD]: candidate.get(SOURCE_TYPE_FIELD, ""),
        PDF_FIELD_MAPPING[SOURCE_FILE_FIELD]: candidate.get(SOURCE_FILE_FIELD, ""),
        PDF_FIELD_MAPPING[SOURCE_PAGE_FIELD]: candidate.get(SOURCE_PAGE_FIELD, ""),
        PDF_FIELD_MAPPING[SOURCE_REGION_FIELD]: candidate.get(SOURCE_REGION_FIELD, ""),
        PDF_FIELD_MAPPING[IMPORT_BATCH_ID_FIELD]: candidate.get(IMPORT_BATCH_ID_FIELD, ""),
        PDF_FIELD_MAPPING[RECOGNITION_METHOD_FIELD]: candidate.get(RECOGNITION_METHOD_FIELD, ""),
        PDF_FIELD_MAPPING[OCR_CONFIDENCE_FIELD]: candidate.get(OCR_CONFIDENCE_FIELD, ""),
        PDF_FIELD_MAPPING["review_status"]: official_review_status,
        PDF_FIELD_MAPPING[REVIEW_NOTES_FIELD]: candidate.get(REVIEW_NOTES_FIELD, ""),
        PDF_FIELD_MAPPING[ORIGINAL_IMAGE_PATH_FIELD]: candidate.get(ORIGINAL_IMAGE_PATH_FIELD, ""),
    }


def cleanup_test_import_batch(batch_id: str, base_dir: str | Path | None = None) -> None:
    safe_batch_id = validate_safe_id(batch_id, "batch_id")
    if "TEMP" not in safe_batch_id.upper():
        raise ImportReviewError("cleanup_test_import_batch 只能清理 TEMP 测试批次。")
    directory = batch_dir(safe_batch_id, base_dir)
    root = get_staging_root(base_dir)
    directory = ensure_inside_staging(directory, root)
    if directory.exists():
        for child in sorted(directory.rglob("*"), reverse=True):
            if child.is_file() or child.is_symlink():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        directory.rmdir()


def _touch_batch(batch_id: str, base_dir: str | Path | None = None) -> None:
    path = batch_dir(batch_id, base_dir) / "batch.json"
    data = _load_json(path, "导入批次")
    data["updated_at"] = now_iso()
    _atomic_write_json(path, data)


@contextmanager
def _candidate_lock(batch_id: str, candidate_id: str, base_dir: str | Path | None = None):
    path = candidate_path(batch_id, candidate_id, base_dir).with_suffix(".lock")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(path), flags)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(now_iso())
            f.flush()
            os.fsync(f.fileno())
        yield
    except FileExistsError as exc:
        raise ImportReviewError("该候选题正在审核入库，请稍后重试。") from exc
    finally:
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass
