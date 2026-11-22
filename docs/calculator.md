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

MA 新导入读取 `calculate` 或旧名 `calculator`，按题保存结构化配置。历史的 `None`、`Standard`、`Scientific`、`Graphing` 分别对应关闭、基础、科学、科学加独立函数绘图。已安装的历史题优先读取旧字段，缺少档位时从自动生成的计算器提示恢复。页面应用权限后移除该提示。MA 的题目和原有学习记录无需重导。

## 计算范围

表达式框可直接键入，也可用同一面板按键编辑。矩阵、数列和线性规划模型提供结构化编辑和文本输入，两个视图共用当前值。常数、单位、日期、进制和运算类型可用选择控件输入。每道题的计算历史只保留在该题的临时面板中。

- 精确模幂支持整数表达式中的括号、加减乘和非负整数乘方。模数为正整数。结果落在 `0` 到 `m−1`，过程用大整数逐步求余。嵌套指数受计算预算限制。
- 数值积分用于有限区间，遇到非有限值或已知不收敛时会提示。CAS 的不定积分在引擎能给出原函数时添加积分常数，求解能力随实际方程而异。
- 概率和数值工具会报告无效参数。分类指标按真实类别为行、预测类别为列展示，未定义的比率显示为「—」。机器学习交叉熵接受 logits 和从 1 开始的正确类别。

## 构建和发布

浏览器数值库、符号库和领域工具按需载入。锁定依赖和入口位于 [calculator-dependencies](../scripts/calculator-dependencies)。更新时将 `package.json` 和 `package-lock.json` 放入独立依赖缓存，使用 `npm ci`，再运行 `node scripts/calculator-dependencies/build.mjs <依赖缓存绝对路径>`。生成资产与许可证在 `web/vendor/calculator`，发布脚本先验证哈希。按现有流程更新网页版本签名、导出静态资源，并同步后端的计算器字段投影。

表达式插入、题内历史和屏幕及按键样式复用自 MIT 授权的 Calc，针对站内题目权限、双语和触屏做了适配。 [Calc 源码](https://github.com/Develifture/scientific-calculator)

验收使用 `node --test tests/calculator.test.mjs`、Python 的 `test_calculator.py`，以及 `scripts/calculator_browser_fixture.py` 与 `scripts/calculator_browser_acceptance.mjs` 提供的隔离浏览器样例。
