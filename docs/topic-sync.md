# Topic 和 RemNote 同步

## 账号、课程和基线

同一账号的一个 Topic 跨课程共用个人正文、基线和已配对知识库中的 Document。管理员给学员分组时，服务端检查同一学员在其他课程的有效分组。如果共享 Topic 的基线不同，返回冲突提示并保留已有分组。换组或撤下组基线后，已编辑的个人正文继续生效，未编辑的 Topic 读取新的基线。在任一有效分组中关闭共用 Topic 的编辑权限，会同时关闭网站和本地写入。

组基线可引用管理员自己已保存的正文版本。选择时固定该版本，其他学员的个人修订保持独立。分组管理复用网站现有的管理员负责范围。多名管理员能负责同一学员，修改已有分组需要提交看到的原分组。

功能默认向登录账号开放。服务器维护命令 `account-topic-sync --learner <learner_id> exclude` 可停用指定账号，`allow` 恢复开放。设置在下次网站或插件请求时生效。

管理员在「学员学习情况」进入一位学员的详情，展开「课程分组与正文基线」。按课程新建或选择分组，设置编辑权限，可指定官方底本或采用自己当前的课程版本。保存分组后，再将这名学员加入所选组。

## 配对和跳转

浏览器只把一次性配对或打开凭证交给 Navigator。配对凭证有效期为两分钟，打开凭证有效期为 45 秒并限用一次。设备身份和知识库身份由本机服务与网站确认。已经关联其他账号的设备返回账号错配提示。网站用户切换到绑定账号后才可继续。

在同一个 RemNote 知识库使用两台设备，会查到同一组绑定。网站跳转用 RemNote SDK 打开 Document；反向链接先让网站核验当前登录账号，再进入对应 Topic。

首批 HyperSkill 配对从该账号可访问的网站 Topics 和本机完成导入登记交叉核对上游 Topic ID。只登记能在当前知识库中回读为 Document 的单一匹配。无匹配、歧义或不同绑定保留待核对。

## 存储配置

私有快照使用 AES-GCM 加密，仓库路径由账号、Topic 和内容的带密钥指纹生成。SQLite 保存权限、配对、分组和版本索引。原文保留在文件仓库的加密快照中。

候选同步服务由以下环境变量接入私有仓库：

| 变量 | 用途 |
| --- | --- |
| `GRASPMEMOEDU_SYNC_REPO` | 专用私有 GitHub 内容仓 |
| `GRASPMEMOEDU_SYNC_ENCRYPTION_KEY_FILE` | 文件中为 Base64 编码的 32 字节加密主密钥 |
| `GRASPMEMOEDU_SYNC_GITHUB_APP` | GitHub App ID |
| `GRASPMEMOEDU_SYNC_GITHUB_INSTALLATION` | 该 App 在私有仓库的安装 ID |
| `GRASPMEMOEDU_SYNC_GITHUB_KEY_FILE` | 指向只供服务读取的 App PEM 私钥 |

App 只需对专用仓库拥有 Contents 写权限。密钥按服务凭据备份，保持编辑历史可恢复。缺少仓库配置时同步 API 不注册，网站和 Navigator 的既有流程继续运行。

设置 `GRASPMEMOEDU_NAVIGATOR_INSTALLER` 指向 Navigator 发布生成的 Windows x64 ZIP。安装页通过当前登录身份下载，初次安装会在学习者电脑生成本机凭据。更新通过同一安装入口保留设备身份。

## 编辑正文

登录学员在 Topic 正文右上角开启编辑，再点一次关闭。TINE 使用课程或分组基线初始化大纲，首次保存后该账号读取自己的版本。两端写入同一版本索引。如果另一端抢先更新，保存会返回冲突，防止旧页面覆盖新正文。

编辑器独立部署，使用上游 TINE v0.9.2 的 BlockList 和 LSdoc。网站向编辑器传递当前 Topic 大纲，通过独立消息端口收回修改。编辑器不接收登录凭据。构建使用 `scripts/build_topic_editor.py`，参数依次为固定上游源码压缩包、已经安装依赖并构建过 LSdoc 的上游目录、空的发布目录。部署该输出并设置 `GRASPMEMOEDU_TINE_ROOT`，与编辑器一起提供对应 AGPL 源码。环境示例见 [部署配置](../deploy/topic-sync.env.example)。

Navigator 首次同步有正文的现有 Document 时，会在原绑定账号下建立个人版本。未编辑过的其他账号继续使用网站或组基线。已登记同步的 Document 在插件联机时轮询，也允许在窗格中手动同步。嵌套 Document 各有自己的 Topic。正文验收使用 `scripts/topic_sync_browser_acceptance.mjs`，私有仓储可用 `scripts/topic_sync_storage_canary.py` 写入合成内容并验证密文回读。
