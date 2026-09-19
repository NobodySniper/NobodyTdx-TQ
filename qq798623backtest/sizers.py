"""
sizers - A 股仓位管理

backtrader 内置 sizer 不支持「100 股整手」+「百分比仓位」组合。
这里自定义一个 PercentSizer 的子类，自动按 100 股取整。
"""
import backtrader as bt


class PercentSizerWithLot(bt.sizers.PercentSizer):
    """百分比仓位 + 整 100 股取整。

    用法：
        cerebro.addsizer(PercentSizerWithLot, percents=95, lot=100)
        # 每次买入：用 95% 现金，按当前价格算出股数，再 round 到 100 整手
    """

    params = (
        ('percents', 95),     # 用多少 % 现金买入
        ('lot', 100),          # 整手单位（A 股 100）
    )

    def _getsizing(self, comminfo, cash, data, isbuy):
        # 调父类算出基础股数
        size = super()._getsizing(comminfo, cash, data, isbuy)
        if size <= 0:
            return 0
        lot = self.p.lot
        # 向下取整到 lot 的倍数
        size = (size // lot) * lot
        return size
