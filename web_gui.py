"""
视频洞察 - Web GUI（NiceGUI）
浏览器打开，Material Design 暗色主题
"""
import os
import sys
import threading
import asyncio
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
# 状态管理
# ═══════════════════════════════════════════

class AppState:
    def __init__(self):
        self.logs = []
        self.is_running = False
        self.agent_messages = []

state = AppState()


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    state.logs.append(entry)
    # 保留最近 200 条
    if len(state.logs) > 200:
        state.logs = state.logs[-200:]


# ═══════════════════════════════════════════
# 样式
# ═══════════════════════════════════════════

DARK_CSS = """
body {
    background: #1a1a2e !important;
    font-family: 'Segoe UI', system-ui, sans-serif;
}
.q-page {
    background: #1a1a2e !important;
}
"""

CARD_STYLE = "background: #16213e; border-radius: 12px; padding: 20px; margin-bottom: 16px;"

# ═══════════════════════════════════════════
# 页面构建
# ═══════════════════════════════════════════

@ui.page('/')
def main_page():
    ui.add_head_html(f'<style>{DARK_CSS}</style>')

    with ui.column().classes('w-full max-w-5xl mx-auto p-4'):

        # 标题
        ui.label('🎬 视频洞察').classes('text-3xl font-bold text-white mb-1')
        ui.label('下载 · 转录 · 分析 · 智能助手').classes('text-sm text-gray-400 mb-4')

        # Tab 导航
        with ui.tabs().classes('w-full mb-4') as tabs:
            ui.tab('下载', icon='download')
            ui.tab('转录', icon='mic')
            ui.tab('分析', icon='analytics')
            ui.tab('全流程', icon='bolt')
            ui.tab('智能助手', icon='smart_toy')

        with ui.tab_panels(tabs, value='下载').classes('w-full'):

            # ── 下载 Tab ──
            with ui.tab_panel('下载'):
                _build_download_tab()

            # ── 转录 Tab ──
            with ui.tab_panel('转录'):
                _build_transcribe_tab()

            # ── 分析 Tab ──
            with ui.tab_panel('分析'):
                _build_analyze_tab()

            # ── 全流程 Tab ──
            with ui.tab_panel('全流程'):
                _build_pipeline_tab()

            # ── 智能助手 Tab ──
            with ui.tab_panel('智能助手'):
                _build_agent_tab()

        # 底部日志
        with ui.card().classes('w-full').style(CARD_STYLE):
            ui.label('📋 日志').classes('text-sm font-bold text-gray-300 mb-2')
            log_area = ui.markdown('').classes('text-xs text-gray-400 max-h-40 overflow-auto')
            ui.timer(1.0, lambda: log_area.set_content('```\n' + '\n'.join(state.logs[-30:]) + '\n```'))


# ── 下载页面 ──
def _build_download_tab():
    with ui.card().classes('w-full').style(CARD_STYLE):
        ui.label('📥 视频下载').classes('text-xl font-bold text-white mb-3')

        platform = ui.radio(
            {k: f"{v['icon']} {v['name']}" for k, v in PLATFORMS.items()},
            value='auto'
        ).classes('text-gray-300')

        url_input = ui.input(placeholder='粘贴视频链接...', label='链接').classes('w-full')

        save_dir = ui.input(value=str(DOWNLOAD_DIR), label='保存到').classes('w-full')

        status = ui.label('就绪').classes('text-sm text-gray-400')

        async def do_download():
            url = url_input.value.strip()
            if not url:
                ui.notify('请输入链接', type='warning')
                return
            status.set_text('下载中...')
            log(f'开始下载: {url}')

            def run():
                try:
                    result = download(url, platform=platform.value, save_dir=save_dir.value, callback=log)
                    if result:
                        log(f'✅ 下载完成: {result}')
                        status.set_text(f'✅ 完成: {Path(result).name}')
                    else:
                        log('❌ 下载失败')
                        status.set_text('❌ 失败')
                except Exception as e:
                    log(f'❌ 异常: {e}')
                    status.set_text(f'❌ {e}')

            threading.Thread(target=run, daemon=True).start()

        ui.button('开始下载', on_click=do_download, icon='download').classes('mt-2')


