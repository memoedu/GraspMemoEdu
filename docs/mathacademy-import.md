# Math Academy JSON 课程导入

`Import-MathAcademy.ps1` 按源课程 ID 接收两个 ZIP，安装目标课程及显式前置内容。练习先按[题型改造规则](#题型改造)处理。保留原 JSON、缺失信息和图谱来源。

```powershell
# 导出课程和前置 Topic 中所有带选项的题，供本地判定
./Import-MathAcademy.ps1 -TopicsZip 'D:/Downloads/topic-json.zip' -GraphsZip 'D:/Downloads/course-knowledge-graph.zip' -CourseIds 72,140 -QuestionInventory 'D:/Artifacts/GraspMemoEdu/ma-question-inventory.json'

# 使用同一快照和课程范围，在隔离站点安装与验收
./Import-MathAcademy.ps1 -TopicsZip 'D:/Downloads/topic-json.zip' -GraphsZip 'D:/Downloads/course-knowledge-graph.zip' -CourseIds 72,140 -QuestionPlan 'D:/Artifacts/GraspMemoEdu/ma-question-plan.json' -DataDir 'D:/Artifacts/GraspMemoEdu/isolated-import' -OutputDirectory 'D:/Artifacts/GraspMemoEdu/ma-ml-prepared'
```

默认五门课程 ID 为 82、74、66、72、140；`-PlanOnly` 只计算闭包。环境复用项目 Python、Node/marked/MathJax/sanitize-html、Tectonic 和 pdftoppm。源 ZIP 不进入仓库或静态前端。转换缓存位于 `D:/Caches/GraspMemoEdu/mathacademy`；转换代码或渲染配置变化会失效派生缓存。

## 内容和访问

所有导入课程与 Topic 在激活前标为测试材料，归入数学学科。可见性沿用测试材料策略：用途为 test 的管理员，或用途为 test 且同时具备学员和高阶学员身份的账号。显式 Topic 权限仍然生效，游客和正式账号不能通过目录、直接链接或另一课程绕过。

Topic 使用 `ma-topic-<源ID>`，课程使用 `ma-course-<源ID>`。一个 Topic 共享正文、内容版本和学习身份；课程成员与外部前置分别保存。目标课程完整导入，关联课程仅包含闭包内的前置，并在目录说明范围。

`availability.saved/readable/trainable` 分别表示保存、阅读、训练资格。不满足现有题量、题面、答案等训练条件时，提供原文阅读与具体缺失原因，不建立学习记录、FSRS 卡片、训练任务或完成状态，也不能解锁下游。抓取时的输入答案、完成标记和私有源字段不进入公开阅读投影。

普通 MA 的只读页面合并显示相邻指导，保留各段身份与标题。Machine Learning I（源课程 72）的 Topic 按源顺序逐块显示正文。每个原 tutorial 单独成页，其中同级最高标题各自位于对应正文页的开头，标题前有内容时单独保留。学员阅读、管理员预览和新答疑沿用相同正文块及字段译文。共享 Topic 沿用同一布局与学习身份。

MA 源包用 `question.exampleId` 指明习题对应的例题，tutorial 没有对应例题的字段。可训练 Topic 使用[网站通用的默认绑定](topic-format-v2.md#身份顺序与引论)。例题绑定它前面最近的一块正文，更早的独立正文按原顺序阅读。选择「未掌握」后打开绑定正文。

训练内容的篇末阅读必须点击继续才能完成 Topic。组合输入采用题型协议 2，整题最多 64 段、128 个控件、16384 字符；只有最后一段提交整题，刷新恢复同题草稿。

新 Topic 保留原生单空、多空和分段顺序，按题型方案处理选择题和下拉选项。分段正文可以来自各段自己的结构或原文分隔符。只读 Topic 自动开放已取得的控件供试答，并保留缺失段的诊断。缺少原控件、分段正文或已验证答案时，补充来源后按原题 ID 继续处理。已有训练 Topic 的原控件修订使用 `mathacademy_interactions` 及核验答案。

源数据的 `calculate` 或 `calculator` 作为题目元数据保存。已导入及今后导入的 Machine Learning 系列按课程目录开放 CAS 档和全部计算器模块。其余 MA 材料默认至少开放科学计算器，保留绘图、更高档位及站内明确配置的例外。旧版提示保留在存档中。见 [按题配置计算器](calculator.md)。

中文展示包覆盖课内讲解、带解例题、练习题面、选项和解析，包括复习时查看的作答历史。课程名和 Topic 名沿用英文，Draft 和 Notes 保留原文。译文按原文字段绑定，并随对应 Topic 版本安装。源材料增量更新时复用未改动字段的译文。

更新题目修订的展示包时，可逐字保留同一 Topic 版本已安装的历史译文。再次打开已绑定历史修订的作答时仍可读取对应译文。新增或修改的译文必须绑定现有原文字段。

Math Academy 使用共用离线渲染器。源文本的行内和独立公式标记进入同一数学解析器，生成带 `data-tex` 的公式。所有 MA 课程的导入在离线渲染后检查嵌套 HTML 字段，包括指导、题干、选项、解析和分段提示。可见的残余 TeX 和 MathJax 错误记录到 `conversion-failures.json`，包含 Topic、字段路径及错误类型。代码示例中的字面语法不计入。可用 `python -m graspmemoedu.mathacademy_formula_audit <Topic JSON> ...` 独立复查同一规则。

已安装的 `tex_repairs` 供原内容版本的阅读和回看使用。展示安装器只允许原样携带这些历史字段。新的公式修复从冻结原稿走共用渲染，再绑定正确译文，并核对图片、代码与控件。原题、题型、作答记录及内容版本继续由原有存储维护。

每段指导使用对应原文字段绑定的译文。ML1 的标题拆分在应用中投影，原始 Topic 版本和翻译绑定继续有效。管理员内容预览、新答疑和答疑中的当前内容使用同一份展示内容。已保存的答疑仍按提交时的快照显示。

## 题型改造

- 先遮住选项读题。在题干、题图和作答要求已经足以确定结果时，把计算、化简、求表达式或求多个量的题改成单空或多空。短的定性结果也可改成填空，只要题目本身明确限定了要判断的对象和结果。场景给定的量、图、单位、精度和答题范围属于题目条件。
- 当选项本身提供待判断的命题、反例、图形、代码或其他候选对象时，保留选择。多段题逐个判断下拉控件，保留段落和原有输入位置。对改成填空的题，检查题面和输入旁是否还带解题提示，去掉示例值、备选结果、提示步骤和选项引用，只保留题目条件和需要填写的量。
- Codex 从本地清单读题并生成方案。方案是以 `题目所在源 Topic ID/源题 ID` 为键的 JSON 对象。每项复制清单中的 `source_sha256`，填写 `mode`（`fill` 或 `keep`）及具体 `reason`。有选项的题全部纳入，缺项、额外项和换源的方案均会被拒绝。范围内没有选项时可以省略方案。
- `fill` 的 MC 默认一个空。多个独立作答量用 `"labels": ["x =", "y ="]` 指定空位，标签只标识作答量。原题题干含有选项式措辞或提示时，以 `"edits": [["原文片段", "新文字"]]` 修改唯一出现的片段，删除时新文字用空字符串。原生下拉题用 `"dropdowns": ["s0-p2"]` 指定清单中的控件编号，段内提示用 `"section_edits": {"s0-p1": [["原文片段", ""]]}` 移除。控件和文本位置从零开始编号。
- 题型变化不提供新的答案证据。课程 ZIP 的缺失答案仍标为缺失，转换所得输入可供试答。Reference 快照只有核验过的正确选项文本可作为填空答案。核对实际渲染，确认填空无选项或解题提示、保留的定性题选项齐全，以及多空与原分段一一对应。
- 审核完成后，可沿同一入口传 `-Target production` 与同一方案发布。每批使用新的产物目录。已安装共享 Topic 对完全相同的冻结源文件复用原内容和身份。有实质来源差异时仍需处理同 ID 冲突。

## 安装、重跑和恢复

已安装的只读 MA 测试 Topic 可用 [SourcePrep 原生练习扩充流程](../../GraspMemoEduSourcePrep/MA_PRACTICE_ENRICHMENT.md) 补齐解答、生成实质变式，再通过本入口安装候选包。安装时绑定当前题目、原始 JSON 和升级前字节，保留原练习 ID、例题顺序、课程关系和共用 Topic 身份。升级前如有学习记录、来源发生变化或所选内容未标记测试材料，安装中止。中文显示包与新 Topic 版本一起切换。

练习扩充在准备和安装时检查原文与译文的渲染，并要求译文字段绑定到本次 Topic 版本的内容。生产启动器在暂停写入前复用同一个校验。遇到旧版补丁或没有当前绑定的译文，须从冻结原稿生成可验证的新包。

原字段同时保留完整 TeX 绘图与对应 HTML 时，导入器按同一字段的原文图形位置关联并离线编译；全部图片数量及显式图片身份必须一致。不会按 `graphics[]` 的附件排列猜测选项图，也不会下载或重绘缺少源码的图片。

已有冻结的官网图形归档时可传 `-OriginalImages`。归档含 `source-images.json` 和按官网图形 ID 保存的 `.image`，导入器核对地址、内容哈希和尺寸，再把图放回原字段。传入归档后，仍缺图的批次停止安装。源会话采集在独立的本地取材环节完成，发布使用同一个离线编译入口。

HTML 注释中的旧图保持隐藏，不计为可见缺图。补图时原 TeX 编译失败的图保留占位和诊断，不手改绘图内容；运行环境缺失等执行故障仍会中止准备。

已导入内容只需补图时，使用 `python -m graspmemoedu.mathacademy_graphics --source-package <原准备包> --course-ids 72 --output <补图包>`，再通过 `--install-package <补图包> --target production` 安装。此入口只处理所选课程的成员，不递归扩展前置。它核对原文件、已安装正文和补图附件的哈希，只替换缺图标签及对应缺失计数；保留其余 HTML、教学版本、课程关系、权限和数据库。重复安装返回 `unchanged`，普通导入的同 ID 覆盖限制继续生效。

正式导入使用已部署的内容安装器。新增课程和补图在服务在线时准备，内容代际切换后重载后端；重复提交同一内容只检查健康状态。练习补充在检查目标 Topic 无学习记录时暂停写入。导入恢复只切回上一代内容指针，整站备份由日常调度独立运行。

准备包包含哈希清单、目录、图谱、派生正文、私有源 JSON 和可用性报告。转换错误中止激活；原材料缺失保留为内容状态。安装复用既有导入锁，先在 `content-batches/<摘要>` 完成合并与校验，最后原子切换 `active-content.json`。旧内容和学习数据库不被覆盖；同 ID 不同正文报冲突。重复安装报告 `unchanged`。

正式入口通过现有 SSH 和 `host.py run-stage` 执行，按前述代际切换流程激活候选包。若安装或健康检查失败，恢复上一内容指针并重启原内容。应用源码发布独立于课程安装。站点备份展开保存有效目录、正文、源 JSON 和图谱，恢复无需原活动指针。

带离线 SVG 的 Topic 阅读响应可达数 MB。部署模板在本应用的 API location 启用 JSON gzip，压缩传输但保持响应内容及权限检查不变；已有多站点服务器只增量应用该 location 的压缩配置，不覆盖其他站点。正文读取使用 60 秒上限；没有进度变更的只读原文不做训练页的周期轮询，初次打开和刷新仍读取服务器。机器学习批次上线时服务内存上限设为 1536 MiB，具体容量仍按主机实际余量核验。

`tests/test_mathacademy_import.py` 使用独立完整合成题验证训练边界；`scripts/mathacademy_interaction_fixture.py` 与 `mathacademy_interaction_acceptance.mjs` 验证 10 段 23 控件、刷新与篇末完成。真实来源另行执行整批转换、共享身份、附件与备份恢复验收，不能用合成样本冒充真实资料完整。
## 公式显示兼容

导入时保留可用的 LaTeX 和 MathJax 字符标记。既有 SVG 公式只有字形路径时，网站用 MathJax 3.2.2 的随附字形表识别字符，再通过共用 KaTeX 渲染。识别不完整时保留原 SVG。字形表可用 `node scripts/build_mathjax_svg_glyphs.mjs --check` 验证。
