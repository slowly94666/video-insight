# -*- coding: utf-8 -*-
"""
视频下载模块
封装 B站/抖音/Twitter/SOOP 的下载逻辑
"""
import os
import re
import subprocess
from pathlib import Path
from config import YTDLP, DOWNLOAD_DIR


def detect_platform(url: str) -> str:
    """自动检测平台"""
    url = url.lower().strip()
    if 'bilibili.com' in url or 'b23.tv' in url:
        return 'bilibili'
    if 'douyin.com' in url or 'v.douyin.com' in url:
        return 'douyin'
    if 'x.com' in url or 'twitter.com' in url:
        return 'twitter'
    if 'soop' in url or 'afreecatv' in url or 'afreeca' in url:
        return 'soop'
    return 'unknown'


def download_bilibili(url: str, save_dir: str, callback=None) -> str:
    """下载B站视频"""
    cmd = [
        YTDLP,
        "-f", "bestvideo+bestaudio/best",
        "--merge-output-format", "mp4",
        "-o", os.path.join(save_dir, "%(title)s.%(ext)s"),
        "--no-check-certificate",
        url
    ]
    return _run_ytdlp(cmd, save_dir, callback)


def download_douyin(url: str, save_dir: str, callback=None) -> str:
    """下载抖音视频"""
    try:
        from lib_douyin import download_douyin as _dl, resolve_short_url
    except ImportError:
        if callback:
            callback("错误: 无法导入抖音下载模块")
        return None

    os.makedirs(save_dir, exist_ok=True)
    if callback:
        callback("正在解析抖音链接...")

    resolved = resolve_short_url(url)
    if callback:
        callback(f"解析结果: {resolved}")

    success = _dl(resolved, save_dir)
    if success:
        return _find_latest_file(save_dir, '.mp4')
    return None


def download_twitter(url: str, save_dir: str, callback=None) -> str:
    """下载 Twitter/X 视频"""
    cmd = [
        YTDLP,
        "-f", "bestvideo+bestaudio/best",
        "--merge-output-format", "mp4",
        "-o", os.path.join(save_dir, "%(title)s.%(ext)s"),
        "--no-check-certificate",
        url
    ]
    return _run_ytdlp(cmd, save_dir, callback)


def download_soop(url: str, save_dir: str, callback=None) -> str:
    """下载 SOOP (AfreecaTV) 视频"""
    cmd = [
        YTDLP,
        "--proxy", "http://127.0.0.1:10808",
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "-f", "bestvideo+bestaudio/best",
        "-o", os.path.join(save_dir, "%(title)s.%(ext)s"),
        "--no-check-certificate",
        "--extractor-args", "afreecatv:all",
        url
    ]
    return _run_ytdlp(cmd, save_dir, callback)


# === 统一入口 ===

DOWNLOADERS = {
    'bilibili': download_bilibili,
    'douyin':   download_douyin,
    'twitter':  download_twitter,
    'soop':     download_soop,
}


def download(url: str, platform: str = None, save_dir: str = None, callback=None) -> str:
    """
    统一下载入口

    Args:
        url: 视频链接
        platform: 平台名（None=自动检测）
        save_dir: 保存目录（None=默认）
        callback: 进度回调 callback(msg: str)

    Returns:
        下载的文件路径，失败返回 None
    """
    if not save_dir:
        save_dir = str(DOWNLOAD_DIR)
    os.makedirs(save_dir, exist_ok=True)

    if not platform:
        platform = detect_platform(url)

    if platform not in DOWNLOADERS:
        if callback:
            callback(f"不支持的平台: {platform}")
        return None

    if callback:
        callback(f"平台: {platform} | 保存到: {save_dir}")

    return DOWNLOADERS[platform](url, save_dir, callback)


# === 工具函数 ===

def _run_ytdlp(cmd: list, save_dir: str, callback=None) -> str:
    """运行 yt-dlp 命令并跟踪输出"""
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        for line in proc.stdout:
            line = line.strip()
            if line and callback:
                callback(line)
        proc.wait()

        if proc.returncode == 0:
            return _find_latest_file(save_dir, '.mp4')
        else:
            if callback:
                callback(f"下载失败 (exit code: {proc.returncode})")
            return None
    except FileNotFoundError:
        if callback:
            callback(f"错误: yt-dlp 未找到，请先运行 install.py 安装依赖")
        return None
    except Exception as e:
        if callback:
            callback(f"下载异常: {e}")
        return None


def _find_latest_file(directory: str, ext: str) -> str:
    """找到目录下最新指定扩展名的文件"""
    files = list(Path(directory).glob(f"*{ext}"))
    if not files:
        return None
    latest = max(files, key=lambda f: f.stat().st_mtime)
    return str(latest)