# ── 转录页面 ──
def _build_transcribe_tab():
    with ui.card().classes('w-full').style(CARD_STYLE):
        ui.label('🎙 语音转录').classes('text-xl font-bold text-white mb-3')

        engine = ui.radio(
            {k: f"{v['name']} — {v['desc']}" for k, v in ASR_ENGINES.items()},
            value='mimo'
        ).classes('text-gray-300')

        video_path = ui.input(placeholder='选择视频文件...', label='视频文件').classes('w-full')

        with ui.row():
            ui.button('选择文件', icon='folder_open', on_click=lambda: ui.upload(
                on_upload=lambda e: video_path.set_value(e.name),
                max_file_size=10_000_000_000
            ))
            # 显示 transcripts 目录最新文件
            latest = sorted(TRANSCRIPT_DIR.glob('*.txt'), key=lambda f: f.stat().st_mtime, reverse=True)
            if latest:
                video_path.set_value(str(latest[0]))

        preview = ui.markdown('*转录结果将显示在这里*').classes('text-sm text-gray-300 max-h-60 overflow-auto')
        status = ui.label('就绪').classes('text-sm text-gray-400')

        async def do_transcribe():
            vp = video_path.value.strip()
            if not vp or not os.path.exists(vp):
                ui.notify('请选择有效的视频文件', type='warning')
                return
            status.set_text('转录中...')
            log(f'开始转录: {Path(vp).name}')

            def run():
                try:
                    text = transcribe(vp, engine=engine.value, callback=log)
                    preview.set_content(text[:3000])
                    status.set_text(f'✅ 完成，共 {len(text)} 字')
                    log(f'✅ 转录完成')
                except Exception as e:
                    status.set_text(f'❌ {e}')
                    log(f'❌ 转录失败: {e}')

            threading.Thread(target=run, daemon=True).start()

        ui.button('开始转录', on_click=do_transcribe, icon='mic').classes('mt-2')


# ── 分析页面 ──
def _build_analyze_tab():
    with ui.card().classes('w-full').style(CARD_STYLE):
        ui.label('📊 文案分析').classes('text-xl font-bold text-white mb-3')

        text_path = ui.input(placeholder='选择文本文件...', label='文本文件').classes('w-full')

        modules = {}
        with ui.row().classes('gap-4'):
            for key, info in ANALYSIS_MODULES.items():
                modules[key] = ui.switch(f"{info['name']}", value=True).classes('text-gray-300')

        preview = ui.markdown('*分析结果将显示在这里*').classes('text-sm text-gray-300 max-h-60 overflow-auto')
        status = ui.label('就绪').classes('text-sm text-gray-400')

        async def do_analyze():
            tp = text_path.value.strip()
            if not tp or not os.path.exists(tp):
                ui.notify('请选择有效的文本文件', type='warning')
                return
            selected = [k for k, v in modules.items() if v.value]
            if not selected:
                ui.notify('请至少选择一个分析模块', type='warning')
                return

            status.set_text('分析中...')
            log(f'开始分析: {Path(tp).name}')

            def run():
                try:
                    with open(tp, 'r', encoding='utf-8') as f:
                        text = f.read()
                    results = analyze(text, modules=selected, source_name=tp, callback=log)
                    output = ""
                    for mod, res in results.items():
                        if "error" in res:
                            output += f"### {mod} ❌\n{res['error']}\n\n"
                        else:
                            output += f"### {mod}\n```json\n{__import__('json').dumps(res, ensure_ascii=False, indent=2)[:500]}\n```\n\n"
                    preview.set_content(output)
                    status.set_text('✅ 分析完成')
                    log('✅ 分析完成')
                except Exception as e:
                    status.set_text(f'❌ {e}')
                    log(f'❌ 分析失败: {e}')

            threading.Thread(target=run, daemon=True).start()

        ui.button('开始分析', on_click=do_analyze, icon='analytics').classes('mt-2')


