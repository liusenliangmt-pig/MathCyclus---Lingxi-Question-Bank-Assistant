import os

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*_args, **_kwargs):
        return False

from .discipline_config import CURRENT_DISCIPLINE

# 加载环境变量
load_dotenv()

# ================= 配置与常量 =================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAPTERS_DIR = os.path.join(BASE_DIR, "chapters")
CSV_INDEX_PATH = os.path.join(BASE_DIR, "utils", "题库索引表.csv")

# 学科配置
DISCIPLINE_KEY = CURRENT_DISCIPLINE.key
DISCIPLINE_NAME = CURRENT_DISCIPLINE.subject_name
SUBJECTS = list(CURRENT_DISCIPLINE.subjects)
PAGE_TITLE = CURRENT_DISCIPLINE.page_title
DEFAULT_OCR_PROMPT = CURRENT_DISCIPLINE.default_ocr_prompt
AI_ROLE_TAGGER = CURRENT_DISCIPLINE.ai_role_tagger
AI_ROLE_SOLVER = CURRENT_DISCIPLINE.ai_role_solver
AI_ROLE_EXAM_INTENT = CURRENT_DISCIPLINE.ai_role_exam_intent
EXPORT_TEMPLATE_SUBJECT_NAME = CURRENT_DISCIPLINE.template_subject_name
MAIN_TEX_TITLE = CURRENT_DISCIPLINE.main_tex_title
MAIN_TEX_CHAPTER_ORDER = list(CURRENT_DISCIPLINE.main_tex_chapter_order)

# AI 配置
AI_API_KEY = os.getenv("AI_API_KEY")
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.openai.com/v1")
AI_MODEL_NAME = os.getenv("AI_MODEL_NAME", "gpt-4o")

# 读取 OCR 提示词 (优先从文件读取，否则从环境变量)
ocr_prompt_file = os.path.join(BASE_DIR, "ocr_prompt.txt")
if os.path.exists(ocr_prompt_file):
    with open(ocr_prompt_file, "r", encoding="utf-8") as f:
        AI_OCR_PROMPT = f.read()
else:
    # 处理 .env 中的换行符转义
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
