"""
macd_cross - MACD 金叉死叉策略

MACD（指数平滑异同移动平均线）交叉策略：
    MACD 线上穿信号线 → 买入（金叉）
    MACD 线下穿信号线 → 卖出（死叉）

默认参数 MACD(12, 26, 9)。
"""
import backtrader as bt
from .base import BaseStrategy


class MacdCrossStrategy(BaseStrategy):
    """MACD 金叉死叉策略。"""

    params = (
        ('fast_period', 12),       # 快线 EMA 周期
        ('slow_period', 26),       # 慢线 EMA 周期
        ('signal_period', 9),      # 信号线 EMA 周期
    )

    # 暴露给前端的参数（前端自动渲染表单，backtest 自动传参）
    _user_params = [
        {'key': 'fast_period', 'label': '快线周期', 'type': 'int', 'default': 12},
        {'key': 'slow_period', 'label': '慢线周期', 'type': 'int', 'default': 26},
        {'key': 'signal_period', 'label': '信号线周期', 'type': 'int', 'default': 9},
    ]

    # 策略显示名（报告标题用）
    _display_name = 'MACD金叉死叉'

    def __init__(self):
        super().__init__()
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.p.fast_period,
            period_me2=self.p.slow_period,
            period_signal=self.p.signal_period,
        )
        self.cross = bt.indicators.CrossOver(self.macd.macd, self.macd.signal)

    def next(self):
        """每根 bar 触发：判断 MACD 金叉死叉信号。"""
        self.bar_count += 1
        if self.order:
            return
        if not self.position:
            if self.cross[0] > 0:    # 金叉买入
                self.order = self.buy()
        else:
            if self.cross[0] < 0:    # 死叉卖出
                self.order = self.sell()
