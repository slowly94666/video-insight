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
    """读取 MiMo API 配置（用于 ASR 转录）"""
    key = clean_ascii(os.environ.get("API_KEY", ""))
    if key.startswith("tp-"):
        base = "https://token-plan-cn.xiaomimimo.com/v1"
    else:
        base = "https://api.xiaomimimo.com/v1"
    return key, base


# === LLM 提供商配置（支持切换模型） ===
# 在 .env 中设置 LLM_PROVIDER 切换提供商
# 支持：mimo（默认）、deepseek、openai、custom
LLM_PROVIDERS = {
    "mimo": {
        "env_key": "API_KEY",
        "base_url": None,  # 用 get_mimo_config() 判断
        "model": "mimo-v2.5-pro",
    },
    "deepseek": {
        "env_key": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "openai": {
        "env_key": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
    },
    "custom": {
        "env_key": "CUSTOM_API_KEY",
        "base_url": None,  # 从 CUSTOM_BASE_URL 环境变量读
        "model": None,     # 从 CUSTOM_MODEL 环境变量读
    },
}


def get_llm_config():
    """
    读取 LLM API 配置（支持多提供商切换）
    
    .env 示例：
      LLM_PROVIDER=deepseek        # 切换提供商
      DEEPSEEK_API_KEY=sk-xxxxx   # 对应的 API Key
    
    返回: (api_key, base_url, model)
    """
    provider = os.environ.get("LLM_PROVIDER", "mimo").lower()
    
    if provider not in LLM_PROVIDERS:
        raise ValueError(f"不支持的 LLM 提供商: {provider}，可选: {', '.join(LLM_PROVIDERS.keys())}")
    
    cfg = LLM_PROVIDERS[provider]
    
    # API Key
    key = clean_ascii(os.environ.get(cfg["env_key"], ""))
    if not key:
        raise ValueError(f"未设置 {cfg['env_key']} 环境变量，请在 .env 文件中配置")
    
    # Base URL
    if provider == "mimo":
        _, base = get_mimo_config()
    elif provider == "custom":
        base = os.environ.get("CUSTOM_BASE_URL", "")
        if not base:
            raise ValueError("使用 custom 提供商必须设置 CUSTOM_BASE_URL")
    else:
        base = cfg["base_url"]
    
    # Model
    if provider == "custom":
        model = os.environ.get("CUSTOM_MODEL", "")
        if not model:
            raise ValueError("使用 custom 提供商必须设置 CUSTOM_MODEL")
    else:
        model = cfg["model"]
    
    return key, base, model

# === 平台配置 ===
PLATFORMS = {
    "bilibili": {"name": "B站", "icon": "📺"},
    "douyin":   {"name": "抖音", "icon": "🎵"},
    "twitter":  {"name": "Twitter/X", "icon": "🐦"},
    "soop":     {"name": "SOOP (AfreecaTV)", "icon": "📡"},
}

# === ASR 引擎 ===
ASR_ENGINES = {
    "siliconflow": {"name": "SiliconFlow ASR", "desc": "SenseVoice，免费，国内直连"},
    "groq":    {"name": "Groq ASR", "desc": "极速 Whisper API（需代理）"},
    "gemini":  {"name": "Gemini ASR", "desc": "Google 云端（不稳定）"},
    "whisper": {"name": "Whisper", "desc": "本地免费，速度较慢"},
}

# === Gemini ASR 配置 ===
# 在 .env 中设置 GEMINI_API_KEY
# 可选：GEMINI_ASR_MODEL（默认 gemini-2.5-flash-lite）

def get_gemini_asr_config():
    """读取 Gemini ASR 配置"""
    key = clean_ascii(os.environ.get("GEMINI_API_KEY", ""))
    if not key:
        raise ValueError("未配置 GEMINI_API_KEY，请在 .env 文件中设置")
    model = os.environ.get("GEMINI_ASR_MODEL", "gemini-2.5-flash-lite")
    return key, model

# === Groq ASR 配置（Whisper API） ===
# 在 .env 中设置 GROQ_API_KEY
# 可选：GROQ_ASR_MODEL（默认 whisper-large-v3-turbo，另可选 whisper-large-v3）

def get_groq_asr_config():
    """读取 Groq ASR 配置"""
    key = clean_ascii(os.environ.get("GROQ_API_KEY", ""))
    if not key:
        raise ValueError("未配置 GROQ_API_KEY，请在 .env 文件中设置")
    model = os.environ.get("GROQ_ASR_MODEL", "whisper-large-v3-turbo")
    return key, model


# === SiliconFlow ASR（SenseVoice，国内直连） ===
# 在 .env 中设置 SILICONFLOW_API_KEY
# 模型固定 FunAudioLLM/SenseVoiceSmall

def get_siliconflow_asr_config():
    """读取 SiliconFlow ASR 配置"""
    key = clean_ascii(os.environ.get("SILICONFLOW_API_KEY", ""))
    if not key:
        raise ValueError("未配置 SILICONFLOW_API_KEY，请在 .env 文件中设置")
    return key, "FunAudioLLM/SenseVoiceSmall"


# === 分析模块 ===
ANALYSIS_MODULES = {
    "summarizer": {"name": "总结要点", "desc": "总结核心内容，生成大纲"},
    "extractor":  {"name": "提取关键信息", "desc": "提取关键点、实体、关键词"},
    "quality":    {"name": "质量评估", "desc": "评估内容质量与可信度"},
}
