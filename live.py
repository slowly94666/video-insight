# -*- coding: utf-8 -*-
"""
直播源/视频URL提取模块
支持：抖音直播/短视频、快手直播、B站直播
"""
import re
import os
import sys
import json
import time
import subprocess
import requests

try:
    from config import YTDLP
except Exception:
    YTDLP = None

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

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
    if re.search(r"bilibili\.com/video/(BV[\w]+|av\d+)", url):
        return "video_bilibili"
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
    """抖音短视频直链：share page → yt-dlp(浏览器cookies) → patchright/playwright 浏览器抓取"""
    # 提取 video ID
    m = re.search(r'/video/(\d+)', url)
    if not m:
        m = re.search(r'/(\d{15,})', url)
    if not m:
        raise ValueError(f"无法提取视频ID: {url}")

    video_id = m.group(1)
    if callback:
        callback(f"视频ID: {video_id}")

    # ① 移动端 share page（最快，抖音未启用反爬时可用）
    try:
        resp = requests.get(
            f"https://www.iesdouyin.com/share/video/{video_id}/",
            headers={"User-Agent": UA_IPHONE}, timeout=15)
        html = resp.text
        for pat in (
            r'"play_addr".*?"url_list"\s*:\s*\["([^"]+)"',
            r'"playAddr".*?"url_list"\s*:\s*\["([^"]+)"',
            r'"playApi"\s*:\s*"([^"]+)"',
        ):
            m = re.search(pat, html, re.DOTALL)
            if m:
                video_url = m.group(1).replace('\\u002F', '/').replace('playwm', 'play')
                if callback:
                    callback("✓ 移动端 share page 提取成功")
                return [{"quality": "视频", "url": video_url, "type": "mp4"}]
    except Exception as e:
        if callback:
            callback(f"share page 提取异常: {e}")

    # ② yt-dlp 直链（自动借用 Chrome/Edge cookies）
    video_url = _extract_douyin_via_ytdlp(url, callback)
    if video_url:
        return [{"quality": "视频", "url": video_url, "type": "mp4"}]

    # ③ patchright/playwright 无头浏览器抓取
    video_url = _capture_douyin_playwright(url, callback)
    if video_url:
        if callback:
            callback("✓ 浏览器抓取成功")
        return [{"quality": "视频", "url": video_url, "type": "mp4"}]

    raise ValueError(
        "未找到视频地址：抖音已启用反爬，分享页/API 直连已失效。\n"
        "请确认已运行 patchright install chromium（或 playwright install chromium），"
        "并在 Chrome/Edge 中打开过一次抖音后重试。")


def _extract_douyin_via_ytdlp(url, callback=None):
    """yt-dlp 获取抖音直链：依次尝试 cookies 文件 / Chrome / Edge"""
    if not YTDLP:
        return None
    attempts = []
    ytdlp_dir = os.path.dirname(YTDLP)
    cookies_file = os.path.join(ytdlp_dir, "cookies_bili.txt")
    if os.path.isfile(cookies_file):
        attempts.append(("cookies文件", ["--cookies", cookies_file]))
    attempts.append(("Chrome", ["--cookies-from-browser", "chrome"]))
    attempts.append(("Edge", ["--cookies-from-browser", "edge"]))
    for label, extra in attempts:
        try:
            if callback:
                callback(f"yt-dlp 尝试 {label} cookies ...")
            cmd = [YTDLP, "--get-url", "--no-playlist", "--no-warnings",
                   "--no-check-certificate"] + extra + [url]
            p = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=60, encoding="utf-8", errors="ignore",
                               creationflags=CREATE_NO_WINDOW)
            out = (p.stdout or "").strip().splitlines()
            if p.returncode == 0 and out and out[0].startswith("http"):
                if callback:
                    callback(f"✓ yt-dlp({label}) 提取成功")
                return out[0].strip().replace("playwm", "play")
            err = (p.stderr or "").strip().splitlines()
            if callback:
                callback(f"yt-dlp({label}) 失败: {err[-1][:120] if err else p.returncode}")
        except Exception as e:
            if callback:
                callback(f"yt-dlp({label}) 异常: {e}")
    return None


def _capture_douyin_playwright(url, callback=None):
    """用 patchright/playwright 无头浏览器打开页面，拦截 aweme/detail 接口拿直链"""
    try:
        import patchright.sync_api as pw
    except ImportError:
        try:
            from playwright import sync_api as pw
        except ImportError:
            if callback:
                callback("未安装 patchright/playwright，跳过浏览器抓取")
            return None
    if callback:
        callback("启动无头浏览器抓取（约 10-30 秒）...")
    video_url, missing = _douyin_browser_capture(pw, url, callback)
    if not video_url and missing:
        if _install_patchright_browser(callback):
            if callback:
                callback("浏览器内核已就绪，重新抓取...")
            video_url, _ = _douyin_browser_capture(pw, url, callback)
    return video_url


def _douyin_browser_capture(pw, url, callback=None):
    """真正启动浏览器抓取直链；返回 (video_url, browser_missing)"""
    try:
        with pw.sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"])
            context = browser.new_context(
                user_agent=UA,
                viewport={"width": 1280, "height": 720},
                locale="zh-CN")
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
            page = context.new_page()
            video_url = _douyin_playwright_capture(page, url, callback)
            browser.close()
            return video_url, False
    except Exception as e:
        if callback:
            callback(f"无头浏览器失败: {e}")
        msg = str(e).lower()
        missing = ("executable doesn't exist" in msg
                   or "please run the following command" in msg
                   or "browser executable" in msg)
        return None, missing


