1. **《第1章 磁共振基础》×《Introductory Quantum Optics》Unit 1 + Unit 2 全七课交付报告**
    - **交付目录**：本包通过解耦工作流完整维护 Open Academy 格式的磁共振课程 Unit 1（3 课）与 Unit 2（4 课），合计 7 门已开放正课、21 个知识点、14 幅受控调色板 SVG、175 道互动练习及 24 张 FSRS-5 复习卡片（外加 Unit 3 共 3 门 `stub` 契约预览卡）。
    - **核心交付文件索引（均使用相对路径）**
        - 课程规划与双源元数据：[curriculum.yaml](../curriculum.yaml)、[sources/index.yaml](../sources/index.yaml)、[courses/mr-fundamentals.yaml](../courses/mr-fundamentals.yaml)
        - 概念先修图与符号准入表：[concepts/magnetic-resonance.yaml](../concepts/magnetic-resonance.yaml)、[notation.yaml](../notation.yaml)
        - Unit 1 正课与配套题库（共 3 课 · 9 步 · 75 题）：
            - 第 1 课：[lessons/spin-zeeman-and-drive.yaml](../lessons/spin-zeeman-and-drive.yaml)（`version: 1`，2 幅 SVG）与 [exercises/spin-zeeman-and-drive.yaml](../exercises/spin-zeeman-and-drive.yaml)（25 题，`zeeman-final-explain`）
            - 第 2 课：[lessons/rotating-wave-and-frame.yaml](../lessons/rotating-wave-and-frame.yaml)（`version: 4`，2 幅 SVG）与 [exercises/rotating-wave-and-frame.yaml](../exercises/rotating-wave-and-frame.yaml)（25 题，`rwa-final-explain`）
            - 第 3 课：[lessons/su2-evolution-and-rabi-prob.yaml](../lessons/su2-evolution-and-rabi-prob.yaml)（`version: 1`，2 幅 SVG）与 [exercises/su2-evolution-and-rabi-prob.yaml](../exercises/su2-evolution-and-rabi-prob.yaml)（25 题，`rabi-final-explain`）
        - Unit 2 正课与配套题库（共 4 课 · 12 步 · 100 题）：
            - 第 4 课（Unit 2 第 1 课）：[lessons/single-qubit-gates.yaml](../lessons/single-qubit-gates.yaml)（`version: 1`，2 幅 SVG）与 [exercises/single-qubit-gates.yaml](../exercises/single-qubit-gates.yaml)（25 题，`u2-l1-final-explain`）
            - 第 5 课（Unit 2 第 2 课）：[lessons/bloch-sphere-representation.yaml](../lessons/bloch-sphere-representation.yaml)（`version: 1`，2 幅 SVG）与 [exercises/bloch-sphere-representation.yaml](../exercises/bloch-sphere-representation.yaml)（25 题，`bloch-final-explain`）
            - 第 6 课（Unit 2 第 3 课）：[lessons/bloch-siegert-shift.yaml](../lessons/bloch-siegert-shift.yaml)（`version: 1`，2 幅 SVG）与 [exercises/bloch-siegert-shift.yaml](../exercises/bloch-siegert-shift.yaml)（25 题，`bs-final-explain`）
            - 第 7 课（Unit 2 第 4 课）：[lessons/longitudinal-sideband-excitation.yaml](../lessons/longitudinal-sideband-excitation.yaml)（`version: 1`，2 幅 SVG）与 [exercises/longitudinal-sideband-excitation.yaml](../exercises/longitudinal-sideband-excitation.yaml)（25 题，`longitudinal-sideband-final-explain`）
        - 校验工具、按课解耦 SVG 模块与数学验算插件：
            - 通用调度与渲染工具：[tools/academy_check.py](../tools/academy_check.py)、[tools/build_svgs.py](../tools/build_svgs.py)、[tools/verify_math.py](../tools/verify_math.py)、[tools/render_preview.py](../tools/render_preview.py)
            - SVG 模块：[tools/svgs/_geom.py](../tools/svgs/_geom.py)、[tools/svgs/spin-zeeman-and-drive.py](../tools/svgs/spin-zeeman-and-drive.py)、[tools/svgs/rotating-wave-and-frame.py](../tools/svgs/rotating-wave-and-frame.py)、[tools/svgs/su2-evolution-and-rabi-prob.py](../tools/svgs/su2-evolution-and-rabi-prob.py)、[tools/svgs/single-qubit-gates.py](../tools/svgs/single-qubit-gates.py)、[tools/svgs/bloch-sphere-representation.py](../tools/svgs/bloch-sphere-representation.py)、[tools/svgs/bloch-siegert-shift.py](../tools/svgs/bloch-siegert-shift.py)、[tools/svgs/longitudinal-sideband-excitation.py](../tools/svgs/longitudinal-sideband-excitation.py)
            - 数学验算插件：[tools/checks/_common.py](../tools/checks/_common.py)、[tools/checks/spin-zeeman-and-drive.py](../tools/checks/spin-zeeman-and-drive.py)、[tools/checks/rotating-wave-and-frame.py](../tools/checks/rotating-wave-and-frame.py)、[tools/checks/su2-evolution-and-rabi-prob.py](../tools/checks/su2-evolution-and-rabi-prob.py)、[tools/checks/single-qubit-gates.py](../tools/checks/single-qubit-gates.py)、[tools/checks/bloch-sphere-representation.py](../tools/checks/bloch-sphere-representation.py)、[tools/checks/bloch-siegert-shift.py](../tools/checks/bloch-siegert-shift.py)、[tools/checks/longitudinal-sideband-excitation.py](../tools/checks/longitudinal-sideband-excitation.py)
        - 先修依赖链导出与生成的交互预览：[reports/_prereqs_l1.txt](./_prereqs_l1.txt)、[reports/_prereqs_l2.txt](./_prereqs_l2.txt)、[reports/_prereqs_l3.txt](./_prereqs_l3.txt)、[reports/_prereqs_u2_l1.txt](./_prereqs_u2_l1.txt)、[reports/_prereqs_u2_l2.txt](./_prereqs_u2_l2.txt)、[reports/_prereqs_u2_l3.txt](./_prereqs_u2_l3.txt)、[reports/_prereqs_u2_l4.txt](./_prereqs_u2_l4.txt)、[preview/index.html](../preview/index.html)、[preview/rotating-wave-and-frame.html](../preview/rotating-wave-and-frame.html)

