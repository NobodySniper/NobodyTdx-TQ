"""
backtest - 回测主入口

用法：
    python -m qq798623backtest.backtest

流程：
    1. 配置日志
    2. TQ 初始化 → 拉 K 线 → 切到回测区间
    3. 转 backtrader feed
    4. 配置 Cerebro（broker + sizer + strategy + observers + analyzers）
    5. 跑回测
    6. 出全套报告 + 写 trades.csv

小白只改 config.py 即可。
"""
import os
import sys
import logging
from logging.handlers import TimedRotatingFileHandler

import backtrader as bt
from tqcenter import tq

from .config import (
    STOCK_CODE, STOCK_NAME, TARGET_START, TARGET_END,
    INIT_CASH, COMMISSION_RATE, STAMP_TAX_RATE,
    STRATEGY_NAME, STRATEGY_PARAMS, LOG_DIR, BASE_DIR,
    RUN_ID,
)
from .data_fetcher import (
    fetch_kline_df, to_backtrader_feed,
    resolve_stock_code, lookup_stock_name,
)
from .broker import AStockCommission
from .sizers import PercentSizerWithLot
from .strategies import get_strategy_class


# ============================================================
# 日志
# ============================================================

def setup_logging() -> logging.Logger:
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger('qq798623backtest')
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    fh = TimedRotatingFileHandler(
        os.path.join(LOG_DIR, 'backtest.log'),
        when='midnight', interval=1, backupCount=30, encoding='utf-8',
    )
    fh.suffix = '%Y%m%d'
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


# ============================================================
# 交易 CSV 导出
# ============================================================

def _save_trades_csv(strat, out_path: str):
    """把每笔完整交易写到 CSV（中文表头）。

    strat.trade_records 由策略类 notify_order 自己收集，结构：
    {
        '开仓日期': str (YYYY-MM-DD),
        '开仓价': float,
        '平仓日期': str (YYYY-MM-DD),
        '平仓价': float,
        '持仓数量': int,
        '毛利盈亏': float,
        '净盈亏': float,
        '是否盈利': '是' / '否',
    }
    """
    import csv as _csv
    fieldnames = ['开仓日期', '开仓价', '平仓日期', '平仓价', '持仓数量',
                  '毛利盈亏', '净盈亏', '是否盈利']
    rows = list(strat.trade_records)
    if not rows:
        return
    with open(out_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = _csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ============================================================
# 分析器
# ============================================================

def _calc_calmar_ratio(rnorm_pct: float, maxdd_pct: float):
    """Calmar 比率 = 年化收益% / 最大回撤%。

    backtrader 内置 Calmar analyzer 把 maxdd 当作 100% 当分母（实际单位是 % 不是小数），
    算出来的比率是正常 Calmar 的 1/100，读起来像 0.002 这种没意义的小数。
    所以这里用两个官方指标（Returns.rnorm + DrawDown.max）直接相除。
    """
    if not maxdd_pct:
        return None
    return round(rnorm_pct / maxdd_pct, 3)


def setup_analyzers(cerebro: bt.Cerebro):
    """装载 backtrader 内置的分析器（不重复造轮子）。"""
    # 日收益率时间序列 → 画资金曲线
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='time_return',
                        timeframe=bt.TimeFrame.Days)
    # 总收益 / 年化收益 / 平均收益 → 直接读，不用自己算
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    # Sharpe 比率（官方实现）
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe',
                        timeframe=bt.TimeFrame.Days, riskfreerate=0.0,
                        annualize=True)
    # 最大回撤（官方实现，含长度/金额等详细字段）
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    # 交易统计（总/胜/亏/盈亏比等）
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    # 按年份的收益率（直接给年度列表）
    cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name='annual')
    # Calmar 比率：backtrader 内置 Calmar 把 maxdd 当 100% 当分母（实现 bug），
    # 直接用 Returns.rnorm / DrawDown.max 自己算（_calc_calmar_ratio）


# ============================================================
# 主流程
# ============================================================

