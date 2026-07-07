import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*_args, **_kwargs):
        return False

from .discipline_config import DEFAULT_DISCIPLINE_KEY, DisciplineConfig, get_discipline_config


load_dotenv()


@dataclass(frozen=True)
class RuntimeConfig:
    discipline: DisciplineConfig
    base_dir: str
    chapters_dir: str
    csv_index_path: str
    discipline_key: str
    discipline_name: str
    page_title: str
    page_intro: str
    school_stages: tuple[str, ...]
    grades: tuple[str, ...]
    question_types: tuple[str, ...]
    subjects: tuple[str, ...]
    default_ocr_prompt: str
    ai_role_tagger: str
    ai_role_solver: str
    ai_role_exam_intent: str
    export_template_subject_name: str
    main_tex_title: str
    main_tex_chapter_order: tuple[str, ...]
    default_unit_rules: tuple[str, ...]
    default_formula_rules: tuple[str, ...]


def build_runtime_config(discipline_code: str | None = None, base_dir: str | None = None) -> RuntimeConfig:
    resolved_base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    discipline = get_discipline_config(discipline_code)
    chapters_dir = os.path.join(resolved_base_dir, discipline.question_bank_dirname)
    csv_index_path = os.path.join(resolved_base_dir, "utils", discipline.index_filename)
    return RuntimeConfig(
        discipline=discipline,
        base_dir=resolved_base_dir,
        chapters_dir=chapters_dir,
        csv_index_path=csv_index_path,
        discipline_key=discipline.key,
        discipline_name=discipline.subject_name,
        page_title=discipline.page_title,
        page_intro=discipline.page_intro,
        school_stages=discipline.school_stages,
        grades=discipline.grades,
        question_types=discipline.question_types,
        subjects=discipline.subjects,
        default_ocr_prompt=discipline.default_ocr_prompt,
        ai_role_tagger=discipline.ai_role_tagger,
        ai_role_solver=discipline.ai_role_solver,
        ai_role_exam_intent=discipline.ai_role_exam_intent,
        export_template_subject_name=discipline.template_subject_name,
        main_tex_title=discipline.main_tex_title,
        main_tex_chapter_order=discipline.main_tex_chapter_order,
        default_unit_rules=discipline.default_unit_rules,
        default_formula_rules=discipline.default_formula_rules,
    )


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_RUNTIME_CONFIG = build_runtime_config(DEFAULT_DISCIPLINE_KEY, base_dir=BASE_DIR)

# Backward-compatible defaults for existing mathematics-only code paths.
CHAPTERS_DIR = DEFAULT_RUNTIME_CONFIG.chapters_dir
CSV_INDEX_PATH = DEFAULT_RUNTIME_CONFIG.csv_index_path
DISCIPLINE_KEY = DEFAULT_RUNTIME_CONFIG.discipline_key
DISCIPLINE_NAME = DEFAULT_RUNTIME_CONFIG.discipline_name
PAGE_TITLE = DEFAULT_RUNTIME_CONFIG.page_title
PAGE_INTRO = DEFAULT_RUNTIME_CONFIG.page_intro
SCHOOL_STAGES = list(DEFAULT_RUNTIME_CONFIG.school_stages)
GRADES = list(DEFAULT_RUNTIME_CONFIG.grades)
QUESTION_TYPES = list(DEFAULT_RUNTIME_CONFIG.question_types)
SUBJECTS = list(DEFAULT_RUNTIME_CONFIG.subjects)
DEFAULT_OCR_PROMPT = DEFAULT_RUNTIME_CONFIG.default_ocr_prompt
AI_ROLE_TAGGER = DEFAULT_RUNTIME_CONFIG.ai_role_tagger
AI_ROLE_SOLVER = DEFAULT_RUNTIME_CONFIG.ai_role_solver
AI_ROLE_EXAM_INTENT = DEFAULT_RUNTIME_CONFIG.ai_role_exam_intent
EXPORT_TEMPLATE_SUBJECT_NAME = DEFAULT_RUNTIME_CONFIG.export_template_subject_name
MAIN_TEX_TITLE = DEFAULT_RUNTIME_CONFIG.main_tex_title
MAIN_TEX_CHAPTER_ORDER = list(DEFAULT_RUNTIME_CONFIG.main_tex_chapter_order)
DEFAULT_UNIT_RULES = list(DEFAULT_RUNTIME_CONFIG.default_unit_rules)
DEFAULT_FORMULA_RULES = list(DEFAULT_RUNTIME_CONFIG.default_formula_rules)

AI_API_KEY = os.getenv("AI_API_KEY")
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.openai.com/v1")
AI_MODEL_NAME = os.getenv("AI_MODEL_NAME", "gpt-4o")

ocr_prompt_file = os.path.join(BASE_DIR, "ocr_prompt.txt")
if os.path.exists(ocr_prompt_file):
    with open(ocr_prompt_file, "r", encoding="utf-8") as f:
        AI_OCR_PROMPT = f.read()
else:
    AI_OCR_PROMPT = os.getenv("AI_OCR_PROMPT", DEFAULT_OCR_PROMPT).replace("\\n", "\n")


PAPER_TYPES = {
    "G": "高考题",
    "M": "模拟题",
    "W": "外国题",
    "XK": "学考题",
    "XS": "线上联考",
    "QJ": "强基计划题",
    "JS": "竞赛题",
}
