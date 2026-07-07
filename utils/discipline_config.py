from dataclasses import dataclass


@dataclass(frozen=True)
class DisciplineConfig:
    key: str
    subject_name: str
    subjects: tuple[str, ...]
    page_title: str
    default_ocr_prompt: str
    ai_role_tagger: str
    ai_role_solver: str
    ai_role_exam_intent: str
    template_subject_name: str
    main_tex_title: str
    main_tex_chapter_order: tuple[str, ...]


MATHEMATICS = DisciplineConfig(
    key="mathematics",
    subject_name="数学",
    subjects=(
        "集合",
        "复数",
        "不等式",
        "函数",
        "概率",
        "统计",
        "排列组合",
        "解析几何",
        "圆锥曲线",
        "解三角形",
        "三角函数",
        "立体几何",
        "向量",
        "数列",
        "导数",
        "线性规划",
        "数论",
        "命题与逻辑",
        "流程框图",
        "未分类",
    ),
    page_title="高中数学题库管理系统",
    default_ocr_prompt="请识别这张图片中的数学题，并严格按照 LaTeX 格式输出。",
    ai_role_tagger="专业的高中数学教研专家",
    ai_role_solver="资深高中数学教研专家",
    ai_role_exam_intent="资深的高中数学教研专家",
    template_subject_name="数学",
    main_tex_title="高中数学思维体系",
    main_tex_chapter_order=(
        "集合",
        "复数",
        "不等式",
        "函数",
        "概率",
        "统计",
        "排列组合",
        "解析几何",
        "圆锥曲线",
        "解三角形",
        "三角函数",
        "立体几何",
        "向量",
        "数列",
        "导数",
        "线性规划",
        "数论",
        "命题与逻辑",
        "流程框图",
    ),
)


DISCIPLINES = {
    MATHEMATICS.key: MATHEMATICS,
}

ACTIVE_DISCIPLINE_KEY = "mathematics"
CURRENT_DISCIPLINE = DISCIPLINES[ACTIVE_DISCIPLINE_KEY]
