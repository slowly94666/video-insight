# -*- coding: utf-8 -*-
"""
Video Insight — 视频洞察
原生 tkinter GUI，简洁布局
v5 — OperationRunner 操作抽象 + 主题系统 + 线程安全
"""
import os, sys, json, threading, subprocess, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from config import (DOWNLOAD_DIR, TRANSCRIPT_DIR, ANALYSIS_DIR,
                    PLATFORMS, ASR_ENGINES, ANALYSIS_MODULES)
from downloader import download, detect_platform
from transcriber import transcribe
from analyzer import analyze_unified, parse_sections
from live import extract as live_extract, find_potplayer
from theme import THEME
from operation import OperationRunner, CancelledError

ANALYSIS_FORMATS = {
    "full": "📋 完整", "brief": "📝 精简", "facts": "🔍 核查",
    "annotate": "💬 批注", "card": "🃏 一图",
}


class VideoInsightApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Video Insight")
        self.root.geometry("1200x800")
        self.root.minsize(900, 650)

        # ── 状态（数据） ──
        self.format_var = tk.StringVar(value="full")
        self.raw_result = None
        self.sections = {}
        self.live_urls = []
        self._save_dir = str(DOWNLOAD_DIR)

        # ── 操作运行器（取代手动 cancel_event + 按钮管理） ──
        self.runner = OperationRunner(ui_call=self._ui_call)
        self.runner.on_state_change(self._on_op_state_change)

        self.build_ui()

    # ═══════════════════ 线程安全基础 ═══════════════════

    def _ui_call(self, fn):
        """所有跨线程 UI 更新的唯一编组入口"""
        self.root.after(0, fn)

    def _on_op_state_change(self, state):
        """OperationRunner 状态变更 → 更新按钮"""
        from operation import OpState
        if state == OpState.RUNNING:
            for btn in self.action_buttons:
                btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
        else:
            for btn in self.action_buttons:
                btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")

    def _emit_log(self, msg):
        """线程安全的日志输出"""
        ts = datetime.now().strftime("%H:%M:%S")
        self._ui_call(lambda: self._log_impl(ts, msg))

    def _log_impl(self, ts, msg):
        """日志写入（必须主线程调用）"""
        self.log_box.insert("end", f"[{ts}] {msg}\n")
        self.log_box.see("end")

    def _emit_flow(self, key, state):
        """线程安全的流程指示器更新"""
        self._ui_call(lambda: self._flow_highlight(key, state))

    def _emit_status(self, text, color_key="secondary"):
        """线程安全的状态栏更新"""
        self._ui_call(lambda: self._set_status_impl(text, color_key))

    def _emit_transcript(self, text):
        """线程安全的转录文本写入"""
        self._ui_call(lambda: self.transcript_text.insert("end", text))

    def _emit_report(self):
        """线程安全的分析报告刷新"""
        self._ui_call(self._render_report)

    # ═══════════════════ UI 构建 ═══════════════════

    def build_ui(self):
        T = THEME  # 简写

        # ── 标题 ──
        top = tk.Frame(self.root, bg=T.bg_primary)
        top.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(top, text="Video Insight", font=("Microsoft YaHei UI", 14, "bold"),
                 fg=T.text_primary, bg=T.bg_primary).pack(side="left")
        tk.Label(top, text="  下载 → 转录 → 分析", font=("Microsoft YaHei UI", 9),
                 fg=T.text_secondary, bg=T.bg_primary).pack(side="left")

        # ── 流程指示器 ──
        self.flow_frame = tk.Frame(self.root, bg=T.bg_primary)
        self.flow_frame.pack(fill="x", padx=12, pady=(0, 8))
        self.flow_labels = {}
        for i, (key, icon, label) in enumerate([
            ("download", "📥", "下载视频"), ("transcribe", "🎙", "语音转录"),
            ("analyze", "🧠", "分析报告"),
        ]):
            f = tk.Frame(self.flow_frame, bg=T.flow_idle_bg,
                         relief="groove", bd=1)
            f.pack(side="left", padx=2)
            lbl = tk.Label(f, text=f"  {icon}  {label}  ",
                           font=("Microsoft YaHei UI", 10),
                           fg=T.flow_idle_fg, bg=T.flow_idle_bg)
            lbl.pack(padx=2, pady=2)
            self.flow_labels[key] = {"frame": f, "label": lbl}
            if i < 2:
                tk.Label(self.flow_frame, text=" → ", font=("", 10),
                         fg=T.divider, bg=T.bg_primary).pack(side="left", padx=2)

        # ── URL 输入 ──
        url_frame = tk.Frame(self.root, bg=T.bg_primary)
        url_frame.pack(fill="x", padx=12, pady=(0, 2))
        tk.Label(url_frame, text="粘贴链接:", font=("Microsoft YaHei UI", 10),
                 fg=T.text_primary, bg=T.bg_primary).pack(anchor="w")
        url_row = tk.Frame(url_frame, bg=T.bg_primary)
        url_row.pack(fill="x", pady=(2, 0))
        self.url_entry = tk.Entry(url_row, font=("Consolas", 11),
                                  bg=T.bg_input, fg=T.text_primary,
                                  insertbackground=T.text_primary,
                                  relief="solid", bd=1)
        self.url_entry.pack(side="left", fill="x", expand=True)
        self.url_entry.bind("<Return>", lambda e: self.run_pipeline())

        # ── 功能按钮 ──
        btn_frame = tk.Frame(self.root, bg=T.bg_primary)
        btn_frame.pack(fill="x", padx=12, pady=(4, 4))

        btn_cfg = {"font": ("Microsoft YaHei UI", 10), "width": 10, "relief": "flat",
                   "bd": 1, "padx": 8, "pady": 3}

        self.pipeline_btn = tk.Button(btn_frame, text="⚡ 全流程",
                                      font=("Microsoft YaHei UI", 10, "bold"),
                                      width=10, command=self.run_pipeline,
                                      bg=T.accent, fg="#ffffff",
                                      activebackground=T.accent, relief="flat")
        self.pipeline_btn.pack(side="left", padx=(0, 4))

        self.dl_btn = tk.Button(btn_frame, text="📥 仅下载", **btn_cfg,
                                command=self.run_download, bg=T.bg_card,
                                fg=T.text_primary, activebackground=T.bg_input)
        self.dl_btn.pack(side="left", padx=(0, 4))

        self.tr_btn = tk.Button(btn_frame, text="🎙 转录文件", **btn_cfg,
                                command=self.pick_and_transcribe, bg=T.bg_card,
                                fg=T.text_primary, activebackground=T.bg_input)
        self.tr_btn.pack(side="left", padx=(0, 4))

        self.an_btn = tk.Button(btn_frame, text="🧠 分析文本", **btn_cfg,
                                command=self.pick_and_analyze, bg=T.bg_card,
                                fg=T.text_primary, activebackground=T.bg_input)
        self.an_btn.pack(side="left", padx=(0, 4))

        self.live_btn = tk.Button(btn_frame, text="📺 直播源", **btn_cfg,
                                  command=self.run_live_extract, bg=T.bg_card,
                                  fg=T.text_primary, activebackground=T.bg_input)
        self.live_btn.pack(side="left", padx=(0, 4))

        self.stop_btn = tk.Button(btn_frame, text="⏹ 停止",
                                  font=("Microsoft YaHei UI", 10),
                                  fg=T.danger, bg=T.bg_card, width=8,
                                  command=self._stop_operation, state="disabled",
                                  relief="flat", bd=1, padx=8, pady=3)
        self.stop_btn.pack(side="right")

        self.action_buttons = [self.pipeline_btn, self.dl_btn, self.tr_btn,
                               self.an_btn, self.live_btn]

        # ── 选项行 ──
        opt_frame = tk.Frame(self.root, bg=T.bg_primary)
        opt_frame.pack(fill="x", padx=12, pady=(0, 4))
        tk.Label(opt_frame, text="转录:", font=("Microsoft YaHei UI", 9),
                 fg=T.text_secondary, bg=T.bg_primary).pack(side="left")
        engines = list(ASR_ENGINES.keys())
        self.engine_var = tk.StringVar(value=engines[0])
        ttk.Combobox(opt_frame, textvariable=self.engine_var, values=engines,
                     state="readonly", width=12,
                     font=("Microsoft YaHei UI", 9)).pack(side="left", padx=(4, 12))

        tk.Label(opt_frame, text="报告:", font=("Microsoft YaHei UI", 9),
                 fg=T.text_secondary, bg=T.bg_primary).pack(side="left")
        self.format_frame = tk.Frame(opt_frame, bg=T.bg_primary)
        self.format_frame.pack(side="left", padx=(4, 12))
        for key, label in ANALYSIS_FORMATS.items():
            tk.Radiobutton(self.format_frame, text=label, variable=self.format_var,
                           value=key, font=("Microsoft YaHei UI", 8),
                           fg=T.text_secondary, bg=T.bg_primary,
                           selectcolor=T.bg_primary,
                           command=self._on_format_changed).pack(side="left", padx=(0, 4))

        self.status_var = tk.StringVar(value="● 就绪")
        self.status_label = tk.Label(opt_frame, textvariable=self.status_var,
                                     font=("Microsoft YaHei UI", 9), fg=T.text_secondary,
                                     bg=T.bg_primary)
        self.status_label.pack(side="left")

        # 下载目录选择
        tk.Button(opt_frame, text="📂 下载目录", font=("Microsoft YaHei UI", 8),
                  relief="flat", bd=1, padx=6,
                  bg=T.bg_card, fg=T.text_secondary,
                  command=self._pick_save_dir).pack(side="right", padx=(4, 0))
        self.dir_label = tk.Label(opt_frame, text=Path(self._save_dir).name,
                                  font=("Microsoft YaHei UI", 8), fg=T.text_dim,
                                  bg=T.bg_primary)
        self.dir_label.pack(side="right")

        # ── 双栏输出 ──
        output_frame = tk.Frame(self.root, bg=T.bg_primary)
        output_frame.pack(fill="both", expand=True, padx=12, pady=(4, 4))

        # 左：转录文本
        left = tk.Frame(output_frame, bg=T.bg_card, relief="solid", bd=1)
        left.pack(side="left", fill="both", expand=True, padx=(0, 4))

        lt = tk.Frame(left, bg=T.bg_card)
        lt.pack(fill="x", padx=4, pady=(4, 0))
        self.lt = lt
        tk.Label(lt, text="📝 转录文本", font=("Microsoft YaHei UI", 10, "bold"),
                 fg=T.text_primary, bg=T.bg_card).pack(side="left")
        tk.Button(lt, text="📂", font=("Microsoft YaHei UI", 8), width=3,
                  relief="flat", bd=1, bg=T.bg_input, fg=T.text_secondary,
                  command=lambda: self._open_dir(TRANSCRIPT_DIR)
                  ).pack(side="right", padx=(2, 0))
        tk.Button(lt, text="📋 复制", font=("Microsoft YaHei UI", 8), width=8,
                  relief="flat", bd=1, bg=T.bg_input, fg=T.text_secondary,
                  command=lambda: self._copy_text(self.transcript_text)
                  ).pack(side="right", padx=(4, 0))

        # 路径标签（初始隐藏，操作完成后显示）
        self.transcript_path_label = tk.Label(left, text="",
            font=("Microsoft YaHei UI", 7), fg=T.text_dim, bg=T.bg_card, anchor="w")

        # 直播源操作栏（默认隐藏）
        self.live_bar = tk.Frame(left, bg=T.bg_card)
        self.live_copy_btn = tk.Button(self.live_bar, text="📋 复制链接",
                                       font=("Microsoft YaHei UI", 8),
                                       width=10, relief="flat",
                                       command=self._copy_live_url)
        self.live_play_btn = tk.Button(self.live_bar, text="▶ PotPlayer 播放",
                                       font=("Microsoft YaHei UI", 8),
                                       width=12, relief="flat",
                                       command=self._play_live_url)

        self.transcript_path_label.pack(fill="x", padx=4, pady=(2, 0))  # 初始隐藏内容为空

        self.transcript_text = tk.Text(left, font=("Microsoft YaHei UI", 10),
                                       wrap="word", relief="flat", borderwidth=0,
                                       bg=T.bg_card, fg=T.text_primary,
                                       insertbackground=T.text_primary)
        self.transcript_text.pack(side="left", fill="both", expand=True,
                                  padx=4, pady=4)
        tsb = tk.Scrollbar(left, command=self.transcript_text.yview)
        tsb.pack(side="right", fill="y")
        self.transcript_text.configure(yscrollcommand=tsb.set)

        # 右：分析报告
        right = tk.Frame(output_frame, bg=T.bg_card, relief="solid", bd=1)
        right.pack(side="right", fill="both", expand=True, padx=(4, 0))

        rt = tk.Frame(right, bg=T.bg_card)
        rt.pack(fill="x", padx=4, pady=(4, 0))
        tk.Label(rt, text="🧠 分析报告", font=("Microsoft YaHei UI", 10, "bold"),
                 fg=T.text_primary, bg=T.bg_card).pack(side="left")
        tk.Button(rt, text="📂", font=("Microsoft YaHei UI", 8), width=3,
                  relief="flat", bd=1, bg=T.bg_input, fg=T.text_secondary,
                  command=lambda: self._open_dir(ANALYSIS_DIR)
                  ).pack(side="right", padx=(2, 0))
        tk.Button(rt, text="📋 复制", font=("Microsoft YaHei UI", 8), width=8,
                  relief="flat", bd=1, bg=T.bg_input, fg=T.text_secondary,
                  command=lambda: self._copy_text(self.analysis_text)
                  ).pack(side="right", padx=(4, 0))

        # 路径标签（操作完成后显示）
        self.analysis_path_label = tk.Label(right, text="",
            font=("Microsoft YaHei UI", 7), fg=T.text_dim, bg=T.bg_card, anchor="w")
        self.analysis_path_label.pack(fill="x", padx=4, pady=(2, 0))

        self.analysis_text = tk.Text(right, font=("Microsoft YaHei UI", 10),
                                     wrap="word", relief="flat", borderwidth=0,
                                     bg=T.bg_card, fg=T.text_primary,
                                     insertbackground=T.text_primary)
        self.analysis_text.pack(side="left", fill="both", expand=True,
                                padx=4, pady=4)
        asb = tk.Scrollbar(right, command=self.analysis_text.yview)
        asb.pack(side="right", fill="y")
        self.analysis_text.configure(yscrollcommand=asb.set)

        # ── 日志 ──
        log_frame = tk.Frame(self.root, bg=T.bg_primary)
        log_frame.pack(fill="both", padx=12, pady=(0, 8), expand=False)
        tk.Label(log_frame, text="日志:", font=("Microsoft YaHei UI", 9, "bold"),
                 fg=T.text_secondary, bg=T.bg_primary).pack(anchor="w", pady=(0, 2))
        self.log_box = tk.Text(log_frame, font=("Consolas", 9),
                               fg=T.text_secondary, bg=T.bg_log,
                               wrap="word", relief="solid", height=8,
                               borderwidth=1, highlightthickness=0,
                               insertbackground=T.text_secondary)
        self.log_box.pack(fill="both", expand=True)
        self.log_box.insert("end", "就绪，等待输入...\n")

    # ═══════════════════ 工具方法 ═══════════════════

    def _log(self, msg):
        """旧接口兼容 — 从主线程调用直接写入，从工作线程调用需走 _ui_call"""
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_impl(ts, msg)

    def _flow_highlight(self, key, state):
        """更新流程指示器颜色（主线程调用）"""
        if key not in self.flow_labels:
            return
        T = THEME
        f, lbl = self.flow_labels[key]["frame"], self.flow_labels[key]["label"]
        colors = {
            "active":    (T.flow_active_bg, T.flow_active_fg),
            "done":      (T.flow_done_bg, T.flow_done_fg),
            "cancelled": (T.flow_cancelled_bg, T.flow_cancelled_fg),
            "idle":      (T.flow_idle_bg, T.flow_idle_fg),
        }
        bg, fg = colors.get(state, (T.flow_idle_bg, T.flow_idle_fg))
        f.configure(bg=bg)
        lbl.configure(bg=bg, fg=fg)

    def _reset_flow(self):
        for key in self.flow_labels:
            self._flow_highlight(key, "idle")

    def _set_status_impl(self, text, color_key="secondary"):
        """设置状态栏文字+颜色（主线程调用）"""
        T = THEME
        color_map = {
            "accent": T.accent, "success": T.success,
            "danger": T.danger, "warning": T.warning,
            "secondary": T.text_secondary,
        }
        self.status_var.set(text)
        self.status_label.configure(fg=color_map.get(color_key, T.text_secondary))

    def _stop_operation(self):
        """停止按钮回调"""
        self.runner.cancel()
        self._emit_log("⏹ 正在停止...")
        self._emit_status("⏹ 停止中...", "danger")
        self.stop_btn.configure(state="disabled")

    def _copy_text(self, widget):
        content = widget.get("1.0", "end-1c")
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self._log("📋 已复制到剪贴板")

    def _copy_live_url(self):
        if self.live_urls:
            url = self.live_urls[0].get("url", "")
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self._log(f"📋 已复制: {url[:60]}...")

    def _play_live_url(self):
        if not self.live_urls:
            return
        pp = find_potplayer()
        if not pp:
            messagebox.showerror("未找到", "未找到 PotPlayer")
            return
        subprocess.Popen([pp, self.live_urls[0]["url"]], shell=False)
        self._log("▶ 已发送到 PotPlayer")

    def _pick_save_dir(self):
        path = filedialog.askdirectory(title="选择下载目录", initialdir=self._save_dir)
        if path:
            self._save_dir = path
            self.dir_label.configure(text=Path(path).name)
            self._log(f"📂 下载目录: {path}")

    def _open_dir(self, dir_path):
        """在资源管理器中打开目录"""
        os.startfile(str(dir_path))

    # ═══════════════════ 报告渲染 ═══════════════════

    def _on_format_changed(self):
        if self.sections:
            self._render_report()

    def _render_report(self):
        fmt = self.format_var.get()
        s = self.sections

        def show(text):
            self.analysis_text.delete("1.0", "end")
            self.analysis_text.insert("end", text)

        if fmt == "full":
            show(s.get("analysis", ""))
        elif fmt == "brief":
            show(f"📋 {s.get('headline','')}\n\n---\n\n"
                 f"🔑 要点:\n{s.get('keypoints','')}\n\n{s.get('scores','')}")
        elif fmt == "facts":
            show(f"## 🔍 事实核查\n\n{s.get('facts','')}")
        elif fmt == "annotate":
            show(f"## 💬 对话批注\n\n{s.get('annotations','')}")
        elif fmt == "card":
            import re
            scores = s.get("scores", "")
            qm = re.search(r'质量[:\s]*(\d+)', scores)
            cm = re.search(r'可信度[:\s]*(\d+)', scores)
            qs = qm.group(1) if qm else "?"
            cs = cm.group(1) if cm else "?"
            try:
                qb = "█" * (int(qs) // 10) + "░" * (10 - int(qs) // 10)
                cb = "█" * (int(cs) // 10) + "░" * (10 - int(cs) // 10)
            except (ValueError, TypeError):
                qb = cb = "?" * 10
            kp = s.get("keypoints", "").replace("\n", "\n║  ")
            head = s.get('headline', '')[:40]
            show(f"╔══════════════════════════════╗\n"
                 f"║        📊 分析报告          ║\n"
                 f"╠══════════════════════════════╣\n"
                 f"║  {head}\n"
                 f"║  ⭐ 质量:   {qb} {qs}/100\n"
                 f"║  🔒 可信度: {cb} {cs}/100\n"
                 f"╠══════════════════════════════╣\n"
                 f"║  🔑 核心要点:                ║\n║  {kp}\n"
                 f"╚══════════════════════════════╝")

    # ═══════════════════ 操作入口 ═══════════════════

    def run_pipeline(self):
        url = self.url_entry.get().strip()
        if not url:
            self._log("⚠ 请输入视频链接")
            return
        if not self.runner.start(self._pipeline_thread, url):
            self._log("⚠ 请等待当前操作完成")
            return
        self.transcript_text.delete("1.0", "end")
        self.analysis_text.delete("1.0", "end")
        self._reset_flow()
        self._emit_status("⚡ 全流程中...", "accent")
        self._log(f"⚡ 全流程: {url[:100]}")

    def _pipeline_thread(self, op, check, url):
        """全流程：下载 → 转录 → 分析"""
        # [1/3] 下载
        check()
        self._emit_flow("download", "active")
        self._emit_log("📥 [1/3] 下载中...")
        platform = detect_platform(url)
        path = download(url, platform=platform, save_dir=self._save_dir,
                       callback=lambda m: self._emit_log(m),
                       cancel_event=op.cancel_event)
        check()
        if not path:
            raise RuntimeError("下载失败")
        self._emit_log(f"✅ 下载完成: {Path(path).name}")
        self._emit_flow("download", "done")

        # [2/3] 转录
        check()
        self._emit_flow("transcribe", "active")
        self._emit_log("🎙 [2/3] 转录中...")
        engine = self.engine_var.get()
        text, ts_path = transcribe(path, engine=engine,
                         callback=lambda m: self._emit_log(m))
        check()
        self._emit_transcript(text)
        self._emit_log(f"✅ 转录完成: {len(text)} 字")
        self._emit_flow("transcribe", "done")

        # [3/3] 分析
        check()
        self._emit_flow("analyze", "active")
        self._emit_log("🧠 [3/3] 分析中...")
        raw, an_path = analyze_unified(text, source_name=path,
                             callback=lambda m: self._emit_log(m))
        check()
        self.raw_result = raw
        self.sections = parse_sections(raw)
        self._emit_report()
        self._emit_log("✅ 全流程完成")
        self._emit_flow("analyze", "done")
        self._emit_status("✅ 全流程完成", "success")
        self._ui_call(lambda: self.transcript_path_label.configure(text=ts_path))
        self._ui_call(lambda: self.analysis_path_label.configure(text=an_path))

    # ── 仅下载 ──

    def run_download(self):
        url = self.url_entry.get().strip()
        if not url:
            self._log("⚠ 请输入链接")
            return
        if not self.runner.start(self._download_thread, url):
            self._log("⚠ 请等待当前操作完成")
            return
        self._reset_flow()
        self._emit_status("📥 下载中...", "accent")
        self._log(f"📥 下载: {url[:100]}")

    def _download_thread(self, op, check, url):
        check()
        self._emit_flow("download", "active")
        platform = detect_platform(url)
        path = download(url, platform=platform, save_dir=self._save_dir,
                       callback=lambda m: self._emit_log(m),
                       cancel_event=op.cancel_event)
        check()
        if not path:
            raise RuntimeError("下载失败")
        self._emit_log(f"✅ {Path(path).name}")
        self._emit_flow("download", "done")
        self._emit_status(f"✅ {Path(path).name}", "success")

    # ── 转录文件 ──

    def pick_and_transcribe(self):
        path = filedialog.askopenfilename(
            title="选择视频/音频",
            filetypes=[("媒体", "*.mp4 *.mkv *.webm *.flv *.avi *.mov *.mp3 *.wav *.m4a"),
                       ("所有", "*.*")])
        if not path:
            return
        if not self.runner.start(self._transcribe_thread, path):
            self._log("⚠ 请等待当前操作完成")
            return
        self.transcript_text.delete("1.0", "end")
        self._reset_flow()
        self._emit_status("🎙 转录中...", "accent")
        self._log(f"🎙 转录: {Path(path).name}")

    def _transcribe_thread(self, op, check, path):
        check()
        self._emit_flow("transcribe", "active")
        text, saved_path = transcribe(path, engine=self.engine_var.get(),
                         callback=lambda m: self._emit_log(m))
        check()
        self._emit_transcript(text)
        self._emit_log(f"✅ {len(text)} 字")
        self._emit_flow("transcribe", "done")
        self._emit_status(f"✅ {saved_path}", "success")
        self._ui_call(lambda: self.transcript_path_label.configure(text=saved_path))

    # ── 分析文本 ──

    def pick_and_analyze(self):
        path = filedialog.askopenfilename(
            title="选择转录文本",
            filetypes=[("文本", "*.txt *.md"), ("所有", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            self._log(f"❌ 读取失败: {e}")
            return
        self._start_analyze(text, path)

    def _start_analyze(self, text, path):
        if not self.runner.start(self._analyze_thread, text, path):
            self._log("⚠ 请等待当前操作完成")
            return
        self.analysis_text.delete("1.0", "end")
        self._reset_flow()
        self._emit_status("🧠 分析中...", "accent")
        self._log(f"🧠 分析: {Path(path).name if isinstance(path, str) else path} "
                  f"({len(text)} 字)")

    def _analyze_thread(self, op, check, text, path):
        check()
        self._emit_flow("analyze", "active")
        raw, saved_path = analyze_unified(text, source_name=path,
                             callback=lambda m: self._emit_log(m))
        check()
        self.raw_result = raw
        self.sections = parse_sections(raw)
        self._emit_report()
        self._emit_log("✅ 分析完成")
        self._emit_flow("analyze", "done")
        self._emit_status(f"✅ {saved_path}", "success")
        self._ui_call(lambda: self.analysis_path_label.configure(text=saved_path))

    # ── 直播源 ──

    def run_live_extract(self):
        url = self.url_entry.get().strip()
        if not url:
            self._log("⚠ 请输入链接")
            return
        # 直播源提取不占用下载/转录操作，但仍走 OperationRunner 统一管理
        if not self.runner.start(self._live_thread, url):
            self._log("⚠ 请等待当前操作完成")
            return
        self._emit_status("📺 提取中...", "accent")
        self._log(f"📺 提取: {url[:100]}")

    def _live_thread(self, op, check, url):
        results = live_extract(url)
        if not results:
            raise RuntimeError("未提取到直播源")

        self.live_urls = results
        lines = [f"=== 直播源 ({len(results)} 个) ===\n"]
        for i, r in enumerate(results):
            lines.append(f"{i+1}. {r.get('quality','?')}: {r.get('url','')}")
        self._emit_transcript("\n".join(lines))

        # 显示直播源操作栏
        self._ui_call(lambda: self.live_bar.pack(
            fill="x", pady=(4, 0), after=self.lt))
        self._ui_call(lambda: self.live_copy_btn.pack(side="left", padx=(0, 4)))
        pp = find_potplayer()
        if pp:
            self._ui_call(lambda: self.live_play_btn.pack(side="left"))
        else:
            self._ui_call(lambda: self.live_play_btn.pack_forget())
        self._emit_log(f"✅ {len(results)} 个源" + (" ▶ 可播放" if pp else ""))
        self._emit_status(f"✅ {len(results)} 个源，可复制/播放", "success")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    VideoInsightApp().run()