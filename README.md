# Video Insight — 视频洞察

一站式视频工具：下载 → 语音转录 → 文案分析。

## 架构

```
启动视频Agent.pyw          ← 入口（Windows 双击启动）
│
├── gui_tk.py              ← GUI 层（tkinter 单页布局）
│   ├── 6 个功能按钮：全流程 / 仅下载 / 转录文件 / 分析文本 / 直播源 / 停止
│   ├── 5 种报告格式：完整 / 精简 / 核查 / 批注 / 一图
│   └── 双栏输出：左=转录文本，右=分析报告
│
├── operation.py           ← 操作抽象层（线程管理 / 互斥 / 取消）
├── theme.py               ← 主题色彩管理（LIGHT / DARK 预设）
│
├── downloader.py          ← 统一下载层
│   ├── B站 / Twitter / SOOP → yt-dlp 子进程
│   └── 抖音 → lib_douyin（DT-Scraper → Playwright 无头 → 有头）
│
├── lib_douyin.py          ← 抖音专用下载引擎（三层回退）
├── transcriber.py         ← 语音转录层
│   └── 4 引擎：SiliconFlow SenseVoice / Groq Whisper / Gemini / 本地 Whisper
│
├── analyzer.py            ← LLM 分析层（DeepSeek / OpenAI / 自定义）
├── agent.py               ← ReAct Agent 层（CLI 自主规划模式）
├── live.py                ← 直播源提取（抖音 / 快手 / B站）
│
├── config.py              ← 配置中心（.env 加载 + 多提供商切换）
├── install.py             ← 依赖安装（自动下载 yt-dlp + ffmpeg）
├── setup.bat              ← Windows 一键安装脚本
│
├── bin/                   ← 二进制工具（yt-dlp, ffmpeg, ffprobe — install.py 下载）
├── downloads/             ← 下载的视频
├── transcripts/           ← 转录文本（.txt）
└── analysis/              ← 分析报告（.md）
```

## 数据流

```
URL 输入 → detect_platform() → download() → .mp4 文件
  → extract_audio() → transcribe() → 文本
  → analyze_unified() → parse_sections() → 结构化报告
```

## 新机部署

```bash
# 1. 克隆
git clone https://github.com/slowly94666/video-insight.git
cd video-insight

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 下载二进制工具（yt-dlp + ffmpeg + ffprobe）
python install.py

# 4. 安装抖音下载引擎（二选一）
pip install patchright && patchright install chromium
# 或
pip install playwright && playwright install chromium

# 5. 配置 API Key
copy .env.example .env
# 编辑 .env，至少填写 LLM 和 ASR 的 API Key

# 6. 启动
python gui_tk.py
# 或双击「启动视频Agent.pyw」
```

> **注意**：`bin/` 不在 Git 仓库中，**必须运行 `python install.py`** 下载，否则下载和转录功能全部不可用。

## 功能矩阵

| 功能 | 支持平台 / 引擎 | 说明 |
|------|--------------|------|
| 📥 下载 | B站 / 抖音 / Twitter / SOOP | 粘贴链接，自动检测平台 |
| 🎙 转录 | SiliconFlow / Groq / Gemini / Whisper | 4 引擎可选，GUI 内切换 |
| 🧠 分析 | DeepSeek / OpenAI / 自定义 | 5 种报告格式切换 |
| 📺 直播源 | 抖音 / 快手 / B站 | 提取直播流地址，一键 PotPlayer 播放 |
| ⚡ 全流程 | 下载 → 转录 → 分析 | 一键完成 |

## 环境变量（.env）

```env
# LLM 提供商（deepseek / openai / custom）
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxx

# ASR 引擎（在 GUI 中切换，按需配置 Key）
SILICONFLOW_API_KEY=sk-xxx   # 首选，国内直连
GEMINI_API_KEY=xxx           # 备选
GROQ_API_KEY=xxx             # 备选（需代理）
API_KEY=tp-xxx               # MiMo（旧，已过期）
```

## 依赖清单

| 依赖 | 用途 | 安装方式 |
|------|------|----------|
| Python 3.10+ | 运行环境 | [python.org](https://www.python.org/) |
| requests | HTTP 请求 | `pip install requests` |
| python-dotenv | .env 加载 | `pip install python-dotenv` |
| yt-dlp | B站/Twitter/SOOP 下载 | `python install.py` |
| ffmpeg / ffprobe | 音频提取 | `python install.py` |
| patchright / playwright | 抖音下载引擎 | `pip install patchright && patchright install chromium` |
| openai-whisper | 本地转录（可选） | `pip install openai-whisper` |