# 零碎知识简藏

登录后，在学习页工具栏点击「零碎知识简藏」开启或关闭。开关随本浏览器的账号保存。拖选站内内容后出现「卡／摘／问／读」。公式以整条选取，优先保留页面提供的 LaTeX。触屏可直接点选公式。Alt+Shift+S 选中当前公式或内容块，Alt+Shift+C 将焦点移到操作按钮。

- **卡**可编辑正反面和分类，也可发起多轮问答、选入回复或整合生成多张卡片草稿。确认保存后进入「课程之外自由学习」。
- **摘**保存当前选区原文。打开「课程之外自由学习 → 摘录」可按日期查看，下载当日或全部的 RemNote Markdown 大纲。当天以账号时区为准，未设置时使用 Asia/Shanghai。
- **问**用「快速答案」类型发起一次问答。回答可继续追问或加入卡片。
- **读**提供词义与朗读。站内词典有匹配时显示词典义项，其他选区可请求语境释义。朗读使用设备提供的本地语音。

桌面浏览器默认打开独立小窗，窗口尺寸、移动和最小化由浏览器与操作系统管理。「在当前页置顶」把操作界面移到原标签页的非模态浮窗，可拖动、缩放或最小化。「普通窗口」切回独立窗口。窄屏触控设备和阻止弹窗的浏览器直接使用同页浮窗。词义、回答和制卡生成在对应操作触发后运行。原始选区可预览，带入所在内容块由用户选择。

「课程之外自由学习」按提问类型和日期展示个人卡片。到期卡片在同一页翻面、自评，由网站现有 FSRS 引擎计算间隔。保存、复习和摘录只属于当前账号。卡片、摘录、复习记录和模型用量保存在现有学习数据库，随站点备份。

## 维护

提问类型、通用提示和整合规则由 KnowledgeClipper 的 Git 版本提供。更新网站使用的版本时执行 `python scripts/sync_clipper_rules.py <KnowledgeClipper 源码目录> <提交或标签>`，用 `--check` 核对生成物，然后跑剪藏测试。网站负责素材选取、弹窗、账号保存和复习适配，桌面程序继续使用自己的宿主与模型接入。

生成服务复用站内文本调用传输。可用 `GRASPMEMOEDU_CLIPPER_API_KEY`、`GRASPMEMOEDU_CLIPPER_BASE_URL` 和 `GRASPMEMOEDU_CLIPPER_MODEL` 同时指定独立配置。三项均未设置时使用站内现有的专用文本模型设置。服务端计量独立于判题，`GRASPMEMOEDU_CLIPPER_DAILY_ACCOUNT` 和 `GRASPMEMOEDU_CLIPPER_DAILY_GLOBAL` 的默认值 `0` 表示不限量。两项支持设置正整数限制，按 Asia/Shanghai 自然日计数。进入模型的请求会计量，词典查询和浏览器朗读各用自己的路径。

隔离验收先运行 `python -m unittest tests.test_clipper.ClipperTests tests.test_web_export`。浏览器验收用 `python scripts/clipper_browser_fixture.py <全新数据目录> --port <空闲端口>` 和 `node scripts/clipper_browser_acceptance.mjs <证据目录> <数据目录> <隔离网址>`，浏览器测试使用合成材料与确定性的模型响应。
