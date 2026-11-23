1. **《第1章 磁共振基础》×《Introductory Quantum Optics》Ch. 4 Unit 1 全三课交付报告**
    - **交付目录**：本包完整维护 Open Academy 格式的磁共振课程 Unit 1（全部 3 课共 9 个知识点与 75 道互动练习），并升级交互式网页应用至多课统一架构。
    - **核心交付文件索引（均使用相对路径）**
        - 课程规划与双源元数据：[curriculum.yaml](../curriculum.yaml)、[sources/index.yaml](../sources/index.yaml)、[courses/mr-fundamentals.yaml](../courses/mr-fundamentals.yaml)
        - 概念先修图与符号准入表：[concepts/magnetic-resonance.yaml](../concepts/magnetic-resonance.yaml)、[notation.yaml](../notation.yaml)
        - Unit 1 正课与配套题库（共 3 课 · 9 步 · 75 题）：
            - 第 1 课：[lessons/spin-zeeman-and-drive.yaml](../lessons/spin-zeeman-and-drive.yaml)（`version: 1`，2 幅 SVG）与 [exercises/spin-zeeman-and-drive.yaml](../exercises/spin-zeeman-and-drive.yaml)（25 题，涵盖 15 道课堂与测验题、9 道 FSRS `recall` 题、课末总结 `zeeman-final-explain`）
            - 第 2 课：[lessons/rotating-wave-and-frame.yaml](../lessons/rotating-wave-and-frame.yaml)（`version: 4`，2 幅 SVG）与 [exercises/rotating-wave-and-frame.yaml](../exercises/rotating-wave-and-frame.yaml)（25 题，`rwa-final-explain`）
            - 第 3 课：[lessons/su2-evolution-and-rabi-prob.yaml](../lessons/su2-evolution-and-rabi-prob.yaml)（`version: 1`，2 幅 SVG）与 [exercises/su2-evolution-and-rabi-prob.yaml](../exercises/su2-evolution-and-rabi-prob.yaml)（25 题，`rabi-final-explain`）
        - 校验工具、按课解耦 SVG 模块与数学验算插件：[tools/academy_check.py](../tools/academy_check.py)、[tools/build_svgs.py](../tools/build_svgs.py)、[tools/svgs/_geom.py](../tools/svgs/_geom.py)、[tools/svgs/spin-zeeman-and-drive.py](../tools/svgs/spin-zeeman-and-drive.py)、[tools/svgs/rotating-wave-and-frame.py](../tools/svgs/rotating-wave-and-frame.py)、[tools/svgs/su2-evolution-and-rabi-prob.py](../tools/svgs/su2-evolution-and-rabi-prob.py)、[tools/verify_math.py](../tools/verify_math.py)、[tools/checks/_common.py](../tools/checks/_common.py)、[tools/checks/spin-zeeman-and-drive.py](../tools/checks/spin-zeeman-and-drive.py)、[tools/checks/rotating-wave-and-frame.py](../tools/checks/rotating-wave-and-frame.py)、[tools/checks/su2-evolution-and-rabi-prob.py](../tools/checks/su2-evolution-and-rabi-prob.py)、[tools/render_preview.py](../tools/render_preview.py)
        - 先修依赖链导出与生成的交互预览：[reports/_prereqs_l1.txt](./_prereqs_l1.txt)、[reports/_prereqs_l2.txt](./_prereqs_l2.txt)、[reports/_prereqs_l3.txt](./_prereqs_l3.txt)、[preview/index.html](../preview/index.html)、[preview/rotating-wave-and-frame.html](../preview/rotating-wave-and-frame.html)

