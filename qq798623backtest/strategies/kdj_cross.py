"""
kdj_cross - KDJ 金叉死叉策略

KDJ（随机指标）交叉策略：
    K 线上穿 D 线 → 买入（金叉）
    K 线下穿 D 线 → 卖出（死叉）

默认参数 KDJ(9, 3, 3)，与通达信 KDJ 指标一致。
    RSV = (Close - LowestLow) / (HighestHigh - LowestLow) * 100
    K = SMA(RSV, 3)
    D = SMA(K, 3)
    J = 3*K - 2*D
"""
import backtrader as bt
from .base import BaseStrategy


class KdjCrossStrategy(BaseStrategy):
    """KDJ 金叉死叉策略。"""

    params = (
        ('kdj_period', 9),    # RSV 计算周期
        ('k_period', 3),     # K 线平滑周期
        ('d_period', 3),      # D 线平滑周期
    )

    # 暴露给前端的参数（前端自动渲染表单，backtest 自动传参）
    _user_params = [
        {'key': 'kdj_period', 'label': 'RSV周期', 'type': 'int', 'default': 9},
        {'key': 'k_period', 'label': 'K线周期', 'type': 'int', 'default': 3},
        {'key': 'd_period', 'label': 'D线周期', 'type': 'int', 'default': 3},
    ]

    # 策略显示名（报告标题用）
    _display_name = 'KDJ金叉死叉'

    def __init__(self):
        super().__init__()
        # backtrader Stochastic 即 KDJ 的 K/D 计算逻辑
        self.stoch = bt.indicators.Stochastic(
            self.data,
            period=self.p.kdj_period,
            period_dfast=self.p.k_period,
            period_dslow=self.p.d_period,
        )
        # J = 3K - 2D（仅作展示，本策略信号基于 K/D 交叉）
        self.j = 3 * self.stoch.percK - 2 * self.stoch.percD
        # K 上穿 D 为金叉，K 下穿 D 为死叉
        self.cross = bt.indicators.CrossOver(self.stoch.percK, self.stoch.percD)

    def next(self):
        """每根 bar 触发：判断 KDJ 金叉死叉信号。"""
        self.bar_count += 1
        if self.order:
            return
        if not self.position:
            if self.cross[0] > 0:    # 金叉买入
                self.order = self.buy()
        else:
            if self.cross[0] < 0:    # 死叉卖出
                self.order = self.sell()
