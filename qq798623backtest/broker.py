"""
broker - A 股佣金方案（印花税仅卖出）

backtrader 默认 CommInfoBase 不支持 A 股印花税单向收取。
这里重写 _get_operation_cost 实现「卖出额外加印花税」。
"""
import backtrader as bt


class AStockCommission(bt.CommInfoBase):
    """A 股佣金方案：买入收佣金，卖出收佣金 + 印花税。"""

    params = (
        ('stocklike', True),
        ('commtype', bt.CommInfoBase.COMM_PERC),    # 按百分比
        ('commission', 0.0001),                    # 佣金万 1
        ('stamp_tax', 0.001),                      # 印花税千 1（仅卖出）
        ('percabs', False),
    )

    def _getcommission(self, size, price, pseudoexec):
        """单边手续费（不含印花税）。"""
        return abs(size) * price * self.p.commission

    def _get_operation_cost(self, operation, size, price):
        """手续费 + 印花税（卖出加印花税）。"""
        cost = self._getcommission(size, price, pseudoexec=False)
        if size < 0:    # 卖出
            cost += abs(size) * price * self.p.stamp_tax
        return cost
