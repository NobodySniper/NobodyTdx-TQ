"""
analyzer - 回测报告生成器

在 backtrader 自带 Analyzer 基础上，生成更专业的报告：
- Sortino / CAGR 等进阶指标
- 资金曲线 PNG
- 回撤曲线 PNG
- 月度收益热力图 PNG
- 简单 HTML 报告

输出到 reports/ 子目录下。
"""
import os
import json
from datetime import datetime
from typing import Dict, List

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use('Agg')    # 无 GUI 后端，生成 PNG 文件
import matplotlib.pyplot as plt


# 中文字体（Windows 系统自带的 SimHei）
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False


# ============================================================
# 进阶指标计算（仅 Sortino，backtrader 官方没提供）
# ============================================================

def calc_sortino(returns: pd.Series, rf: float = 0.0, periods_per_year: int = 252) -> float:
    """年化 Sortino 比率（只算下行波动）。

    注意：Sharpe/CAGR/最大回撤/Calmar/年化收益 等其他指标全部由 backtrader 官方 Analyzer 提供，
    本函数只补 Sortino（官方没有）。
    """
    neg = returns.copy()
    neg[neg > 0] = 0
    neg_std = neg.std()
    if neg_std == 0 or np.isnan(neg_std):
        return float('nan')
    return float((returns.mean() - rf / periods_per_year) / neg_std * np.sqrt(periods_per_year))


def calc_metrics(equity: pd.Series, init_cash: float) -> Dict[str, float]:
    """计算 Sortino 比率和图表所需的辅助指标。

    其它指标（总收益、年化收益、夏普、回撤、Calmar）由 backtrader 官方 analyzer 直接给出，
    本函数不再重复造轮子。

    Args:
        equity: 资金曲线 Series (index=datetime, value=总资产)
        init_cash: 初始资金

    Returns:
        指标字典（仅含 backtrader 不提供的：Sortino + 交易日数 + 最终权益）
    """
    if equity.empty:
        return {}

    returns = equity.pct_change().fillna(0.0)
    final_value = float(equity.iloc[-1])

    return {
        '初始资金': round(init_cash, 2),
        '最终权益': round(final_value, 2),
        'Sortino比率': round(calc_sortino(returns), 3) if not np.isnan(calc_sortino(returns)) else None,
        '交易日数': len(equity),
    }


# ============================================================
# 图表生成
# ============================================================

def _glow(color: str, linewidth: int = 3):
    """发光效果：用透明粗描边模拟光晕。"""
    from matplotlib.patheffects import withStroke
    return [withStroke(linewidth=linewidth + 4, foreground=color, alpha=0.2),
            withStroke(linewidth=linewidth, foreground=color, alpha=0.45)]


def plot_equity_curve(equity: pd.Series, out_path: str, init_cash: float):
    """绘制资金曲线 + 基准（暗色主题，配深蓝渐变填充）。"""
    fig, ax = plt.subplots(figsize=(14, 5.5))
    fig.patch.set_facecolor('#0f1117')
    ax.set_facecolor('#0f1117')

    ax.plot(equity.index, equity.values, linewidth=2, color='#4f8cff', label='策略资金',
            path_effects=_glow('#4f8cff', 3))
    ax.axhline(init_cash, color='#8b8f9a', linestyle='--', linewidth=1, alpha=0.7, label='初始资金')
    ax.fill_between(equity.index, equity.values, init_cash,
                    where=equity.values >= init_cash, color='#22c55e', alpha=0.15)
    ax.fill_between(equity.index, equity.values, init_cash,
                    where=equity.values < init_cash, color='#ef4444', alpha=0.15)

    ax.set_title('资金曲线', fontsize=16, color='#eef1f8', fontweight='bold', pad=12)
    ax.set_xlabel('日期', color='#7c8194')
    ax.set_ylabel('权益（元）', color='#7c8194')
    ax.tick_params(colors='#7c8194')
    ax.legend(loc='upper left', facecolor='#1a1d28', edgecolor=(1,1,1,0.08),
              labelcolor='#eef1f8')
    ax.grid(True, alpha=0.08, color='white')
    for spine in ax.spines.values():
        spine.set_color((1,1,1,0.1))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x/10000:.0f}万'))
    fig.tight_layout()
    fig.savefig(out_path, dpi=140, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)