2. **双教材对照集成架构与符号契约**
    - **主从与内容边界约定**
        - 主骨架与符号约定严格以《第1章 磁共振基础》（`ch1-magnetic-resonance`，§§1.1–1.4 式 `1.1–1.40`）为准；Gerry & Knight《Introductory Quantum Optics》（`introductory-quantum-optics`，Ch. 4 §§4.1–4.5、§4.8、Ch. 11 §11.10、Appendix A §§A.1–A.2 与 Appendix C）作为二能级同构、耦合概率幅微分方程、量子门线路合成、密度矩阵纯度/谱分解以及大失谐色散 AC Stark 频移对照融入 Unit 1 与 Unit 2 全七课。
        - 第 3 单元全部 3 课（`rabi-and-ramsey-spectroscopy`、`spin-echo-and-noise-correlation`、`dynamical-decoupling-and-xy4`）继续保持 `status: stub`，不在 Unit 1/2 提前泄露 `FWHM`、$T_2^*$、$T_2$、$\tau_c$、$\eta(t)$、$\sigma_b$、Hahn 回波或 XY4/CPMG 保真度公式。
    - **全七课严格统一的物理符号与先修栅栏**
        - 态矢量对应：$|1\rangle \stackrel{\text{def}}{=} |m_S = -1/2\rangle \leftrightarrow |g\rangle = (0,1)^T$（电子自旋下能级 / 原子基态），$|0\rangle \stackrel{\text{def}}{=} |m_S = +1/2\rangle \leftrightarrow |e\rangle = (1,0)^T$（电子自旋上能级 / 原子激发态）。
        - 算符与参数对应：$2S_z \leftrightarrow \hat{\sigma}_3 = \sigma_z$，$2S_x \leftrightarrow \hat{\sigma}_+ + \hat{\sigma}_- = \sigma_x$，横纵驱动系数分别为 $2\Omega = -\gamma_e B_x \leftrightarrow 2V/\hbar$ 与 $\Omega_z = -\gamma_e B_z$。
        - 严格遵守 `notation.yaml` 先修有向无环图：`bloch-siegert-shift` 与 `longitudinal-sideband-excitation` 仅以 `rotating-wave-and-frame` 为硬前置（不依赖 `su2-evolution-and-rabi-prob` 的 $\delta,\Omega_{\text{eff}},\vec{\boldsymbol{\sigma}}$ 或软前置记号），分别独立引入 $\Delta_{\text{BS}} = \Omega'^2/[2(\omega_0-\omega')]$ 与纵向调制指数 $\chi = \Omega_z/\omega_z$、贝塞尔边带振幅 $J_n(\chi)\Omega$ 及第 $n$ 阶边带失谐 $\Delta_n = \omega_0 - \omega + n\omega_z$。

