# Hyperskill Topic 接入

每篇 theory 对应一个统一架构的 Topic v2。译文按最外层正文标题拆成有序的多个 Introduction；首个标题前非空内容命名为“引言”，没有内容则不创建空引言。低一级标题留在所在节内。Topic 的 `modules`、`memory_chunks`、`memory_points`、`flashcards` 都为空，当前为纯引论；以后可按统一 Topic 规则在对应 Introduction 下增加范式训练或原子练习，空结构不产生 FSRS 卡。

Practice 保存在原生 `TrainingCatalog` 的 `hyperskill-practice` 题库。接入 Practice 的 Topic 显示为“学习任务”，读完后进入对应的题组，原题、作答和复习排程沿用题库记录。题组用稳定 ID 关联，增量导入导致题库版本变更时仍指向同一题组。已有验证答案的可站内判分题计入完成。缺少已验证答案和需要去 Hyperskill 作答的题可以选做。已读内容和已完成的题随现有记录继承。

`prepare_hyperskill.mjs` 从本地译文和已认证读取的 practice 生成确定性来源包，`prepare_hyperskill_branch.mjs` 按源目录合并完整分支。HTML 使用安全渲染器的 HTML 入口，避免 Markdown 解析改变代码里的星号和下划线。图片复用 Hyperskill→RemNote 的下载、哈希与 SVG 转 PNG 路径，优先复用本地已校验图片；原附件和来源 JSON 随包保存，网页内嵌图片。`academy_import --extend-course` 对新格式调用 `hyperskill_import`：追加新 Topic 和题组，已有问题及父子关系不能被覆盖，重复安装幂等。题库追加内容时仅迁移版本绑定，已存在的卡片、日期、作答快照和评分保持原值。

旧原子 Topic 的一次性转换在停服发布窗口完成。原 `topics` 行逐字保存在 `hyperskill_topic_archives`，历史、在途轮次和 FSRS 卡移到题库，正文使用新的阅读状态；旧事件与原始内容包保留。新章节不凭旧练习状态伪造“已阅读”。迁移前备份，异常同时回滚数据库、题库和正文指针；未处理的暂停、判题中状态、部分显式 Topic 权限或已排入试卷的题库卡片会阻止迁移，不能静默扩大访问权。测试标记随正文激活，题库同样仅向合格测试账号开放。

当前支持 choice、matching、number、string、fill-blanks、sorting、parsons、table、code。填空保留题内空格，排序保留选项身份，Parsons 同时提交行顺序与缩进，表格按实际行列名称提交。代码题保留源模板和公开输入输出示例，语言以 Hyperskill 返回值为准。未知题型停止导入，不能静默删题。

共享阅读页按源标题等级构建可折叠正文层级，题目身份不随展开收起变化；代码字符、缩进、列表编号和图片出现顺序保留。代码块可横向滚动，正文适应窄屏。

导入先运行 `capture_hyperskill_presentations.mjs <private-config> <source> <output>`，复用现有 attempt 或仅创建未作答 attempt，捕获全部公开 dataset，再准备来源包。每题保存 `hyperskill_presentation`（公开选项、空格、行列、代码模板与已内嵌图片），不含会话、凭据和标准答案。缺少展示数据阻止新导入。已有题只允许在原字段完全一致时增补此字段；历史快照不改写，读取时按相同原字段补充展示。

网页使用共享 `training.js` 阅读器、`hyperskill.js` 输入控件与 Academy 的轮次授权。旧原子格式保留兼容入口。题面直接从题库展示；进入题组静默探测 127.0.0.1:18769，选题后后台准备当前轮次。非代码题提交时按选项、配对、排序、表格内容身份重映射到实时 dataset，避免随机排列错位；源内容变化则停止本次提交。服务绑定固定 HTTPS 后端与明确的网页 Origin，不接受任意代理 URL、命令或路径。

