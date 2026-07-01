# -*- coding: utf-8 -*-
"""
视频Agent - 智能体（ReAct 模式）
用户说目标 → agent 规划 → 调用工具 → 观察结果 → 继续/调整
"""
import os
import json
import requests
from pathlib import Path
from config import get_mimo_config, DOWNLOAD_DIR, TRANSCRIPT_DIR, ANALYSIS_DIR

# ═══════════════════════════════════════════
# 工具注册
# ═══════════════════════════════════════════

TOOLS = {}

def tool(name, description, params=""):
    """装饰器：注册一个工具"""
    def decorator(func):
        TOOLS[name] = {
            "name": name,
            "description": description,
            "params": params,
            "func": func,
        }
        return func
    return decorator


@tool("download", "下载视频", "url: 视频链接, platform: 平台（可选，auto/bilibili/douyin/twitter/soop）")
def _tool_download(url: str, platform: str = "auto") -> str:
    from downloader import download, detect_platform
    def cb(msg):
        pass  # agent 模式静默
    plat = None if platform == "auto" else platform
    result = download(url, platform=plat, callback=cb)
    if result:
        return f"下载成功: {result}"
    return "下载失败"


@tool("transcribe", "转录视频为文字", "video_path: 视频文件路径, engine: 转录引擎（mimo/whisper，默认 mimo）")
def _tool_transcribe(video_path: str, engine: str = "mimo") -> str:
    from transcriber import transcribe
    def cb(msg):
        pass
    text = transcribe(video_path, engine=engine, callback=cb)
    return f"转录完成，共 {len(text)} 字。前200字预览：\n{text[:200]}"


@tool("analyze", "分析文案内容", "text_path: 文本文件路径, modules: 分析模块（逗号分隔：summarizer,extractor,quality，默认全部）")
def _tool_analyze(text_path: str, modules: str = "") -> str:
    from analyzer import analyze
    def cb(msg):
        pass
    with open(text_path, 'r', encoding='utf-8') as f:
        text = f.read()
    mod_list = [m.strip() for m in modules.split(",") if m.strip()] if modules else None
    results = analyze(text, modules=mod_list, source_name=text_path, callback=cb)
    summary = []
    for mod, res in results.items():
        if "error" in res:
            summary.append(f"[{mod}] 失败: {res['error']}")
        else:
            summary.append(f"[{mod}] {json.dumps(res, ensure_ascii=False)[:300]}")
    return "\n".join(summary)


