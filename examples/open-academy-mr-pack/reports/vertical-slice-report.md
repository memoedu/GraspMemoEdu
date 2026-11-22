1. **《第1章 磁共振基础》Open Academy 垂直切片交付报告**
    - **隔离工作目录**：全部课程内容、检验脚本、审核中间产物、HTML 预览与本报告均位于 `examples/open-academy-mr-pack`，未修改工作区 主仓库原有业务代码。
    - **核心交付文件索引**
        - 课程规划与来源元数据：[curriculum.yaml](../curriculum.yaml)、[sources/index.yaml](../sources/index.yaml)、[courses/mr-fundamentals.yaml](../courses/mr-fundamentals.yaml)
        - 概念先修图与符号准入表：[concepts/magnetic-resonance.yaml](../concepts/magnetic-resonance.yaml)、[notation.yaml](../notation.yaml)
        - 垂直切片正课与配套习题：[lessons/rotating-wave-and-frame.yaml](../lessons/rotating-wave-and-frame.yaml)（`version: 3`，3 步知识模块、2 幅程序计算坐标的 SVG）、[exercises/rotating-wave-and-frame.yaml](../exercises/rotating-wave-and-frame.yaml)（25 题，覆盖 `basics`、`lesson_only` 参数理解、3 个参数化数值模板、排错、`transfer`、9 道 FSRS `recall` 及课末总结 `rwa-final-explain`）
        - 校验工具、先修导出与交互预览：[tools/academy_check.py](../tools/academy_check.py)、[tools/build_svgs.py](../tools/build_svgs.py)、[tools/verify_math.py](../tools/verify_math.py)、[tools/render_preview.py](../tools/render_preview.py)、[tools/_prereqs_output.txt](../tools/_prereqs_output.txt)、[preview/rotating-wave-and-frame.html](../preview/rotating-wave-and-frame.html)

2. **Open Academy 工作流对照与自动化实测结果**
    - **课程架构设计（对应 `plan-course` 与 `write-from-sources`）**：保留全章 `grounded: true` 与 `ch1-magnetic-resonance` 单来源溯源；除课程 3 个单元共 10 个核心概念外，增设不入课程清单的外部前置基线概念 `qm-spin-and-operators-foundation`（`status: stub`，作为 `spin-zeeman-and-drive` 的硬前置），显式契约化大学量子力学与数学预备知识（$i^2=-1$、欧拉公式、偏导与乘积法则、狄拉克记号、$S_z|m_S=\pm 1/2\rangle = \pm\frac{1}{2}|m_S=\pm 1/2\rangle$、厄米共轭与幺正算符 $U^\dagger U=\mathbb{1}$、$\hbar=1$ 薛定谔方程及圆偏振光子角动量 $+1/-1$）。
    - **中文可读性与静态规则校验（[tools/academy_check.py](../tools/academy_check.py)）**
        - 在本地无 `pnpm` 环境下，将原仓库 `apps/api/src/content/validate.ts`、`warnings.ts` 与 CLI `prereqs` 完整移植为 Python CLI，并采用中文等效词计数公式 $\operatorname{round}(0.6\times\text{cjk} + \text{latin} + \text{math})$。
        - 最终定稿后运行 `academy_check.py check ... -v` 退出码 `0`：**0 errors，0 warnings**。
        - 各部分等效词实测指标：`where_this_fits` `eq=113`（允许区间 30–130）；Step 1 `tldr eq=46`、`explain eq=360`；Step 2 `tldr eq=57`、`explain eq=373`；Step 3 `tldr eq=52`、`explain eq=314`（`tldr` 上限 60，`explain` 上限 380）。
    - **SVG 几何坐标与静态规则校验（[tools/build_svgs.py](../tools/build_svgs.py)）**
        - 两幅内嵌 `<svg>` 均通过三角函数与弧线终点解析计算生成，不使用 `fill="none"`（采用 `fill="#ffffff" fill-opacity="0"`），文字描边防遮挡，并同步保存到 [tools/_generated_svgs/svg1.svg](../tools/_generated_svgs/svg1.svg) 与 [tools/_generated_svgs/svg2.svg](../tools/_generated_svgs/svg2.svg)；定稿重新执行均输出 `validate -> OK`。
    - **符号推导、例题数值与习题模板穷举校验（[tools/verify_math.py](../tools/verify_math.py)）**
        - SymPy 精确核验原讲义式 `(1.5)–(1.12)` 的矩阵与算符恒等式。
        - NumPy 核验 Steps 1–3 `worked` 全部数值算例（包括 $\Omega/(2\pi) = 10\text{ MHz}$、$\omega_0/(2\pi) = 10\text{ GHz}$、$\omega/(2\pi) = 9.99\text{ GHz}$、$(\omega_0-\omega)/(2\pi) = 10\text{ MHz}$、$\varphi = \pi/2$ 下旋转法与升降算符法所得 $H_I/(2\pi) = 10\text{ MHz}\cdot S_z + 10\text{ MHz}\cdot S_y$、$|m_S=\pm 1/2\rangle$ 逐态验证），以及 $N=6$ 截断 Fock 空间玻色子恒等式 $e^{i\omega t\,a^\dagger a}a^\dagger e^{-i\omega t\,a^\dagger a} = a^\dagger e^{i\omega t}$，并断言 `worked` 中不含未引入的 Python 代码块。
        - 习题模板与正则校验：`rwa-split-drive-amp-template` 5 组有效参数（5 个不同答案，范围 `[2.8, 14.0]`）；`rwa-frame-detuning-template` 59 组有效参数（59 个不同答案，范围 `[-520.0, 590.0]`）；`rwa-ladder-phase-template` 16 组有效参数（9 个不同答案，范围 `[50.4, 806.4]`），零错误项碰撞；表达式题 `rwa-recall-frame-formula` 与文本正则题 `rwa-recall-split-formula`（6 个示例全匹配）、`rwa-recall-ladder-formula`（7 个示例全匹配）全部通过。