def plot_drawdown(equity: pd.Series, out_path: str):
    """绘制回撤曲线（暗色主题）。"""
    fig, ax = plt.subplots(figsize=(14, 3.2))
    fig.patch.set_facecolor('#0f1117')
    ax.set_facecolor('#0f1117')

    roll_max = equity.cummax()
    drawdown = (equity - roll_max) / roll_max * 100
    ax.fill_between(equity.index, drawdown.values, 0, color='#ef4444', alpha=0.35,
                    linewidth=0)
    ax.plot(equity.index, drawdown.values, linewidth=1.2, color='#f87171', alpha=0.9)

    ax.set_title('回撤曲线', fontsize=14, color='#eef1f8', fontweight='bold', pad=10)
    ax.set_xlabel('日期', color='#7c8194')
    ax.set_ylabel('回撤 (%)', color='#7c8194')
    ax.tick_params(colors='#7c8194')
    ax.grid(True, alpha=0.08, color='white')
    for spine in ax.spines.values():
        spine.set_color((1,1,1,0.1))
    ax.set_ylim(bottom=min(drawdown.min() * 1.1, -1), top=0)  # 回撤方向向下
    fig.tight_layout()
    fig.savefig(out_path, dpi=140, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)


def plot_monthly_heatmap(equity: pd.Series, out_path: str):
    """绘制月度收益热力图（暗色主题，红蓝渐变）。"""
    returns = equity.pct_change().dropna()
    if returns.empty:
        fig, ax = plt.subplots(figsize=(10, 3))
        fig.patch.set_facecolor('#0f1117')
        ax.set_facecolor('#0f1117')
        ax.text(0.5, 0.5, '数据不足，无法生成月度热力图', ha='center', va='center',
                color='#7c8194', fontsize=12)
        ax.axis('off')
        fig.savefig(out_path, dpi=100, facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close(fig)
        return

    df = pd.DataFrame({'ret': returns})
    df['year'] = df.index.year
    df['month'] = df.index.month
    pivot = df.pivot_table(index='year', columns='month', values='ret', aggfunc='sum').fillna(0)
    pivot = pivot.reindex(columns=range(1, 13), fill_value=0)

    fig, ax = plt.subplots(figsize=(11, max(2.5, len(pivot) * 0.5)))
    fig.patch.set_facecolor('#0f1117')
    ax.set_facecolor('#0f1117')

    arr = pivot.values
    m = float(np.nanmax(np.abs(arr))) if arr.size else 1e-12
    if m == 0:
        m = 1e-12
    im = ax.imshow(arr, aspect='auto', cmap='RdYlBu_r', vmin=-m, vmax=m, alpha=0.9)
    ax.set_xticks(range(12))
    ax.set_xticklabels(range(1, 13), color='#7c8194')
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, color='#eef1f8')

    # 单元格内标注百分比
    for i in range(len(pivot.index)):
        for j in range(12):
            v = arr[i, j]
            if abs(v) > m * 0.15:  # 只标注显著数值
                ax.text(j, i, f'{v*100:.1f}%', ha='center', va='center',
                        fontsize=8 if len(pivot) > 3 else 9,
                        color='#ffffff' if abs(v) > m * 0.4 else '#e8eaed',
                        fontweight='bold')

    cbar = plt.colorbar(im, ax=ax, label='月度收益')
    cbar.outline.set_edgecolor((1,1,1,0.1))
    cbar.ax.yaxis.set_tick_params(color='#7c8194')
    cbar.ax.tick_params(colors='#7c8194')
    cbar.set_label('月度收益', color='#7c8194')
    ax.set_title('月度收益热力图', fontsize=14, color='#eef1f8', fontweight='bold', pad=10)
    for spine in ax.spines.values():
        spine.set_color((1,1,1,0.1))
    fig.tight_layout()
    fig.savefig(out_path, dpi=140, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)


# ============================================================
# K 线走势图 + 买卖标记
# ============================================================

