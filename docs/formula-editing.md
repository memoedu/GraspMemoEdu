# 公式编辑与自动补全

在学习、复习和题库的答题框里直接输入 `f(x)`、`3/7`、`x^12` 或 `\frac{1}{2}`，框内会随输入显示公式。输入左括号会补齐右括号，再键入右括号会把光标移到括号外。自由作答框里的 `^` 和 `_` 会打开上标或下标分组。精确填空和「用文字填写答题控件」保留键入的原文，例如 `x^12` 的两个数字会一起显示在上标位置。需要在这两类输入框里明确分组时，可以输入 `(` 或 `{`。

输入 `f` 后按 Tab，可以插入 `f()` 并在括号内继续输入。上下方向键可选中候选，再按 Enter 接受。下拉框里的每个公式候选只显示一次渲染结果。输入 `!` 会看到阶乘符号，输入 `x` 可以直接继续写变量。自由作答时，点公式预览或离开输入框会将已识别的公式转为就地编辑的节点。用方向键在公式中移动，按 Esc 可选中整条公式并复制或删除。

答疑和反馈支持混排文字与公式。输入 `$...$`、`\(...\)`、`$$...$$` 或 `\[...\]` 即可渲染，也可点「插入公式」或从补全列表选择模板。

在编辑区里选中 `a/b` 可建议改成分式。补全仍用站点已有的下拉组件和「回答」「其他」开关。静态模板在构建时生成 KaTeX 预览。针对当前选区产生的预览用有容量上限的会话缓存复用。首批规则在浏览器内运行。

Milkdown 的 ProseMirror 文档将公式当作可选中的节点，MathLive 负责节点内编辑。墨干编辑器 Liii 的数学模式、结构占位与方向键操作用于交互参考。草稿和提交仍使用原表单字段，已有 LaTeX 分隔符在该公式未编辑时按原文保留。精确对答案和编程编辑沿用各自输入约定。计算器可视化编辑将在表达式往返验证后单独接入。

## 构建与验收

在独立缓存目录使用 `scripts/formula-dependencies` 的包配置和锁文件运行 `npm ci`。然后从项目根目录运行 `node scripts/formula-dependencies/build.mjs <缓存目录>`，更新本地模块、字体、许可证和资源哈希。答疑适配的源文件是 `scripts/chat_editor_source.mjs`，用 `node scripts/build_chat_editor.mjs` 更新现有答疑运行包。按 README 重新生成前端版本和静态导出。

使用 `scripts/calculator_browser_fixture.py` 启动隔离站点，随后运行 `node scripts/formula_browser_acceptance.mjs <产物目录> <本地站点>`。学习和复习入口使用 `scripts/review_web_acceptance.mjs` 的 `--autocomplete-only` 模式检查。公共导出测试校验公式运行文件、字体及预览的 SHA-256。

[墨干编辑器 Liii 数学模式](https://liiistem.cn/docs/guide-equation) · [Milkdown](https://milkdown.dev/docs) · [MathLive](https://mathlive.io/mathfield/) · [KaTeX](https://katex.org/docs/api.html)
