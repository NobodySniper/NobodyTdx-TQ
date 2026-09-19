"""
base - 策略基类

所有策略继承此类，只需实现 __init__（指标）和 next（信号）。
通用逻辑（订单通知、交易记录、日志）由基类统一处理。
"""
import backtrader as bt


class BaseStrategy(bt.Strategy):
    """策略基类：封装订单通知、交易记录、日志等通用功能。

    子类只需在 __init__ 中定义指标，在 next 中发送 buy/sell 信号。
    self.trade_records 自动收集完整交易记录供 CSV 导出。

    子类可通过 _user_params 声明暴露给前端的参数：
        _user_params = [
            {'key': 'fast_period', 'label': '快线周期', 'type': 'int', 'default': 10},
        ]
    前端自动渲染表单，backtest 自动传参，策略作者无需改其他文件。
    """

    # 暴露给前端的参数声明（子类覆盖）
    _user_params = []

    # 策略显示名（子类覆盖，用于报告标题）
    _display_name = ''

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.datetime(0)
        print(f'[{dt}] {txt}')

    def __init__(self):
        self.order = None
        self.bar_count = 0
        # 当前未平仓持仓（持仓时记买入信息）
        self.open_record = None
        # 已平仓的完整交易列表（导出 CSV 用）
        self.trade_records = []

    def notify_order(self, order):
        """订单状态通知：BUY 成交时记 entry，SELL 成交时合并完整交易。"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            side = 'BUY' if order.isbuy() else 'SELL'
            self.log(
                f'{side} EXECUTED price={order.executed.price:.2f} '
                f'size={order.executed.size} '
                f'commission={order.executed.comm:.2f}'
            )

            if order.isbuy():
                # 记录买入信息（持仓期）
                self.open_record = {
                    'entry_date': self.datas[0].datetime.datetime(0),
                    'entry_price': float(order.executed.price),
                    'size': int(order.executed.size),
                    'entry_commission': float(order.executed.comm),
                }
            else:
                # 卖出成交 → 合并成完整交易
                if self.open_record is not None:
                    sell_price = float(order.executed.price)
                    sell_size = int(order.executed.size)
                    sell_comm = float(order.executed.comm)

                    entry = self.open_record
                    # 用 abs 防止卖出 size 为负
                    size = abs(sell_size) if sell_size else abs(entry['size'])
                    gross_pnl = (sell_price - entry['entry_price']) * size
                    net_pnl = gross_pnl - entry['entry_commission'] - sell_comm

                    self.trade_records.append({
                        '开仓日期': entry['entry_date'].date().isoformat()
                            if hasattr(entry['entry_date'], 'date') else str(entry['entry_date'])[:10],
                        '开仓价': round(entry['entry_price'], 4),
                        '平仓日期': self.datas[0].datetime.datetime(0).date().isoformat(),
                        '平仓价': round(sell_price, 4),
                        '持仓数量': size,
                        '毛利盈亏': round(gross_pnl, 2),
                        '净盈亏': round(net_pnl, 2),
                        '是否盈利': '是' if net_pnl > 0 else '否',
                    })
                    self.open_record = None

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'Order {order.Status[order.status]}')
        self.order = None

    def notify_trade(self, trade):
        """交易完成通知（用于控制台日志）。"""
        if trade.isclosed:
            self.log(
                f'TRADE CLOSED gross={trade.pnl:.2f} '
                f'net={trade.pnlcomm:.2f} hold_bars={trade.barlen}'
            )