# 视频Agent

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
git clone https://github.com/your-username/video-agent.git
cd video-agent
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
python install.py
```
`install.py` 会自动下载 yt-dlp 和 ffmpeg 到 `bin/` 目录。

### 3. 配置 API Key
```bash
# 复制配置模板
copy .env.example .env
# 编辑 .env，填入你的 MiMo API Key
```

### 4. 启动
```bash
python gui.py
```
Windows 用户也可以双击 `setup.bat` 一键完成安装。

## 目录结构

```
video-agent/
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

## 依赖

- Python 3.9+
- ffmpeg / ffprobe（install.py 自动下载）
- yt-dlp（install.py 自动下载）
- MiMo API Key（[获取地址](https://xiaomimimo.com)）

## 平台说明

| 平台 | 下载方式 | 备注 |
|------|----------|------|
| B站 | yt-dlp | 支持番剧/普通视频 |
| 抖音 | Playwright/DT-Scraper | 需要安装 patchright |
| Twitter/X | yt-dlp | 需要 cookies（可选） |
| SOOP | yt-dlp + 代理 | 需要配置代理 |
