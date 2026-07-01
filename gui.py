# -*- coding: utf-8 -*-
"""
视频Agent - 统一 GUI
合并下载 · 转录 · 分析 三大功能
"""
import os
import sys
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
from pathlib import Path
from datetime import datetime

# 确保在项目目录下运行
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from config import (
    DOWNLOAD_DIR, TRANSCRIPT_DIR, ANALYSIS_DIR,
    PLATFORMS, ASR_ENGINES, ANALYSIS_MODULES
)
from downloader import download, detect_platform
from transcriber import transcribe
from analyzer import analyze

# 主题
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class VideoAgentApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("视频Agent - 下载 · 转录 · 分析")
        self.geometry("1000x700")
        self.minsize(850, 600)

        # 状态
        self.current_step = "download"
        self.is_running = False
        self.pipeline_running = False

        # 流水线中间结果
        self._pipeline_video = None
        self._pipeline_text = None

        self._build_ui()

    # ════════════════════════════════════════
    # UI 构建
    # ════════════════════════════════════════

    def _build_ui(self):
        # 主容器
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── 左侧导航栏 ──
        self.sidebar = ctk.CTkFrame(self, width=160, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_propagate(False)

        ctk.CTkLabel(self.sidebar, text="🎬 视频Agent",
                     font=("", 18, "bold")).pack(pady=(20, 30))

        self.nav_buttons = {}
        nav_items = [
            ("download",  "📥  下载"),
            ("transcribe","🎙  转录"),
            ("analyze",   "📊  分析"),
            ("pipeline",  "⚡  一键全流程"),
        ]
        for key, label in nav_items:
            btn = ctk.CTkButton(
                self.sidebar, text=label, anchor="w",
                font=("", 14), height=40, width=140,
                command=lambda k=key: self._switch_step(k)
            )
            btn.pack(pady=4, padx=10)
            self.nav_buttons[key] = btn

        # ── 右侧主区域 ──
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)

        # 各步骤页面
        self.pages = {}
        self._build_download_page()
        self._build_transcribe_page()
        self._build_analyze_page()
        self._build_pipeline_page()

        # 底部日志
        self.log_frame = ctk.CTkFrame(self, height=150)
        self.log_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=(0, 10))
        self.grid_rowconfigure(1, weight=0, minsize=130)
        self.log_frame.grid_propagate(False)

        ctk.CTkLabel(self.log_frame, text="📋 日志", font=("", 12, "bold")).pack(anchor="w", padx=10, pady=(5, 0))
        self.log_text = ctk.CTkTextbox(self.log_frame, wrap="word", font=("", 11))
        self.log_text.pack(fill="both", expand=True, padx=10, pady=5)

        self._switch_step("download")

    # ── 下载页面 ──
    def _build_download_page(self):
        page = ctk.CTkFrame(self.main_frame)
        page.grid_columnconfigure(0, weight=1)

        # 标题
        ctk.CTkLabel(page, text="📥 视频下载", font=("", 20, "bold")).pack(anchor="w", padx=15, pady=(15, 5))

        # 平台选择
        f = ctk.CTkFrame(page)
        f.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(f, text="平台:", font=("", 13)).pack(side="left", padx=5)
        self.dl_platform = ctk.StringVar(value="auto")
        platforms = [("自动检测", "auto")] + [(v["name"], k) for k, v in PLATFORMS.items()]
        for text, val in platforms:
            ctk.CTkRadioButton(f, text=text, variable=self.dl_platform,
                              value=val).pack(side="left", padx=8)

        # URL 输入
        f2 = ctk.CTkFrame(page)
        f2.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(f2, text="链接:", font=("", 13)).pack(side="left", padx=5)
        self.dl_url = ctk.CTkEntry(f2, placeholder_text="粘贴视频链接...")
        self.dl_url.pack(side="left", fill="x", expand=True, padx=5)

        # 保存路径
        f3 = ctk.CTkFrame(page)
        f3.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(f3, text="保存到:", font=("", 13)).pack(side="left", padx=5)
        self.dl_save_dir = ctk.StringVar(value=str(DOWNLOAD_DIR))
        ctk.CTkEntry(f3, textvariable=self.dl_save_dir).pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(f3, text="选择", width=60,
                      command=self._pick_dl_dir).pack(side="left", padx=2)

        # 下载按钮
        self.dl_btn = ctk.CTkButton(page, text="开始下载", font=("", 14, "bold"),
                                    height=40, command=self._start_download)
        self.dl_btn.pack(pady=15)

        self.pages["download"] = page

    # ── 转录页面 ──
    def _build_transcribe_page(self):
        page = ctk.CTkFrame(self.main_frame)
        page.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(page, text="🎙 语音转录", font=("", 20, "bold")).pack(anchor="w", padx=15, pady=(15, 5))

        # 引擎选择
        f = ctk.CTkFrame(page)
        f.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(f, text="引擎:", font=("", 13)).pack(side="left", padx=5)
        self.tr_engine = ctk.StringVar(value="mimo")
        for key, info in ASR_ENGINES.items():
            ctk.CTkRadioButton(f, text=f"{info['name']} - {info['desc']}",
                              variable=self.tr_engine, value=key).pack(side="left", padx=8)

        # 视频文件选择
        f2 = ctk.CTkFrame(page)
        f2.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(f2, text="视频:", font=("", 13)).pack(side="left", padx=5)
        self.tr_video_path = ctk.StringVar()
        ctk.CTkEntry(f2, textvariable=self.tr_video_path,
                    placeholder_text="选择视频文件或从下载结果自动填入").pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(f2, text="选择", width=60,
                      command=self._pick_video_file).pack(side="left", padx=2)

        # 转录按钮
        self.tr_btn = ctk.CTkButton(page, text="开始转录", font=("", 14, "bold"),
                                    height=40, command=self._start_transcribe)
        self.tr_btn.pack(pady=15)

        # 转录结果预览
        ctk.CTkLabel(page, text="转录结果预览:", font=("", 12, "bold")).pack(anchor="w", padx=15)
        self.tr_preview = ctk.CTkTextbox(page, wrap="word", height=150, font=("", 11))
        self.tr_preview.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        self.pages["transcribe"] = page

    # ── 分析页面 ──
    def _build_analyze_page(self):
        page = ctk.CTkFrame(self.main_frame)
        page.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(page, text="📊 文案分析", font=("", 20, "bold")).pack(anchor="w", padx=15, pady=(15, 5))

        # 文本来源
        f = ctk.CTkFrame(page)
        f.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(f, text="文本:", font=("", 13)).pack(side="left", padx=5)
        self.an_text_path = ctk.StringVar()
        ctk.CTkEntry(f, textvariable=self.an_text_path,
                    placeholder_text="选择 .txt 文件或从转录结果自动填入").pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(f, text="选择", width=60,
                      command=self._pick_text_file).pack(side="left", padx=2)

        # 模块选择
        f2 = ctk.CTkFrame(page)
        f2.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(f2, text="分析模块:", font=("", 13)).pack(anchor="w", padx=5, pady=(5, 0))
        self.an_modules = {}
        for key, info in ANALYSIS_MODULES.items():
            var = ctk.BooleanVar(value=True)
            ctk.CTkCheckBox(f2, text=f"{info['name']} - {info['desc']}",
                           variable=var).pack(anchor="w", padx=20, pady=2)
            self.an_modules[key] = var

        # 分析按钮
        self.an_btn = ctk.CTkButton(page, text="开始分析", font=("", 14, "bold"),
                                    height=40, command=self._start_analyze)
        self.an_btn.pack(pady=15)

        # 分析结果预览
        ctk.CTkLabel(page, text="分析结果:", font=("", 12, "bold")).pack(anchor="w", padx=15)
        self.an_preview = ctk.CTkTextbox(page, wrap="word", height=120, font=("", 11))
        self.an_preview.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        self.pages["analyze"] = page

    # ── 一键全流程页面 ──
    def _build_pipeline_page(self):
        page = ctk.CTkFrame(self.main_frame)
        page.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(page, text="⚡ 一键全流程", font=("", 20, "bold")).pack(anchor="w", padx=15, pady=(15, 5))
        ctk.CTkLabel(page, text="输入链接 → 下载 → 转录 → 分析 → 生成报告",
                     font=("", 12), text_color="gray").pack(anchor="w", padx=15)

        # URL
        f = ctk.CTkFrame(page)
        f.pack(fill="x", padx=15, pady=10)
        ctk.CTkLabel(f, text="链接:", font=("", 13)).pack(side="left", padx=5)
        self.pl_url = ctk.CTkEntry(f, placeholder_text="粘贴视频链接...")
        self.pl_url.pack(side="left", fill="x", expand=True, padx=5)

        # 引擎 + 模块
        f2 = ctk.CTkFrame(page)
        f2.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(f2, text="转录引擎:", font=("", 13)).pack(side="left", padx=5)
        self.pl_engine = ctk.StringVar(value="mimo")
        ctk.CTkRadioButton(f2, text="MiMo", variable=self.pl_engine, value="mimo").pack(side="left", padx=8)
        ctk.CTkRadioButton(f2, text="Whisper", variable=self.pl_engine, value="whisper").pack(side="left", padx=8)

        # 分析模块
        f3 = ctk.CTkFrame(page)
        f3.pack(fill="x", padx=15, pady=5)
        self.pl_modules = {}
        for key, info in ANALYSIS_MODULES.items():
            var = ctk.BooleanVar(value=True)
            ctk.CTkCheckBox(f3, text=info['name'], variable=var).pack(side="left", padx=10)
            self.pl_modules[key] = var

        # 进度条
        self.pl_progress = ctk.CTkProgressBar(page)
        self.pl_progress.pack(fill="x", padx=15, pady=10)
        self.pl_progress.set(0)

        self.pl_status = ctk.CTkLabel(page, text="就绪", font=("", 12))
        self.pl_status.pack(anchor="w", padx=15)

        # 开始按钮
        self.pl_btn = ctk.CTkButton(page, text="🚀 开始全流程", font=("", 16, "bold"),
                                    height=50, command=self._start_pipeline)
        self.pl_btn.pack(pady=20)

        self.pages["pipeline"] = page

    # ════════════════════════════════════════
    # 导航
    # ════════════════════════════════════════

    def _switch_step(self, step):
        self.current_step = step
        for key, page in self.pages.items():
            if key == step:
                page.grid(row=0, column=0, sticky="nsew")
            else:
                page.grid_forget()
        for key, btn in self.nav_buttons.items():
            if key == step:
                btn.configure(fg_color=("gray75", "gray25"))
            else:
                btn.configure(fg_color=("gray68", "gray30"))

    # ════════════════════════════════════════
    # 文件选择
    # ════════════════════════════════════════

    def _pick_dl_dir(self):
        d = filedialog.askdirectory(title="选择保存目录")
        if d:
            self.dl_save_dir.set(d)

    def _pick_video_file(self):
        f = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[("视频文件", "*.mp4 *.mkv *.avi *.flv *.webm *.mov"), ("所有文件", "*.*")]
        )
        if f:
            self.tr_video_path.set(f)

    def _pick_text_file(self):
        f = filedialog.askopenfilename(
            title="选择文本文件",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if f:
            self.an_text_path.set(f)

    # ════════════════════════════════════════
    # 日志
    # ════════════════════════════════════════

    def _log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}] {msg}\n")
        self.log_text.see("end")

    # ════════════════════════════════════════
    # 下载
    # ════════════════════════════════════════

    def _start_download(self):
        url = self.dl_url.get().strip()
        if not url:
            messagebox.showwarning("提示", "请输入视频链接")
            return
        if self.is_running:
            return
        self.is_running = True
        self.dl_btn.configure(state="disabled", text="下载中...")
        threading.Thread(target=self._run_download, args=(url,), daemon=True).start()

    def _run_download(self, url):
        def cb(msg):
            self.after(0, self._log, msg)
        try:
            platform = self.dl_platform.get()
            if platform == "auto":
                platform = None
            save_dir = self.dl_save_dir.get()
            result = download(url, platform=platform, save_dir=save_dir, callback=cb)
            if result:
                self.after(0, self._log, f"✅ 下载完成: {result}")
                self.after(0, lambda: self.tr_video_path.set(result))
            else:
                self.after(0, self._log, "❌ 下载失败")
        except Exception as e:
            self.after(0, self._log, f"❌ 下载异常: {e}")
        finally:
            self.after(0, lambda: self.dl_btn.configure(state="normal", text="开始下载"))
            self.is_running = False

    # ════════════════════════════════════════
    # 转录
    # ════════════════════════════════════════

    def _start_transcribe(self):
        video = self.tr_video_path.get().strip()
        if not video:
            messagebox.showwarning("提示", "请选择视频文件")
            return
        if not os.path.exists(video):
            messagebox.showerror("错误", f"文件不存在: {video}")
            return
        if self.is_running:
            return
        self.is_running = True
        self.tr_btn.configure(state="disabled", text="转录中...")
        self.tr_preview.delete("1.0", "end")
        threading.Thread(target=self._run_transcribe, args=(video,), daemon=True).start()

    def _run_transcribe(self, video):
        def cb(msg):
            self.after(0, self._log, msg)
        try:
            engine = self.tr_engine.get()
            text = transcribe(video, engine=engine, callback=cb)
            self.after(0, self._log, f"✅ 转录完成，共 {len(text)} 字")
            self.after(0, lambda: self.tr_preview.insert("1.0", text[:2000]))
            # 自动填入分析页面
            latest = max(TRANSCRIPT_DIR.glob("*.txt"), key=lambda f: f.stat().st_mtime, default=None)
            if latest:
                self.after(0, lambda: self.an_text_path.set(str(latest)))
        except Exception as e:
            self.after(0, self._log, f"❌ 转录失败: {e}")
        finally:
            self.after(0, lambda: self.tr_btn.configure(state="normal", text="开始转录"))
            self.is_running = False

    # ════════════════════════════════════════
    # 分析
    # ════════════════════════════════════════

    def _start_analyze(self):
        text_path = self.an_text_path.get().strip()
        if not text_path:
            messagebox.showwarning("提示", "请选择文本文件")
            return
        if not os.path.exists(text_path):
            messagebox.showerror("错误", f"文件不存在: {text_path}")
            return
        selected = [k for k, v in self.an_modules.items() if v.get()]
        if not selected:
            messagebox.showwarning("提示", "请至少选择一个分析模块")
            return
        if self.is_running:
            return
        self.is_running = True
        self.an_btn.configure(state="disabled", text="分析中...")
        self.an_preview.delete("1.0", "end")
        threading.Thread(target=self._run_analyze, args=(text_path, selected), daemon=True).start()

    def _run_analyze(self, text_path, modules):
        def cb(msg):
            self.after(0, self._log, msg)
        try:
            with open(text_path, 'r', encoding='utf-8') as f:
                text = f.read()
            results = analyze(text, modules=modules, source_name=text_path, callback=cb)
            # 预览结果
            preview = ""
            for mod, res in results.items():
                if "error" in res:
                    preview += f"[{mod}] 错误: {res['error']}\n\n"
                else:
                    preview += f"[{mod}] {str(res)[:300]}\n\n"
            self.after(0, lambda: self.an_preview.insert("1.0", preview))
            self.after(0, self._log, "✅ 分析完成")
        except Exception as e:
            self.after(0, self._log, f"❌ 分析失败: {e}")
        finally:
            self.after(0, lambda: self.an_btn.configure(state="normal", text="开始分析"))
            self.is_running = False

    # ════════════════════════════════════════
    # 一键全流程
    # ════════════════════════════════════════

    def _start_pipeline(self):
        url = self.pl_url.get().strip()
        if not url:
            messagebox.showwarning("提示", "请输入视频链接")
            return
        if self.is_running:
            return
        self.is_running = True
        self.pipeline_running = True
        self.pl_btn.configure(state="disabled", text="运行中...")
        self.pl_progress.set(0)
        threading.Thread(target=self._run_pipeline, args=(url,), daemon=True).start()

    def _run_pipeline(self, url):
        def cb(msg):
            self.after(0, self._log, msg)

        def set_progress(v, status):
            self.after(0, self.pl_progress.set, v)
            self.after(0, self.pl_status.configure, {"text": status})

        try:
            # Step 1: 下载
            set_progress(0.05, "步骤 1/3: 下载视频...")
            platform = detect_platform(url)
            cb(f"检测到平台: {platform}")
            video_path = download(url, platform=platform, callback=cb)
            if not video_path:
                cb("❌ 下载失败，流程中断")
                return
            cb(f"✅ 下载完成: {Path(video_path).name}")
            set_progress(0.33, "步骤 1/3 完成 ✓")

            # Step 2: 转录
            set_progress(0.38, "步骤 2/3: 转录中...")
            engine = self.pl_engine.get()
            text = transcribe(video_path, engine=engine, callback=cb)
            cb(f"✅ 转录完成，共 {len(text)} 字")
            set_progress(0.66, "步骤 2/3 完成 ✓")

            # Step 3: 分析
            set_progress(0.70, "步骤 3/3: 分析中...")
            modules = [k for k, v in self.pl_modules.items() if v.get()]
            if modules:
                results = analyze(text, modules=modules, source_name=video_path, callback=cb)
                cb(f"✅ 分析完成")
            else:
                cb("跳过分析（未选择模块）")
            set_progress(1.0, "全流程完成 ✅")

            cb("=" * 40)
            cb("🎉 全流程完成！")
            cb(f"  下载: {DOWNLOAD_DIR}")
            cb(f"  转录: {TRANSCRIPT_DIR}")
            cb(f"  分析: {ANALYSIS_DIR}")

        except Exception as e:
            err_msg = str(e)
            cb(f"❌ 流程异常: {err_msg}")
            self.after(0, lambda m=err_msg: self.pl_status.configure(text=f"失败: {m}"))
        finally:
            self.after(0, lambda: self.pl_btn.configure(state="normal", text="🚀 开始全流程"))
            self.is_running = False
            self.pipeline_running = False


def main():
    app = VideoAgentApp()
    app.mainloop()


if __name__ == "__main__":
    main()
