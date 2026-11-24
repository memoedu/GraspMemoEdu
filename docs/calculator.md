# 按题配置计算器

Topic 省略计算器档位时，题目默认开放科学计算器。课程作者可用 `calculate` 设置 Topic 档位，Example 或 Practice 可以覆盖或明确关闭。两级 `disable_modules` 和 `disable_keys` 取并集。独立题库由题组或单题显式开放计算器。

## 材料字段

Topic v2 JSON 的根和 Example、Practice 节点都可写 `calculate`。Markdown 的 `topic-format` 和对应的 `topic-node` 元数据采用同一字段。题库 JSON 在题组和题目对象上使用相同字段。档位可以用字符串简写，也可以与模块、按键配置一起写成对象。

```json
{
  "calculate": {
    "level": "advanced",
    "enable_modules": ["modular", "machine_learning"],
    "disable_modules": ["probability"],
    "disable_keys": ["matrix_inverse", "sin"]
  }
}
```

- `none` 或 `null` 明确关闭。只配置禁用项时沿用当前默认档位。
- `basic` 提供算术、乘方、根式、绝对值和对数。
- `scientific` 增加三角及反三角函数、角度制、双曲函数、阶乘、排列组合、复数、科学记数法和常数。可单独加开 `graph`。
- `advanced` 增加函数绘图、数值定积分、矩阵、概率分布和统计回归。
- `cas` 再增加化简、符号求导、不定积分和解方程。
- `advanced` 和 `cas` 可通过 `enable_modules` 加开 `modular`、`machine_learning`、`physics`、`chemistry`、`signal`、`programmer`、`astronomy`、`geography`、`finance`、`optimization` 或 `ecology`。单题显式设置档位时，用该题配置的加开模块。

模块 ID 和运算 ID 见 [站内工具目录](../web/calculator-policy.js)。例如 `matrix` 是模块，`matrix_inverse` 是其中一个操作，`sin` 是科学键。禁用项会同时作用于工具入口和计算引擎。手输及粘贴表达式会检查允许的运算、别名、符号和常数。切题会清空该次计算会话。

Math Academy 的 Machine Learning I、II，以及今后导入且源课程名以 `Machine Learning` 开头的同系列课程，开放 CAS 档和全部计算器模块。Topic 和单题的档位、禁用模块及禁用按键均不限制这些题目。阅读、学习和复习按同一个 Topic 使用此权限，共享 Topic 在各入口沿用同一配置。权限在读取课程目录时投影，无需重导现有 Topic。

其余 MA 材料默认至少开放科学计算器。来源的 `None` 和 `Standard` 档位不参与计算器定档，`Scientific` 继续开放科学计算，`Graphing` 继续开放科学计算和独立函数绘图。更高档位及原有模块、按键限制继续有效。来源字段缺失或移除时同样适用。系统仍读取历史提示以识别档位，题面会隐藏自动生成的计算器提示。

对于按题定档的 MA 材料，站内可在 Topic 或单题使用 `"calculate": {"level": "none", "override_ma_minimum": true}`，也可将档位设为 `basic`。Topic 例外覆盖 MA 原题的档位，单题带同一标记可覆盖 Topic 例外。MA 来源字段不能写入该标记。

## 计算范围

题目工具位于题目卡片右栏。科学计算器是主要入口。函数绘图、统计与回归、解方程、求导和不定积分使用独立面板。机器学习的分类指标与主成分分析也保留独立面板，以展示混淆矩阵或投影结果。每道题只显示获准的入口。如果题目关闭了表达式计算，其他已获准的运算保留独立入口。点击图标可打开面板，也可以用方向键浏览图标、按 Enter 打开，关闭后焦点回到原图标。