def plot_kline_with_signals(df, trade_records, out_path: str,
                            stock_name: str = '', ma_fast: int = 10, ma_slow: int = 20):
    """绘制 K 线走势图 + MA 均线 + 买卖点标记。

    Args:
        df: 回测区间 DataFrame，需要 open/high/low/close 列，index 为 datetime。
        trade_records: 策略 trade_records 列表（含开仓日期/开仓价/平仓日期/平仓价）。
        out_path: PNG 输出路径。
        stock_name: 股票中文名（标题用）。
        ma_fast: 快线周期（用于绘制参考均线）。
        ma_slow: 慢线周期。
    """
    import matplotlib.dates as mdates

    fig, ax = plt.subplots(figsize=(14, 6))

    # 确保 index 是 datetime
    plot_df = df.copy()
    if not isinstance(plot_df.index, pd.DatetimeIndex):
        plot_df.index = pd.to_datetime(plot_df.index)

    dates = plot_df.index
    opens = plot_df['open'].values
    highs = plot_df['high'].values
    lows = plot_df['low'].values
    closes = plot_df['close'].values

    # 绘制 K 线（简化版：竖线 + 横线）
    width = 0.6  # bar 宽度（天数比例）
    for i in range(len(plot_df)):
        color = '#26a69a' if closes[i] < opens[i] else '#ef5350'  # 红涨绿跌
        # 影线
        ax.vlines(dates[i], lows[i], highs[i], color=color, linewidth=0.8, alpha=0.8)
        # 实体
        bottom = min(opens[i], closes[i])
        height = abs(closes[i] - opens[i]) or (closes[i] * 0.002)  # 防止十字星高度=0
        ax.bar(dates[i], height, width=width, bottom=bottom,
               color=color, edgecolor=color, alpha=0.85)

    # 绘制 MA 均线
    ma_f = plot_df['close'].rolling(window=ma_fast).mean()
    ma_s = plot_df['close'].rolling(window=ma_slow).mean()
    ax.plot(dates, ma_f.values, color='#42a5f5', linewidth=1.2, label=f'MA{ma_fast}', alpha=0.9)
    ax.plot(dates, ma_s.values, color='#ab47bc', linewidth=1.2, label=f'MA{ma_slow}', alpha=0.9)

    # 买卖标记
    for rec in trade_records:
        # 买入点（开仓）
        entry_date = pd.to_datetime(rec['开仓日期'])
        entry_price = rec['开仓价']
        ax.annotate('B', xy=(entry_date, entry_price * 0.94),
                    fontsize=9, fontweight='bold', color='#ef5350',
                    ha='center', va='top')
        ax.scatter(entry_date, entry_price, marker='^', s=80, color='#ef5350',
                   zorder=5, edgecolors='white', linewidths=0.8)

        # 卖出点（平仓）
        exit_date = pd.to_datetime(rec['平仓日期'])
        exit_price = rec['平仓价']
        ax.annotate('S', xy=(exit_date, exit_price * 1.06),
                    fontsize=9, fontweight='bold', color='#26a69a',
                    ha='center', va='bottom')
        ax.scatter(exit_date, exit_price, marker='v', s=80, color='#26a69a',
                   zorder=5, edgecolors='white', linewidths=0.8)

    ax.set_title(f'{stock_name} K线走势与买卖标记', fontsize=14)
    ax.set_xlabel('日期')
    ax.set_ylabel('价格')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.2)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


# ============================================================
# ECharts K 线数据生成（交互式）
# ============================================================

