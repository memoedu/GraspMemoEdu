# 公式编辑与自动补全

学习、复习、题库中的适用文本答题框，以及答疑和反馈，可以混排文字和公式。输入 `$...$`、`\(...\)`、`$$...$$` 或 `\[...\]` 后，支持的数学 LaTeX 会就地渲染。也可以点「插入公式」，或者在补全列表中选用公式模板。输入 `f`，按 Tab 插入 `f()` 并把光标放进括号。上下方向键可选中候选，再按 Enter 接受。已经进入公式时，可用方向键在公式结构间移动，或按 Esc 选中整条公式，再复制或删除。

在编辑区里选中 `a/b` 可建议改成分式。补全仍用站点已有的下拉组件和「回答」「其他」开关。静态模板在构建时生成 KaTeX 预览。针对当前选区产生的预览用有容量上限的会话缓存复用。首批规则在浏览器内运行。

Milkdown 的 ProseMirror 文档将公式当作可选中的节点，MathLive 负责节点内编辑。墨干编辑器 Liii 的数学模式、结构占位与方向键操作用于交互参考。草稿和提交仍使用原表单字段，已有 LaTeX 分隔符在该公式未编辑时按原文保留。精确对答案和编程编辑沿用各自输入约定。计算器可视化编辑将在表达式往返验证后单独接入。

## 构建与验收

在独立缓存目录使用 `scripts/formula-dependencies` 的包配置和锁文件运行 `npm ci`。然后从项目根目录运行 `node scripts/formula-dependencies/build.mjs <缓存目录>`，更新本地模块、字体、许可证和资源哈希。答疑适配的源文件是 `scripts/chat_editor_source.mjs`，用 `node scripts/build_chat_editor.mjs` 更新现有答疑运行包。按 README 重新生成前端版本和静态导出。

使用 `scripts/calculator_browser_fixture.py` 启动隔离站点，随后运行 `node scripts/formula_browser_acceptance.mjs <产物目录> <本地站点>`。学习和复习入口使用 `scripts/review_web_acceptance.mjs` 的 `--autocomplete-only` 模式检查。公共导出测试校验公式运行文件、字体及预览的 SHA-256。

[墨干编辑器 Liii 数学模式](https://liiistem.cn/docs/guide-equation) · [Milkdown](https://milkdown.dev/docs) · [MathLive](https://mathlive.io/mathfield/) · [KaTeX](https://katex.org/docs/api.html)
