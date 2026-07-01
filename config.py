# -*- coding: utf-8 -*-
"""
视频Agent - 统一配置
自包含版本，不依赖外部目录
"""
import os
from pathlib import Path

# === 路径配置 ===
AGENT_DIR = Path(__file__).parent
BIN_DIR = AGENT_DIR / "bin"

# 输出目录
DOWNLOAD_DIR = AGENT_DIR / "downloads"
TRANSCRIPT_DIR = AGENT_DIR / "transcripts"
ANALYSIS_DIR = AGENT_DIR / "analysis"

for d in [DOWNLOAD_DIR, TRANSCRIPT_DIR, ANALYSIS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# === 工具路径 ===
def _find_bin(name):
    """在 bin/ 目录或系统 PATH 中查找可执行文件"""
    local = BIN_DIR / name
    if local.exists():
        return str(local)
    # fallback: 系统 PATH
    import shutil
    found = shutil.which(name.replace(".exe", ""))
    return found or str(local)

YTDLP = _find_bin("yt-dlp.exe")
FFMPEG = _find_bin("ffmpeg.exe")
FFPROBE = _find_bin("ffprobe.exe")

# === .env 配置 ===
def _load_env():
    """从 .env 文件加载环境变量（不覆盖已有的）"""
    env_file = AGENT_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding='utf-8', errors='ignore').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            key, val = line.split('=', 1)
            key, val = key.strip(), val.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = val

_load_env()

def clean_ascii(text):
    """过滤非 ASCII 字符"""
    if not text:
        return ""
    return text.encode('ascii', 'ignore').decode('ascii').strip()

def get_mimo_config():
    """读取 MiMo API 配置"""
    key = clean_ascii(os.environ.get("MIMO_API_KEY", ""))
    if key.startswith("tp-"):
        base = "https://token-plan-cn.xiaomimimo.com/v1"
    else:
        base = "https://api.xiaomimimo.com/v1"
    return key, base

# === 平台配置 ===
PLATFORMS = {
    "bilibili": {"name": "B站", "icon": "📺"},
    "douyin":   {"name": "抖音", "icon": "🎵"},
    "twitter":  {"name": "Twitter/X", "icon": "🐦"},
    "soop":     {"name": "SOOP (AfreecaTV)", "icon": "📡"},
}

# === ASR 引擎 ===
ASR_ENGINES = {
    "mimo":   {"name": "MiMo ASR", "desc": "云端快速，需要 API Key"},
    "whisper": {"name": "Whisper", "desc": "本地免费，速度较慢"},
}

# === 分析模块 ===
ANALYSIS_MODULES = {
    "summarizer": {"name": "总结要点", "desc": "总结核心内容，生成大纲"},
    "extractor":  {"name": "提取关键信息", "desc": "提取关键点、实体、关键词"},
    "quality":    {"name": "质量评估", "desc": "评估内容质量与可信度"},
}