def generate_kline_echarts_data(df, trade_records, stock_name: str = '',
                                ma_fast: int = 10, ma_slow: int = 20) -> str:
    """将 OHLCV + 买卖点转为 ECharts 所需的 JSON 字符串。

    Returns:
        JSON 字符串，可直接嵌入 HTML 的 <script> 中。
    """
    plot_df = df.copy()
    if not isinstance(plot_df.index, pd.DatetimeIndex):
        plot_df.index = pd.to_datetime(plot_df.index)

    # K 线数据：[日期, 开, 收, 低, 高]（ECharts K 线格式）
    kline_data = []
    for dt, row in plot_df.iterrows():
        kline_data.append([
            dt.strftime('%Y-%m-%d'),
            round(float(row['open']), 4),
            round(float(row['close']), 4),
            round(float(row['low']), 4),
            round(float(row['high']), 4),
        ])

    # MA 均线
    ma_f = plot_df['close'].rolling(window=ma_fast).mean()
    ma_s = plot_df['close'].rolling(window=ma_slow).mean()
    ma_f_data = []
    ma_s_data = []
    dates = list(plot_df.index)
    for i, dt in enumerate(dates):
        v_f = ma_f.iloc[i]
        v_s = ma_s.iloc[i]
        ma_f_data.append([dt.strftime('%Y-%m-%d'), round(float(v_f), 4)] if not pd.isna(v_f) else None)
        ma_s_data.append([dt.strftime('%Y-%m-%d'), round(float(v_s), 4)] if not pd.isna(v_s) else None)

    # 买卖标记点（ECharts scatter 系列）
    buy_points = []  # [日期, 价格, 额外信息]
    sell_points = []
    for rec in trade_records:
        buy_points.append([
            rec['开仓日期'],
            round(float(rec['开仓价']), 4),
            f"买入 {rec['持仓数量']:,}股"
        ])
        sell_points.append([
            rec['平仓日期'],
            round(float(rec['平仓价']), 4),
            f"卖出 {rec['持仓数量']:,}股"
        ])

    # 成交量数据
    vol_data = []
    for dt, row in plot_df.iterrows():
        vol_data.append([
            dt.strftime('%Y-%m-%d'),
            int(row.get('volume', 0)) if 'volume' in row else 0,
            bool(row['close'] >= row['open']),  # 涨跌颜色，确保是 python bool
        ])

    result = {
        'stock_name': stock_name,
        'kline': kline_data,
        'ma_fast': {'name': f'MA{ma_fast}', 'data': ma_f_data},
        'ma_slow': {'name': f'MA{ma_slow}', 'data': ma_s_data},
        'buy_points': buy_points,
        'sell_points': sell_points,
        'volume': vol_data,
    }
    return json.dumps(result, ensure_ascii=False, default=str)


# ============================================================
# HTML 报告
# ============================================================

