"""
视频洞察 - Web GUI（像素风暗黑主题）
浏览器打开，复古像素风格
"""
import os
import sys
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

# ═══════════════════════════════════════════
# 状态
# ═══════════════════════════════════════════

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
# 像素风 CSS
# ═══════════════════════════════════════════

PIXEL_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');

:root {
    --bg-dark: #0a0a1a;
    --bg-panel: #12122a;
    --bg-brick: #1a1a3e;
    --bg-brick-hover: #252555;
    --border: #3a3a6e;
    --accent: #00ff88;
    --accent2: #ff6b9d;
    --accent3: #4ecdc4;
    --text: #e0e0ff;
    --text-dim: #8888aa;
    --glow: 0 0 10px rgba(0,255,136,0.3);
}

* {
    font-family: 'Press Start 2P', monospace !important;
    font-size: 10px !important;
    letter-spacing: 1px;
}

body {
    background: var(--bg-dark) !important;
    color: var(--text);
    image-rendering: pixelated;
}

/* 像素风砖块按钮 */
.pixel-btn {
    background: var(--bg-brick) !important;
    border: 3px solid var(--border) !important;
    border-radius: 0 !important;
    color: var(--text) !important;
    padding: 12px 20px !important;
    cursor: pointer;
    transition: all 0.1s;
    box-shadow:
        inset -3px -3px 0 #0d0d25,
        inset 3px 3px 0 #2a2a5e,
        4px 4px 0 #000 !important;
    text-transform: uppercase;
    position: relative;
}

.pixel-btn:hover {
    background: var(--bg-brick-hover) !important;
    box-shadow:
        inset -3px -3px 0 #0d0d25,
        inset 3px 3px 0 #3a3a7e,
        4px 4px 0 #000,
        var(--glow) !important;
    transform: translate(-1px, -1px);
}

.pixel-btn:active {
    box-shadow:
        inset 3px 3px 0 #0d0d25,
        inset -3px -3px 0 #2a2a5e,
        1px 1px 0 #000 !important;
    transform: translate(2px, 2px);
}

.pixel-btn.primary {
    border-color: var(--accent) !important;
    color: var(--accent) !important;
    box-shadow:
        inset -3px -3px 0 #004d2a,
        inset 3px 3px 0 #33ffaa,
        4px 4px 0 #000,
        0 0 15px rgba(0,255,136,0.2) !important;
}

.pixel-btn.danger {
    border-color: var(--accent2) !important;
    color: var(--accent2) !important;
}

/* 像素面板 */
.pixel-panel {
    background: var(--bg-panel) !important;
    border: 3px solid var(--border) !important;
    border-radius: 0 !important;
    padding: 16px !important;
    box-shadow:
        inset -2px -2px 0 #0a0a1a,
        inset 2px 2px 0 #1e1e44,
        6px 6px 0 #000 !important;
    margin-bottom: 16px !important;
}

/* 像素输入框 */
.pixel-input input, .pixel-input textarea {
    background: #0d0d25 !important;
    border: 2px solid var(--border) !important;
    border-radius: 0 !important;
    color: var(--accent) !important;
    font-family: 'Press Start 2P', monospace !important;
    padding: 8px 12px !important;
    box-shadow: inset 2px 2px 0 #000 !important;
}

.pixel-input input:focus, .pixel-input textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: inset 2px 2px 0 #000, var(--glow) !important;
}

/* Tab 像素化 */
.q-tab {
    background: var(--bg-brick) !important;
    border: 2px solid var(--border) !important;
    border-radius: 0 !important;
    color: var(--text-dim) !important;
    margin-right: 4px !important;
    box-shadow:
        inset -2px -2px 0 #0d0d25,
        inset 2px 2px 0 #2a2a5e,
        3px 3px 0 #000 !important;
}

.q-tab--active {
    background: var(--bg-brick-hover) !important;
    color: var(--accent) !important;
    border-color: var(--accent) !important;
}

/* 像素滚动条 */
::-webkit-scrollbar { width: 12px; }
::-webkit-scrollbar-track { background: var(--bg-dark); }
::-webkit-scrollbar-thumb {
    background: var(--border);
    border: 2px solid var(--bg-dark);
}

/* 像素开关 */
.q-toggle__track {
    background: #333 !important;
}

/* 发光文字 */
.glow-text {
    color: var(--accent);
    text-shadow: 0 0 10px rgba(0,255,136,0.5);
}

.glow-pink {
    color: var(--accent2);
    text-shadow: 0 0 10px rgba(255,107,157,0.5);
}

/* 像素分隔线 */
.pixel-hr {
    border: none;
    border-top: 3px dashed var(--border);
    margin: 12px 0;
}

