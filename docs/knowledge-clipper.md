# 零碎知识简藏

登录后，在学习页工具栏点「零碎知识简藏」开启，再点一次关闭。开关按当前浏览器和账号保留。选中正文后选择「读」「卡」「摘」或「问」。点一张图片还可以选「图」，继续收集正反面图片。按 Alt+Shift+S 选中指针所在的公式或内容块，Alt+Shift+C 将焦点移到操作菜单。

操作页默认在当前标签页内置顶。拖动标题栏可移动，拖动边缘可调整大小。支持最小化、铺满标签页及切换到独立普通窗口。答题区域继续接受滚动与输入。

## 选区、上下文与朗读

连续拖选英文时，会按选中位置补全词首和词尾，包括词内连字符和撇号。再次拖选会建立新选区。来源句子按实际位置提取，同一个词在页面中出现多次也能区分。行内公式以完整的 LaTeX 保存，代码保留缩进，选中的图片按原位置进入摘录。

要摘录公式的一部分，可双击公式或点「选取公式片段」。在面板中拖选后点「摘录」，所选 LaTeX 和页面来源会带入现有剪藏流程。

在「设置 → 零碎知识简藏」中可以关闭上下文或把范围从一句改为一段。默认带入一句。开启上下文后，如果公式出现在来源句或所选段落中，朗读会同时读出文字和公式。查义、理解卡和书写卡使用原文与本次选区的位置。公式的语音读法只用于合成录音。再次读到同一个词时，工具按来源、读音和实际录音文本判断能否复用。

设置页集中管理浮点快捷操作、语言卡练习方式、词典、图片与 OCR、请求重试、朗读和快捷键。也可以调整当前账号的提示词和模式。选择自有服务时，在该页面绑定凭据。站点按账号加密保存，后续读取只显示绑定状态和服务信息。

## 保存与复习

「卡」进入共享卡片编辑器。「问」用当前选区发起对话。「摘」可保存原文、手动制卡、挖空、合并或撤销合并。「读」可查义、听读、生成语言卡并复用历史录音。开启某项快捷保存后，点击对应操作即确认按设置保存结果。其余草稿、图片、对话和录音保存在当前浏览器的账号空间。

保存后的卡片在「个人自由学习」按类型查看，并通过 FSRS 翻面复习和评分。可查看按日期整理的摘录，导出今天或全部摘录。纯文本摘录下载为 Markdown，含图片的摘录下载为包含 Markdown 和原图的 ZIP。公式、代码块及图片位置保留在导出内容中。

## 运行与更新

网站与桌面版运行同一份 KnowledgeClipper 工作流和卡片编辑器。网站提供页面选区、账号存储与网络服务。已发布的运行包和规则目录分别由 `scripts/clipper-assets.json` 的 SHA-256 校验。执行 `python -m graspmemoedu.clipper_bundle` 准备本地运行文件，`export-web` 会检验并复制指定版本。`GRASPMEMOEDU_CLIPPER_BUNDLE` 可指定同一发行包的本地路径。维护时用 `python scripts/sync_clipper_rules.py <KnowledgeClipper目录> <提交> --check` 对照上游源码核验规则。

内容模型沿用站内专用文本服务，也可同时设置 `GRASPMEMOEDU_CLIPPER_API_KEY`、`GRASPMEMOEDU_CLIPPER_BASE_URL` 和 `GRASPMEMOEDU_CLIPPER_MODEL`。可为多模态内容配置 `GRASPMEMOEDU_CLIPPER_IMAGE_MODEL`。语音和 OCR 的站点服务使用同名变量的 `SPEECH_` 与 `OCR_` 前缀，如 `GRASPMEMOEDU_CLIPPER_SPEECH_MODEL`。小米 MiMo 和 OpenAI Realtime 均沿用 MimoTTS 的合成实现，服务器须安装 FFmpeg。兼容的音频接口需返回 MP3。

面向 OpenAI 支持地区的站点使用 OpenAI Realtime 朗读时，可设置 `GRASPMEMOEDU_CLIPPER_OPENAI_SSH_PORT=18773`，并安装 `deploy/graspmemoedu-openai-tunnel.service`。SSH 服务仅监听回环，使用专用密钥和运维确认的主机公钥。远端应把该密钥限定为连接 `api.openai.com:443`，并禁用会话及其他转发。站点保留到 OpenAI 的 TLS 证书校验。将 OpenAI 的语音配置放入 root 专用的 `/etc/graspmemoedu/openai-tunnel/speech.env`，验证合成后，再把 `deploy/98-clipper-openai.conf` 安装到后端的 systemd drop-in 目录。回退时，移除该 drop-in，重新加载 systemd 并重启后端。服务器节点轮换后，须先验证新节点，再更新目标主机、固定的主机公钥以及远端放行的专用公钥。

图片识别可直接复用桌面使用的 MinerU 程序。用 `GRASPMEMOEDU_CLIPPER_MINERU_RUNNER` 指向服务器上已安装的 `mineru_ocr.py`，并在运行服务中配置站点的 `MINERU_API_TOKEN`。识别沿用设置中的语言、表格、公式和等待时间，核验原始 ZIP 和 Markdown 后返回。账号自有视觉服务仍使用该账号绑定的接口。

自有服务绑定需要服务器上的 `GRASPMEMOEDU_CLIPPER_VAULT_KEY`，值为 Base64 编码的 32 字节随机密钥。该密钥由站点运维保管并随私有密钥备份。独立配额 `GRASPMEMOEDU_CLIPPER_DAILY_ACCOUNT` 和 `GRASPMEMOEDU_CLIPPER_DAILY_GLOBAL` 默认均为 0，表示不限量。按 Asia/Shanghai 自然日计量。已保存的内容、媒体与复习记录进入现有学习数据库。
