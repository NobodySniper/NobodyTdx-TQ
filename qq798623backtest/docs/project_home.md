<div align="center">

# 宁尚拙回测系统

### A 股量化回测 · Web 前端 · 交互式报告

*宁静以虚心，虚心以尚拙，尚拙以胜巧*

</div>

---

## 这是什么？

一个**开箱即用**的 A 股回测系统：填代码 → 选策略 → 点回测 → 看报告。

不写代码也能回测。报告里有交互式 K 线图、资金曲线、回撤曲线、月度热力图，红涨绿跌，中国股民习惯配色。

### 核心特点

| 特点 | 说明 |
|---|---|
| **AI 写策略** | 把策略编写指南喂给 GPT/Claude，自然语言描述 → 自动生成可运行策略，注册即用 |
| **Web 前端** | 浏览器填参数 → 一键回测 → 报告内嵌展示 |
| **交互式 K 线** | ECharts 渲染，缩放/平移/悬停/十字线，买卖标记 |
| **A 股规则** | 印花税千 1（仅卖出）+ 佣金万 1 + 100 股整手 |
| **多策略** | MA 金叉死叉 / MACD，策略自带参数声明，前端自动渲染 |
| **官方指标** | backtrader Analyzer：Sharpe / Sortino / Calmar / 年度收益 |

### 截图

> 回测报告页面：极光深色主题 + 玻璃拟态卡片 + ECharts 交互 K 线

### 快速开始

```bash
# 1. 安装通达信量化交易终端（提供 tqcenter 数据接口）
# 2. 把项目放到通达信插件目录 PYPlugins\user\ 下
# 3. 安装依赖
cd PYPlugins\user\qq798623backtest
pip install -r requirements.txt
# 4. 双击 start.bat → 浏览器打开 http://127.0.0.1:5119
```

> 需要通达信量化交易终端（提供 TQ 数据接口，非 pip 包）

### 自定义策略

#### AI 写策略（推荐）

把 [策略编写指南](strategies/新建策略指南.md) 喂给任意大模型（GPT / Claude / MiniMax），用自然语言描述你的策略思路，大模型读完指南就能生成符合规范的策略代码，注册即可回测。

策略自带参数声明，前端自动渲染表单，**无需改其他文件**：

```python
class MyStrategy(BaseStrategy):
    params = (('rsi_period', 14),)
    
    _user_params = [
        {'key': 'rsi_period', 'label': 'RSI周期', 'type': 'int', 'default': 14},
    ]
    
    def __init__(self):
        super().__init__()
        self.rsi = bt.indicators.RSI(self.data.close, period=self.p.rsi_period)
    
    def next(self):
        # 你的信号逻辑
        ...
```

详见 [策略编写指南](strategies/新建策略指南.md)。

### 联系

- **QQ**：798623
- **GitHub**：https://github.com/NobodySniper
- **哔哩哔哩**：https://space.bilibili.com/3546688065112927

如需定制策略或功能，请联系作者。

---

<div align="center">

**如果这个项目对你有帮助，欢迎 Star**

*宁尚拙回测系统 V0.0.1 · MIT License*

</div>