def _douyin_playwright_capture(page, url, callback=None):
    """等待并捕获抖音视频直链"""
    captured = {"video": None, "audio": None, "detail": {}}

    def on_response(response):
        try:
            resp_url = response.url
            ct = response.headers.get("content-type", "")
            if "aweme/v1/web/aweme/detail" in resp_url and response.status == 200:
                body = response.body()
                if body and len(body) > 10:
                    data = json.loads(body)
                    detail = data.get("aweme_detail", {}) or {}
                    if detail:
                        captured["detail"] = detail
                        captured["video"] = _douyin_pick_best_url(detail)
            if "video/mp4" in ct and response.status in (200, 206):
                if "media-video" in resp_url and not captured["video"]:
                    captured["video"] = resp_url
                elif "media-audio" in resp_url:
                    captured["audio"] = resp_url
        except Exception:
            pass

    page.on("response", on_response)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        if callback:
            callback(f"页面打开异常: {e}")

    if callback:
        callback("等待视频地址...")
    for _ in range(25):
        time.sleep(1)
        if captured["video"]:
            break
        try:
            src = page.evaluate("""() => {
                const v = document.querySelector('video');
                return v ? (v.src || v.currentSrc || '') : '';
            }""")
            if src and src.startswith("http") and "uuu_265" not in src:
                captured["video"] = src
                break
        except Exception:
            pass
    video_url = captured["video"]
    return video_url.replace("playwm", "play") if video_url else None


def _douyin_pick_best_url(detail):
    """从 aweme/detail 数据里挑最高码率无水印直链"""
    video = detail.get("video", {}) or {}
    bit_rate_list = video.get("bit_rate", []) or []
    if bit_rate_list:
        bit_rate_list.sort(key=lambda x: x.get("bit_rate", 0), reverse=True)
        for br in bit_rate_list:
            urls = (br.get("play_addr", {}) or {}).get("url_list", []) or []
            if urls:
                return urls[0]
    urls = (video.get("play_addr", {}) or {}).get("url_list", []) or []
    return urls[0] if urls else None


def _install_patchright_browser(callback=None):
    """首次使用自动下载 Chromium 内核（约 150MB），失败时切 npmmirror 镜像重试"""
    if callback:
        callback("未检测到浏览器内核，开始自动下载 Chromium（约 150MB，仅首次）...")
    commands = [
        ([sys.executable, "-m", "patchright", "install", "chromium"], None),
        ([sys.executable, "-m", "patchright", "install", "chromium"],
         "https://cdn.npmmirror.com/binaries/playwright"),
        ([sys.executable, "-m", "playwright", "install", "chromium"],
         "https://cdn.npmmirror.com/binaries/playwright"),
    ]
    for cmd, mirror in commands:
        try:
            env = os.environ.copy()
            if mirror:
                env["PLAYWRIGHT_DOWNLOAD_HOST"] = mirror
            if callback:
                callback("运行: " + " ".join(cmd))
            p = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=600, encoding="utf-8", errors="ignore",
                               env=env, creationflags=CREATE_NO_WINDOW)
            tail = ((p.stdout or "") + (p.stderr or "")).strip().splitlines()[-5:]
            for line in tail:
                if line.strip() and callback:
                    callback("  " + line.strip()[:120])
            if p.returncode == 0:
                if callback:
                    callback("✓ Chromium 安装完成")
                return True
            if callback:
                callback(f"安装未成功(exit={p.returncode})，换下一个方案")
        except subprocess.TimeoutExpired:
            if callback:
                callback("安装超时（网络慢？），换下一个方案")
        except Exception as e:
            if callback:
                callback(f"安装异常: {e}")
    if callback:
        callback("自动安装失败，请手动在 PowerShell 运行: patchright install chromium")
    return False


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

def extract_video(raw_text, callback=None):
    """提取短视频直链：抖音短视频（三层回退） / B站视频（yt-dlp 标题）"""
    url = extract_url(raw_text)
    if not url:
        raise ValueError("未找到链接")
    if callback:
        callback(f"提取到链接: {url}")

    resolved = resolve_short_url(url)
    if resolved != url and callback:
        callback(f"展开为: {resolved}")

    link_type = detect_type(resolved)
    if link_type == "unknown":
        link_type = detect_type(url)
    if callback:
        callback(f"类型: {link_type}")

    if link_type == "video_douyin":
        return extract_douyin_video_url(resolved, callback)
    if link_type == "video_bilibili":
        return extract_bilibili_video(resolved, callback)
    raise ValueError(f"暂不支持该链接的视频源提取: {link_type}")


def extract_bilibili_video(url, callback=None):
    """B站视频：yt-dlp 取标题，直链需 cookies/Referer，返回页面地址供复制/下载"""
    if not YTDLP:
        raise ValueError("未找到 yt-dlp")
    title = "B站视频"
    try:
        cmd = [YTDLP, "--get-title", "--no-playlist"]
        ytdlp_dir = os.path.dirname(YTDLP)
        cookies_file = os.path.join(ytdlp_dir, "cookies_bili.txt")
        if os.path.isfile(cookies_file):
            cmd += ["--cookies", cookies_file]
        cmd.append(url)
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=15, encoding="utf-8", errors="ignore",
                           creationflags=CREATE_NO_WINDOW)
        if p.returncode == 0 and p.stdout.strip():
            title = p.stdout.strip().splitlines()[0]
    except Exception:
        pass
    return [{"quality": title[:40], "url": url, "type": "video"}]


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