def render_html_report(metrics: Dict[str, float],
                      title: str,
                      stock_code: str,
                      stock_name: str,
                      strategy_name: str,
                      equity_png: str,
                      dd_png: str,
                      heatmap_png: str,
                      trades_csv: str,
                      out_path: str,
                      kline_png: str = '',
                      trade_records: list = None,
                      kline_data_json: str = ''):
    """生成酷炫风格 HTML 报告（极光背景 + 玻璃拟态卡片 + 入场动画 + 渐变光效）。"""
    def fmt(v):
        if v is None:
            return "N/A"
        if isinstance(v, str):
            return v
        if isinstance(v, float) and (v != v):  # NaN
            return "N/A"
        if isinstance(v, float):
            return f"{v:,.4f}" if abs(v) < 100 else f"{v:,.2f}"
        if isinstance(v, int):
            return f"{v:,}"
        return str(v)

    def val_color(v):
        """返回 (显示文本, css 类名)。"""
        if v is None or (isinstance(v, float) and (v != v)):
            return "N/A", 'muted'
        if isinstance(v, (int, float)):
            return fmt(v), 'pos' if v >= 0 else 'neg'
        return str(v), 'muted'

    # 指标分组：核心指标（大卡片）+ 详细指标（小卡片网格）
    core_keys = ['总收益率%', 'CAGR年化%', '最大回撤%', '夏普比率', 'Calmar比率', '胜率']
    core_cards = []
    for i, k in enumerate(core_keys):
        if k not in metrics:
            continue
        v = metrics[k]
        s, cls = val_color(v)
        # 给核心指标加单位
        unit = ''
        if k.endswith('%') or k == '胜率':
            unit = '<span class="unit">%</span>'
        core_cards.append(
            f'<div class="metric-card" style="animation-delay:{0.1 + i * 0.08:.2f}s">'
            f'<div class="metric-label">{k}</div>'
            f'<div class="metric-value {cls}">{s}{unit}</div></div>'
        )
    core_str = "\n".join(core_cards)

    # 剩余指标放小卡片
    detail_cards = []
    for i, (k, v) in enumerate(metrics.items()):
        if k in core_keys:
            continue
        s, cls = val_color(v)
        detail_cards.append(
            f'<div class="detail-card" style="animation-delay:{0.5 + i * 0.05:.2f}s">'
            f'<div class="detail-label">{k}</div>'
            f'<div class="detail-value {cls}">{s}</div></div>'
        )
    detail_str = "\n".join(detail_cards)

    gen_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    equity_img = os.path.basename(equity_png)
    dd_img = os.path.basename(dd_png)
    heat_img = os.path.basename(heatmap_png)
    csv_name = os.path.basename(trades_csv)
    kline_img = os.path.basename(kline_png) if kline_png else ''

    # 交易明细表格行
    trade_rows_html = []
    if trade_records:
        for rec in trade_records:
            pnl = rec.get('净盈亏', 0)
            pnl_cls = 'pos' if pnl >= 0 else 'neg'
            pnl_str = f'{pnl:,.2f}'
            gross = rec.get('毛利盈亏', 0)
            gross_cls = 'pos' if gross >= 0 else 'neg'
            gross_str = f'{gross:,.2f}'
            win_str = rec.get('是否盈利', '')
            win_cls = 'pos' if win_str == '是' else 'neg'
            trade_rows_html.append(
                f'<tr>'
                f'<td>{rec.get("开仓日期","")}</td>'
                f'<td>{rec.get("开仓价",""):,.4f}</td>'
                f'<td>{rec.get("平仓日期","")}</td>'
                f'<td>{rec.get("平仓价",""):,.4f}</td>'
                f'<td>{rec.get("持仓数量",0):,}</td>'
                f'<td class="{gross_cls}">{gross_str}</td>'
                f'<td class="{pnl_cls}">{pnl_str}</td>'
                f'<td class="{win_cls}">{win_str}</td>'
                f'</tr>'
            )
    trade_table_rows = "\n".join(trade_rows_html)

    # K 线图 section（优先交互式 ECharts，否则 PNG）
    if kline_data_json:
        kline_section = (
            '<div class="chart-section">'
            '<div class="chart-title">K线走势与买卖标记（交互式）</div>'
            '<div class="chart-card" id="kline-chart" style="background:#0d1019;height:500px;"></div>'
            '</div>'
        )
    elif kline_img:
        kline_section = (
            f'<div class="chart-section">'
            f'<div class="chart-title">K线走势与买卖标记</div>'
            f'<div class="chart-card">'
            f'<img src="{kline_img}" alt="K线走势与买卖标记">'
            f'</div></div>'
        )
    else:
        kline_section = ''

    # ECharts 初始化脚本（仅在有数据时生成）
    if kline_data_json:
        kline_script = f'''<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<script>
var klineData = {kline_data_json};
var chart = echarts.init(document.getElementById('kline-chart'), 'dark');
var upColor = '#ef5350';   // 红涨（中国股市）
var downColor = '#26a69a';  // 绿跌
var buyColor = '#ef5350';   // 红买
var sellColor = '#26a69a';  // 绿卖

var option = {{
  backgroundColor: 'transparent',
  animation: true,
  tooltip: {{
    trigger: 'axis',
    axisPointer: {{ type: 'cross' }},
    backgroundColor: 'rgba(20,22,35,0.95)',
    borderColor: 'rgba(129,140,248,0.3)',
    borderWidth: 1,
    textStyle: {{ color: '#e8eaed' }},
  }},
  legend: {{
    data: ['日K', klineData.ma_fast.name, klineData.ma_slow.name, '买入', '卖出'],
    textStyle: {{ color: '#8b8f9a' }},
    top: 8,
  }},
  grid: [
    {{ left: '8%', right: '5%', top: '12%', height: '58%' }},
    {{ left: '8%', right: '5%', top: '76%', height: '16%' }},
  ],
  xAxis: [
    {{
      type: 'category',
      data: klineData.kline.map(d => d[0]),
      boundaryGap: false,
      axisLine: {{ lineStyle: {{ color: 'rgba(255,255,255,0.15)' }} }},
      axisLabel: {{ color: '#7c8194', fontSize: 10 }},
      splitLine: {{ show: false }},
    }},
    {{
      type: 'category',
      gridIndex: 1,
      data: klineData.kline.map(d => d[0]),
      boundaryGap: false,
      axisLine: {{ lineStyle: {{ color: 'rgba(255,255,255,0.15)' }} }},
      axisLabel: {{ show: false }},
    }},
  ],
  yAxis: [
    {{
      scale: true,
      splitLine: {{ lineStyle: {{ color: 'rgba(255,255,255,0.05)' }} }},
      axisLabel: {{ color: '#7c8194', fontSize: 10 }},
    }},
    {{
      gridIndex: 1,
      splitNumber: 2,
      axisLabel: {{ color: '#7c8194', fontSize: 9 }},
      splitLine: {{ lineStyle: {{ color: 'rgba(255,255,255,0.05)' }} }},
    }},
  ],
  dataZoom: [
    {{ type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 }},
    {{ type: 'slider', xAxisIndex: [0, 1], bottom: '2%', height: 18, borderColor: 'rgba(255,255,255,0.1)', textStyle: {{ color: '#7c8194' }} }},
  ],
  series: [
    {{
      name: '日K',
      type: 'candlestick',
      data: klineData.kline.map(d => [d[1], d[2], d[3], d[4]]),
      itemStyle: {{
        color: upColor, color0: downColor,
        borderColor: upColor, borderColor0: downColor,
      }},
    }},
    {{
      name: klineData.ma_fast.name,
      type: 'line',
      data: klineData.ma_fast.data.map(d => d ? d[1] : null),
      smooth: true,
      showSymbol: false,
      lineStyle: {{ color: '#42a5f5', width: 1.5 }},
    }},
    {{
      name: klineData.ma_slow.name,
      type: 'line',
      data: klineData.ma_slow.data.map(d => d ? d[1] : null),
      smooth: true,
      showSymbol: false,
      lineStyle: {{ color: '#ab47bc', width: 1.5 }},
    }},
    {{
      name: '买入',
      type: 'scatter',
      data: klineData.buy_points.map(p => [p[0], p[1]]),
      symbol: 'triangle',
      symbolSize: 20,
      symbolOffset: [0, 12],
      itemStyle: {{ color: buyColor, borderColor: '#fff', borderWidth: 1.5 }},
      zlevel: 1,
      tooltip: {{ formatter: function(p) {{ return p.data[2] || ('买入 ' + p.value[1]); }} }},
    }},
    {{
      name: '卖出',
      type: 'scatter',
      data: klineData.sell_points.map(p => [p[0], p[1]]),
      symbol: 'triangle',
      symbolSize: 20,
      symbolOffset: [0, -12],
      symbolRotate: 180,
      itemStyle: {{ color: sellColor, borderColor: '#fff', borderWidth: 1.5 }},
      zlevel: 1,
    }},
    {{
      name: '成交量',
      type: 'bar',
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: klineData.volume.map(v => ({{
        value: v[1],
        itemStyle: {{ color: v[2] ? upColor : downColor, opacity: 0.6 }},
      }})),
    }},
  ],
}};
chart.setOption(option);
window.addEventListener('resize', function() {{ chart.resize(); }});
</script>'''
    else:
        kline_script = ''

    # 用 Jinja2 渲染 report.html（与首页共用 _base.html 页头）
    from jinja2 import Environment, FileSystemLoader

    template_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'webapp', 'templates',
    )
    env = Environment(loader=FileSystemLoader(template_dir), autoescape=False)
    template = env.get_template('report.html')

    html = template.render(
        stock_name=stock_name,
        stock_code=stock_code,
        strategy_name=strategy_name,
        gen_time=gen_time,
        core_str=core_str,
        detail_str=detail_str,
        equity_img=equity_img,
        dd_img=dd_img,
        heat_img=heat_img,
        csv_name=csv_name,
        kline_section=kline_section,
        trade_table_rows=trade_table_rows,
        kline_script=kline_script,
    )

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
