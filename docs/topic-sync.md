# Topic 和 RemNote 同步

## 账号、课程和基线

同一账号的一个 Topic 跨课程共用个人正文、基线和已配对知识库中的 Document。管理员给学员分组时，服务端检查同一学员在其他课程的有效分组。如果共享 Topic 的基线不同，返回冲突提示并保留已有分组。换组或撤下组基线后，已编辑的个人正文继续生效，未编辑的 Topic 读取新的基线。在任一有效分组中关闭共用 Topic 的编辑权限，会同时关闭网站和本地写入。

组基线可引用管理员自己已保存的正文版本。选择时固定该版本，其他学员的个人修订保持独立。分组管理复用网站现有的管理员负责范围。多名管理员能负责同一学员，修改已有分组需要提交看到的原分组。

## 配对和跳转

浏览器只把一次性配对或打开凭证交给 Navigator。配对凭证有效期为两分钟，打开凭证有效期为 45 秒并限用一次。设备身份和知识库身份由本机服务与网站确认。已经关联其他账号的设备返回账号错配提示。网站用户切换到绑定账号后才可继续。

在同一个 RemNote 知识库使用两台设备，会查到同一组绑定。网站跳转用 RemNote SDK 打开 Document；反向链接先让网站核验当前登录账号，再进入对应 Topic。

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

部署此阶段前须分别验收 GitHub App 的真实读取和写入、正式插件的安装与配对，以及 HyperSkill 现有文档的匹配。TINE 编辑器和正文往返属于后续接入。
