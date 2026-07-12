# -*- coding: utf-8 -*-
"""
直播源/视频URL提取模块
支持：抖音直播/短视频、快手直播、B站直播
"""
import re
import os
import subprocess
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
UA_IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"


def extract_url(text):
    """从分享文案中提取 URL"""
    urls = re.findall(r'https?://[\w./?=&#%:@~_-]+', text)
    if urls:
        url = urls[-1].rstrip('，。！？,.!?')
        return url
    return None


def resolve_short_url(url):
    """解析短链接"""
    try:
        resp = requests.get(url, allow_redirects=True, headers={"User-Agent": UA}, timeout=10)
        return resp.url
    except Exception:
        return url


def is_live_url(url):
    """判断是否是直播链接"""
    return any(re.search(p, url) for p in [
        r"live\.douyin\.com/\d+",
        r"live\.kuaishou\.com",
        r"live\.bilibili\.com/\d+",
    ])


def detect_type(url):
    """判断链接类型: live_douyin / live_kuaishou / live_bilibili / video_douyin / unknown"""
    if "live.douyin.com" in url:
        return "live_douyin"
    if "live.kuaishou.com" in url or "v.kuaishou.com" in url or "f.kuaishou.com" in url:
        return "live_kuaishou"
    if "live.bilibili.com" in url:
        return "live_bilibili"
    if "douyin.com" in url or "v.douyin.com" in url:
        return "video_douyin"
    return "unknown"


# ═══════════════════════════════════════════
# 直播源提取
# ═══════════════════════════════════════════

def extract_douyin_live(url, callback=None):
    """提取抖音直播源"""
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": "https://live.douyin.com/"})

    if "v.douyin.com" in url:
        url = resolve_short_url(url)

    m = re.search(r"live\.douyin\.com/(\d+)", url)
    if not m:
        raise ValueError("无法提取抖音直播间ID")
    room_id = m.group(1)

    if callback:
        callback(f"抖音直播间: {room_id}")

    s.get(f"https://live.douyin.com/{room_id}", timeout=15)
    resp = s.get("https://live.douyin.com/webcast/room/web/enter/", params={
        "aid": "6383", "device_platform": "web",
        "browser_language": "zh-CN", "browser_platform": "Win32",
        "browser_name": "Chrome", "browser_version": "131.0.0.0",
        "web_rid": room_id,
    }, timeout=15)

    data = resp.json()
    rooms = data.get("data", {}).get("data", [])
    if not rooms or rooms[0].get("status") != 2:
        raise ValueError("未开播")

    flv = rooms[0].get("stream_url", {}).get("flv_pull_url", {})
    return [{"quality": q, "url": u, "type": "flv"} for q, u in flv.items()]


def extract_kuaishou_live(url, callback=None):
    """提取快手直播源"""
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": "https://live.kuaishou.com/"})

    if "v.kuaishou.com" in url or "f.kuaishou.com" in url:
        url = resolve_short_url(url)

    m = re.search(r"kuaishou\.com/(?:u/)?(\w+)", url)
    if not m:
        raise ValueError("无法提取快手ID")
    user_id = m.group(1)

    if callback:
        callback(f"快手主播: {user_id}")

    s.get("https://live.kuaishou.com/", timeout=10)
    resp = s.get(f"https://live.kuaishou.com/u/{user_id}", timeout=15)

    m = re.search(r'"liveStreamUrl"\s*:\s*"([^"]+)"', resp.text)
    if not m:
        raise ValueError("未开播或获取失败")
    stream_url = m.group(1).replace("\\u002F", "/")
    return [{"quality": "原画", "url": stream_url, "type": "flv"}]


def extract_bilibili_live(url, callback=None):
    """提取B站直播源"""
    h = {"User-Agent": UA, "Referer": "https://live.bilibili.com/"}

    m = re.search(r"bilibili\.com/(\d+)", url)
    if not m:
        raise ValueError("无法提取B站房间号")
    room_id = m.group(1)

    if callback:
        callback(f"B站直播间: {room_id}")

    info = requests.get(
        f"https://api.live.bilibili.com/room/v1/Room/get_info?room_id={room_id}",
        headers=h, timeout=10
    ).json()
    if info['code'] != 0 or info['data'].get('live_status') != 1:
        raise ValueError("未开播")

    play = requests.get(
        f"https://api.live.bilibili.com/room/v1/Room/playUrl?cid={room_id}&platform=web&quality=4",
        headers=h, timeout=10
    ).json()
    if play['code'] != 0:
        raise ValueError("获取失败")

    return [{"quality": "原画", "url": play['data']['durl'][0]['url'], "type": "flv"}]