2. **双教材对照集成架构与符号契约**
    - **主从与内容边界约定**
        - 主骨架与符号约定严格以《第1章 磁共振基础》（`ch1-magnetic-resonance`，§1.1 式 `1.1–1.16`）为准；Gerry & Knight《Introductory Quantum Optics》（`introductory-quantum-optics`，Ch. 4 §4.1–§4.5）作为物理同构对照、耦合概率幅微分方程平行推导、粒子数反转 / 共振脉冲与全量子 Jaynes–Cummings 推广素材融入 Unit 1 全三课。
        - 第 2 单元第 1 课 `single-qubit-gates` 及后续单元概念继续保持 `status: stub`，待后续逐步填充，不在 Unit 1 提前泄漏任意相位单比特门矩阵或 Bloch 球细节。
    - **全三课严格统一的物理符号与算符字典**
        - 态矢量对应：$|1\rangle \stackrel{\text{def}}{=} |m_S = -1/2\rangle \leftrightarrow |g\rangle$（电子自旋下能级 / 原子基态），$|0\rangle \stackrel{\text{def}}{=} |m_S = +1/2\rangle \leftrightarrow |e\rangle$（电子自旋上能级 / 原子激发态）；JC 光子真空态写作 $|n=0\rangle$ 以避免与自旋态 $|0\rangle$ 记号碰撞。
        - 算符与参数对应：$2S_z \leftrightarrow \hat{\sigma}_3$，$2S_x \leftrightarrow \hat{\sigma}_+ + \hat{\sigma}_-$，失谐 $\delta = \omega_0 - \omega \leftrightarrow \Delta$，驱动耦合强度 $\Omega \leftrightarrow V/\hbar$（由 $2\Omega\cos(\omega t)S_x = \Omega\cos(\omega t)(2S_x) \leftrightarrow (V/\hbar)\cos(\omega t)(\hat{\sigma}_+ + \hat{\sigma}_-)$ 严格对齐，而非 $V/(2\hbar)$）。
        - 外部先修基线 `qm-spin-and-operators-foundation`（`status: stub`）显式覆盖 $-\vec{\boldsymbol{\mu}}\cdot\boldsymbol{B}$ 与 $-\hat{\boldsymbol{d}}\cdot\boldsymbol{E}$ 偶极耦合、二阶常系数线性微分方程、$(\vec{\boldsymbol{n}}\cdot\vec{\boldsymbol{\sigma}})^2 = \mathbb{1}$ 泡利指数公式与圆偏振角动量约定。

3. **自动化校验与交互网页验证结果**
    - **按课解耦 SVG 自动注入与防漂移门禁（[tools/build_svgs.py](../tools/build_svgs.py) & `tools/svgs/<concept_id>.py`）**：将 6 幅图拆至 3 个互不干扰的 `tools/svgs/<concept_id>.py` 模块（共用 `_geom.py`）；`build_svgs.py` 支持 `--concept <id>` 单课构建、原位无损更新对应 `lessons/<concept_id>.yaml` 内嵌代码块，并在 `--check` 与 [tools/academy_check.py](../tools/academy_check.py) 中强制校验代码与 YAML 零漂移，均输出 `validate -> OK` 与 `YAML sync -> OK`。
    - **Open Academy 静态规则与字数检查（[tools/academy_check.py](../tools/academy_check.py) `check -v`）**
        - 最终修订后退出码 `0`：**0 errors，0 warnings**（全部 21 处词数检查均在规范区间内）。
        - 第 1 课实测：`where_this_fits eq=111`，三步 `tldr` 为 `44 / 42 / 36`，三步 `explain` 为 `209 / 236 / 248`。
        - 第 2 课 v4 实测：`where_this_fits eq=113`，三步 `tldr` 为 `46 / 57 / 52`，三步 `explain` 为 `349 / 373 / 295`。
        - 第 3 课实测：`where_this_fits eq=128`，三步 `tldr` 为 `38 / 41 / 55`，三步 `explain` 为 `198 / 206 / 329`。
    - **按课解耦符号推导、ODE 等价、例题与 75 题模板验证（[tools/verify_math.py](../tools/verify_math.py) & `tools/checks/<concept_id>.py`）**
        - 将原单体脚本解耦为通用调度器 [tools/verify_math.py](../tools/verify_math.py)、共享自旋/矩阵断言底座 [tools/checks/_common.py](../tools/checks/_common.py) 与 3 个互不干扰的单课插件模块（均导出 `verify(lesson_path, pack_dir)`），自动从 `concepts/*.yaml` 发现 `status: authored` 概念并按课程单元顺序校验；支持 `--pack`、`--concept <id>`（单课隔离校验）及 `--require-checks`（严格要求每个 `authored` 概念具备 `tools/checks/<id>.py`）。
        - SymPy 与 NumPy 核验 Unit 1 式 `(1.1)–(1.16)`：包括 $2S_z=\hat{\sigma}_3$、$2S_x=\hat{\sigma}_++\hat{\sigma}_-$、$\Omega=V/\hbar$、三维 Rodrigues 旋转、升降算符变换、$SU(2)$ 演化算符 $U_I$、$U_I|1\rangle$ 括号勘误校验、共振 $\pi/2$ 脉冲叠加态 $\frac{1}{\sqrt{2}}(|1\rangle - i e^{-i\varphi}|0\rangle)$、Gerry & Knight 耦合概率幅 ODE 与二阶方程 $\ddot{C}_e - i\delta\dot{C}_e + \frac{\Omega^2}{4}C_e = 0$ 解析解等价性、反转度 $W(t)=-\cos(\Omega t)$、以及 JC 模型 $2\times 2$ 子空间量子化拉比频率 $\Omega(n)=2\lambda\sqrt{n+1}$ 与真空拉比频率 $\Omega(0)=2\lambda$。
        - 核验全部 3 课的 Worked Examples 数值计算（无嵌入式 Python 块）及全部 75 道练习（第 1–3 课各 25 题，含全数参数化模板、静态数值 `common_wrong` 碰撞校验、表达式变量自由度与正则校验）。
    - **全三单元 `authored` / `stub` 自适应网页与 Node `vm` 运行验证（[tools/render_preview.py](../tools/render_preview.py)）**
        - 自动遍历 `courses/mr-fundamentals.yaml` 全部 3 个 Unit（共 10 节概念：3 节 `authored` 互动正课 + 7 节 `stub` 契约预览卡）；点击任意 Stub 课可查看描述、可跳转前置依赖链、规划学习目标、`notation.yaml` 注册符号及独立填充指引。
        - 同时生成 [preview/index.html](../preview/index.html)（默认第 1 课）与 [preview/rotating-wave-and-frame.html](../preview/rotating-wave-and-frame.html)（默认第 2 课），共享 `localStorage` 状态键 `open_academy_mr_progress_v1`、12 张 FSRS-5 预测卡片（9 张 KP 卡 + 3 张维度卡）与「快进到最早到期卡」控制。
        - Node `vm` 实测确认两份 HTML 均包含 3 个单元导航组、10 个课标签、7 个 Stub 契约面板、75 个题目 DOM 槽位、`EX_MAP`（75）、`KP_META`（9）、`LESSONS_META`（10）及 `cardSpecs()`（12 张卡片），切换至 `single-qubit-gates` Stub 面板与已开放正课均无报错。