/* 砖块容器 */
.brick-row {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}

.brick {
    background: var(--bg-brick);
    border: 2px solid var(--border);
    padding: 10px 16px;
    box-shadow:
        inset -2px -2px 0 #0d0d25,
        inset 2px 2px 0 #2a2a5e,
        3px 3px 0 #000;
    cursor: pointer;
    transition: all 0.1s;
}

.brick:hover, .brick.active {
    border-color: var(--accent);
    box-shadow:
        inset -2px -2px 0 #0d0d25,
        inset 2px 2px 0 #2a2a5e,
        3px 3px 0 #000,
        var(--glow);
}

.brick.active {
    color: var(--accent);
}

/* 扫描线效果 */
.scanlines::after {
    content: '';
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: repeating-linear-gradient(
        0deg,
        transparent,
        transparent 2px,
        rgba(0,0,0,0.1) 2px,
        rgba(0,0,0,0.1) 4px
    );
    pointer-events: none;
    z-index: 9999;
}

/* 聊天消息 */
.msg-user {
    background: #1a1a3e;
    border: 2px solid var(--accent3);
    padding: 10px;
    margin: 8px 0;
    box-shadow: 3px 3px 0 #000;
}

.msg-bot {
    background: #0d0d25;
    border: 2px solid var(--accent);
    padding: 10px;
    margin: 8px 0;
    box-shadow: 3px 3px 0 #000;
}
"""

# ═══════════════════════════════════════════
# 页面
# ═══════════════════════════════════════════

@ui.page('/')
def main_page():
    ui.add_head_html(f'<style>{PIXEL_CSS}</style>')

    with ui.column().classes('w-full max-w-5xl mx-auto p-4 scanlines'):

        # 标题区
        with ui.row().classes('items-center gap-4 mb-2'):
            ui.label('VIDEO INSIGHT').classes('text-2xl glow-text')
        ui.label('// DOWNLOAD * TRANSCRIBE * ANALYZE').classes('text-xs mb-4').style('color: #8888aa')

        # 像素分隔
        ui.html('<hr class="pixel-hr">')

        # Tab 导航
        with ui.tabs().classes('w-full mb-4') as tabs:
            ui.tab('DOWNLOAD', icon='download')
            ui.tab('TRANSCRIBE', icon='mic')
            ui.tab('ANALYZE', icon='analytics')
            ui.tab('PIPELINE', icon='bolt')
            ui.tab('AGENT', icon='smart_toy')

        with ui.tab_panels(tabs, value='DOWNLOAD').classes('w-full'):

            with ui.tab_panel('DOWNLOAD'):
                _build_download_tab()
            with ui.tab_panel('TRANSCRIBE'):
                _build_transcribe_tab()
            with ui.tab_panel('ANALYZE'):
                _build_analyze_tab()
            with ui.tab_panel('PIPELINE'):
                _build_pipeline_tab()
            with ui.tab_panel('AGENT'):
                _build_agent_tab()

        # 日志区
        with ui.card().classes('w-full pixel-panel'):
            ui.label('SYSTEM LOG').classes('text-xs glow-text mb-2')
            log_area = ui.markdown('').classes('text-xs max-h-32 overflow-auto').style('color: #6666aa')
            ui.timer(1.0, lambda: log_area.set_content('\n'.join(f'`{l}`' for l in state.logs[-20:])))


# ── 下载 ──
def _build_download_tab():
    with ui.card().classes('w-full pixel-panel'):
        ui.label('DOWNLOAD VIDEO').classes('text-sm glow-text mb-3')

        # 平台砖块选择
        ui.label('SELECT PLATFORM').classes('text-xs mb-2').style('color: #8888aa')
        platform_val = {'value': 'auto'}

        with ui.row().classes('gap-2 mb-4') as brick_row:
            bricks = {}
            all_opts = {'auto': 'AUTO', **{k: v['name'].upper() for k, v in PLATFORMS.items()}}
            for key, label in all_opts.items():
                def make_handler(k=key):
                    def handler():
                        platform_val['value'] = k
                        for bk, b in bricks.items():
                            b.classes(remove='active') if bk != k else b.classes(add='active')
                    return handler
                b = ui.label(label).classes('brick active' if key == 'auto' else 'brick')
                b.on('click', make_handler())
                bricks[key] = b

        url_input = ui.input(placeholder='PASTE VIDEO URL...').classes('w-full pixel-input')
        save_dir = ui.input(value=str(DOWNLOAD_DIR), label='SAVE TO').classes('w-full pixel-input')

        status = ui.label('> READY').classes('text-xs').style('color: #8888aa')

        async def do_download():
            url = url_input.value.strip()
            if not url:
                ui.notify('INPUT URL', type='warning')
                return
            status.set_text('> DOWNLOADING...')
            log(f'Download: {url}')

            def run():
                try:
                    plat = platform_val['value']
                    result = download(url, platform=plat if plat != 'auto' else None, save_dir=save_dir.value, callback=log)
                    if result:
                        log(f'DONE: {Path(result).name}')
                        status.set_text(f'> DONE: {Path(result).name}')
                    else:
                        status.set_text('> FAILED')
                except Exception as e:
                    log(f'ERROR: {e}')
                    status.set_text(f'> ERROR: {e}')

            threading.Thread(target=run, daemon=True).start()

        ui.button('START DOWNLOAD', on_click=do_download, icon='download').classes('pixel-btn primary mt-2')


# ── 转录 ──
def _build_transcribe_tab():
    with ui.card().classes('w-full pixel-panel'):
        ui.label('TRANSCRIBE AUDIO').classes('text-xs glow-text mb-3')

        engine = ui.radio(
            {'mimo': 'MIMO ASR (CLOUD)', 'whisper': 'WHISPER (LOCAL)'},
            value='mimo'
        ).classes('text-xs mb-4')

        video_path = ui.input(placeholder='VIDEO FILE PATH...', label='FILE').classes('w-full pixel-input')

        preview = ui.markdown('*RESULT WILL APPEAR HERE*').classes('text-xs max-h-48 overflow-auto').style('color: #aaaacc')
        status = ui.label('> READY').classes('text-xs').style('color: #8888aa')

        async def do_transcribe():
            vp = video_path.value.strip()
            if not vp or not os.path.exists(vp):
                ui.notify('SELECT VALID FILE', type='warning')
                return
            status.set_text('> TRANSCRIBING...')
            log(f'Transcribe: {Path(vp).name}')

            def run():
                try:
                    text = transcribe(vp, engine=engine.value, callback=log)
                    preview.set_content(text[:3000])
                    status.set_text(f'> DONE: {len(text)} CHARS')
                    log(f'DONE: {len(text)} chars')
                except Exception as e:
                    status.set_text(f'> ERROR: {e}')
                    log(f'ERROR: {e}')

            threading.Thread(target=run, daemon=True).start()

        ui.button('START TRANSCRIBE', on_click=do_transcribe, icon='mic').classes('pixel-btn primary mt-2')


# ── 分析 ──
def _build_analyze_tab():
    with ui.card().classes('w-full pixel-panel'):
        ui.label('ANALYZE TEXT').classes('text-xs glow-text mb-3')

        text_path = ui.input(placeholder='TEXT FILE PATH...', label='FILE').classes('w-full pixel-input')

        ui.label('MODULES').classes('text-xs mb-2').style('color: #8888aa')
        module_switches = {}
        with ui.row().classes('gap-4 mb-2'):
            for key, info in ANALYSIS_MODULES.items():
                module_switches[key] = ui.switch(info['name'].upper(), value=True).classes('text-xs')

        preview = ui.markdown('*RESULTS WILL APPEAR HERE*').classes('text-xs max-h-48 overflow-auto').style('color: #aaaacc')
        status = ui.label('> READY').classes('text-xs').style('color: #8888aa')

        async def do_analyze():
            tp = text_path.value.strip()
            if not tp or not os.path.exists(tp):
                ui.notify('SELECT VALID FILE', type='warning')
                return
            selected = [k for k, v in module_switches.items() if v.value]
            if not selected:
                ui.notify('SELECT AT LEAST 1 MODULE', type='warning')
                return
            status.set_text('> ANALYZING...')
            log(f'Analyze: {Path(tp).name}')

            def run():
                try:
                    with open(tp, 'r', encoding='utf-8') as f:
                        text = f.read()
                    results = analyze(text, modules=selected, source_name=tp, callback=log)
                    output = ""
                    for mod, res in results.items():
                        if "error" in res:
                            output += f"**{mod.upper()}** ERROR: {res['error']}\n\n"
                        else:
                            output += f"**{mod.upper()}**\n```json\n{json.dumps(res, ensure_ascii=False, indent=2)[:600]}\n```\n\n"
                    preview.set_content(output)
                    status.set_text('> DONE')
                    log('Analysis done')
                except Exception as e:
                    status.set_text(f'> ERROR: {e}')
                    log(f'ERROR: {e}')

            threading.Thread(target=run, daemon=True).start()

        ui.button('START ANALYZE', on_click=do_analyze, icon='analytics').classes('pixel-btn primary mt-2')


# ── 全流程 ──
def _build_pipeline_tab():
    with ui.card().classes('w-full pixel-panel'):
        ui.label('FULL PIPELINE').classes('text-sm glow-pink mb-1')
        ui.label('URL > DOWNLOAD > TRANSCRIBE > ANALYZE').classes('text-xs mb-3').style('color: #8888aa')

        url_input = ui.input(placeholder='PASTE VIDEO URL...', label='URL').classes('w-full pixel-input')

        with ui.row().classes('gap-4 mb-2'):
            engine = ui.radio({'mimo': 'MIMO', 'whisper': 'WHISPER'}, value='mimo').classes('text-xs')

        with ui.row().classes('gap-4 mb-2'):
            module_switches = {}
            for key, info in ANALYSIS_MODULES.items():
                module_switches[key] = ui.switch(info['name'].upper(), value=True).classes('text-xs')

        progress = ui.linear_progress(value=0, show_value=False).classes('w-full')
        status = ui.label('> READY').classes('text-xs').style('color: #8888aa')

        async def do_pipeline():
            url = url_input.value.strip()
            if not url:
                ui.notify('INPUT URL', type='warning')
                return
            state.is_running = True
            log(f'Pipeline start: {url}')

            def run():
                try:
                    status.set_text('[1/3] DOWNLOADING...')
                    progress.set_value(0.1)
                    platform = detect_platform(url)
                    log(f'Platform: {platform}')
                    video_path = download(url, platform=platform, callback=log)
                    if not video_path:
                        raise Exception('Download failed')
                    log('Download done')
                    progress.set_value(0.33)

                    status.set_text('[2/3] TRANSCRIBING...')
                    progress.set_value(0.4)
                    text = transcribe(video_path, engine=engine.value, callback=log)
                    log(f'Transcribe done: {len(text)} chars')
                    progress.set_value(0.66)

                    status.set_text('[3/3] ANALYZING...')
                    progress.set_value(0.7)
                    mods = [k for k, v in module_switches.items() if v.value]
                    if mods:
                        analyze(text, modules=mods, source_name=video_path, callback=log)
                    progress.set_value(1.0)
                    status.set_text('> PIPELINE COMPLETE')
                    log('PIPELINE COMPLETE')
                except Exception as e:
                    status.set_text(f'> ERROR: {e}')
                    log(f'ERROR: {e}')
                finally:
                    state.is_running = False

            threading.Thread(target=run, daemon=True).start()

        ui.button('RUN PIPELINE', on_click=do_pipeline, icon='bolt').classes('pixel-btn primary mt-2')


# ── 智能助手 ──
def _build_agent_tab():
    with ui.card().classes('w-full pixel-panel'):
        ui.label('AI AGENT').classes('text-sm glow-text mb-1')
        ui.label('TELL ME WHAT YOU WANT').classes('text-xs mb-3').style('color: #8888aa')

        chat_box = ui.column().classes('w-full max-h-80 overflow-auto mb-2')

        with chat_box:
            with ui.row().classes('msg-bot w-full'):
                ui.markdown('''**AGENT READY**

AVAILABLE COMMANDS:
- DOWNLOAD VIDEO
- TRANSCRIBE VIDEO
- ANALYZE TEXT
- LIST FILES

TRY: **DOWNLOAD THIS VIDEO https://v.douyin.com/xxx**''')

        with ui.row().classes('w-full gap-2'):
            input_box = ui.input(placeholder='INPUT COMMAND...').classes('flex-grow pixel-input')

            async def send():
                goal = input_box.value.strip()
                if not goal or state.is_running:
                    return
                input_box.set_value('')
                state.is_running = True

                with chat_box:
                    with ui.row().classes('msg-user w-full'):
                        ui.label(goal).classes('text-xs')

                with chat_box:
                    msg_container = ui.row().classes('msg-bot w-full')
                    with msg_container:
                        result_label = ui.markdown('**THINKING...**').classes('text-xs')

                def run():
                    try:
                        from agent import run_agent
                        def cb(m):
                            current = result_label.content or ''
                            result_label.set_content(current + f'\n{m}')
                        result = run_agent(goal, callback=cb)
                        result_label.set_content(f'**RESULT:**\n\n{result}')
                    except Exception as e:
                        result_label.set_content(f'**ERROR:** {e}')
                    finally:
                        state.is_running = False

                threading.Thread(target=run, daemon=True).start()

            input_box.on('keydown.enter', send)
            ui.button('SEND', on_click=send, icon='send').classes('pixel-btn primary')


# ═══════════════════════════════════════════
# 启动
# ═══════════════════════════════════════════

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title='VIDEO INSIGHT',
        dark=True,
        port=8080,
        reload=False,
    )