科学计算器下方的「更多科学函数」默认折叠。展开后默认显示「一元函数」，可切换到「多元函数」或当前题目开放的专业类别。点按函数可在光标处插入，也可直接键入 `sinh(1)`、`cosh(0)` 或 `round(1.234, 2)`。专业函数支持 `2*sigmoid(-1)`、`cross_entropy([1000,1001,1002],3)`、`determinant([[1,2],[3,4]])` 等写法。向量使用 `[1,2,3]`，矩阵使用 `[[1,2],[3,4]]`，数值及数组结果可用 `Ans` 继续参与计算。需要输入数据网格、单位或线性规划模型时，可在相应类别使用表单。函数目录参考 [NumWorks 的分类工具箱](https://www.numworks.com/manual/calculation/)，表达式语法复用 [Math.js](https://mathjs.org/docs/expressions/syntax.html)。

「化简」位于「复制」旁，用 Nerdamer 将当前算式化简并把结果显示在原面板。例如 `2*x+3*x+y-y` 化简为 `5*x`。点「精确模幂」会显示模数框，使用原表达式和正整数模数计算余数。大整数结果可以精确复制，安全整数范围内的余数也可储值或用 `Ans` 调用。题目原有的档位、模块和按键设置仍同时用于界面与计算引擎。

表达式框可直接键入，也可用同一面板按键编辑。矩阵、数列和线性规划模型提供结构化编辑和文本输入，两个视图共用当前值。常数、单位、日期、进制和运算类型可用选择控件输入。每道题的计算历史只保留在该题的临时面板中。

指数形式的单个数值旁会显示 `↻`（结果格式，FORMAT）。点击可将 `1.2e+24` 展开为 `1200000000000000000000000`，再点一次切回。两种格式使用同样的答案字号和字距，过长的十进制数字会换行。新结果沿用自动显示，计算精度与答题填入值保持原样。可按题通过 `disable_keys: ["result_notation"]` 禁用。符号参考[卡西欧 FORMAT 手册](https://support.casio.com/global/en/calc/manual/fx-991CW%2BUK_en/changing_calculation_result_format/changing_the_display_format_calc_results.html)。

点击「转换」把当前结果填入原题，计算器保持打开。多空题可连续计算并从第一空依次填写，也可点选题中空位固定目标。多值选项先逐个点击「记录」，最后一次计算后点击「转换」。计算器会列出已记录的值，转换失败时可以撤回末值后重试。操作示例见[答题转换](answer-conversion.md)。

点击 `logₐ` 插入 `log_`，再输入底数和括号中的真数。例如 `log_2(8)` 得到 3。键盘也接受 `log₂(8)`、`log(8, 2)` 和以花括号包住底数表达式的写法，如 `log_{1+2}(27)`。`ln(8)` 和 `log(8)` 为自然对数，`log10(8)` 为常用对数。按题禁用任意底数对数可使用 `disable_keys: ["log_base"]`。

从首个匹配字符开始显示候选。例如输入 `f` 即可看到 `floor`。按 Tab 补全当前候选，或用 ↑、↓ 选择后按 Enter。直接按 Enter 仍会执行原输入框的动作。计算器候选遵循当前档位与按键权限。学习、复习、题库回答及答疑、反馈等文本框也可插入计算用词。设置中的「自动补全」提供「计算器」「回答」「其他」三个独立开关，默认全开并保存在当前浏览器。

科学档及以上可以为当前表达式填写临时变量值。输入 `2x+y` 后点击「变量值」，原式下方会列出未储存的变量。输入框支持实体和屏幕键盘。多个字母相乘可写成 `x*y`，`xy` 视为一个变量名。此功能可用 `disable_keys: ["assign_variables"]` 关闭。

四档表达式面板都支持储存。点「储存」打开字母键盘，同时在 `→` 后聚焦变量名输入框。可点 `A–F` 快捷储存，或输入名称后点「保存」或按 Enter。直接在表达式框输入 `α=5`、`x_1=8` 也可储存。`A += 1`、`A -= 1`、`A *= 2`、`A /= 2` 和 `A ^= 2` 会更新已有数值，其中 `^=` 沿用计算器的乘方语义。`==`、`!=`、`<`、`<=`、`>` 和 `>=` 返回数值 `1` 或 `0`，可继续参与运算或储存。表达式接受中文括号和逗号，并忽略 `\` 与 `$`，例如 `$\sinh（0）$`。

科学档及以上可点「定义函数」，输入 `F = X + 1` 并按等号。计算器会从右侧推断参数，定义完成后回到普通输入，此时 `F(3)` 得到 `4`。推断参数按 ASCII 顺序排列，所以 `G = 10*Y + X` 定义的是 `G(X, Y)`。直接输入 `G(Y, X) = 10*Y + X` 可明确指定参数顺序，无需切换状态。普通输入中的 `F = X + 1` 会读取 `X` 的当前值并储存数值。函数定义和数值共用名称，以最近一次成功赋值或定义为准。参数最多 12 个，显式参数之外可引用已储存的数值。变量名区分大小写，`G` 没有储值或定义时仍表示万有引力常数。可用 `disable_keys: ["define_function"]` 单独关闭自定义函数。

表达式和文本框共用补全菜单。输入 `F` 可补成 `F(`，已定义的函数也会加入候选。`x₁`、`x_1`、`x_{1}` 指向同一变量。在储存名称中，`v^{2}` 对应 `v²`，算式里的 `v^2` 仍表示乘方。点 `RCL` 可调用已存的变量或函数。「复制」把当前结果写入剪贴板。在同一题内重新打开计算器可继续使用本题的储值和函数。

储存后的变量可以直接在表达式或「变量值」输入框中调用。要按题关闭储存与调用，可用 `disable_keys: ["memory_registers"]`。箭头操作参考 [TI 的 STO→](https://education.ti.com/en/customer-support/knowledge-base/ti-83-84-plus-family/product-usage/34428)，调用参考[卡西欧的储值与调用](https://support.casio.com/global/en/calc/manual/fx-991CW%2BUK_en/basic_calculations/using_memory_functions.html)。
普通四则运算和数值储存使用同一套权限，在页面直接完成。科学运算继续用 Worker，输入函数或乘方时会在后台准备数学库。

- 精确模幂支持整数表达式中的括号、加减乘和非负整数乘方。模数为正整数。结果落在 `0` 到 `m−1`，过程用大整数逐步求余。嵌套指数受计算预算限制。
- 数值积分用于有限区间，遇到非有限值或已知不收敛时会提示。CAS 的不定积分在引擎能给出原函数时添加积分常数，求解能力随实际方程而异。
- 概率和数值工具会报告无效参数。分类指标按真实类别为行、预测类别为列展示，未定义的比率显示为「—」。机器学习交叉熵接受 logits 和从 1 开始的正确类别。

## 构建和发布

浏览器数值库、符号库和领域工具按需载入。锁定依赖和入口位于 [calculator-dependencies](../scripts/calculator-dependencies)。更新时将 `package.json` 和 `package-lock.json` 放入独立依赖缓存，使用 `npm ci`，再运行 `node scripts/calculator-dependencies/build.mjs <依赖缓存绝对路径>`。生成资产与许可证在 `web/vendor/calculator`，发布脚本先验证哈希。按现有流程更新网页版本签名、导出静态资源，并同步后端的计算器字段投影。

文本补全复用 [Textcomplete](https://github.com/yuku/textcomplete) 和原生输入框。全站由 `installAutocomplete` 统一接入，新输入框自动获得默认候选，可通过 `setInputCompletions` 指定自己的候选来源。自定义输入区域可用 `data-autocomplete` 声明场景或显式关闭补全。

表达式插入、题内历史和屏幕及按键样式复用自 MIT 授权的 Calc，针对站内题目权限、双语和触屏做了适配。 [Calc 源码](https://github.com/Develifture/scientific-calculator)

面板固定在右侧，窄屏贴右下方，右上角的题目工具栏仍可操作。面板随题目页面加载，点击后即可输入。浏览器只在提交运算或解析待赋值变量时启动计算 Worker。点选计算器输入位置后，可使用工具栏中的麦克风插入算式。详见[语音输入](voice-input.md)。

验收使用 `node --test tests/calculator.test.mjs`、Python 的 `test_calculator.py`，以及 `scripts/calculator_browser_fixture.py` 与 `scripts/calculator_browser_acceptance.mjs` 提供的隔离浏览器样例。