4. **独立子代理审计与两轮盲测修订闭环**
    - **先修一致性审计员（`e68a87c6`）**：确认全三课 75 题均落在先修边界内且未向 Unit 2/3 超纲泄露；精准捕获并修复第 3 课共振 $\pi/2$ 脉冲末态相位误作 $e^{+i\varphi}$ 的符号矛盾（已修正为 $\frac{1}{\sqrt{2}}(|1\rangle - i e^{-i\varphi}|0\rangle)$ 并在 `verify_math.py` 加入符号断言），并将课程级 `est_minutes` 从 `18 / 20 / 20` 调整为 `25 / 28 / 32`。
    - **第 1–3 课 Round 1 Cold-Reader 隔离盲测（`be860c92`、`67a7cde0`、`316ee3e5`）及修复**：
        - 第 1 课：修复 `zm-optical-transfer` 题干“不满足对称定态”前提自相矛盾与外部节号引用；Step 3 补充 $S_x|m_S=\pm 1/2\rangle = \frac{1}{2}|m_S=\mp 1/2\rangle$ 推导依据；修正 Step 1 SVG 无障碍标签量级（对质子 658 倍、相差约 $10^3$ 倍）并移除提前出现的 $|g\rangle/|e\rangle$ 剧透，明确 `E/h` 与「线偏振驱动项总系数」。
        - 第 2 课 v4：Step 1 补充相对本征进动频率 $\omega_0$ 的差/和频说明；Step 3 补充单模量子光场能量项 $\omega a^\dagger a$、耦合常数 $\lambda$、湮灭算符共轭与原子自由演化图像 $\hat{\sigma}_+ e^{i\omega_0 t}$，明确区分 $\hat{H}_0$ 自由演化图像（缓变 $\omega_0-\omega$ vs 快变 $\omega_0+\omega$）与驱动旋转系 $U_i$；显式规范 `rwa-recall-ladder-formula` 乘法与前后顺序。
        - 第 3 课：修复 `rabi-pulse-spot-mistake` 正确选项把 $H$ 与 $H_I$ 混写导致的 $\Omega$ vs $2\Omega$ 自相矛盾；消除 Step 1 `rabi-axis-basics` 对未定义 $|1\rangle,|0\rangle$ 的提前泄露；以零光子真空态 $|n=0\rangle$ 消除光子真空与自旋态 $|0\rangle$ 的记号冲突；写明 ODE 振荡试探解 $C_e(t)\propto e^{i\lambda t}$、去除 Step 2 配图超前的 `W`/`π 脉冲` 术语、补全 JC 激发初态切换反转反号说明及 Step 3 Worked Example 完整周期，并明示 `rabi-recall-pulse-formula` 的激发初态与 `sqrt(...)` 语法。
    - **Round 2 Cold-Reader 复验（`feb73ab7`）与终版收口**：确认第 1、3 课与第 2 课 JC 桥接等关键阻塞均已 `[RESOLVED]`；最后顺手消除了 Round 2 新捕获的 1 处 `rwa-recall-ladder-formula` 括号示例原答案泄露（改为 `e^(...)*S^+` 占位格式）、补充 Step 1 中 $H_0=\omega_0 S_z$ 进动说明并修正 1 处「布居概率」错别字，之后完整重跑 `build_svgs.py`、`academy_check.py -v`、`verify_math.py`、`render_preview.py` 与 Node `vm`。

