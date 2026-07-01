# -*- coding: utf-8 -*-
"""
转录模块
封装音频提取 + ASR 转录（MiMo 分段 / Whisper 本地）
"""
import os
import subprocess
import tempfile
import base64
import requests
from pathlib import Path
from config import FFMPEG, FFPROBE, get_mimo_config, TRANSCRIPT_DIR


# === 音频提取 ===

def extract_audio(video_path: str, output_path: str = None) -> str:
    """从视频提取音频（mp3 128k）"""
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"视频文件不存在: {video_path}")

    if output_path is None:
        output_path = video_path.parent / f"{video_path.stem}.mp3"
    output_path = Path(output_path)

    cmd = [
        FFMPEG, "-i", str(video_path),
        "-vn", "-acodec", "libmp3lame",
        "-ab", "128k", "-ar", "44100",
        "-y", str(output_path)
    ]
    subprocess.run(cmd, capture_output=True, text=True,
                   encoding='utf-8', errors='ignore', check=True)
    return str(output_path)


def get_duration(media_path: str) -> float:
    """获取媒体时长（秒）"""
    cmd = [
        FFPROBE, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(media_path)
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding='utf-8', errors='ignore', check=True)
        return float(r.stdout.strip())
    except:
        return 0.0


# === MiMo ASR（带分段） ===

CHUNK_MAX_BYTES = 2 * 1024 * 1024  # 2MB


def _mimo_transcribe_single(audio_path: str, api_key: str, api_base: str) -> str:
    """转录单个音频片段"""
    with open(audio_path, 'rb') as f:
        audio_b64 = base64.b64encode(f.read()).decode('ascii')

    url = f"{api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mimo-v2.5-asr",
        "messages": [{
            "role": "user",
            "content": [{
                "type": "input_audio",
                "input_audio": {"data": audio_b64, "format": "mp3"}
            }]
        }]
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"MiMo ASR HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()["choices"][0]["message"]["content"].strip()


def _split_audio(audio_path: str, chunk_duration: float) -> list:
    """按时长切分音频，返回分段路径列表"""
    duration = get_duration(audio_path)
    if duration <= 0:
        return [audio_path]

    tmp_dir = tempfile.mkdtemp()
    chunks = []
    start = 0.0
    idx = 0
    ext = Path(audio_path).suffix

    while start < duration:
        chunk_path = os.path.join(tmp_dir, f"chunk_{idx:03d}{ext}")
        cmd = [
            FFMPEG, "-y", "-i", audio_path,
            "-ss", str(start), "-t", str(chunk_duration),
            "-acodec", "copy", chunk_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        if os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 0:
            chunks.append(chunk_path)
        start += chunk_duration
        idx += 1

    return chunks


def transcribe_mimo(audio_path: str, callback=None) -> str:
    """MiMo ASR 转录（大文件自动分段）"""
    api_key, api_base = get_mimo_config()
    if not api_key:
        raise ValueError("未配置 MIMO_API_KEY，请在 .env 文件中设置")

    audio_path = str(audio_path)
    file_size = os.path.getsize(audio_path)

    # 小文件直接转录
    if file_size <= CHUNK_MAX_BYTES:
        if callback:
            callback("MiMo ASR 转录中...")
        text = _mimo_transcribe_single(audio_path, api_key, api_base)
        if callback:
            callback("✓ 转录完成")
        return text

    # 大文件分段
    duration = get_duration(audio_path)
    chunk_duration = max((CHUNK_MAX_BYTES / file_size) * duration * 0.9, 30.0)
    n_chunks = int(duration / chunk_duration) + 1

    if callback:
        callback(f"音频 {file_size / 1024 / 1024:.1f}MB，分 {n_chunks} 段转录...")

    chunks = _split_audio(audio_path, chunk_duration)
    texts = []

    for i, chunk in enumerate(chunks):
        if callback:
            callback(f"  转录第 {i + 1}/{len(chunks)} 段...")
        t = _mimo_transcribe_single(chunk, api_key, api_base)
        texts.append(t)
        try:
            os.remove(chunk)
        except:
            pass

    if callback:
        callback(f"✓ 转录完成（共 {len(chunks)} 段）")
    return "\n".join(texts)


# === Whisper 本地转录 ===

def transcribe_whisper(audio_path: str, model: str = "medium", language: str = "zh", callback=None) -> str:
    """Whisper 本地转录"""
    try:
        import whisper
    except ImportError:
        raise ImportError("请先安装 openai-whisper: pip install openai-whisper")

    if callback:
        callback(f"Whisper ({model}) 加载模型...")
    m = whisper.load_model(model)
    if callback:
        callback("转录中...")
    result = m.transcribe(str(audio_path), language=language)
    if callback:
        callback("✓ 转录完成")
    return result["text"]


# === 统一入口 ===

def transcribe(video_path: str, engine: str = "mimo", callback=None) -> str:
    """
    统一转录入口：提取音频 → ASR → 返回文本

    Args:
        video_path: 视频文件路径
        engine: "mimo" 或 "whisper"
        callback: 进度回调

    Returns:
        转录的文本
    """
    if callback:
        callback("正在提取音频...")

    audio_path = extract_audio(video_path)

    try:
        if engine == "mimo":
            text = transcribe_mimo(audio_path, callback)
        else:
            text = transcribe_whisper(audio_path, callback=callback)
    finally:
        try:
            os.remove(audio_path)
        except:
            pass

    # 保存转录结果
    video_name = Path(video_path).stem
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = TRANSCRIPT_DIR / f"{video_name}_{ts}.txt"
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(text)

    if callback:
        callback(f"转录已保存: {out_file.name}")

    return text