3. **自动化校验与交互网页验证结果**
    - **按课解耦 SVG 自动注入与防漂移门禁（[tools/build_svgs.py](../tools/build_svgs.py) & `tools/svgs/<concept_id>.py`）**：7 个模块共 14 幅图在 `--check` 与 [tools/academy_check.py](../tools/academy_check.py) 中全部输出 `validate -> OK` 与 `YAML sync -> OK`（`All 7 concept SVG modules verified (check-only)`）。
    - **Open Academy 静态规则与字数检查（[tools/academy_check.py](../tools/academy_check.py) `check -v`）**
        - 退出码 `0`：**0 errors，0 warnings**（全部 7 课共 49 处词数检查均在规范区间内，先修记号栅栏、模板多样性与 `recap` 契约全数通过）。
        - Unit 2 实测词数：
            - `single-qubit-gates`：`where_this_fits eq=103`，三步 `tldr` 为 `51 / 50 / 58`，三步 `explain` 为 `187 / 216 / 275`。
            - `bloch-sphere-representation`：`where_this_fits eq=115`，三步 `tldr` 为 `40 / 39 / 42`，三步 `explain` 为 `208 / 246 / 247`。
            - `bloch-siegert-shift`：`where_this_fits eq=80`，三步 `tldr` 为 `44 / 44 / 49`，三步 `explain` 为 `282 / 277 / 300`。
            - `longitudinal-sideband-excitation`：`where_this_fits eq=112`，三步 `tldr` 为 `52 / 41 / 42`，三步 `explain` 为 `278 / 303 / 326`。
    - **按课解耦符号推导、数值动力学、例题与 175 题模板验证（[tools/verify_math.py](../tools/verify_math.py) & `tools/checks/<concept_id>.py`）**
        - `--require-checks` 自动发现全部 7 个 `authored` 概念并执行全部 7 个独立验算模块（`0` 缺失）：
            - Unit 1（式 `1.1–1.16`）：自旋–偶极同构、三维 Rodrigues 旋转、升降算符变换、$SU(2)$ 演化与式 `(1.15)` 勘误校验、Gerry–Knight 耦合概率幅 ODE 与 JC 量子化拉比振荡。
            - `single-qubit-gates`（式 `1.33` 与 G&K §11.10 式 `11.24–11.29`）：全部 9 类脉冲门矩阵（$(\pi/2)_\beta, (\pi)_\beta, (\pi)_x, (\pi)_y, T_{\text{MR}}, S_{\text{MR}}, Z_{\text{MR}}, H_{\text{MR}}$）、$\det(U)=+1$、$H_{\text{MR}}^2=-\mathbb{1}$ 及四门通用态合成恒等式 $\hat{U}_{\text{PG}}(\varphi+\pi/2)\hat{U}_{\text{H}}\hat{U}_{\text{PG}}(2\theta)\hat{U}_{\text{H}}|0\rangle = e^{i\theta}(\cos\theta|0\rangle + e^{i\varphi}\sin\theta|1\rangle)$。
            - `bloch-sphere-representation`（式 `1.34–1.40` 与 G&K 附录 A 式 `A4–A27`）：纯态/混态密度矩阵展开、泡利积恒等式 $\sigma_i\sigma_j = \delta_{ij}\mathbb{1} + i\epsilon_{ijk}\sigma_k$、迹反演 $\vec{\boldsymbol{n}}=\operatorname{Tr}(\rho\vec{\boldsymbol{\sigma}})$、纯度 $\operatorname{Tr}(\rho^2)=(1+|\vec{\boldsymbol{n}}|^2)/2$、本征值 $(1\pm|\vec{\boldsymbol{n}}|)/2$ 及 10 组随机混态 $SU(2)\to SO(3)$ 旋转等价性。
            - `bloch-siegert-shift`（式 `1.17–1.23` 与 G&K §4.8 / 附录 C）：双重旋转系变换、倾斜轴对角化、$\cos^2(\theta/2)/\sin^2(\theta/2)$ 精确投影分解、二阶展开 $\Delta_{\text{BS}} = \Omega'^2/[2(\omega_0-\omega')]$、大失谐 JC 色散频移等价性及含反旋项的全含时薛定谔方程 / Shirley Floquet 数值共振峰比对。
            - `longitudinal-sideband-excitation`（式 `1.24–1.32`）：升降算符 $\frac{1}{2}$ 因子、含时变换 $U_i(t)$ 的 $[U_i(t), S_z]=0$ 标量链式求导、雅可比–安格尔级数截断误差（$<10^{-12}$）、第一类贝塞尔积分奇偶对消与小参量极限 $J_1(\chi)\approx \chi/2$、二次旋转系常系数有效哈密顿量及倍频条件 $\omega = \omega_0/(1-n)$。
        - 核验全部 7 课共 21 个知识点的 Worked Examples 数值计算（无嵌入式 Python 块）及全部 175 道练习（每课 25 题，含全数参数化模板、静态/动态 `common_wrong` 非碰撞、表达式自由变量与正则校验）。
    - **全三单元自适应网页与 Node `vm` 运行验证（[tools/render_preview.py](../tools/render_preview.py)）**
        - 在零修改 [tools/render_preview.py](../tools/render_preview.py) 代码的前提下自动渲染全部 3 个 Unit（10 节概念：7 节 `authored` 互动正课 + 3 节 Unit 3 `stub` 契约预览卡），生成 [preview/index.html](../preview/index.html) 与 [preview/rotating-wave-and-frame.html](../preview/rotating-wave-and-frame.html)。
        - Node `vm` 实测确认两份 HTML 均包含 3 个单元导航组、10 个课标签（7 `authored` + 3 `stub`）、3 个 Unit 3 Stub 契约面板、175 个题目 DOM 槽位、`EX_MAP`（175）、`KP_META`（21）、`LESSONS_META`（10）及 `cardSpecs()`（24 张 FSRS 卡 = 21 张 KP 卡 + 3 张维度卡），在 Unit 2 四课与 Unit 3 Stub 面板之间切换、作答判题、触发 FSRS 排程并持久化至 `localStorage` 均零异常通过。

