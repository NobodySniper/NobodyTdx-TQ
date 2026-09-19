"""
data_fetcher - 从通达信 TQ 拉 K 线 → 转 backtrader feed

数据源层，未来换 tqserver / 本地 csv 只改这里。
"""
import pandas as pd
from datetime import datetime, timedelta

import backtrader as bt
from tqcenter import tq

from .config import STOCK_CODE, TARGET_START, TARGET_END


# ============================================================
# 股票代码归一化（6 位数字 → 完整代码）
# ============================================================

_A_SUFFIX_MAP = {
    '6': '.SH', '9': '.SH',                # 上交所主板 + B 股
    '0': '.SZ', '3': '.SZ', '2': '.SZ',    # 深交所主板/创业板/B 股
    '4': '.BJ', '8': '.BJ',                # 北交所
}


def resolve_stock_code(input_code: str) -> str:
    """'600519' -> '600519.SH'，完整代码原样返回。"""
    if '.' in input_code:
        return input_code.strip().upper()
    code = input_code.strip().zfill(6)
    suffix = _A_SUFFIX_MAP.get(code[0])
    if suffix is None:
        raise ValueError(
            f"无法识别股票代码首位 {code[0]!r}（{input_code}），"
            f"支持的首位: {list(_A_SUFFIX_MAP.keys())}"
        )
    return code + suffix


def lookup_stock_name(code: str) -> str:
    """通过 TQ 查股票中文名（失败返回 code 本身）。"""
    try:
        for item in tq.get_stock_list(market='5', list_type=1):
            if isinstance(item, dict) and item.get('Code') == code:
                return item.get('Name', '') or code
    except Exception:
        pass
    return code


# ============================================================
# 拉数据（不依赖 backtrader，方便复用）
# ============================================================

def fetch_kline_df(code: str, start: str = '', end: str = '',
                   period: str = '1d', warmup_days: int = 30) -> pd.DataFrame:
    """从 TQ 拉历史 K 线，返回 pandas DataFrame。

    Args:
        code: 完整代码如 '600519.SH'
        start/end: 起止日期，YYYYMMDD 格式，end 为空取昨日
        period: K 线周期，默认日线
        warmup_days: 拉数起点前推的天数（用于 MA 等指标 warmup）

    Returns:
        DataFrame: index=日期(DatetimeIndex), columns=[open, high, low, close, volume]
    """
    today = datetime.now()
    if not end:
        end = (today - timedelta(days=1)).strftime('%Y%m%d')
    if not start:
        start = TARGET_START
    actual_start = (pd.to_datetime(start) - timedelta(days=warmup_days + 10)).strftime('%Y%m%d')

    raw = tq.get_market_data(
        field_list=['Close', 'Open', 'High', 'Low', 'Volume'],
        stock_list=[code],
        start_time=actual_start,
        end_time=end,
        dividend_type='front',
        period=period,
        fill_data=True,
    )
    if not raw or raw.get('Close') is None or raw['Close'].empty:
        raise ValueError(
            f"API 返回空 {code} {period} [{actual_start}, {end}]。"
            f"请检查通达信客户端是否已下载该合约的盘后数据。"
        )

    df = pd.DataFrame({
        'open':   raw['Open'][code].astype(float),
        'high':   raw['High'][code].astype(float),
        'low':    raw['Low'][code].astype(float),
        'close':  raw['Close'][code].astype(float),
        'volume': raw['Volume'][code].astype(float),
    })
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    # 截取真实回测区间（去掉 warmup 部分）
    df_back = df.loc[start:]
    return df, df_back


# ============================================================
# backtrader feed 适配
# ============================================================

def to_backtrader_feed(df: pd.DataFrame, name: str = 'stock') -> bt.feeds.PandasData:
    """把 DataFrame 转成 backtrader 可用的 PandasData feed。

    要求 DataFrame 列：open, high, low, close, volume
    """
    feed = bt.feeds.PandasData(
        dataname=df,
        datetime=None,       # 用 index
        open='open', high='high', low='low', close='close', volume='volume',
        openinterest=-1,     # 没有持仓量字段，置 -1
        name=name,
    )
    return feed
