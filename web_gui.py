"""
视频洞察 - Web GUI（像素风暗黑主题）
"""
import os
import threading
import json
from pathlib import Path
from datetime import datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from nicegui import ui
from config import (
    DOWNLOAD_DIR, TRANSCRIPT_DIR, ANALYSIS_DIR,
    PLATFORMS, ASR_ENGINES, ANALYSIS_MODULES
)
from downloader import download, detect_platform
from transcriber import transcribe
from analyzer import analyze


class AppState:
    def __init__(self):
        self.logs = []
        self.is_running = False

state = AppState()

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    state.logs.append(f"[{ts}] {msg}")
    if len(state.logs) > 200:
        state.logs = state.logs[-200:]


# ═══════════════════════════════════════════
# 像素风 CSS（支持中文）
# ═══════════════════════════════════════════

PIXEL_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');

:root {
    --bg: #0a0a1a;
    --bg2: #12122a;
    --brick: #1a1a3e;
    --brick-h: #252555;
    --border: #3a3a6e;
    --green: #00ff88;
    --pink: #ff6b9d;
    --cyan: #4ecdc4;
    --text: #e0e0ff;
    --dim: #8888aa;
}

body {
    background: var(--bg) !important;
    color: var(--text);
    image-rendering: pixelated;
}

/* 英文用像素字体，中文用系统默认 */
.pixel-font {
    font-family: 'Press Start 2P', monospace;
    font-size: 11px;
    letter-spacing: 1px;
}

/* 像素砖块按钮 */
.p-btn {
    background: var(--brick);
    border: 3px solid var(--border);
    border-radius: 0;
    color: var(--text);
    padding: 10px 18px;
    cursor: pointer;
    font-size: 12px;
    box-shadow:
        inset -3px -3px 0 #0d0d25,
        inset 3px 3px 0 #2a2a5e,
        4px 4px 0 #000;
    text-align: center;
    min-width: 80px;
    transition: all 0.1s;
}
.p-btn:hover {
    background: var(--brick-h);
    box-shadow:
        inset -3px -3px 0 #0d0d25,
        inset 3px 3px 0 #3a3a7e,
        4px 4px 0 #000,
        0 0 10px rgba(0,255,136,0.3);
    transform: translate(-1px, -1px);
}
.p-btn:active {
    box-shadow:
        inset 3px 3px 0 #0d0d25,
        inset -3px -3px 0 #2a2a5e,
        1px 1px 0 #000;
    transform: translate(2px, 2px);
}
.p-btn.green { border-color: var(--green); color: var(--green); }
.p-btn.pink  { border-color: var(--pink);  color: var(--pink); }

/* 砖块选项 */
.brick-group {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}
.brick-item {
    background: var(--brick);
    border: 2px solid var(--border);
    padding: 8px 14px;
    cursor: pointer;
    font-size: 12px;
    color: var(--dim);
    box-shadow:
        inset -2px -2px 0 #0d0d25,
        inset 2px 2px 0 #2a2a5e,
        3px 3px 0 #000;
    transition: all 0.1s;
    user-select: none;
}
.brick-item:hover {
    border-color: var(--green);
    color: var(--text);
}
.brick-item.active {
    border-color: var(--green);
    color: var(--green);
    box-shadow:
        inset -2px -2px 0 #0d0d25,
        inset 2px 2px 0 #2a2a5e,
        3px 3px 0 #000,
        0 0 8px rgba(0,255,136,0.25);
}

/* 面板 */
.p-panel {
    background: var(--bg2);
    border: 3px solid var(--border);
    border-radius: 0;
    padding: 18px;
    box-shadow:
        inset -2px -2px 0 #0a0a1a,
        inset 2px 2px 0 #1e1e44,
        6px 6px 0 #000;
}

/* 标题栏 */
.section-title {
    font-size: 14px;
    color: var(--green);
    text-shadow: 0 0 8px rgba(0,255,136,0.4);
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 2px dashed var(--border);
}