# ── 全流程页面 ──
def _build_pipeline_tab():
    with ui.card().classes('w-full').style(CARD_STYLE):
        ui.label('⚡ 一键全流程').classes('text-xl font-bold text-white mb-1')
        ui.label('输入链接 → 下载 → 转录 → 分析 → 生成报告').classes('text-sm text-gray-400 mb-3')

        url_input = ui.input(placeholder='粘贴视频链接...', label='链接').classes('w-full')

        with ui.row().classes('gap-4 items-center'):
            engine = ui.radio({'mimo': 'MiMo', 'whisper': 'Whisper'}, value='mimo').classes('text-gray-300')

        with ui.row().classes('gap-4'):
            module_switches = {}
            for key, info in ANALYSIS_MODULES.items():
                module_switches[key] = ui.switch(info['name'], value=True).classes('text-gray-300')

        progress = ui.linear_progress(value=0, show_value=False).classes('w-full')
        status = ui.label('就绪').classes('text-sm text-gray-400')

        async def do_pipeline():
            url = url_input.value.strip()
            if not url:
                ui.notify('请输入链接', type='warning')
                return

            state.is_running = True
            log(f'开始全流程: {url}')

            def run():
                try:
                    # Step 1: 下载
                    status.set_text('步骤 1/3: 下载中...')
                    progress.set_value(0.1)
                    platform = detect_platform(url)
                    log(f'平台: {platform}')
                    video_path = download(url, platform=platform, callback=log)
                    if not video_path:
                        raise Exception('下载失败')
                    log(f'✅ 下载完成')
                    progress.set_value(0.33)

                    # Step 2: 转录
                    status.set_text('步骤 2/3: 转录中...')
                    progress.set_value(0.4)
                    text = transcribe(video_path, engine=engine.value, callback=log)
                    log(f'✅ 转录完成，{len(text)} 字')
                    progress.set_value(0.66)

                    # Step 3: 分析
                    status.set_text('步骤 3/3: 分析中...')
                    progress.set_value(0.7)
                    mods = [k for k, v in module_switches.items() if v.value]
                    if mods:
                        analyze(text, modules=mods, source_name=video_path, callback=log)
                    progress.set_value(1.0)
                    status.set_text('✅ 全流程完成')
                    log('🎉 全流程完成')

                except Exception as e:
                    status.set_text(f'❌ {e}')
                    log(f'❌ 流程异常: {e}')
                finally:
                    state.is_running = False

            threading.Thread(target=run, daemon=True).start()

        ui.button('🚀 开始全流程', on_click=do_pipeline, icon='bolt', color='amber').classes('mt-2 text-lg px-8 py-3')


# ── 智能助手页面 ──
def _build_agent_tab():
    with ui.card().classes('w-full').style(CARD_STYLE):
        ui.label('🤖 智能助手').classes('text-xl font-bold text-white mb-1')
        ui.label('用自然语言告诉我你想做什么').classes('text-sm text-gray-400 mb-3')

        chat_container = ui.column().classes('w-full max-h-96 overflow-auto')

        # 初始欢迎消息
        with chat_container:
            with ui.chat_message(name='助手', avatar='🤖', sent=False):
                ui.markdown('''你好！我是视频分析助手，可以帮你：
- 📥 下载视频（B站/抖音/Twitter/SOOP）
- 🎙 转录视频为文字
- 📊 分析文案内容
- 🔗 组合完成复杂任务

试试说：**帮我下载这个抖音视频并分析它的内容**''')

        with ui.row().classes('w-full gap-2'):
            input_box = ui.input(placeholder='输入你的目标...', label='').classes('flex-grow')

            async def send_message():
                goal = input_box.value.strip()
                if not goal or state.is_running:
                    return
                input_box.set_value('')
                state.is_running = True

                # 显示用户消息
                with chat_container:
                    with ui.chat_message(name='你', avatar='👤', sent=True):
                        ui.label(goal)

                # 运行 agent
                with chat_container:
                    msg = ui.chat_message(name='助手', avatar='🤖', sent=False)
                    with msg:
                        result_label = ui.markdown('🤔 思考中...')

                def run():
                    try:
                        from agent import run_agent
                        def cb(m):
                            result_label.set_content(result_label.content + '\n' + m)
                        result = run_agent(goal, callback=cb)
                        result_label.set_content(f'**最终结果：**\n\n{result}')
                    except Exception as e:
                        result_label.set_content(f'❌ 异常: {e}')
                    finally:
                        state.is_running = False

                threading.Thread(target=run, daemon=True).start()

            input_box.on('keydown.enter', send_message)
            ui.button('发送', on_click=send_message, icon='send')


# ═══════════════════════════════════════════
# 启动
# ═══════════════════════════════════════════

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title='视频洞察 - Video Insight',
        dark=True,
        port=8080,
        favicon='🎬',
        reload=False,
    )