3. **三轮独立审查闭环与 Round 3 后定稿说明（遵守 3 轮硬上限）**
    - **Round 1 与 Round 2 审查及修订摘要**
        - 采用隔离的 `research` 子代理分别扮演仅阅读无答案载荷（`tools/_cold_reader_payload.txt`（本地审查临时载荷，未入库）、`tools/_cold_reader_payload_r2.txt`（本地审查临时载荷，未入库））的冷读审查员与核对先修契约的先修审计员。
        - 前两轮冷读总结均准确命中 `objective`，并陆续暴露并修正了：缺少大学 QM/微积分前置契约、Step 3 例题误嵌入不属 `implementation` 概念的 Python/`numpy` 代码段、将本征基矢误写作`基态`、缺少 `H_I` 薛定谔推导与 `项①/②` `\underbrace` 显式标号、三维旋转公式未同时比对左右两端 `U_i^\dagger` 与 `U_i`、`### 旋波近似的局限性` 置于第 3 步而非第 1 步、以及 `worked` 句尾截断与 `微波`/`单比特` 措辞泄露等问题。
    - **Round 3 最终审查实况**
        - **先修审计员（`25050b30`）结论：`PASS WITH MINOR NOTES`**。确认本课与全部 25 道练习均完全落在 [tools/_prereqs_output.txt](../tools/_prereqs_output.txt) 或课前显式定义范围内，无任何 `Not yet taught` 符号或后续概念（$\delta, \Omega_{\text{eff}}, \vec{\boldsymbol{\sigma}}, \Delta_{\text{BS}}, J_n(\chi), \rho, T_2^*, T_2, F_{XY4}$ 等）提前泄露；唯一小问题为基线 `qm-spin-and-operators-foundation` 中 `左右旋圆偏振光子分别携带角动量 +1 与 -1` 字序与正课 `右旋=+1 / 左旋=-1` 相反。
        - **冷读审查员（`2d0a0fae`，阅读 `tools/_cold_reader_payload_r3.txt`（本地审查临时载荷，未入库））**：两句话主旨准确命中 `objective`，15 道随堂问题与 `rwa-final-explain` 全部可仅凭正文与先修基线正确解答；检查清单 `(b)`、`(c)`、`(e)`、`(h)`、`(i)` 全部通过，指出 4 项具体问题：`(a)` Section 0 与 Step 1 第 43 行 `左旋/右旋` 映射矛盾（另附带建议显式点出 `$S_y$` 与 `$S$` 的意义）；`(d)` Step 2 `aria-label` 缺少正文提及的`橙色箭头`与 Step 1 `aria-label` 缺少`①`；`(f)` `### 旋波近似的局限性` 为纯名词主题标题；`(g)` Step 3 结尾向高自旋与玻色子推广的一句堆叠过多分句与冒号括注。
    - **Round 3 后定稿微调（依 `write-lesson/SKILL.md` §7.3 3 轮上限规则，未开启第 4 轮子代理审查）**
        - 已逐项落地上述明确修改：在 `qm-spin-and-operators-foundation` 改写为 `绕 +z 轴逆时针（右旋）与顺时针（左旋）旋转的圆偏振光子分别携带角动量 +1 与 -1` 并统一单位算符为 `\mathbb{1}`；在 Step 1 显式说明 `$S_y$` 为 $y$ 方向自旋分量并将 `### 旋波近似的局限性` 改为行动/结论导向的 `### 判断旋波近似何时在强驱动下失效`；在 `build_svgs.py` 与课内 SVG 同步补全 `aria-label` 中的`①`与`沿橙色箭头`描述；拆分 Step 2、Step 3 长句并将 `h.c.` 共轭规则写清为 `(cA)^\dagger = c^*A^\dagger` 与 `(U_i^\dagger S^+ U_i)^\dagger = U_i^\dagger S^- U_i`。上述最后修改尚未经过第 4 轮冷读或先修子代理复审，但已重新跑通 `build_svgs.py`、`academy_check.py check -v`（0 error / 0 warning）、`verify_math.py` 与 `render_preview.py`。