def run():
    logger = setup_logging()
    logger.info('=' * 50)
    logger.info('回测启动')
    logger.info('=' * 50)

    try:
        # 1. 股票代码归一化
        full_code = resolve_stock_code(STOCK_CODE)

        # 2. TQ 初始化（lookup_stock_name 依赖 TQ，必须在 initialize 之后）
        tq.initialize(__file__)

        # 查中文名（config.py 留空则自动查）
        stock_name = STOCK_NAME or lookup_stock_name(full_code) or full_code
        logger.info('股票: %s (%s)', stock_name, full_code)

        # 3. 拉数据
        df_full, df_back = fetch_kline_df(full_code, TARGET_START, TARGET_END)
        if df_full.empty:
            logger.error('拉取数据为空')
            return
        logger.info('数据: 总 %d 根 / 回测区间 %d 根', len(df_full), len(df_back))

        # 4. Cerebro 编排
        cerebro = bt.Cerebro(stdstats=True)

        # 资金
        cerebro.broker.setcash(INIT_CASH)

        # 佣金（含 A 股印花税）
        cerebro.broker.addcommissioninfo(AStockCommission(
            commission=COMMISSION_RATE,
            stamp_tax=STAMP_TAX_RATE,
        ))

        # 仓位：95% 现金买入 + 100 股整手
        cerebro.addsizer(PercentSizerWithLot, percents=95, lot=100)

        # 数据：只喂回测区间（去掉 warmup，避免 2023 等历史年份被算进指标）
        feed = to_backtrader_feed(df_back, name=full_code)
        cerebro.adddata(feed)

        # 策略（动态传参：从 config.STRATEGY_PARAMS 字典读取）
        StrategyCls = get_strategy_class()
        strategy_name = getattr(StrategyCls, '_display_name', '') or STRATEGY_NAME
        logger.info('策略: %s', strategy_name)
        cerebro.addstrategy(StrategyCls, **STRATEGY_PARAMS)

        # 分析器
        setup_analyzers(cerebro)

        # 5. 跑
        logger.info('开始回测...')
        results = cerebro.run()
        strat = results[0]

        # 6. 构建资金曲线
        import pandas as pd
        tr = strat.analyzers.time_return.get_analysis()
        equity_series = pd.Series(tr)
        equity_curve = (1 + equity_series).cumprod() * INIT_CASH
        equity_curve.index = pd.to_datetime(equity_curve.index)

        # 7. 计算指标 + 出报告
        from .analyzer import (
            calc_metrics, plot_equity_curve, plot_drawdown,
            plot_monthly_heatmap, render_html_report,
        )

        # 拼装完整指标字典（HTML 报告用）— 主要用 backtrader 官方 analyzer
        ret = strat.analyzers.returns.get_analysis()
        drawdown = strat.analyzers.drawdown.get_analysis()
        trade_an = strat.analyzers.trades.get_analysis()
        calmar = strat.analyzers.calmar.get_analysis() if hasattr(strat.analyzers, 'calmar') else {}
        local_metrics = calc_metrics(equity_curve, INIT_CASH)   # 提供 Sortino + 交易日数

        metrics = dict(local_metrics)     # 拷贝过来（含初始资金 / 最终权益 / Sortino / 交易日数）
        metrics['总收益率%'] = round(ret.get('rtot', 0) * 100, 2)
        metrics['CAGR年化%'] = round(ret.get('rnorm', 0) * 100, 2)
        metrics['最大回撤%'] = round(drawdown.get('max', {}).get('drawdown', 0), 2)
        sharpe = strat.analyzers.sharpe.get_analysis().get('sharperatio')
        metrics['夏普比率'] = round(sharpe, 3) if sharpe == sharpe else None
        metrics['Calmar比率'] = _calc_calmar_ratio(
            ret.get('rnorm', 0) * 100, drawdown.get('max', {}).get('drawdown', 0))
        # 交易统计（交易次数 / 盈利次数 / 胜率）
        closed_n = trade_an.get('total', {}).get('closed', 0) if trade_an else 0
        won_n = trade_an.get('won', {}).get('total', 0) if trade_an else 0
        metrics['交易次数'] = closed_n
        metrics['盈利次数'] = won_n
        metrics['胜率'] = round(won_n / closed_n * 100, 2) if closed_n else None

        reports_dir = os.path.join(BASE_DIR, 'reports')
        # 每次回测独立子目录：reports/{代码}_{启动时间}/
        subdir_name = f"{full_code.replace('.', '_')}_{RUN_ID}"
        run_reports_dir = os.path.join(reports_dir, subdir_name)
        os.makedirs(run_reports_dir, exist_ok=True)

        equity_png = os.path.join(run_reports_dir, 'equity_curve.png')
        dd_png = os.path.join(run_reports_dir, 'drawdown.png')
        heatmap_png = os.path.join(run_reports_dir, 'monthly_heatmap.png')
        kline_png = os.path.join(run_reports_dir, 'kline_signals.png')
        html_path = os.path.join(run_reports_dir, 'report.html')
        trades_csv = os.path.join(run_reports_dir, 'trades.csv')

        try:
            from .analyzer import plot_kline_with_signals, generate_kline_echarts_data
            plot_equity_curve(equity_curve, equity_png, INIT_CASH)
            plot_drawdown(equity_curve, dd_png)
            plot_monthly_heatmap(equity_curve, heatmap_png)
            plot_kline_with_signals(df_back, strat.trade_records, kline_png,
                                    stock_name=stock_name,
                                    ma_fast=STRATEGY_PARAMS.get('fast_period', 10),
                                    ma_slow=STRATEGY_PARAMS.get('slow_period', 20))
            kline_json = generate_kline_echarts_data(
                df_back, strat.trade_records,
                stock_name=stock_name,
                ma_fast=STRATEGY_PARAMS.get('fast_period', 10),
                ma_slow=STRATEGY_PARAMS.get('slow_period', 20))
            _save_trades_csv(strat, trades_csv)
            render_html_report(
                metrics=metrics,
                title=f"{stock_name} {strategy_name}",
                stock_code=full_code,
                stock_name=stock_name,
                strategy_name=strategy_name,
                equity_png=equity_png,
                dd_png=dd_png,
                heatmap_png=heatmap_png,
                trades_csv=trades_csv,
                out_path=html_path,
                kline_png=kline_png,
                trade_records=strat.trade_records,
                kline_data_json=kline_json,
            )
        except Exception as e:
            logger.warning('生成图表/HTML 报告失败: %s', e)

        # 8. 控制台打印简洁指标（用官方 analyzer 数据）
        ret = strat.analyzers.returns.get_analysis()
        drawdown = strat.analyzers.drawdown.get_analysis()
        trade_an = strat.analyzers.trades.get_analysis()
        annual = strat.analyzers.annual.get_analysis()

        total_ret_pct = ret.get('rtot', 0) * 100
        annual_ret_pct = ret.get('rnorm', 0) * 100     # annualized return
        max_dd_pct = drawdown.get('max', {}).get('drawdown', 0)
        calmar_ratio = _calc_calmar_ratio(annual_ret_pct, max_dd_pct)

        closed = trade_an.get('total', {}).get('closed', 0) if trade_an else 0
        wins = trade_an.get('won', {}).get('total', 0) if trade_an else 0
        win_rate = (wins / closed * 100) if closed else 0

        print('\n' + '=' * 60)
        print(f'  回测报告  {strategy_name} | {stock_name} ({full_code})')
        print('=' * 60)
        print(f'  初始资金        : {INIT_CASH:>14,.2f}')
        print(f'  最终权益        : {cerebro.broker.getvalue():>14,.2f}')
        print(f'  总收益率        : {total_ret_pct:>14.2f} %  (Returns.rtot)')
        print(f'  CAGR年化        : {annual_ret_pct:>14.2f} %  (Returns.rnorm)')
        print(f'  最大回撤        : {max_dd_pct:>14.2f} %  (DrawDown.max)')
        print(f'  Sharpe比率      : {metrics.get("夏普比率") or "N/A":>14}  (SharpeRatio)')
        print(f'  Sortino比率     : {metrics.get("Sortino比率") or "N/A":>14}')
        print(f'  Calmar比率      : {calmar_ratio if calmar_ratio is not None else "N/A":>14}  (CAGR/MaxDD)')
        print(f'  交易次数        : {closed:>14d}')
        print(f'  盈利次数        : {wins:>14d}')
        print(f'  胜率            : {win_rate:>14.2f} %')
        print(f'  交易日数        : {metrics.get("交易日数", 0):>14d}')
        print('-' * 60)
        print('  年度收益率（AnnualReturn）:')
        for year, pct in annual.items():
            print(f'    {year}: {pct * 100:>+8.2f} %')
        print('=' * 60)
        print(f'  详细图表报告: {html_path}')
        print('=' * 60 + '\n')

        logger.info('回测完成: 总收益 %.2f%%, 最大回撤 %.2f%%, 夏普 %s, Sortino %s, Calmar %s',
                    total_ret_pct, max_dd_pct,
                    metrics.get('夏普比率'), metrics.get('Sortino比率'),
                    calmar_ratio)

        # 9. 推送 TQ
        try:
            tq.send_message(
                f'[回测完成] {stock_name}({full_code}) '
                f'{strategy_name} | 总收益 {total_ret_pct:.2f}%'
            )
        except Exception as e:
            logger.warning('send_message 失败: %s', e)

    except Exception as e:
        logger.exception('回测异常: %s', e)
    finally:
        try:
            tq.close()
        except Exception:
            pass


if __name__ == '__main__':
    run()
