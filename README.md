# 视频洞察 (video-insight)

一站式视频下载 → 语音转录 → 文案分析工具。

## 功能

| 步骤 | 功能 | 说明 |
|------|------|------|
| 📥 下载 | B站/抖音/Twitter/SOOP | 自动检测平台，粘贴链接即下 |
| 🎙 转录 | MiMo ASR / Whisper | 云端快速或本地免费 |
| 📊 分析 | 总结/提取/质量评估 | AI 驱动的文案分析 |
| ⚡ 全流程 | 下载→转录→分析 | 一键完成，自动生成报告 |

## 快速开始

### 1. 克隆项目
```bash
git clone https://github.com/slowly94666/video-insight.git
cd video-insight
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
python install.py
```
`install.py` 会自动下载 yt-dlp 和 ffmpeg 到 `bin/` 目录。

### 3. 配置 API Key
```bash
copy .env.example .env
# 编辑 .env，填入你的 API Key
```

### 4. 启动
```bash
python gui.py
```
Windows 用户也可以双击 `setup.bat` 一键完成安装。

## 完整依赖清单

| 依赖 | 用途 | 安装方式 |
|------|------|----------|
| Python 3.9+ | 运行环境 | [python.org](https://www.python.org/) |
| ffmpeg / ffprobe | 音频提取、视频合并 | `python install.py` 自动下载 |
| yt-dlp | B站/Twitter/SOOP 下载 | `python install.py` 自动下载 |
| requests | API 调用 | `pip install requests` |
| customtkinter | GUI 界面 | `pip install customtkinter` |
| patchright（可选）| 抖音下载（反检测浏览器）| `pip install patchright && patchright install chromium` |
| playwright（可选）| 抖音下载备选方案 | `pip install playwright && playwright install chromium` |
| openai-whisper（可选）| Whisper 本地转录 | `pip install openai-whisper` |

> **抖音下载说明**：优先用 patchright（反检测更强），没有则用 playwright，都没有则尝试 DT-Scraper。三个都没有会报错。
>
> **Whisper 说明**：仅在选择 Whisper 引擎时需要，默认用 MiMo ASR（云端，无需额外安装）。

## 目录结构

```
video-insight/
├── gui.py              # 统一 GUI
├── config.py           # 配置管理
├── downloader.py       # 视频下载
├── transcriber.py      # 语音转录
├── analyzer.py         # 文案分析
├── lib_douyin.py       # 抖音下载引擎
├── install.py          # 依赖安装脚本
├── setup.bat           # Windows 一键安装
├── .env.example        # API Key 模板
├── requirements.txt    # Python 依赖
├── bin/                # 工具（yt-dlp/ffmpeg，自动下载）
├── downloads/          # 下载的视频
├── transcripts/        # 转录文本
└── analysis/           # 分析报告
```