5. **全章 10 个概念切分状态与原讲义勘误清单**
    - **课程架构状态**：`qm-spin-and-operators-foundation`（`stub` 外部基线）→ **Unit 1（全部 `authored`：`spin-zeeman-and-drive` v1、`rotating-wave-and-frame` v4、`su2-evolution-and-rabi-prob` v1，对应讲义式 `1.1–1.16` 与 Gerry & Knight Ch. 4 §4.1–§4.5）** → Unit 2（`single-qubit-gates`、`bloch-sphere-representation`、`bloch-siegert-shift`、`longitudinal-sideband-excitation` 均为 `stub`）→ Unit 3（`rabi-and-ramsey-spectroscopy`、`spin-echo-and-noise-correlation`、`dynamical-decoupling-and-xy4` 均为 `stub`）。
    - **原讲义《第1章 磁共振基础》12 处已核实源码勘误摘要（Unit 1 相关项已在正课及习题中纠正）**
        1. **正文第 1 页（PDF p.3）**：水中质子误印为电子下标 $\gamma_e$（应为 $\gamma_n$）；`磁旋磁` 应为 `旋磁比`；节号 `1.22` 应为 `1.2.2`。
        2. **正文第 2 页（PDF p.4）**：`2\Omega = -\gamma_e S_x` 误将横向驱动场振幅 $B_x$ 写作算符 $S_x$（第 1 课已明确排错）；`1.21` 对应 `1.2.1`。
        3. **正文第 4 页（PDF p.6）式 `(1.15)`**：$(\cos\frac{\theta}{2} + i\sin\frac{\theta}{2})n_z|1\rangle$ 括号错误（第 3 课正文与习题已纠正为 $(\cos\frac{\theta}{2} + i\sin\frac{\theta}{2}\,n_z)|1\rangle$）；同页出现 `式(??)`。
        4. **正文第 4 页（PDF p.6）式 `(1.19)` 下方**：$\cos\theta$ 根号内 $(\omega_0-\omega')$ 漏平方。
        5. **正文第 5 页（PDF p.7）式 `(1.20)/(1.23)` 下方**：$\omega-\omega'$ 漏下标 `0`；$\Delta_{\text{BS}}$ 印成 $\Delta_{\text{SB}}$。
        6. **正文第 5–6 页式 `(1.26)/(1.28)/(1.30)/(1.31)`**：升降算符改写漏系数 `1/2`。
        7. **正文第 6–7 页式 `(1.29)–(1.32)`**：贝塞尔参数 $\chi$ 多处误印为 $x$，式 `(1.32)` 末尾漏写 $S_x$。
        8. **正文第 7、14、15 页**：`(\pi)_\pi`（应为 `(\pi)_x`）、`磁声`（应为 `磁噪声`）、`讲(1.62)式子`（应为 `将`）。
        9. **正文第 8 页式 `(1.36)`**：纯态投影混用 $|\psi_1\rangle\langle\varphi_1|$。
        10. **正文第 8 页式 `(1.38)`**：泡利积迹恒等式错留 `\sigma_k / 2`。
        11. **正文第 10、12 页**：积分变量 $b$ 与标准差 $\sigma_b$ 混写；$\gamma_e$ 漏负号。
        12. **正文第 13 页式 `(1.58)`**：慢噪声回波衰减指数 $t^2$ 误印，按 $p=3$ 关系应为 $t^3$。