代码题点击“在 IDEA 中解题”，调用官方插件的 `GET /api/hyperskill?step_id=…&language=java&user_id=…`，与官方 Solve in IDEA 入口一致。插件负责项目、题目文件、模板、编译、Check、上游 attempt 和提交；网站及桥接不创建代码文件、不读取本机答案、不代发代码 POST。本机服务使用官方 `/api/hyperskill/info` 发现 IDEA；未运行时可以启动已配置 IDEA，不重启运行中的 IDE。协议依据 [HyperskillRestService](https://github.com/hyperskill/hyperskill-plugin/blob/main/intellij-plugin/hs-core/src/org/hyperskill/academy/learning/stepik/hyperskill/HyperskillRestService.kt)。

打开前记录当前提交基线，随后仅同步同一用户、同一题目、基线后新增的回执，不绑定网页 attempt（官方插件自行创建）。按时间顺序处理每次 Check，前面的提交仍判题时不越过它；持久化待传事件后再发送，丢失确认重传原事件。通过或云端关闭轮次后停止观察；同题新轮次接管前一轮观察，24 小时后需重新打开。网页打开时约每 2.5 秒查询，桥接后台每 30 秒补传。原 Academy 题库插件流程保留。

本机服务从现有 LiveCookieSnapshot 读取 Hyperskill 登录态，每次写入前检查账号身份。Cookie 和 CSRF 凭据只用于 Hyperskill 请求，不传到 GraspMemoEdu 或网页。网页的能力票据限制到当前账号、内容版本和作答轮次。运行目录与配置位于本机私密应用数据目录，不能提交 Git。

提交前持久化请求；POST 返回不确定时只查询原提交，不自动再发 POST。查询以本人和题目限定，再按 attempt、答案和时间关联；Hyperskill 当前忽略列表中的 attempt 查询参数，不能依赖它过滤。匹配不唯一时保留待确认状态。判题完成后，原始提交 ID、attempt ID、答案、判定、时间及反馈保留在 `training_external_rounds` 回执；云端确认前保留本机待传记录。同一学员的上游提交不能被重用于另一轮评分。

非代码题经 Hyperskill 判定正确后，原始回执的答案及 dataset 写入共享 `hyperskill_answers`。题目内容签名包含 step、题面和公开 dataset，忽略纯排列变化；代码题、错误回执、无 dataset 的旧回执不自动进入缓存。已有共享参考的新作答直接使用服务器判题，即使本机桥接在线。闭合题型按内容身份比较，文字、数值、填空的其他表达复用原有语义判题器。已开始的官方轮次保留原判题路径，避免遗失待确认的提交。站内判分不产生新的官方正确回执，学习记录和 FSRS 仍按学员独立。

复习准入使用全学科共用题库规则：首次直接通过且未主动加入错题本，记 5、保留作答记录，不创建 FSRS Card，也不进入后续复习。主动加入错题本或已有排程的题目，直接通过 Good；少量有效错误后通过 Hard；三次不同有效错误后通过或主动结束失败轮次 Again。对相同答案的重复失败不重复增加错误负担；没有终态判定不评分。需要复习的每个 problem 使用独立 FSRS Card，完成一道题不会把整个 Topic 标记完成。

此接口集成使用网站内部协议，协议变化时应停止提交并修复适配器。判题状态不等于完整标准答案：界面展示服务实际返回的判定和反馈，不承诺每道题都会返回完整解答。

本机启动使用 `Start-HyperskillBridge.ps1 -ConfigPath <private config>`。`Register-HyperskillBridge.ps1` 注册当前用户的 Windows 任务 `GraspMemoEdu-HyperskillBridge`，登录后启动，每分钟检查一次。轻量检查向本机服务读取实例 ID，并核对已记录的 PID、进程开始时间、Node 路径和实际加载的脚本、配置。匹配时直接返回。缺少记录、依赖或服务无响应时，原 PowerShell 启动器负责核对和恢复。任务沿用 DeveloperGovernance 的无窗口启动器、90 秒启动时限和电池模式设置。退出登录后停止，下次登录恢复。

后台查回执可通过已有 SSH 连接交给 Mac。Windows 私有配置中可增加 `backgroundSSH`，其中 `host` 是已有可信 SSH 别名，`node`、`script` 和 `config` 分别是 Mac 上的 Node、`scripts/hyperskill_background.mjs` 和私有配置的绝对路径。Mac 配置沿用 `cookieModule`、`cookieWorkflowRoot`、`cookieDataRoot`、`expectedUserId`，必须由 Mac 本机登录取得同一账号的会话。Mac 只接收提交查询，不接收网站票据和轮次账本。Windows 按现有轮次文件串行领取、保存事件 ID 并提交给网站，用户主动刷新或操作 IDE 继续走原本机入口。SSH 中断时后台保留原轮次，已落盘的事件仍按原 ID 重试。

网页进入题组时检查并预热一次，连接正常后停止连接轮询，切回页面或网络事件不会重复探测已正常的服务。提交和打开 IDEA 前按需检查；实际请求发现本机服务不可达后，按 2、4、8、16、30 秒间隔重试，恢复后立即停止，隐藏页面暂停，回到页面或网络恢复时立即尝试。健康检查成功不代表上游准备成功：准备接口错误保留反馈并允许显式重试，不因此启动健康轮询。恢复过程中保留作答草稿和原提交标识，不自动重发答案；有在途判题或 IDEA Check 时继续查询结果，本机断连时暂停查询，恢复原轮次后继续。连接异常时提供“重新连接”按钮。配置包括固定 backend、origins、port、directory、cookieModule、cookieWorkflowRoot、cookieDataRoot、expectedUserId，可选 ideaExecutable 和 ideaProperties，不含复制出来的 Cookie。服务只监听本机地址；浏览器可能要求用户允许网站访问本地网络。

验证入口：`tests/test_hyperskill_training.py`、`tests/test_hyperskill_answers.py`、`tests/test_hyperskill.py`、`scripts/test_hyperskill_bridge.mjs`、`scripts/test_hyperskill_ide.mjs`、`scripts/test_hyperskill_presentation.mjs`、`scripts/test_hyperskill_sections.mjs`、`scripts/validate_hyperskill_branch.py`、`scripts/hyperskill_bank_acceptance.mjs`、`scripts/test_hyperskill_render.mjs`。经用户授权的真实提交验收使用测试学员，保留上游提交 ID、独立卡片的复习日期和去重结果；合成契约测试不作为真实提交通过的证据。