# ═══════════════════════════════════════════
# 抖音短视频 URL 提取（不下载，只拿直链）
# ═══════════════════════════════════════════

def extract_douyin_video_url(url, callback=None):
    """通过移动端 share page 提取抖音短视频直链（纯requests）"""
    # 提取 video ID
    m = re.search(r'/video/(\d+)', url)
    if not m:
        m = re.search(r'/(\d{15,})', url)
    if not m:
        raise ValueError(f"无法提取视频ID: {url}")

    video_id = m.group(1)
    if callback:
        callback(f"视频ID: {video_id}")

    # 访问移动端 share page
    share_url = f"https://www.iesdouyin.com/share/video/{video_id}/"
    resp = requests.get(share_url, headers={"User-Agent": UA_IPHONE}, timeout=15)
    html = resp.text

    # 提取 play_addr URL
    m = re.search(r'"play_addr".*?"url_list"\s*:\s*\["([^"]+)"', html, re.DOTALL)
    if not m:
        m = re.search(r'"playAddr".*?"url_list"\s*:\s*\["([^"]+)"', html, re.DOTALL)
    if not m:
        raise ValueError("未找到视频地址（可能视频已删除或需要登录）")

    video_url = m.group(1).replace('\\u002F', '/')
    # 去水印
    video_url = video_url.replace('playwm', 'play')

    if callback:
        callback(f"视频地址已获取")

    return [{"quality": "视频", "url": video_url, "type": "mp4"}]


# ═══════════════════════════════════════════
# 统一入口
# ═══════════════════════════════════════════

def extract(raw_text, callback=None):
    """
    统一提取入口

    Args:
        raw_text: 用户输入的链接或分享文案
        callback: 进度回调

    Returns:
        list of dict: [{"quality": "xxx", "url": "xxx", "type": "flv/mp4"}]
    """
    # 从文案中提取 URL
    url = extract_url(raw_text)
    if not url:
        raise ValueError("未找到链接")

    if callback:
        callback(f"提取到链接: {url}")

    # 解析短链
    resolved = resolve_short_url(url)
    if resolved != url and callback:
        callback(f"解析为: {resolved}")

    # 判断类型
    link_type = detect_type(resolved)
    if link_type == "unknown":
        link_type = detect_type(url)

    if callback:
        callback(f"类型: {link_type}")

    if link_type == "live_douyin":
        return extract_douyin_live(url, callback)
    elif link_type == "live_kuaishou":
        return extract_kuaishou_live(url, callback)
    elif link_type == "live_bilibili":
        return extract_bilibili_live(url, callback)
    elif link_type == "video_douyin":
        return extract_douyin_video_url(resolved, callback)
    else:
        # 尝试抖音直播 → 视频
        try:
            return extract_douyin_live(url, callback)
        except ValueError:
            return extract_douyin_video_url(resolved, callback)


# ═══════════════════════════════════════════
# PotPlayer
# ═══════════════════════════════════════════

def find_potplayer():
    """查找 PotPlayer 可执行文件路径"""
    candidates = []
    for env in ["ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"]:
        base = os.environ.get(env, "")
        if base:
            for sub in ["", "PotPlayer", "DAUM/PotPlayer", "DAUM\\PotPlayer"]:
                for exe in ["PotPlayerMini64.exe", "PotPlayerMini.exe"]:
                    candidates.append(os.path.join(base, sub, exe))
    for drive in ["C", "D", "E"]:
        for sub in ["Program Files/DAUM/PotPlayer", "Program Files (x86)/DAUM/PotPlayer",
                    "Program Files/PotPlayer", "PotPlayer"]:
            for exe in ["PotPlayerMini64.exe", "PotPlayerMini.exe"]:
                candidates.append(f"{drive}:/{sub}/{exe}")
    try:
        import winreg
        for root_key in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            for sub in [r"SOFTWARE\PotPlayer", r"SOFTWARE\DAUM\PotPlayer"]:
                try:
                    key = winreg.OpenKey(root_key, sub)
                    val, _ = winreg.QueryValueEx(key, "InstallPath")
                    if val:
                        for exe in ["PotPlayerMini64.exe", "PotPlayerMini.exe"]:
                            candidates.append(os.path.join(val, exe))
                except Exception:
                    pass
    except ImportError:
        pass
    for p in os.environ.get("PATH", "").split(os.pathsep):
        for exe in ["PotPlayerMini64.exe", "PotPlayerMini.exe"]:
            candidates.append(os.path.join(p, exe))
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def open_in_potplayer(url):
    """用 PotPlayer 打开指定 URL"""
    exe = find_potplayer()
    if not exe:
        raise FileNotFoundError("未找到 PotPlayer，请确认已安装")
    subprocess.Popen([exe, url], shell=False)
    return exe