/* 表单行：标签 + 输入对齐 */
.form-row {
    display: grid;
    grid-template-columns: 100px 1fr;
    gap: 10px;
    align-items: center;
    margin-bottom: 10px;
}
.form-label {
    font-size: 12px;
    color: var(--dim);
    text-align: right;
}

/* 输入框 */
.q-field__control {
    background: #0d0d25 !important;
    border: 2px solid var(--border) !important;
    border-radius: 0 !important;
}
.q-field__control:before,
.q-field__control:after { display: none !important; }
.q-field__native {
    color: var(--green) !important;
    font-family: 'Microsoft YaHei', monospace !important;
    font-size: 12px !important;
    padding: 6px 10px !important;
}
.q-field__label { color: var(--dim) !important; font-size: 11px !important; }

/* Tab */
.q-tab {
    background: var(--brick) !important;
    border: 2px solid var(--border) !important;
    border-radius: 0 !important;
    color: var(--dim) !important;
    margin-right: 4px !important;
    min-height: 36px !important;
    padding: 0 14px !important;
    box-shadow:
        inset -2px -2px 0 #0d0d25,
        inset 2px 2px 0 #2a2a5e,
        3px 3px 0 #000 !important;
}
.q-tab--active {
    color: var(--green) !important;
    border-color: var(--green) !important;
}
.q-tab__label { font-size: 11px !important; }

/* 分隔线 */
.pixel-hr {
    border: none;
    border-top: 3px dashed var(--border);
    margin: 12px 0;
}

/* 聊天 */
.msg-row { display: flex; margin-bottom: 10px; }
.msg-row.right { justify-content: flex-end; }
.msg-row.left { justify-content: flex-start; }
.msg-bubble {
    max-width: 80%;
    padding: 10px 14px;
    font-size: 12px;
    line-height: 1.8;
}
.msg-user {
    background: #1a1a3e;
    border: 2px solid var(--cyan);
    box-shadow: 3px 3px 0 #000;
}
.msg-bot {
    background: #0d0d25;
    border: 2px solid var(--green);
    box-shadow: 3px 3px 0 #000;
}

/* 进度条 */
.q-linear-progress__track {
    background: #1a1a3e !important;
    border: 2px solid var(--border) !important;
    border-radius: 0 !important;
}
.q-linear-progress__model {
    background: var(--green) !important;
    box-shadow: 0 0 6px rgba(0,255,136,0.5);
}

/* 日志 */
.log-box {
    background: #0d0d25;
    border: 2px solid var(--border);
    padding: 8px 12px;
    font-size: 11px;
    color: #6666aa;
    max-height: 120px;
    overflow-y: auto;
    font-family: 'Microsoft YaHei', monospace;
    line-height: 1.6;
}

/* 扫描线 */
.scanlines::after {
    content: '';
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: repeating-linear-gradient(
        0deg, transparent, transparent 2px,
        rgba(0,0,0,0.08) 2px, rgba(0,0,0,0.08) 4px
    );
    pointer-events: none;
    z-index: 9999;
}

/* 标题 */
.main-title {
    font-family: 'Press Start 2P', monospace;
    font-size: 20px;
    color: var(--green);
    text-shadow: 0 0 12px rgba(0,255,136,0.5);
}
.sub-title {
    font-size: 12px;
    color: var(--dim);
    margin-top: 4px;
}