@tool("list_files", "列出目录中的文件", "dir_type: 目录类型（downloads/transcripts/analysis）")
def _tool_list_files(dir_type: str = "downloads") -> str:
    dirs = {
        "downloads": DOWNLOAD_DIR,
        "transcripts": TRANSCRIPT_DIR,
        "analysis": ANALYSIS_DIR,
    }
    d = dirs.get(dir_type, DOWNLOAD_DIR)
    files = sorted(d.glob("*"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        return f"{dir_type}/ 目录为空"
    lines = []
    for f in files[:20]:
        size = f.stat().st_size / 1024
        lines.append(f"  {f.name} ({size:.0f}KB)")
    return f"{dir_type}/ 目录（最近20个）：\n" + "\n".join(lines)


@tool("read_text", "读取文本文件内容", "file_path: 文件路径")
def _tool_read_text(file_path: str) -> str:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        if len(text) > 3000:
            return text[:3000] + f"\n...(截断，共{len(text)}字)"
        return text
    except Exception as e:
        return f"读取失败: {e}"


@tool("detect_platform", "检测视频链接的平台", "url: 视频链接")
def _tool_detect_platform(url: str) -> str:
    from downloader import detect_platform
    return detect_platform(url)


# ═══════════════════════════════════════════
# LLM 大脑
# ═══════════════════════════════════════════

def _build_system_prompt():
    """构建 system prompt，包含工具说明"""
    tool_docs = []
    for name, info in TOOLS.items():
        tool_docs.append(f"- {name}({info['params']}): {info['description']}")
    tools_text = "\n".join(tool_docs)

    return f"""你是一个视频分析助手。你可以帮用户下载视频、转录语音、分析文案。

可用工具：
{tools_text}

你必须严格按照以下 JSON 格式回复，不要有其他内容：

思考过程：
{{"think": "你的分析和计划", "action": "tool_name", "args": {{"参数名": "值"}}}}

如果任务完成，回复：
{{"think": "总结", "action": "done", "result": "给用户的最终回答"}}

规则：
1. 每次只调用一个工具
2. args 必须是合法的 JSON 对象
3. 不需要参数时 args 为 {{}}
4. 观察工具结果后再决定下一步
5. 如果工具失败，尝试其他方案
6. 任务完成后必须 action: "done"
"""


def chat(messages: list) -> str:
    """调用 MiMo API 对话"""
    api_key, api_base = get_mimo_config()
    url = f"{api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "mimo-v2.5-pro",
        "messages": messages,
        "max_tokens": 1500,
        "temperature": 0.3,
    }
    resp = requests.post(url, json=data, headers=headers, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"API 错误 {resp.status_code}: {resp.text[:200]}")
    return resp.json()["choices"][0]["message"]["content"]


def _parse_response(text: str) -> dict:
    """从 LLM 回复中解析 JSON 指令"""
    import re
    # 尝试直接解析
    try:
        return json.loads(text)
    except:
        pass
    # 提取 JSON 块
    matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    for m in reversed(matches):  # 取最后一个完整 JSON
        try:
            return json.loads(m)
        except:
            continue
    return {"think": text, "action": "done", "result": text}


# ═══════════════════════════════════════════
# ReAct 主循环
# ═══════════════════════════════════════════

MAX_STEPS = 10

def run_agent(goal: str, callback=None) -> str:
    """
    Agent 主入口

    Args:
        goal: 用户目标（自然语言）
        callback: 进度回调 callback(msg: str)

    Returns:
        最终结果文本
    """
    def log(msg):
        if callback:
            callback(msg)

    log(f"🎯 目标: {goal}")

    system_prompt = _build_system_prompt()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": goal},
    ]

    for step in range(1, MAX_STEPS + 1):
        log(f"\n--- 步骤 {step}/{MAX_STEPS} ---")

        # 思考
        log("🤔 思考中...")
        response = chat(messages)
        messages.append({"role": "assistant", "content": response})

        # 解析指令
        cmd = _parse_response(response)
        think = cmd.get("think", "")
        action = cmd.get("action", "done")
        log(f"💭 {think}")

        # 完成
        if action == "done":
            result = cmd.get("result", think)
            log(f"\n✅ 完成")
            return result

        # 调用工具
        if action not in TOOLS:
            log(f"⚠️ 未知工具: {action}，跳过")
            messages.append({"role": "user", "content": f"错误：没有工具 {action}，可用工具：{', '.join(TOOLS.keys())}"})
            continue

        args = cmd.get("args", {})
        log(f"🔧 调用 {action}({json.dumps(args, ensure_ascii=False)})")

        try:
            tool_result = TOOLS[action]["func"](**args)
            log(f"📋 结果: {str(tool_result)[:200]}")
            messages.append({"role": "user", "content": f"工具结果：{tool_result}"})
        except Exception as e:
            error_msg = f"工具执行失败: {e}"
            log(f"❌ {error_msg}")
            messages.append({"role": "user", "content": error_msg})

    log(f"\n⚠️ 达到最大步数 ({MAX_STEPS})，停止")
    return "任务未完成，达到最大步数限制。"


# ═══════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        goal = " ".join(sys.argv[1:])
    else:
        print("视频Agent - 智能助手")
        print("输入目标，我来帮你完成。输入 q 退出。")
        print("-" * 40)
        goal = input("你的目标: ").strip()
        if not goal or goal.lower() == 'q':
            sys.exit(0)

    def cli_callback(msg):
        print(msg)

    result = run_agent(goal, callback=cli_callback)
    print("\n" + "=" * 40)
    print("最终结果：")
    print(result)