4. **全章 10 个概念切分与垂直切片讲义映射**
    - **外部前置基线（不纳入课程清单）**：`qm-spin-and-operators-foundation`（`status: stub`），契约化大学量子力学、线性代数与微积分基准。
    - **Unit 1：单自旋磁共振与相干演化**
        - `spin-zeeman-and-drive`（`stub`）：对应讲义 1.1 节前段，正文第 1–2 页（PDF p.3–4），式 `(1.1)–(1.4)`。
        - `rotating-wave-and-frame`（**`authored` 垂直切片**）：对应讲义 1.1 节中段，正文第 2–3 页（PDF p.4–5），式 `(1.5)–(1.12)`；三步对应分别为：Step 1 `rwa-split-field`（拆解线偏振与 RWA 舍去项①并界定强驱动失效条件，式 `(1.5)–(1.6)`）→ Step 2 `rwa-rotating-frame`（相互作用图像 $U_i=e^{-i\omega t S_z}$ 与三维旋转公式，式 `(1.7)–(1.9)`）→ Step 3 `rwa-ladder-operators`（升降算符 $S^\pm$ 法与向高自旋/玻色子 $a^\dagger,a$ 推广，式 `(1.10)–(1.12)`）。
        - `su2-evolution-and-rabi-prob`（`stub`）：对应讲义 1.1 节后段，正文第 3–4 页（PDF p.5–6），式 `(1.13)–(1.16)`。
    - **Unit 2：单比特门、Bloch 表象与非共振微扰**
        - `single-qubit-gates`（`stub`）：对应 1.3 节，正文第 7–8 页（PDF p.9–10），式 `(1.33)` 与单比特门矩阵。
        - `bloch-sphere-representation`（`stub`）：对应 1.4 节，正文第 8–9 页（PDF p.10–11），式 `(1.34)–(1.40)`。
        - `bloch-siegert-shift`（`stub`）：对应 1.2.1 节，正文第 4–5 页（PDF p.6–7），式 `(1.17)–(1.23)`。
        - `longitudinal-sideband-excitation`（`stub`）：对应 1.2.2 节，正文第 5–7 页（PDF p.7–9），式 `(1.24)–(1.32)`。
    - **Unit 3：频率测量与抗噪声脉冲序列**
        - `rabi-and-ramsey-spectroscopy`（`stub`）：对应 1.5.1 节，正文第 9–12 页（PDF p.11–14），式 `(1.41)–(1.50)`。
        - `spin-echo-and-noise-correlation`（`stub`）：对应 1.5.2 节前中段，正文第 12–14 页（PDF p.14–16），式 `(1.51)–(1.60)`。
        - `dynamical-decoupling-and-xy4`（`stub`）：对应 1.5.2 节后段，正文第 14–16 页（PDF p.16–18），式 `(1.61)–(1.68)`（讲义目录所列 p.17 参考文献页未包含在当前 18 页 PDF 内）。

