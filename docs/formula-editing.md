# 公式编辑与自动补全

在网站正文、题目或解析中，双击公式，或点公式旁的「选取公式片段」。在打开的只读公式中拖动选取，点「复制 LaTeX」或按 Ctrl+C／⌘C。方向键移动选点，Shift 加方向键扩展选区，Esc 关闭。也可以在公式上悬停或整选后按 Alt+Shift+F。未选择片段时，复制取得整式 LaTeX。少数无法交给 MathLive 渲染的公式会显示可选取的 LaTeX 源文。

在学习、复习和题库的答题框里直接输入 `f(x)`、`3/7`、`x^12` 或 `\frac{1}{2}`，公式就在当前光标处排版。分式出现后，可点击分子或分母，直接选中数字并改写。文字和公式可以写在同一行。输入左括号会补齐右括号，再键入右括号会把光标移到括号外。自由作答框里的 `^` 和 `_` 会打开上标或下标分组。精确填空和「用文字填写答题控件」保留键入的原文，例如 `x^12` 的两个数字会一起显示在上标位置。在下标中继续输入 `i+1` 会自动补成 `_{i+1}`。也可以自己输入括号，或用右方向键移出当前分组。

输入 `f` 后按 Tab，可以插入 `f()` 并在括号内继续输入。上下方向键可选中候选，再按 Enter 接受。下拉框里的每个公式候选只显示一次渲染结果。输入 `!` 会看到阶乘符号，输入 `x` 可以直接继续写变量。用方向键在公式中移动，按 Esc 可选中整条公式并复制或删除。

答疑和反馈支持混排文字与公式。输入 `$...$`、`\(...\)`、`$$...$$` 或 `\[...\]` 即可渲染，也可点「插入公式」或从补全列表选择模板。

在编辑区里选中 `a/b` 可建议改成分式。补全仍用站点已有的下拉组件和「回答」「其他」开关。静态模板在构建时生成 KaTeX 预览。针对当前选区产生的预览用有容量上限的会话缓存复用。首批规则在浏览器内运行。

Milkdown 的 ProseMirror 文档将公式当作可选中的节点，MathLive 负责节点内编辑。墨干编辑器 Liii 的数学模式、结构占位与方向键操作用于交互参考。表单字段负责保存草稿和提交，进入公式编辑后隐藏。已有 LaTeX 分隔符在该公式未编辑时按原文保留。精确对答案和编程编辑沿用各自输入约定。计算器可视化编辑将在表达式往返验证后单独接入。

## 构建与验收

在独立缓存目录使用 `scripts/formula-dependencies` 的包配置和锁文件运行 `npm ci`。然后从项目根目录运行 `node scripts/formula-dependencies/build.mjs <缓存目录>`，更新本地模块、字体、许可证和资源哈希。答疑适配的源文件是 `scripts/chat_editor_source.mjs`，用 `node scripts/build_chat_editor.mjs` 更新现有答疑运行包。按 README 重新生成前端版本和静态导出。

使用 `scripts/calculator_browser_fixture.py` 启动隔离站点，随后运行 `node scripts/formula_browser_acceptance.mjs <产物目录> <本地站点>`。学习和复习入口使用 `scripts/review_web_acceptance.mjs` 的 `--autocomplete-only` 模式检查。浏览器验收会分别点击并修改分子和分母，同时检查作答区、可见公式和实际提交值。公共导出测试校验公式运行文件、字体及预览的 SHA-256。

[墨干编辑器 Liii 数学模式](https://liiistem.cn/docs/guide-equation) · [Milkdown](https://milkdown.dev/docs) · [MathLive](https://mathlive.io/mathfield/) · [KaTeX](https://katex.org/docs/api.html)
