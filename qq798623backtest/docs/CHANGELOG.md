# 更新日志

所有版本变更记录。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/)。

---

## [Unreleased]

### 新增

- **飞书交流群**：README 与 GitHub 主页宣传页加入飞书交流群二维码(`assets/img/feishu.png`),二维码失效可加 QQ 798623 拉群
- **自定义许可证**：LICENSE 文件 + README License 段写明商业用途需授权,取代原 MIT

### 变更

- GitHub 主页宣传页(`docs/project_home.md`)页脚 License 标识由 MIT 改为自定义许可证说明

---

## [V0.0.1] - 2026-09-18

### 新增

- **Web 前端**：Flask Web 界面，浏览器填参数 → 一键回测 → 报告内嵌展示
- **交互式 K 线图**：ECharts 渲染，支持缩放/平移/悬停十字线/成交量副图
- **红涨绿跌配色**：中国股市习惯，K 线 + 成交量 + 买卖标记统一
- **极光深色主题**：玻璃拟态卡片 + 入场动画 + 渐变光效
- **双策略**：MA 金叉死叉（ma_cross）+ MACD 金叉死叉（macd_cross）
- **策略注册中心**：`_registry` 字典注册，前端自动列出可用策略
- **策略基类 BaseStrategy**：封装订单通知/交易记录/日志，子类只写 `__init__` + `next`
- **_user_params 声明**：策略自带参数声明，前端自动渲染表单，backtest 自动传参
- **_display_name**：策略自带显示名，报告标题自动切换
- **A 股规则**：印花税千 1（仅卖出）+ 佣金万 1（双边）+ 100 股整手
- **backtrader 官方 Analyzer**：Sharpe / Sortino / Calmar / 最大回撤 / 年度收益 / TradeAnalyzer
- **交易明细表格**：HTML 内嵌交易明细 + CSV 下载
- **资金曲线/回撤曲线/月度热力图**：暗色主题 PNG
- **start.bat**：双击启动，自适应目录，端口 5119 自增
- **策略编写指南**：大模型友好 Markdown，含 YAML 机器可读契约
- **README.md**：使用说明
- **requirements.txt**：依赖列表
- **docs/project_home.md**：GitHub 主页宣传

### 修复

- backtrader trade.size=0 已知 bug：在 notify_order 里用 order.executed 收集交易记录
- Calmar 比率 N/A：backtrader 内置 Calmar 实现有 bug，改用 Returns.rnorm / DrawDown.max 自己算
- 年度收益率 2023=0%：改喂回测区间数据（去掉 warmup）
- matplotlib 日期序列化问题：用 backtrader.utils.num2date
- Windows subprocess 编码问题：不依赖解析子进程输出，用文件时间戳扫描报告
- 端口残留：signal handler + os._exit(0) 强制退出
