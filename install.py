# -*- coding: utf-8 -*-
"""
视频Agent - 依赖安装脚本
自动下载 yt-dlp 和 ffmpeg 到 bin/ 目录
"""
import os
import sys
import urllib.request
import zipfile
import shutil
import subprocess
from pathlib import Path

BIN_DIR = Path(__file__).parent / "bin"
BIN_DIR.mkdir(exist_ok=True)

IS_WINDOWS = sys.platform == "win32"


def download_file(url, dest):
    """下载文件并显示进度"""
    print(f"  下载: {url}")
    urllib.request.urlretrieve(url, dest)
    print(f"  保存到: {dest}")


def install_ytdlp():
    """安装 yt-dlp"""
    print("\n[1/3] 安装 yt-dlp...")
    if IS_WINDOWS:
        dest = BIN_DIR / "yt-dlp.exe"
        if dest.exists():
            print(f"  已存在: {dest}")
            return True
        url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
        try:
            download_file(url, dest)
            return True
        except Exception as e:
            print(f"  下载失败: {e}")
            print("  备选方案: pip install yt-dlp")
            return False
    else:
        # Linux/Mac: 用 pip
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "yt-dlp"], check=True)
            print("  yt-dlp 已通过 pip 安装")
            return True
        except Exception as e:
            print(f"  安装失败: {e}")
            return False


def install_ffmpeg():
    """安装 ffmpeg"""
    print("\n[2/3] 安装 ffmpeg...")
    if IS_WINDOWS:
        exe = BIN_DIR / "ffmpeg.exe"
        probe = BIN_DIR / "ffprobe.exe"
        if exe.exists() and probe.exists():
            print(f"  已存在: {exe}")
            return True

        # 下载 ffmpeg essentials zip
        url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        zip_path = BIN_DIR / "ffmpeg.zip"
        try:
            download_file(url, zip_path)
            print("  解压中...")
            with zipfile.ZipFile(zip_path, 'r') as z:
                for name in z.namelist():
                    if name.endswith("ffmpeg.exe"):
                        with z.open(name) as src, open(exe, 'wb') as dst:
                            dst.write(src.read())
                    elif name.endswith("ffprobe.exe"):
                        with z.open(name) as src, open(probe, 'wb') as dst:
                            dst.write(src.read())
            zip_path.unlink()
            print(f"  ffmpeg 已安装到: {BIN_DIR}")
            return True
        except Exception as e:
            print(f"  自动安装失败: {e}")
            print("  请手动下载 ffmpeg 并把 ffmpeg.exe / ffprobe.exe 放到 bin/ 目录")
            print("  下载地址: https://www.gyan.dev/ffmpeg/builds/")
            return False
    else:
        # Linux/Mac: 提示用包管理器
        print("  请用包管理器安装:")
        print("    Ubuntu/Debian: sudo apt install ffmpeg")
        print("    Mac: brew install ffmpeg")
        return True


def install_python_deps():
    """安装 Python 依赖"""
    print("\n[3/3] 安装 Python 依赖...")
    req_file = Path(__file__).parent / "requirements.txt"
    if req_file.exists():
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(req_file)])
    else:
        subprocess.run([sys.executable, "-m", "pip", "install",
                        "customtkinter", "requests", "openai-whisper"])


def main():
    print("=" * 50)
    print("  视频Agent - 依赖安装")
    print("=" * 50)

    install_python_deps()
    install_ytdlp()
    install_ffmpeg()

    print("\n" + "=" * 50)
    print("  安装完成！")
    print(f"  工具目录: {BIN_DIR}")
    print("=" * 50)

    # 检查 .env
    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        print("\n提示: 请创建 .env 文件并配置 API Key:")
        print("  API_KEY=your_key_here")
        print("  (复制 .env.example 并填入你的 key)")


if __name__ == "__main__":
    main()
