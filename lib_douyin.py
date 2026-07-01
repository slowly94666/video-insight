#!/usr/bin/env python3
"""
抖音视频下载器 v2
主路径: DT-Scraper (X-Bogus 签名) → 秒级响应，无需浏览器
备用路径: Playwright 有头模式 → 签名算法失效时顶上
"""
import sys
import os
import re
import json
import subprocess
import urllib.parse
import urllib.request
import time

from config import FFMPEG as _FFMPEG
FFMPEG = _FFMPEG
MAX_RETRY = 3
RETRY_DELAY = 2  # 秒


# ═══════════════════════════════════════════
# 1. URL 提取与解析
# ═══════════════════════════════════════════

def extract_url(text):
    """从抖音分享文本中提取 URL，清理尾部中文标点"""
    # 找 http(s) 链接：只匹配合法 URL 字符
    urls = re.findall(r'https?://[\w./?=&#%:@~_-]+', text)
    for u in urls:
        # 清理尾部可能误吞的标点
        u = re.sub(r'[，。！？、,.!?」』》]+$', '', u).rstrip('/')
        if 'douyin.com' in u:
            return u
    # 没有 http 前缀的短链
    m = re.search(r'(v\.douyin\.com/[\w-]+)', text)
    if m:
        return 'https://' + m.group(1)
    # 文本本身就是 URL
    cleaned = re.sub(r'[，。！？、,.!?」』》\s]+$', '', text.strip())
    return cleaned


def resolve_short_url(url):
    """解析抖音短链接，带重试"""
    url = extract_url(url)
    # 已经是完整链接就不解析
    if 'douyin.com/video/' in url:
        return url

    for attempt in range(1, MAX_RETRY + 1):
        print(f"[解析短链中... (尝试 {attempt}/{MAX_RETRY})]")
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            resp = urllib.request.urlopen(req, timeout=10)
            final = resp.geturl()
            print(f"[解析结果] {final}")
            return final
        except Exception as e:
            print(f"[解析失败] {e}")
            if attempt < MAX_RETRY:
                time.sleep(RETRY_DELAY)

    print("[错误] 短链解析失败，已重试全部次数")
    return url


# ═══════════════════════════════════════════
# 2. 下载（带断点续传）
# ═══════════════════════════════════════════