5. **原讲义《第1章 磁共振基础》12 处已核实源码勘误总表**
    1. **正文第 1 页（PDF p.3）**：水中质子误印为电子下标 $\gamma_e \approx 2\pi\times 4.2576\text{ kHz/G}$（应为 $\gamma_n$）；同段「其他常遇到的**磁旋磁**有」应为「**旋磁比**有」；且正文指向「放在第 **1.22** 节讨论」（目录节号为 **1.2.2**）。
    2. **正文第 2 页（PDF p.4）**：`2\Omega = -\gamma_e S_x` 把横向驱动场振幅 $B_x$ 误写为自旋算符 $S_x$（已在 [lessons/rotating-wave-and-frame.yaml](../lessons/rotating-wave-and-frame.yaml) 中改为 `2\Omega = -\gamma_e B_x`）；同段「将在 **1.21** 节详细讨论」对应目录 **1.2.1** 节。
    3. **正文第 4 页（PDF p.6）式 `(1.15)` 及交叉引用**：$|\psi\rangle = (\cos\frac{\theta}{2} + i\sin\frac{\theta}{2})n_z|1\rangle + \cdots$ 括号位置错误（应为 $(\cos\frac{\theta}{2} + i\sin\frac{\theta}{2}\, n_z)|1\rangle$）；同页出现未编译解析的 `式(??)`。
    4. **正文第 4 页（PDF p.6）式 `(1.19)` 下方 `cos θ`**：$\cos\theta = (\omega_0 - \omega')/\sqrt{(\omega_0 - \omega') + \Omega'^2}$ 根号内漏写了 $(\omega_0 - \omega')$ 的平方。
    5. **正文第 5 页（PDF p.7）式 `(1.20)` 与式 `(1.23)` 下方**：$\cos\theta = 1 - \frac{1}{2}(\frac{\Omega'}{\omega - \omega'})^2$ 分母漏写了 $\omega_0$ 中的下标 `0`（应为 $\omega_0 - \omega'$）；同页下文将 $\Delta_{\text{BS}}$ 下标颠倒印作 $\Delta_{\text{SB}} = \Omega^2/2(\omega_0 + \omega)$（亦宜加外括号明示分母为 $2(\omega_0+\omega)$）。
    6. **正文第 5 页（PDF p.7）式 `(1.26)` 及第 6 页（PDF p.8）式 `(1.28)`、`(1.30)`、`(1.31)`**：由圆偏振改写为升降算符时整条链路漏掉了系数 `1/2`，将 $\frac{\Omega}{2}(e^{-i(\omega t+\varphi)}S^+ + h.c.)$ 误作 $\Omega(e^{-i(\omega t+\varphi)}S^+ + h.c.)$，导致式 `(1.26)`、`(1.28)`、`(1.30)`、`(1.31)` 驱动幅度均偏大两倍。
    7. **正文第 6 页（PDF p.8）式 `(1.29)`–`(1.32)` 与第 7 页（PDF p.9）**：前面定义贝塞尔参数 $\chi = \Omega_z/\omega_z$，但随后式 `(1.29)`–`(1.31)`、`1.32` 与第 7 页正文中多处把希腊字母 $\chi$ 误排为拉丁字母 $x$（写作 $J_n(x)$、$J_{-1}(x)$）；且式 `(1.32)` 中 $\cos(\varphi - n\varphi_z)$ 后面漏写了自旋算符 $S_x$。
    8. **正文第 7 页（PDF p.9）**：$\beta = 0$ 时的 $\pi$ 脉冲被错印为 `(\pi)_\pi`（下标应为 $x$，即 `(\pi)_x`；另如第 14 页/PDF p.16 出现「磁声的性质」应为「磁噪声的性质」、第 15 页/PDF p.17 出现`讲(1.62)式子`应为`将`）。
    9. **正文第 8 页（PDF p.10）式 `(1.36)`**：混态密度矩阵误写为 $p_1|\psi_1\rangle\langle\varphi_1| + p_2|\psi_2\rangle\langle\varphi_2|$（同一纯态的右矢与左矢字母混用了 $\psi$ 与 $\varphi$）。
    10. **正文第 8 页（PDF p.10）式 `(1.38)`**：泡利矩阵乘积迹计算中，最外层的 `/2` 已与泡利恒等式抵消为 $\delta_{ij}$，却仍错留出 `\sigma_k / 2`（式 `(1.38)` 方括号内应为 $\delta_{ij}\mathbb{1} + i\epsilon_{ijk}\sigma_k$）。
    11. **正文第 10 页（PDF p.12）与第 12 页（PDF p.14）**：第 10 页「当 $\gamma_e b \geqslant \Omega$ 时，上图的边峰会消失」将积分样本变量 $b$ 误作高斯分布标准差 $\sigma_b$（且 $\gamma_e < 0$ 需取绝对值 $|\gamma_e|\sigma_b \geqslant \Omega$）；第 12 页括号中「注意 $\gamma_e = 2\pi\times 2.8\text{ MHz/G}$」漏掉了电子旋磁比的负号（应写明正值幅度或 $-2\pi\times 2.8\text{ MHz/G}$）。
    12. **正文第 13 页（PDF p.15）式 `(1.58)`**：回波序列慢噪声极限下写出 $C(t) = e^{-\eta^2 t^2 / 12\tau_c}$ 与 $T_2 = (12\tau_c/\eta^2)^{1/3}$，指数里的 $t^2$ 误印，按紧接下页（正文第 14 页/PDF p.16）所写 `(1.58) 式中 p = 3` 及特征时间三次方根关系应为 $t^3$（即 $e^{-\eta^2 t^3 / (12\tau_c)}$）。
