# 宁尚拙回测系统 V0.0.1

> 宁静以虚心，虚心以尚拙，尚拙以胜巧

基于 [backtrader](https://github.com/mementum/backtrader) 的 A 股量化回测系统，数据源为通达信 TQ API。
内置 Web 前端，填写参数 → 一键回测 → 交互式报告，适合量化入门和小白分享。

---

## 功能

- **AI 写策略**：把 [策略编写指南](strategies/新建策略指南.md) 喂给 GPT/Claude，自然语言描述 → 自动生成可运行策略代码，注册即可回测
- **Web 前端**：浏览器填参数 → 一键回测 → 报告内嵌展示
- **交互式 K 线图**：ECharts 渲染，支持缩放/平移/悬停/十字线
- **红涨绿跌**：中国股市习惯配色
- **A 股规则**：佣金万 1（双边）+ 印花税千 1（仅卖出）+ 100 股整手
- **多策略**：MA 金叉死叉 / MACD 金叉死叉，支持自定义策略扩展
- **官方指标**：backtrader 内置 Analyzer（Sharpe / Sortino / Calmar / 最大回撤 / 年度收益等）
- **报告输出**：HTML + 资金曲线 + 回撤曲线 + 月度热力图 + 交易明细 CSV
- **自动中文名**：输入 6 位代码自动补后缀 + 查中文名

## 环境要求

- Python 3.12+
- 通达信量化交易终端（提供 TQ 数据接口，非 pip 包）

## 安装

### 1. 安装通达信量化交易终端

下载并安装 [通达信量化交易终端](https://www.tdx.com.cn/)，安装后会自带 `tqcenter` Python 库。

### 2. 放置项目

项目必须放在通达信的插件目录下才能找到 `tqcenter`：

```
通达信安装目录\
└── PYPlugins\
    └── user\
        └── qq798623backtest\   ← 项目放这里
```

### 3. 安装 Python 依赖

```bash
cd PYPlugins\user\qq798623backtest
pip install -r requirements.txt
```

> `tqcenter` 由通达信客户端提供，不在 pip 中，无需单独安装。

## 使用

### 方式一：Web 前端（推荐）

双击 `start.bat`，浏览器打开 `http://127.0.0.1:5119`：

1. 填写股票代码（6 位数字，如 `603955`）
2. 选择策略（ma_cross / macd_cross）
3. 调整参数（均线周期、资金、费率）
4. 点击「开始回测」
5. 报告自动展示在页面内

### 方式二：命令行

```bash
cd qq798623backtest
python -m qq798623backtest.backtest
```

修改 `config.py` 调整参数：

```python
STOCK_CODE = '603955'       # 6 位数字
STRATEGY_KEY = 'ma_cross'   # 策略
TARGET_START = '20240101'   # 起始日
INIT_CASH = 1000000         # 初始资金
```

## 自定义策略

只需 2 步，无需改其他文件：

1. 在 `strategies/` 下新建 `.py` 文件
2. 在 `strategies/__init__.py` 的 `_registry` 加一行

详见 [策略编写指南](strategies/新建策略指南.md)。

## 项目结构

```
qq798623backtest/
├── start.bat              # 双击启动 Web 前端
├── config.py              # 配置文件（小白改这里）
├── backtest.py            # 回测主入口
├── analyzer.py            # 报告生成（HTML + 图表 + ECharts）
├── broker.py              # A 股佣金 + 印花税
├── sizers.py             # 仓位管理（95% + 100 股整手）
├── data_fetcher.py        # 通达信 TQ 数据拉取
├── strategies/            # 策略目录
│   ├── __init__.py        # 注册中心
│   ├── base.py            # 策略基类
│   ├── ma_cross.py        # MA 金叉死叉
│   ├── macd_cross.py      # MACD 金叉死叉
│   └── 新建策略指南.md     # 大模型友好编写指南
├── webapp/                # Web 前端
│   ├── app.py             # Flask 入口
│   └── templates/
│       └── index.html     # 极光深色主题前端
├── reports/               # 回测报告输出目录
├── logs/                  # 日志目录
├── requirements.txt
└── docs/                  # 文档
```

## 联系

- QQ：798623
- GitHub：https://github.com/NobodySniper
- 哔哩哔哩：https://space.bilibili.com/3546688065112927

## 飞书交流群

欢迎加入宁尚拙回测系统飞书交流群,一起聊量化、提问题、分享策略。

![飞书交流群二维码](qq798623backtest/assets/img/feishu.png)

> 二维码失效请加 QQ 798623 拉你进群。

如需定制策略或功能，请联系作者。

## License

本项目采用自定义许可证(**非 MIT,非 Apache,非 GPL**)。
- 允许个人学习、研究与非商业分享;
- **任何商业用途必须事先获得作者书面授权**;
- 详见 [LICENSE](LICENSE)。

署名:**宁尚拙**
- 主页:https://github.com/NobodySniper
- 哔哩哔哩:https://space.bilibili.com/3546688065112927
- 联系:QQ 798623
