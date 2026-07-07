# Math Regression Test Report

- 时间：2026-07-07 20:43:13
- 分支：`physics-support`（通过 `.git/HEAD` 检查）
- 项目路径：`F:\AI project\MathCyclus---Lingxi-Question-Bank-Assistant\MathCyclus---Lingxi-Question-Bank-Assistant`
- 本阶段未增加任何物理功能

## 1. 环境信息

- Python 版本：`3.12.13`
- 虚拟环境位置：`F:\AI project\MathCyclus---Lingxi-Question-Bank-Assistant\MathCyclus---Lingxi-Question-Bank-Assistant\.venv`
- `.venv`：已存在并可用
- `.env`：不存在；本阶段未创建、未修改
- 主要依赖版本：
- `streamlit 1.59.0`
- `python-dotenv 1.2.2`
- `requests 2.34.2`
- `Pillow 12.3.0`
- `PyMuPDF 1.28.0`

## 2. 已做最小代码修复

- `utils/batch_gen.py`
- 修复内容：将 `update_chapter_contents()` 的 docstring 改为 raw docstring，消除 `\input` 导致的 `SyntaxWarning`
- 业务逻辑变更：无
- 修复后验证：
- 只读语法编译通过
- `SyntaxWarning` 复检通过

## 3. Streamlit 启动验证

- 启动命令：`streamlit run question_bank_app.py`
- 启动方式：使用项目本地虚拟环境
- 启动结果：通过
- 启动端口：`8501`
- 本地访问：`http://localhost:8501`
- 浏览器访问本地页面：通过
- HTTP 连通性检查：通过
- 启动期 Python 异常堆栈：未发现导致启动失败的异常

终端/日志中的非阻塞告警：

- 多次出现 `st.components.v1.html` 已弃用提示，建议后续替换为 `st.iframe`
- 在高级检索交互期间，日志中出现一次 Streamlit Session State widget warning，并附带调用栈；未导致页面不可用或程序退出，但建议后续单独清理

## 4. 数学功能回归结果

- 首页正常显示：通过
- 题库统计显示 70 道真实题目：通过
- 按知识板块筛选：通过
- 按年份筛选：通过
- 按标签筛选：通过
- 全文搜索：通过
- 可打开单题详情：通过
- 题干、答案、解析读取：通过
- 随机选择少量题目组卷：通过
- 组卷结果不存在缺失文件：通过
- LaTeX 源文件导出：通过
- PDF 编译：跳过，原因是本机未安装 `xelatex`
- AI OCR / AI 解答 / AI 标签 / AI 润色在无 `.env` 时安全降级：通过

说明：

- 浏览器回归验证确认首页、浏览页、筛选、搜索、单题详情均可正常工作
- 组卷页已可打开；考虑到 Streamlit 前端按钮自动化不稳定，组卷导出使用后端 smoke test 做补充验证
- 抽样组卷使用了 3 个真实且互不重复的题目文件，成功导出 `.tex`

## 5. 只读 Smoke Test 结果

- 真实题目文件数：`70`
- CSV 索引记录数：`70`
- CSV 每条记录对应 `.tex` 文件存在：通过
- 题目详情解析成功：`70 / 70`
- 题干非空：`70 / 70`
- 至少存在题干、答案、解析均非空的题目详情：通过
- 具备完整题干/答案/解析的题目数：`22`
- 抽样组卷无重复题：通过
- 导出 `.tex` 文件生成成功：通过
- 所有修改过的 Python 文件语法检查通过：通过

补充观察：

- 有 `45` 个真实题目文件的 `answer` 代码块为空
- 有 `45` 个真实题目文件的 `solutions` 代码块为空
- 已抽查源文件，确认这属于当前题库源数据现状，不是本次解析器回归引入的问题

## 6. 逐项状态

- 环境分支检查：通过
- Python 版本检查：通过
- `.venv` 检查/创建：通过
- 依赖安装：通过
- `utils/batch_gen.py` SyntaxWarning 修复：通过
- 修复后语法检查：通过
- Streamlit 启动：通过
- 浏览器访问本地页面：通过
- 首页显示：通过
- 题库数量 70：通过
- 板块筛选：通过
- 年份筛选：通过
- 标签筛选：通过
- 全文搜索：通过
- 单题详情打开：通过
- 详情解析非空：通过
- 抽样组卷：通过
- 组卷无缺失文件：通过
- LaTeX 导出：通过
- PDF 编译：跳过
- AI 功能缺省降级：通过
- CSV 映射检查：通过
- 抽样无重复题：通过
- 修改过的 Python 文件语法正常：通过

## 7. 失败摘要

- 无阻塞失败项

## 8. 结论

- 当前数学系统已完成本地启动与核心回归验证，可以作为后续 `physics-support` 分支开发基线
- 建议进入物理功能开发阶段
- 进入下一阶段前的注意点：
- 先不要把“题库中已有 45 题缺少答案/解析”误判为本次程序回归问题
- 若后续需要进一步提纯基线，可单独处理 `st.components.v1.html` 弃用提示和高级检索页的 Session State warning
