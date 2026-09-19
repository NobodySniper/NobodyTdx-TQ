"""
webapp/app.py - 宁尚拙回测系统 Web 前端

启动：python -m qq798623backtest.webapp.app
浏览器：http://localhost:5119

流程：前端表单 → 写 config.py → subprocess 跑 backtest → 内嵌展示报告
现有 backtest.py / config.py 核心逻辑零改动。
"""
import os
import re
import sys
import subprocess
import socket

from flask import Flask, render_template, request, jsonify

# ── 路径 ──────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # qq798623backtest/
CONFIG_PATH = os.path.join(BASE_DIR, 'config.py')
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')
PYTHON_EXE = sys.executable  # 当前 Python 解释器

# ── Flask ──────────────────────────────────────────
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
app = Flask(
    __name__,
    template_folder=template_dir,
    static_folder=ASSETS_DIR,       # /assets/... → 项目根目录 assets/
    static_url_path='/assets',
)


# ── 端口自增（5119 起步，被占用自动 +1）──────────────
def find_free_port(start: int = 5119, max_try: int = 100) -> int:
    for port in range(start, start + max_try):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    raise RuntimeError(f'端口 {start}~{start + max_try} 全被占用')


# ── 读 config.py 当前值（正则提取，不 import）────────
def read_config() -> dict:
    """从 config.py 文件中正则提取当前配置值。"""
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        text = f.read()

    result = {}
    # 提取 STRATEGY_KEY 值
    m = re.search(r"^STRATEGY_KEY\s*=\s*'([^']+)'", text, re.M)
    result['STRATEGY_KEY'] = m.group(1) if m else 'ma_cross'

    # 提取简单赋值（不含 STRATEGY_PARAMS）
    for key in ['STOCK_CODE', 'STOCK_NAME', 'TARGET_START', 'TARGET_END',
                'STRATEGY_NAME', 'INIT_CASH', 'COMMISSION_RATE', 'STAMP_TAX_RATE']:
        m = re.search(rf'^{key}\s*=\s*[\'"]?([^\'"#\n]+?)[\'"]?\s*(?:#|$)',
                       text, re.M)
        if m:
            val = m.group(1).strip()
            try:
                val = int(val)
            except ValueError:
                try:
                    val = float(val)
                except ValueError:
                    pass
            result[key] = val
    return result


# ── 写 config.py（正则替换，不覆盖整个文件）──────────
def write_config(form_data: dict):
    """用正则把表单值替换到 config.py 对应行。

    策略参数写到 STRATEGY_PARAMS 字典（整体替换），其他值逐行替换。
    """
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        text = f.read()

    # 拆分：通用配置 vs 策略参数
    general_keys = {'STOCK_CODE', 'STOCK_NAME', 'TARGET_START', 'TARGET_END',
                    'STRATEGY_KEY', 'INIT_CASH', 'COMMISSION_RATE', 'STAMP_TAX_RATE'}
    strategy_params = {k: v for k, v in form_data.items() if k not in general_keys}

    # 逐行替换通用配置
    for key, val in form_data.items():
        if key not in general_keys:
            continue
        if isinstance(val, str):
            replacement = f"{key} = '{val}'"
        else:
            replacement = f"{key} = {val}"
        text = re.sub(
            rf'^{key}\s*=.*$',
            replacement,
            text,
            count=1,
            flags=re.M,
        )

    # 整体替换 STRATEGY_PARAMS 字典（匹配从 STRATEGY_PARAMS = 到 } 的多行块）
    if strategy_params:
        params_str = 'STRATEGY_PARAMS = {\n'
        for k, v in strategy_params.items():
            if isinstance(v, str):
                params_str += f"    '{k}': '{v}',\n"
            else:
                params_str += f"    '{k}': {v},\n"
        params_str += '}'
        text = re.sub(
            r'^STRATEGY_PARAMS\s*=\s*\{[^}]*\}',
            params_str,
            text,
            count=1,
            flags=re.M,
        )

    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        f.write(text)


# ── 找回测开始后生成的最新报告 ─────────────────────
def _find_latest_report(start_ts: float) -> str:
    """扫描 reports/ 目录，返回创建时间晚于 start_ts 的最新 report.html。

    不依赖解析子进程输出文本，避免 Windows 编码问题。
    """
    if not os.path.isdir(REPORTS_DIR):
        return ''
    candidates = []
    for entry in os.listdir(REPORTS_DIR):
        report_file = os.path.join(REPORTS_DIR, entry, 'report.html')
        if os.path.isfile(report_file):
            mtime = os.path.getmtime(report_file)
            if mtime >= start_ts:
                candidates.append((mtime, report_file))
    if not candidates:
        return ''
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