/* 滚动条 */
::-webkit-scrollbar { width: 8px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); }
"""


# ═══════════════════════════════════════════
# 页面
# ═══════════════════════════════════════════

@ui.page('/')
def main_page():
    ui.add_head_html(f'<style>{PIXEL_CSS}</style>')

    with ui.column().classes('w-full max-w-4xl mx-auto p-6 scanlines'):

        # 标题
        ui.label('VIDEO INSIGHT').classes('main-title')
        ui.label('下载 · 转录 · 分析 · 智能助手').classes('sub-title')

        ui.html('<hr class="pixel-hr">')

        # Tab
        with ui.tabs().classes('w-full mb-4') as tabs:
            ui.tab('下载', icon='download')
            ui.tab('转录', icon='mic')
            ui.tab('分析', icon='analytics')
            ui.tab('全流程', icon='bolt')
            ui.tab('智能助手', icon='smart_toy')

        with ui.tab_panels(tabs, value='下载').classes('w-full'):
            with ui.tab_panel('下载'):
                _build_download()
            with ui.tab_panel('转录'):
                _build_transcribe()
            with ui.tab_panel('分析'):
                _build_analyze()
            with ui.tab_panel('全流程'):
                _build_pipeline()
            with ui.tab_panel('智能助手'):
                _build_agent()

        # 日志
        with ui.card().classes('w-full p-panel mt-4'):
            ui.label('系统日志').classes('section-title')
            log_box = ui.label('').classes('log-box w-full')
            ui.timer(1.0, lambda: log_box.set_text('\n'.join(state.logs[-15:])))


# ── 下载 ──
def _build_download():
    with ui.card().classes('w-full p-panel'):
        ui.label('视频下载').classes('section-title')

        # 平台选择
        platform_val = {'v': 'auto'}
        ui.label('平台').classes('form-label')
        with ui.row().classes('brick-group mb-4'):
            bricks = {}
            opts = {'auto': '自动检测', **{k: v['name'] for k, v in PLATFORMS.items()}}
            for key, label in opts.items():
                def make_h(k=key):
                    def h():
                        platform_val['v'] = k
                        for bk, b in bricks.items():
                            b.classes(remove='active') if bk != k else b.classes(add='active')
                    return h
                b = ui.label(label).classes('brick-item active' if key == 'auto' else 'brick-item')
                b.on('click', make_h())
                bricks[key] = b

        # 表单对齐
        with ui.column().classes('w-full gap-2'):
            with ui.row().classes('form-row w-full'):
                ui.label('链接').classes('form-label')
                url_input = ui.input(placeholder='粘贴视频链接...').classes('w-full')

            with ui.row().classes('form-row w-full'):
                ui.label('保存到').classes('form-label')
                save_dir = ui.input(value=str(DOWNLOAD_DIR)).classes('w-full')

        status = ui.label('> 就绪').classes('text-xs mt-2').style('color: #8888aa')

        async def do_download():
            url = url_input.value.strip()
            if not url:
                ui.notify('请输入链接', type='warning')
                return
            status.set_text('> 下载中...')

            def run():
                try:
                    plat = platform_val['v']
                    result = download(url, platform=plat if plat != 'auto' else None,
                                     save_dir=save_dir.value, callback=log)
                    if result:
                        log(f'下载完成: {Path(result).name}')
                        status.set_text(f'> 完成: {Path(result).name}')
                    else:
                        status.set_text('> 失败')
                except Exception as e:
                    log(f'错误: {e}')
                    status.set_text(f'> 错误: {e}')
            threading.Thread(target=run, daemon=True).start()

        ui.button('开始下载', on_click=do_download, icon='download').classes('p-btn green mt-4')


# ── 转录 ──
def _build_transcribe():
    with ui.card().classes('w-full p-panel'):
        ui.label('语音转录').classes('section-title')

        engine_val = {'v': 'mimo'}
        with ui.row().classes('brick-group mb-4'):
            for key, info in ASR_ENGINES.items():
                def make_h(k=key):
                    def h():
                        engine_val['v'] = k
                        for bk, b in engine_bricks.items():
                            b.classes(remove='active') if bk != k else b.classes(add='active')
                    return h
                b = ui.label(info['name']).classes('brick-item active' if key == 'mimo' else 'brick-item')
                b.on('click', make_h())
                engine_bricks = {key: b}
        # 修复：需要在外层保存引用
        engine_bricks_dict = {}
        # 重写引擎选择
        with ui.row().classes('brick-group mb-4') as engine_row:
            for key, info in ASR_ENGINES.items():
                def make_eh(k=key):
                    def h():
                        engine_val['v'] = k
                        for bk, b in engine_bricks_dict.items():
                            b.classes(remove='active') if bk != k else b.classes(add='active')
                    return h
                b = ui.label(info['name']).classes('brick-item active' if key == 'mimo' else 'brick-item')
                b.on('click', make_eh())
                engine_bricks_dict[key] = b

        with ui.row().classes('form-row w-full'):
            ui.label('视频文件').classes('form-label')
            video_path = ui.input(placeholder='选择视频文件路径...').classes('w-full')

        preview = ui.markdown('*转录结果将显示在这里*').classes('text-xs max-h-48 overflow-auto').style('color: #aaaacc')
        status = ui.label('> 就绪').classes('text-xs').style('color: #8888aa')

        async def do_transcribe():
            vp = video_path.value.strip()
            if not vp or not os.path.exists(vp):
                ui.notify('请选择有效的视频文件', type='warning')
                return
            status.set_text('> 转录中...')

            def run():
                try:
                    text = transcribe(vp, engine=engine_val['v'], callback=log)
                    preview.set_content(text[:3000])
                    status.set_text(f'> 完成: {len(text)} 字')
                    log(f'转录完成: {len(text)} 字')
                except Exception as e:
                    status.set_text(f'> 错误: {e}')
            threading.Thread(target=run, daemon=True).start()

        ui.button('开始转录', on_click=do_transcribe, icon='mic').classes('p-btn green mt-4')


# ── 分析 ──
def _build_analyze():
    with ui.card().classes('w-full p-panel'):
        ui.label('文案分析').classes('section-title')

        with ui.row().classes('form-row w-full'):
            ui.label('文本文件').classes('form-label')
            text_path = ui.input(placeholder='选择文本文件路径...').classes('w-full')

        ui.label('分析模块').classes('form-label mb-2')
        module_switches = {}
        with ui.row().classes('brick-group mb-4'):
            for key, info in ANALYSIS_MODULES.items():
                module_switches[key] = ui.switch(info['name'], value=True).classes('text-xs')

        preview = ui.markdown('*分析结果将显示在这里*').classes('text-xs max-h-48 overflow-auto').style('color: #aaaacc')
        status = ui.label('> 就绪').classes('text-xs').style('color: #8888aa')

        async def do_analyze():
            tp = text_path.value.strip()
            if not tp or not os.path.exists(tp):
                ui.notify('请选择有效的文本文件', type='warning')
                return
            selected = [k for k, v in module_switches.items() if v.value]
            if not selected:
                ui.notify('请至少选择一个模块', type='warning')
                return
            status.set_text('> 分析中...')

            def run():
                try:
                    with open(tp, 'r', encoding='utf-8') as f:
                        text = f.read()
                    results = analyze(text, modules=selected, source_name=tp, callback=log)
                    output = ""
                    for mod, res in results.items():
                        if "error" in res:
                            output += f"**{mod}** 失败: {res['error']}\n\n"
                        else:
                            output += f"**{mod}**\n```json\n{json.dumps(res, ensure_ascii=False, indent=2)[:500]}\n```\n\n"
                    preview.set_content(output)
                    status.set_text('> 完成')
                except Exception as e:
                    status.set_text(f'> 错误: {e}')
            threading.Thread(target=run, daemon=True).start()

        ui.button('开始分析', on_click=do_analyze, icon='analytics').classes('p-btn green mt-4')


# ── 全流程 ──
def _build_pipeline():
    with ui.card().classes('w-full p-panel'):
        ui.label('一键全流程').classes('section-title')
        ui.label('链接 → 下载 → 转录 → 分析 → 生成报告').classes('text-xs mb-4').style('color: #8888aa')

        with ui.row().classes('form-row w-full'):
            ui.label('视频链接').classes('form-label')
            url_input = ui.input(placeholder='粘贴视频链接...').classes('w-full')

        engine_val = {'v': 'mimo'}
        with ui.row().classes('brick-group mb-2'):
            engine_bricks = {}
            for key, info in ASR_ENGINES.items():
                def make_eh(k=key):
                    def h():
                        engine_val['v'] = k
                        for bk, b in engine_bricks.items():
                            b.classes(remove='active') if bk != k else b.classes(add='active')
                    return h
                b = ui.label(info['name']).classes('brick-item active' if key == 'mimo' else 'brick-item')
                b.on('click', make_eh())
                engine_bricks[key] = b

        ui.label('分析模块').classes('form-label mb-2')
        module_switches = {}
        with ui.row().classes('brick-group mb-2'):
            for key, info in ANALYSIS_MODULES.items():
                module_switches[key] = ui.switch(info['name'], value=True).classes('text-xs')

        progress = ui.linear_progress(value=0, show_value=False).classes('w-full mb-2')
        status = ui.label('> 就绪').classes('text-xs').style('color: #8888aa')

        async def do_pipeline():
            url = url_input.value.strip()
            if not url:
                ui.notify('请输入链接', type='warning')
                return
            state.is_running = True

            def run():
                try:
                    status.set_text('[1/3] 下载中...')
                    progress.set_value(0.1)
                    platform = detect_platform(url)
                    log(f'平台: {platform}')
                    video_path = download(url, platform=platform, callback=log)
                    if not video_path:
                        raise Exception('下载失败')
                    progress.set_value(0.33)

                    status.set_text('[2/3] 转录中...')
                    progress.set_value(0.4)
                    text = transcribe(video_path, engine=engine_val['v'], callback=log)
                    log(f'转录完成: {len(text)} 字')
                    progress.set_value(0.66)

                    status.set_text('[3/3] 分析中...')
                    progress.set_value(0.7)
                    mods = [k for k, v in module_switches.items() if v.value]
                    if mods:
                        analyze(text, modules=mods, source_name=video_path, callback=log)
                    progress.set_value(1.0)
                    status.set_text('> 全流程完成')
                    log('全流程完成')
                except Exception as e:
                    status.set_text(f'> 错误: {e}')
                    log(f'错误: {e}')
                finally:
                    state.is_running = False
            threading.Thread(target=run, daemon=True).start()

        ui.button('开始全流程', on_click=do_pipeline, icon='bolt').classes('p-btn green mt-4')


# ── 智能助手 ──
def _build_agent():
    with ui.card().classes('w-full p-panel'):
        ui.label('智能助手').classes('section-title')
        ui.label('告诉我你想做什么，我来帮你完成').classes('text-xs mb-4').style('color: #8888aa')

        chat_box = ui.column().classes('w-full max-h-72 overflow-auto mb-3')

        with chat_box:
            with ui.row().classes('msg-row left w-full'):
                ui.markdown('**助手：** 你好！我可以帮你：\n\n'
                           '- 下载视频（B站/抖音/Twitter/SOOP）\n'
                           '- 转录视频为文字\n'
                           '- 分析文案内容\n\n'
                           '试试说：**帮我下载这个视频并分析内容**').classes('msg-bubble msg-bot')

        with ui.row().classes('w-full gap-2'):
            input_box = ui.input(placeholder='输入你的目标...').classes('flex-grow')

            async def send():
                goal = input_box.value.strip()
                if not goal or state.is_running:
                    return
                input_box.set_value('')
                state.is_running = True

                with chat_box:
                    with ui.row().classes('msg-row right w-full'):
                        ui.label(goal).classes('msg-bubble msg-user')

                with chat_box:
                    with ui.row().classes('msg-row left w-full'):
                        result_label = ui.markdown('**思考中...**').classes('msg-bubble msg-bot')

                def run():
                    try:
                        from agent import run_agent
                        def cb(m):
                            current = result_label.content or ''
                            result_label.set_content(current + f'\n{m}')
                        result = run_agent(goal, callback=cb)
                        result_label.set_content(f'**结果：**\n\n{result}')
                    except Exception as e:
                        result_label.set_content(f'**错误：** {e}')
                    finally:
                        state.is_running = False
                threading.Thread(target=run, daemon=True).start()

            input_box.on('keydown.enter', send)
            ui.button('发送', on_click=send, icon='send').classes('p-btn green')


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title='视频洞察', dark=True, port=8080, reload=False)