4. **Unit 2 解耦并行编写与五方两轮隔离审计闭环**
    - **四代理零冲突并行编写**：4 名 `unit2-lesson-author` 子代理同时在各自互不重叠的 4 文件切片（`lessons/<cid>.yaml`、`exercises/<cid>.yaml`、`tools/svgs/<cid>.py`、`tools/checks/<cid>.py`）上独立编写并通过单课 `--concept <cid>` 门禁，无需修改任何共享工具代码。
    - **五方隔离审阅（Round 1）与精准修复**：
        - **先修一致性审计员（`f180c136`）**：核查 4 课正课与 100 道练习的硬/软前置边界与跨课符号一致性，捕获并消除了 `bloch-rotation-component-template` Hint 2 模板求值泄露、`bloch-sphere-representation` 例题中未定义 `-i H` 软前置符号碰撞、`bloch-siegert-shift` 与 `longitudinal-sideband-excitation` 中超前的「线宽」措辞以及 `bs-recall-stark-mc` 对未教纵向调制的超前考查。
        - **第 4–7 课 Cold-Reader 盲测审阅员（`0326dd77`、`dab2b1fc`、`00db3b2e`、`c5458b20`）**：
            - `single-qubit-gates`：将 SVG 1 矩阵元素改为独立坐标防空格折叠、将 SVG 2 纵向门标签移至 $\delta$ 轴左侧避开 $45^\circ$ 射线，修正 KP 2 中 $H_{\text{MR}}$ 与 $(\pi/2)_y$ 的基矢作用对比并移除 Bloch 球超前剧透，在 KP 3 补全 Gerry–Knight 式 `(11.29)` 通用 $(\theta,\varphi)$ 三步代数推导，并显式标明模板题小数精度与替换 `30°` 重合干扰项。
            - `bloch-sphere-representation`：消除 SVG 1 右栏密度矩阵公式越界与 SVG 2 `+90°` 标签重叠，将 `recap` 中软前置标注为选修背景，在 KP 1 写明全部三个泡利矩阵并在 KP 3 补齐 $\theta=\pi$ 轴对称反射公式 $R_{\vec{\boldsymbol{n}}\cdot\pi}(\vec{\boldsymbol{n}}_0)=2(\vec{\boldsymbol{n}}\cdot\vec{\boldsymbol{n}}_0)\vec{\boldsymbol{n}}-\vec{\boldsymbol{n}}_0$，使 Step 1 迁移题解答完全基于纯态对齐自洽。
            - `bloch-siegert-shift`：在 KP 1 阐明被略去的一阶快变纵项 $\Omega\sin\theta\cos\alpha(t)S_z'$（$20\text{ kHz}$）因在 $|\omega-\omega'|\sim 5\text{ GHz}$ 高频零均值振荡、累积相位抖动仅 $\sim 4\times 10^{-6}\text{ rad}$ 而远小于静态线性累积的 $\Delta_{\text{BS}}$（$10\text{ kHz}$），并将算符还原严格表述为 $(S_x',S_y',S_z')\leftrightarrow(S_x,S_y,S_z)$ 幺正等价与 $\sin^2(\theta/2)\sim 10^{-6}$ 态交叠偏差；修正 SVG 1 中 $\cos\theta$ 与 $\cos^2(\theta/2)$ 的泰勒系数区分与绝对值分子 $|\omega_0-\omega'|$，消除 SVG 2 曲线与文字交叠，在 KP 3 补齐 $\frac{1}{2}\Omega'\leftrightarrow\lambda\sqrt{n}$ 算符桥接并移除 `bs-sign-optical-stark-transfer` 题干剧透。
            - `longitudinal-sideband-excitation`：在 KP 1 补全含时相互作用图像变换法则、$[\Theta(t)S_z,\dot{\Theta}(t)S_z]=0$ 标量链式求导及 $[U_i(t),S_z]=0$ 对易消去论证，显式对比 $\Omega_z=-\gamma_e B_z$ 与 $2\Omega=-\gamma_e B_x$，在 KP 3 由贝塞尔积分导出小参量近似 $J_1(\chi)\approx\chi/2$，并将 SVG 1 图例底色设为不透明、修正 SVG 2 `横向 Ω (ω)` 记号与 $\theta_B\ne 90^\circ$ 标签避让。
    - **Round 2 独立复验全票通过**：五位隔离审阅员对修订稿独立复核后均给出 **`PASS`**（`f180c136`、`0326dd77`、`dab2b1fc`、`00db3b2e`、`c5458b20` 全数确认 Round 1 问题 100% `[RESOLVED]` 且零新回归）。

5. **全章 10 个概念切分状态与原讲义勘误清单**
    - **课程架构状态**：`qm-spin-and-operators-foundation`（`stub` 外部基线）→ **Unit 1（全部 `authored`：`spin-zeeman-and-drive` v1、`rotating-wave-and-frame` v4、`su2-evolution-and-rabi-prob` v1）** → **Unit 2（全部 `authored`：`single-qubit-gates` v1、`bloch-sphere-representation` v1、`bloch-siegert-shift` v1、`longitudinal-sideband-excitation` v1，对应讲义 §§1.2–1.4 式 `1.17–1.40`）** → Unit 3（`rabi-and-ramsey-spectroscopy`、`spin-echo-and-noise-correlation`、`dynamical-decoupling-and-xy4` 均为 `stub`）。
    - **原讲义《第1章 磁共振基础》12 处已核实源码勘误摘要（Unit 1 与 Unit 2 相关项均已在正课、习题及数学检查脚本中纠正）**
        1. **正文第 1 页（PDF p.3）**：水中质子误印为电子下标 $\gamma_e$（应为 $\gamma_n$）；`磁旋磁` 应为 `旋磁比`；节号 `1.22` 应为 `1.2.2`。
        2. **正文第 2 页（PDF p.4）**：`2\Omega = -\gamma_e S_x` 误将横向驱动场振幅 $B_x$ 写作算符 $S_x$（第 1 课已明确排错）；`1.21` 对应 `1.2.1`。
        3. **正文第 4 页（PDF p.6）式 `(1.15)`**：$(\cos\frac{\theta}{2} + i\sin\frac{\theta}{2})n_z|1\rangle$ 括号错误（第 3 课已纠正为 $(\cos\frac{\theta}{2} + i\sin\frac{\theta}{2}\,n_z)|1\rangle$）；同页出现 `式(??)`。
        4. **正文第 4 页（PDF p.6）式 `(1.19)` 下方**：$\cos\theta$ 根号内 $(\omega_0-\omega')$ 漏平方（第 6 课 `bloch-siegert-shift` 已纠正并加入符号断言）。
        5. **正文第 5 页（PDF p.7）式 `(1.20)/(1.23)` 下方**：$\omega-\omega'$ 漏下标 `0`（应为 $\omega_0-\omega'$）；$\Delta_{\text{BS}}$ 印成 $\Delta_{\text{SB}}$（第 6 课已纠正）。
        6. **正文第 5–6 页式 `(1.26)/(1.28)/(1.30)/(1.31)`**：升降算符改写漏系数 `1/2`（第 7 课 `longitudinal-sideband-excitation` 已全程恢复 $\frac{1}{2}$ 因子）。
        7. **正文第 6–7 页式 `(1.29)–(1.32)`**：贝塞尔参数 $\chi$ 多处误印为 $x$，式 `(1.32)` 末尾 $\cos(\varphi-n\varphi_z)$ 后漏写算符 $S_x$（第 7 课已纠正）。
        8. **正文第 7、14、15 页**：第 7 页 $\beta=0$ 共振 $\pi$ 脉冲误印为 `(\pi)_\pi`（应为 `(\pi)_x`，第 4 课 `single-qubit-gates` 已纠正）；第 14、15 页 `磁声`（应为 `磁噪声`）、`讲(1.62)式子`（应为 `将`）。
        9. **正文第 8 页式 `(1.36)`**：混态系综展开纯态投影算符误写为 $|\psi_1\rangle\langle\varphi_1|$（应为 $|\psi_1\rangle\langle\psi_1|$，第 5 课 `bloch-sphere-representation` 已纠正；同时指出 G&K 式 `(A25)` 非对角项 $\pm i s_2$ 与标准 $\sigma_y$ 的符号差异）。
        10. **正文第 8 页式 `(1.38)`**：泡利积迹恒等式括号内错留 `\sigma_k / 2`（正确关系为 $\sigma_i\sigma_j = \delta_{ij}\mathbb{1} + i\epsilon_{ijk}\sigma_k$，因子 $1/2$ 来自外部 $\rho=(\mathbb{1}+\vec{\boldsymbol{n}}\cdot\vec{\boldsymbol{\sigma}})/2$，第 5 课已纠正）。
        11. **正文第 10、12 页**：积分变量 $b$ 与标准差 $\sigma_b$ 混写；$\gamma_e$ 漏负号。
        12. **正文第 13 页式 `(1.58)`**：慢噪声回波衰减指数 $t^2$ 误印，按 $p=3$ 关系应为 $t^3$。
