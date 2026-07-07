from dataclasses import dataclass


@dataclass(frozen=True)
class DisciplineConfig:
    key: str
    subject_name: str
    page_title: str
    page_intro: str
    question_bank_dirname: str
    index_filename: str
    school_stages: tuple[str, ...]
    grades: tuple[str, ...]
    question_types: tuple[str, ...]
    subjects: tuple[str, ...]
    default_ocr_prompt: str
    ai_role_tagger: str
    ai_role_solver: str
    ai_role_exam_intent: str
    template_subject_name: str
    main_tex_title: str
    main_tex_chapter_order: tuple[str, ...]
    default_unit_rules: tuple[str, ...]
    default_formula_rules: tuple[str, ...]


MATHEMATICS = DisciplineConfig(
    key="mathematics",
    subject_name="数学",
    page_title="高中数学题库管理系统",
    page_intro="面向高中数学题库的录入、检索、组卷与导出工具。",
    question_bank_dirname="chapters",
    index_filename="题库索引表.csv",
    school_stages=("高中",),
    grades=("高一", "高二", "高三"),
    question_types=("选择题", "填空题", "解答题"),
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
    default_unit_rules=(),
    default_formula_rules=(),
)


PHYSICS = DisciplineConfig(
    key="physics",
    subject_name="物理",
    page_title="中学物理题库管理系统",
    page_intro="面向初中与高中物理题库的录入、检索、抽题、组卷与导出工具。",
    question_bank_dirname="chapters_physics",
    index_filename="物理题库索引表.csv",
    school_stages=("初中", "高中"),
    grades=("八年级", "九年级", "高一", "高二", "高三"),
    question_types=(
        "单项选择题",
        "多项选择题",
        "填空题",
        "作图题",
        "实验探究题",
        "计算题",
        "综合应用题",
        "论证与解释题",
    ),
    subjects=(
        "机械运动",
        "声现象",
        "光现象",
        "质量与密度",
        "力与运动",
        "压强",
        "浮力",
        "功和机械能",
        "简单机械",
        "内能与热机",
        "电流和电路",
        "电压和电阻",
        "欧姆定律",
        "电功率",
        "家庭电路",
        "电与磁",
        "信息与能源",
        "实验探究",
        "运动学",
        "相互作用",
        "牛顿运动定律",
        "曲线运动",
        "万有引力",
        "功和能",
        "动量",
        "机械振动",
        "机械波",
        "静电场",
        "恒定电流",
        "磁场",
        "电磁感应",
        "交变电流",
        "传感器",
        "热学",
        "光学",
        "原子物理",
        "实验",
        "综合题",
    ),
    default_ocr_prompt="请识别这张图片中的物理题，并严格按照 LaTeX 格式输出，保留物理量、单位、图示说明和实验条件。",
    ai_role_tagger="专业的中学物理教研专家",
    ai_role_solver="资深中学物理教研专家",
    ai_role_exam_intent="资深的中学物理命题与组卷专家",
    template_subject_name="物理",
    main_tex_title="中学物理知识体系",
    main_tex_chapter_order=(
        "机械运动",
        "声现象",
        "光现象",
        "质量与密度",
        "力与运动",
        "压强",
        "浮力",
        "功和机械能",
        "简单机械",
        "内能与热机",
        "电流和电路",
        "电压和电阻",
        "欧姆定律",
        "电功率",
        "家庭电路",
        "电与磁",
        "信息与能源",
        "实验探究",
        "运动学",
        "相互作用",
        "牛顿运动定律",
        "曲线运动",
        "万有引力",
        "功和能",
        "动量",
        "机械振动",
        "机械波",
        "静电场",
        "恒定电流",
        "磁场",
        "电磁感应",
        "交变电流",
        "传感器",
        "热学",
        "光学",
        "原子物理",
        "实验",
        "综合题",
    ),
    default_unit_rules=(
        "物理量优先使用 SI 单位。",
        "数值与单位之间保留一个空格，如 5 N、2.0 m/s。",
        "角度使用 °，温度使用 ℃，电能常用 kW·h 时保持原样。",
    ),
    default_formula_rules=(
        "矢量符号、下标和物理量字母保持规范书写。",
        "单位不放入数学公式变量定义中，结果单独写单位。",
        "实验题中的表格、图像和电路图说明应保持可读性。",
    ),
)


DISCIPLINES = {
    MATHEMATICS.key: MATHEMATICS,
    PHYSICS.key: PHYSICS,
}

DEFAULT_DISCIPLINE_KEY = MATHEMATICS.key


def normalize_discipline_code(discipline_code: str | None) -> str:
    code = (discipline_code or "").strip().lower()
    return code or DEFAULT_DISCIPLINE_KEY


def get_discipline_config(discipline_code: str | None = None) -> DisciplineConfig:
    normalized = normalize_discipline_code(discipline_code)
    if normalized not in DISCIPLINES:
        supported = ", ".join(sorted(DISCIPLINES))
        raise KeyError(f"Unsupported discipline '{normalized}'. Supported disciplines: {supported}")
    return DISCIPLINES[normalized]


def list_discipline_codes() -> tuple[str, ...]:
    return tuple(DISCIPLINES.keys())


def list_discipline_options() -> tuple[tuple[str, str], ...]:
    return tuple((code, config.subject_name) for code, config in DISCIPLINES.items())
