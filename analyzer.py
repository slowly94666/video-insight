# -*- coding: utf-8 -*-
"""
文案分析模块
封装 text_analysis/ 的总结/提取/质量评估功能
"""
import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime
from config import get_llm_config, get_mimo_config, ANALYSIS_DIR


# === LLM API 调用 ===

def call_llm_api(prompt: str, text: str, max_tokens: int = 2000) -> str:
    """调用 LLM API 进行文本分析（支持多提供商）"""
    api_key, api_base, model = get_llm_config()
    if not api_key:
        raise ValueError("未配置 API Key，请在 .env 文件中设置")

    url = f"{api_base}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }

    resp = requests.post(url, json=data, headers=headers, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"LLM API HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()["choices"][0]["message"]["content"]


def _parse_json_response(response: str) -> dict:
    """从 API 响应中解析 JSON"""
    import re
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        m = re.search(r'\{[\s\S]*\}', response)
        if m:
            return json.loads(m.group())
        raise Exception("API 返回格式无法解析")


# === 分析模块 ===

def summarize(text: str, callback=None) -> dict:
    """总结要点"""
    if callback:
        callback("正在生成总结...")
    prompt = """你是一个专业的文本分析师。请分析以下视频转录文本，并提供：
1. **总结**：用2-3句话概括文本的核心内容
2. **大纲**：提取3-7个主要要点，按逻辑顺序排列
请用JSON格式返回：
{"summary": "总结内容", "outline": ["要点1", "要点2", "要点3"]}
只返回JSON，不要有其他内容。"""
    result = _parse_json_response(call_llm_api(prompt, text))
    if callback:
        callback("✓ 总结完成")
    return result


def extract_info(text: str, callback=None) -> dict:
    """提取关键信息"""
    if callback:
        callback("正在提取关键信息...")
    prompt = """你是一个专业的文本分析师。请分析以下视频转录文本，并提取：
1. **关键点**：提取3-7个最重要的观点或信息
2. **实体**：识别文本中提到的重要实体（人名、组织、产品、地点等）
3. **关键词**：提取5-10个最能代表文本主题的关键词
请用JSON格式返回：
{"key_points": ["关键点1", "关键点2"], "entities": ["实体1"], "keywords": ["关键词1"]}
只返回JSON，不要有其他内容。"""
    result = _parse_json_response(call_llm_api(prompt, text))
    if callback:
        callback("✓ 提取完成")
    return result


def evaluate_quality(text: str, callback=None) -> dict:
    """质量评估"""
    if callback:
        callback("正在评估质量...")
    prompt = """你是一个专业的内容质量评估师。请分析以下视频转录文本，并评估：
1. **质量评分**：0-100分
2. **可信度评分**：0-100分
3. **优点**：列出2-4个
4. **缺点**：列出2-4个
请用JSON格式返回：
{"quality_score": 85, "credibility_score": 70, "strengths": ["优点1"], "weaknesses": ["缺点1"]}
只返回JSON，不要有其他内容。"""
    result = _parse_json_response(call_llm_api(prompt, text))
    if callback:
        callback("✓ 评估完成")
    return result


# === 报告生成 ===

def _generate_report(module_name: str, filename: str, result: dict) -> str:
    """生成 Markdown 报告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if module_name == "summarizer":
        md = f"# 文本总结报告\n\n**文件**: {filename}\n**时间**: {now}\n\n## 总结\n\n{result.get('summary', '无')}\n\n## 大纲\n\n"
        for i, p in enumerate(result.get('outline', []), 1):
            md += f"{i}. {p}\n"
        return md

    elif module_name == "extractor":
        md = f"# 关键信息提取报告\n\n**文件**: {filename}\n**时间**: {now}\n\n## 关键点\n\n"
        for i, p in enumerate(result.get('key_points', []), 1):
            md += f"{i}. {p}\n"
        md += "\n## 实体\n\n"
        for e in result.get('entities', []):
            md += f"- {e}\n"
        md += "\n## 关键词\n\n"
        for k in result.get('keywords', []):
            md += f"- {k}\n"
        return md

    elif module_name == "quality":
        md = f"# 内容质量评估报告\n\n**文件**: {filename}\n**时间**: {now}\n\n## 评分\n\n| 指标 | 分数 |\n|------|------|\n| 质量 | {result.get('quality_score', 0)}/100 |\n| 可信度 | {result.get('credibility_score', 0)}/100 |\n\n## 优点\n\n"
        for s in result.get('strengths', []):
            md += f"- {s}\n"
        md += "\n## 缺点\n\n"
        for w in result.get('weaknesses', []):
            md += f"- {w}\n"
        return md

    return ""


ANALYZERS = {
    "summarizer": summarize,
    "extractor":  extract_info,
    "quality":    evaluate_quality,
}


def analyze(text: str, modules: list = None, source_name: str = "未知", callback=None) -> dict:
    """
    统一分析入口

    Args:
        text: 要分析的文本
        modules: 要运行的模块列表（默认全部）
        source_name: 来源文件名（用于报告标题）
        callback: 进度回调

    Returns:
        {module_name: result_dict, ...}
    """
    if modules is None:
        modules = list(ANALYZERS.keys())

    results = {}
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = Path(source_name).stem if source_name else "分析"

    for mod_name in modules:
        if mod_name not in ANALYZERS:
            continue
        try:
            if callback:
                callback(f"[{mod_name}] 开始分析...")

            result = ANALYZERS[mod_name](text, callback)
            results[mod_name] = result

            # 保存报告
            md_content = _generate_report(mod_name, source_name, result)
            md_file = ANALYSIS_DIR / f"{safe_name}_{mod_name}_{ts}.md"
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write(md_content)

            json_file = ANALYSIS_DIR / f"{safe_name}_{mod_name}_{ts}.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            if callback:
                callback(f"[{mod_name}] 报告已保存: {md_file.name}")

        except Exception as e:
            if callback:
                callback(f"[{mod_name}] 失败: {e}")
            results[mod_name] = {"error": str(e)}

    return results


# === 统一分析（新版，一次 API 调用输出多种格式） ===

UNIFIED_PROMPT = """你是一位专业的视频内容分析师。请用中文分析以下视频转录文本。

严格按照以下格式输出（用 ##节名## 作为分隔符，不要跳过任何节）：

##HEADLINE##
（用一句话概括视频核心论点，30字以内）

##SUMMARY##
（用200字摘要，分2-3段，自然段落，不要用列表）

##ANALYSIS##
（完整分析报告，Markdown格式。包含：核心论点展开、论据拆解、逻辑分析、各方立场、个人评价。自然流畅，不要用JSON）

##FACTS##
（列出视频中的关键事实声称，用表格，每行一条。格式固定：
| 序号 | 声称 | 判定 | 可信度 | 依据 |
判定用：✅事实 ❌谬误 ⚠️无法验证 ⚡观点
可信度用：高/中/低
依据要简短，10字以内）

##KEYPOINTS##
（3-5个核心要点，每行一个，用"1. "开头）

##ANNOTATIONS##
（选取3-5处值得批注的原文片段，格式：
> 原文片段
💬 [批注：一句话分析]

##SCORES##
质量: 数字/100 | 可信度: 数字/100"""


def analyze_unified(text: str, source_name: str = "未知", callback=None) -> tuple[str, str]:
    """统一分析：一次 LLM 调用，返回多节结构化文本"""
    if callback:
        callback("🧠 分析中...")

    api_key, api_base, model = get_llm_config()
    if not api_key:
        raise ValueError("未配置 API Key")

    url = f"{api_base}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": UNIFIED_PROMPT},
            {"role": "user", "content": text[:12000]}
        ],
        "max_tokens": 2500,
        "temperature": 0.7
    }

    resp = requests.post(url, json=data, headers=headers, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"LLM API HTTP {resp.status_code}: {resp.text[:300]}")

    raw = resp.json()["choices"][0]["message"]["content"]

    # 保存原始结果
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = Path(source_name).stem if source_name else "分析"
    out_file = ANALYSIS_DIR / f"{safe_name}_unified_{ts}.md"
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(raw)

    if callback:
        callback(f"✓ 报告已保存: {out_file.name}")

    return raw, str(out_file)


def parse_sections(raw: str) -> dict:
    """解析统一分析的节段文本，返回 {section_name: content}"""
    import re
    sections = {}
    parts = re.split(r'##(\w+)##\s*\n?', raw)
    # parts: ['', 'HEADLINE', '一句...\n', 'SUMMARY', '200字...\n', ...]
    for i in range(1, len(parts), 2):
        name = parts[i].lower()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        sections[name] = content
    return sections