def download_file(url, filepath, referer='https://www.douyin.com/'):
    """下载文件，支持断点续传"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': referer,
    }

    # 断点续传：检查已下载大小
    existing_size = 0
    if os.path.exists(filepath):
        existing_size = os.path.getsize(filepath)
        if existing_size > 0:
            headers['Range'] = f'bytes={existing_size}-'
            print(f"  [续传] 已有 {existing_size / (1024*1024):.1f} MB")

    req = urllib.request.Request(url, headers=headers)

    for attempt in range(1, MAX_RETRY + 1):
        try:
            resp = urllib.request.urlopen(req, timeout=300)
            break
        except Exception as e:
            if attempt < MAX_RETRY:
                print(f"  [重试 {attempt}/{MAX_RETRY}] {e}")
                time.sleep(RETRY_DELAY * attempt)
                # 重试时重置 Range（服务器可能不支持）
                if 'Range' in headers:
                    existing_size = 0
                    del headers['Range']
                    if os.path.exists(filepath):
                        os.remove(filepath)
                req = urllib.request.Request(url, headers=headers)
            else:
                raise

    # 判断是否是续传响应
    content_length = int(resp.headers.get('Content-Length', 0))
    content_range = resp.headers.get('Content-Range', '')
    if content_range:
        # 服务器支持续传: "bytes 1234-5678/9999"
        total = int(content_range.split('/')[-1])
        downloaded = existing_size
        mode = 'ab'
    else:
        # 不支持续传或全新下载
        total = content_length
        downloaded = 0
        existing_size = 0
        mode = 'wb'

    with open(filepath, mode) as f:
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if total > 0:
                pct = downloaded * 100 // total
                mb = downloaded / (1024 * 1024)
                print(f"\r  {mb:.1f} / {total/(1024*1024):.1f} MB ({pct}%)", end='', flush=True)

    print()
    return downloaded


# ═══════════════════════════════════════════
# 3. ffmpeg 合并
# ═══════════════════════════════════════════

def merge_audio_video(video_path, audio_path, output_path):
    """用 ffmpeg 合并视频和音频"""
    if not os.path.exists(FFMPEG):
        print("[警告] ffmpeg.exe 不存在，只保留视频轨")
        os.rename(video_path, output_path)
        if os.path.exists(audio_path):
            os.remove(audio_path)
        return True

    cmd = [FFMPEG, '-y', '-i', video_path, '-i', audio_path, '-c', 'copy',
           '-movflags', '+faststart', output_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            os.remove(video_path)
            os.remove(audio_path)
            return True
        else:
            print(f"[ffmpeg 错误] {result.stderr[-200:]}")
            os.rename(video_path, output_path)
            try:
                os.remove(audio_path)
            except:
                pass
            return True
    except Exception as e:
        print(f"[ffmpeg 异常] {e}")
        os.rename(video_path, output_path)
        return True


# ═══════════════════════════════════════════
# 4. API 数据解析（画质选择 + 去水印）
# ═══════════════════════════════════════════

def pick_best_video_url(detail):
    """从 aweme/detail 数据中选最高画质的无水印视频 URL"""
    video = detail.get('video', {})
    if not video:
        return None, None

    # 优先从 bit_rate[] 选最高码率
    bit_rate_list = video.get('bit_rate', [])
    if bit_rate_list:
        # 按 bit_rate 降序排列，取最高
        bit_rate_list.sort(key=lambda x: x.get('bit_rate', 0), reverse=True)
        for br in bit_rate_list:
            play_addr = br.get('play_addr', {})
            urls = play_addr.get('url_list', [])
            if urls:
                url = urls[0]
                url = _remove_watermark(url)
                gear = br.get('gear_name', 'unknown')
                bitrate = br.get('bit_rate', 0)
                print(f"[画质] {gear} ({bitrate // 1024} kbps)")
                return url, gear

    # fallback: play_addr.url_list
    play_addr = video.get('play_addr', {})
    urls = play_addr.get('url_list', [])
    if urls:
        url = _remove_watermark(urls[0])
        return url, 'default'

    return None, None


def _remove_watermark(url):
    """把 playwm 替换成 play 实现去水印"""
    if 'playwm' in url:
        url = url.replace('playwm', 'play')
        print("[去水印] playwm → play")
    return url


# ═══════════════════════════════════════════
# 5. 主路径: DT-Scraper（签名直连，秒级响应）
# ═══════════════════════════════════════════

def try_dt_scraper(url, save_path):
    """用 DT-Scraper 库直接解析下载（无需浏览器）"""
    try:
        from DTDownloader import DouyinDownloader
    except ImportError:
        try:
            from dt_scraper import DouyinDownloader
        except ImportError:
            return False

    print("[引擎] DT-Scraper (签名直连)")
    try:
        # 提取视频 ID
        m = re.search(r'video/(\d+)', url)
        if not m:
            return False
        video_id = m.group(1)

        downloader = DouyinDownloader()
        result = downloader.get_video_info(video_id)
        if not result:
            print("[DT-Scraper] 未获取到视频信息")
            return False

        video_url = result.get('video_url') or result.get('play_url')
        title = result.get('title', 'douyin_video')

        if not video_url:
            print("[DT-Scraper] 未获取到视频 URL")
            return False

        video_url = _remove_watermark(video_url)
        safe_title = _safe_filename(title)
        print(f"[标题] {title}")

        output = os.path.join(save_path, f'{safe_title}.mp4')
        print("[下载中...]")
        download_file(video_url, output)
        print(f"[成功] 已保存到 {output}")
        return True

    except Exception as e:
        print(f"[DT-Scraper 失败] {e}")
        return False


# ═══════════════════════════════════════════
# 6. 备用路径: Playwright（有头模式，稳定兜底）
# ═══════════════════════════════════════════

def _get_playwright_module():
    """优先 patchright，fallback 到原版 playwright"""
    try:
        import patchright.sync_api as pw
        print("[引擎] patchright (反检测 Playwright)")
        return pw
    except ImportError:
        pass
    try:
        from playwright import sync_api as pw
        print("[引擎] Playwright (有头模式)")
        return pw
    except ImportError:
        return None


def try_playwright_headless(url, save_path, pw_module):
    """尝试 Playwright/patchright 无头模式"""
    print("[尝试无头模式...]")
    try:
        with pw_module.sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled']
            )
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='zh-CN',
            )
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )
            page = context.new_page()
            result = _playwright_capture(page, url, timeout=20)
            browser.close()
            return result
    except Exception as e:
        print(f"[无头模式失败] {e}")
        return None, None, None


def try_playwright_headed(url, save_path, pw_module):
    """Playwright 有头模式（终极兜底）"""
    print("[打开浏览器...]")
    print("[提示] 浏览器窗口会自动打开，请勿手动关闭")
    with pw_module.sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN',
        )
        page = context.new_page()
        result = _playwright_capture(page, url, timeout=30)
        browser.close()
        return result


def _playwright_capture(page, url, timeout=30):
    """Playwright 页面拦截视频 URL（有头/无头共用逻辑）"""
    captured = {'video': None, 'audio': None, 'title': None, 'detail': None}

    def on_response(response):
        resp_url = response.url
        ct = response.headers.get('content-type', '')
        status = response.status

        # 拦截 aweme/detail API
        if 'aweme/v1/web/aweme/detail' in resp_url and status == 200:
            try:
                body = response.body()
                if body and len(body) > 10:
                    data = json.loads(body)
                    detail = data.get('aweme_detail', {})
                    if detail:
                        captured['title'] = detail.get('desc', '')
                        captured['detail'] = detail
                        best_url, gear = pick_best_video_url(detail)
                        if best_url:
                            captured['video'] = best_url
            except:
                pass

        # 拦截 MSE 视频流（主路径：通常无水印）
        if 'video/mp4' in ct and status in (200, 206):
            if 'media-video' in resp_url and not captured['video']:
                captured['video'] = resp_url
            elif 'media-audio' in resp_url and not captured['audio']:
                captured['audio'] = resp_url

    page.on('response', on_response)

    try:
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
    except Exception as e:
        print(f"[警告] {e}")

    # 轮询等待视频加载
    print("[等待视频加载...]")
    for i in range(timeout):
        time.sleep(1)
        if captured['video']:
            break
        # 检查 video 元素
        src = page.evaluate("""() => {
            const v = document.querySelector('video');
            return v ? (v.src || v.currentSrc || '') : '';
        }""")
        if src and src.startswith('http') and 'uuu_265' not in src:
            captured['video'] = src
            break

    # 获取标题
    if not captured['title']:
        try:
            t = page.title()
            t = re.sub(r'\s*[-–—]\s*抖音.*$', '', t)
            t = re.sub(r'\s*[-–—]\s*Douyin.*$', '', t)
            captured['title'] = t
        except:
            pass

    return captured['video'], captured['audio'], captured['title']


# ═══════════════════════════════════════════
# 7. 主流程
# ═══════════════════════════════════════════

def _safe_filename(title):
    """生成安全文件名"""
    s = re.sub(r'[\\/:*?"<>|\r\n]', '_', title).strip()[:80]
    return s if s else 'douyin_video'


def download_douyin(url, save_path):
    """主入口：依次尝试 DT-Scraper → Playwright 无头 → Playwright 有头"""

    # === 主路径: DT-Scraper ===
    if try_dt_scraper(url, save_path):
        return True

    # === 备用路径: Playwright ===
    pw = _get_playwright_module()
    if not pw:
        print("[错误] 未安装 playwright / patchright")
        print("  pip install patchright && patchright install chromium")
        print("  或: pip install playwright && playwright install chromium")
        return False

    # 先试无头（patchright 可能能绕过检测）
    video_url, audio_url, title = try_playwright_headless(url, save_path, pw)

    # 无头失败 → 有头模式
    if not video_url:
        video_url, audio_url, title = try_playwright_headed(url, save_path, pw)

    # 带重试：有头模式也失败时刷新重试一次
    if not video_url:
        print("[第一次未捕获，刷新重试...]")
        video_url, audio_url, title = try_playwright_headed(url, save_path, pw)

    if not video_url:
        print("[错误] 未捕获到视频 URL")
        return False

    if not title:
        title = 'douyin_video'

    safe_title = _safe_filename(title)
    print(f"[标题] {title}")

    # 下载
    if audio_url:
        print("[下载视频轨...]")
        video_tmp = os.path.join(save_path, f'{safe_title}_video.mp4')
        download_file(video_url, video_tmp)

        print("[下载音频轨...]")
        audio_tmp = os.path.join(save_path, f'{safe_title}_audio.mp4')
        download_file(audio_url, audio_tmp)

        print("[合并视频和音频...]")
        output = os.path.join(save_path, f'{safe_title}.mp4')
        merge_audio_video(video_tmp, audio_tmp, output)
    else:
        print("[下载中...]")
        output = os.path.join(save_path, f'{safe_title}.mp4')
        download_file(video_url, output)

    print(f"[成功] 已保存到 {output}")
    return True


def main():
    if len(sys.argv) < 3:
        print("用法: python douyin_downloader.py <URL> <保存路径>")
        sys.exit(1)

    raw_url = sys.argv[1]
    save_path = sys.argv[2]

    if not os.path.exists(save_path):
        os.makedirs(save_path)

    url = resolve_short_url(raw_url)
    success = download_douyin(url, save_path)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
