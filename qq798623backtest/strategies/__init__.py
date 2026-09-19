"""
strategies - 策略注册中心

新增策略只需两步：
    1. 在当前目录下新建 .py 文件，写一个继承 bt.Strategy 的类
    2. 在下方 _registry 中加一行：'简称': ('文件名', '类名')

config.py 里改 STRATEGY_NAME = '简称' 即可切换策略。
"""
import importlib
from typing import Type


# ── 策略注册表 ──────────────────────────────────────────
# 格式: '简称': ('模块名_不含.py', '策略类名')
_registry = {
    'ma_cross': ('ma_cross', 'MaCrossStrategy'),
    'macd_cross': ('macd_cross', 'MacdCrossStrategy'),
    'kdj_cross': ('kdj_cross', 'KdjCrossStrategy'),
    # 'ma_cross_stop': ('ma_cross_stop', 'MaCrossStopStrategy'),
    # 'turtle': ('turtle', 'TurtleStrategy'),
}


def list_strategies() -> list:
    """返回所有已注册的策略简称列表。"""
    return list(_registry.keys())


def get_strategy_params(name: str = None) -> list:
    """返回策略暴露给前端的参数声明列表。

    Args:
        name: 策略简称，默认取 config.STRATEGY_KEY。

    Returns:
        参数声明列表，如 [{'key': 'fast_period', 'label': '快线周期', ...}]
    """
    cls = get_strategy_class(name)
    return getattr(cls, '_user_params', [])


def get_strategy_class(name: str = None) -> Type:
    """根据注册名加载策略类。

    Args:
        name: 策略简称（如 'ma_cross'），默认取 config.STRATEGY_NAME。

    Returns:
        策略类（bt.Strategy 子类）。
    """
    if name is None:
        from ..config import STRATEGY_KEY
        name = STRATEGY_KEY

    try:
        module_name, class_name = _registry[name]
    except KeyError:
        raise ValueError(
            f"未找到策略 '{name}'，可用策略: {list(_registry.keys())}"
        )

    mod = importlib.import_module(f'.{module_name}', package=__package__)
    return getattr(mod, class_name)