# ── 路由 ──────────────────────────────────────────

@app.route('/')
def index():
    """主页：表单 + 报告展示区。"""
    config = read_config()
    # 读取可用策略列表
    strategies = []
    try:
        from ..strategies import list_strategies
        strategies = list_strategies()
    except Exception:
        strategies = ['ma_cross']
    return render_template('index.html', config=config, strategies=strategies)


@app.route('/api/strategy_params/<key>')
def strategy_params(key):
    """返回指定策略的参数声明（前端动态渲染表单用）。"""
    try:
        from ..strategies import get_strategy_params
        params = get_strategy_params(key)
        return jsonify({'ok': True, 'params': params})
    except Exception as e:
        return jsonify({'ok': False, 'params': [], 'msg': str(e)})


@app.route('/api/run', methods=['POST'])
def run_backtest():
    """接收表单 → 写 config.py → subprocess 跑 backtest → 返回报告路径。

    报告路径不依赖解析子进程输出（避免 Windows 编码问题），
    而是记录开始时间，跑完后扫描 reports/ 目录找最新的 report.html。
    """
    form = request.json

    # 写 config.py
    write_config(form)

    # 记录回测开始时间（用于找最新报告）
    import time
    start_ts = time.time()

    cmd = [PYTHON_EXE, '-m', 'qq798623backtest.backtest']
    cwd = os.path.dirname(BASE_DIR)  # d:\cprogram\tdxTQ\PYPlugins\user

    # 强制 UTF-8 输出（日志展示用，不影响报告路径查找）
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'

    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True,
            timeout=300, encoding='utf-8', errors='replace',
            env=env,
        )
    except subprocess.TimeoutExpired:
        return jsonify({'ok': False, 'msg': '回测超时（5分钟）'})
    except Exception as e:
        return jsonify({'ok': False, 'msg': f'启动失败: {e}'})

    # 日志（仅展示用，errors='replace' 保证不崩）
    output = result.stdout + result.stderr

    # 找回测开始后生成的最新 report.html（不依赖输出文本解析）
    report_html = _find_latest_report(start_ts)

    if report_html:
        report_name = os.path.basename(report_html)
        subdir = os.path.basename(os.path.dirname(report_html))
        return jsonify({
            'ok': True,
            'report_url': f'/report/{subdir}/{report_name}',
            'log': output[-3000:],
        })
    else:
        return jsonify({
            'ok': False,
            'msg': '回测完成但未找到报告文件，请检查通达信客户端是否正常运行',
            'log': output[-3000:],
        })


@app.route('/report/<subdir>/<filename>')
def serve_report(subdir, filename):
    """提供报告文件（HTML / PNG / CSV）。"""
    from flask import send_from_directory
    full_dir = os.path.join(REPORTS_DIR, subdir)
    return send_from_directory(full_dir, filename)


@app.route('/api/open_reports')
def open_reports():
    """在文件管理器中打开 reports 目录。"""
    import subprocess as _sp
    try:
        if not os.path.isdir(REPORTS_DIR):
            os.makedirs(REPORTS_DIR, exist_ok=True)
        if os.name == 'nt':
            _sp.Popen(['explorer', REPORTS_DIR])
        elif sys.platform == 'darwin':
            _sp.Popen(['open', REPORTS_DIR])
        else:
            _sp.Popen(['xdg-open', REPORTS_DIR])
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'msg': str(e)})


if __name__ == '__main__':
    import signal
    import sys

    port = find_free_port(5119)
    print(f'\n  宁尚拙回测系统 V0.0.1')
    print(f'  浏览器打开: http://127.0.0.1:{port}')
    print(f'  按 Ctrl+C 退出\n')

    # 强制退出：确保 Ctrl+C / 关窗口后进程完全终止，端口立即释放
    def _force_exit(*args):
        os._exit(0)

    signal.signal(signal.SIGINT, _force_exit)
    signal.signal(signal.SIGTERM, _force_exit)

    try:
        app.run(host='127.0.0.1', port=port, debug=False, threaded=True)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        os._exit(0)