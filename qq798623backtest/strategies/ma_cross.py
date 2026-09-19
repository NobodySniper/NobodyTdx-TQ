"""
ma_cross - MA 金叉死叉策略

双均线交叉策略：
    快线上穿慢线 → 买入（金叉）
    快线下穿慢线 → 卖出（死叉）

默认参数 MA(10) 上穿 MA(20) 买入，下穿卖出。
"""
import backtrader as bt
from .base import BaseStrategy


class MaCrossStrategy(BaseStrategy):
    """双均线金叉死叉策略。"""

    params = (
        ('fast_period', 10),    # 快线周期
        ('slow_period', 20),    # 慢线周期
    )

    # 暴露给前端的参数（前端自动渲染表单，backtest 自动传参）
    _user_params = [
        {'key': 'fast_period', 'label': '快线周期', 'type': 'int', 'default': 10},
        {'key': 'slow_period', 'label': '慢线周期', 'type': 'int', 'default': 20},
    ]

    # 策略显示名（报告标题用）
    _display_name = 'MA金叉死叉'

    def __init__(self):
        super().__init__()
        self.ma_fast = bt.indicators.SMA(self.data.close, period=self.p.fast_period)
        self.ma_slow = bt.indicators.SMA(self.data.close, period=self.p.slow_period)
        self.cross = bt.indicators.CrossOver(self.ma_fast, self.ma_slow)

    def next(self):
        """每根 bar 触发：判断双均线交叉信号。"""
        self.bar_count += 1
        if self.order:
            return
        if not self.position:
            if self.cross[0] > 0:
                self.order = self.buy()
        else:
            if self.cross[0] < 0:
                self.order = self.sell()