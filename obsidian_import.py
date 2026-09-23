# -*- coding: utf-8 -*-
"""
Obsidian 导入模块 — 一键把转录/分析结果写入 Obsidian 库

用法:
    from obsidian_import import import_to_obsidian, compose_transcript_note, compose_analysis_note

    body = compose_analysis_note(title, sections, source=url)
    path, uri = import_to_obsidian(title, body, source=url)
    os.startfile(uri)  # Windows 下自动在 Obsidian 中打开该笔记

配置（.env）:
    OBSIDIAN_VAULT          库根目录（默认自动探测 ~/Documents/Obsidian 等常见位置）
    OBSIDIAN_IMPORT_SUBDIR  导入子目录（默认 视频洞察）
"""
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, quote

from config import OBSIDIAN_VAULT_DIR, OBSIDIAN_IMPORT_DIR


def _safe_stem(name: str, fallback: str = "视频") -> str:
    """从文件名或 URL 生成安全的笔记名（不含扩展名）"""
    name = (name or "").strip()
    if not name:
        return fallback
    if "://" in name:
        p = urlparse(name)
        last = p.path.rstrip("/").split("/")[-1] if p.path.rstrip("/") else ""
        name = last or p.netloc or fallback
    stem = Path(name).stem if Path(name).suffix else name
    stem = re.sub(r'[\\/:*?"<>|#\[\]]', "_", stem).strip().strip(".")
    return stem[:80] or fallback


def _frontmatter(note_type: str, tags: str, source: str, now: datetime) -> str:
    """生成符合 Obsidian 库模板的 YAML frontmatter"""
    return (
        "---\n"
        f"type: {note_type}\n"
        "status: imported\n"
        f"tags: [{tags}]\n"
        f"source: {json.dumps(source or '', ensure_ascii=False)}\n"
        f"created: {now:%Y-%m-%d}\n"
        f"updated: {now:%Y-%m-%d}\n"
        "---\n\n"
    )


def compose_transcript_note(title: str, transcript: str, source: str = "") -> str:
    """生成转录笔记（Markdown + frontmatter）"""
    now = datetime.now()
    src = source or title
    body = f"# {title} · 视频转录\n\n"
    body += f"> 来源：{src}\n\n"
    body += f"> 转录时间：{now:%Y-%m-%d %H:%M}\n\n---\n\n"
    body += "## 转录全文\n\n" + (transcript or "").strip() + "\n"
    return _frontmatter("data", "视频洞察, 转录", src, now) + body


def compose_analysis_note(title: str, sections: dict, source: str = "") -> str:
    """生成分析笔记（Markdown + frontmatter），sections 来自 parse_sections()"""
    now = datetime.now()
    src = source or title
    body = f"# {title} · 视频洞察分析\n\n"
    body += f"> 来源：{src}\n\n"
    body += f"> 分析时间：{now:%Y-%m-%d %H:%M}\n\n"
    body += "> 工具：Video Insight（下载 → 转录 → LLM 分析）\n\n---\n\n"
    labels = [
        ("headline", "## 一句话核心"),
        ("summary", "## 摘要"),
        ("content", "## 📖 详细内容"),
        ("analysis", "## 完整分析"),
        ("facts", "## 事实核查"),
        ("keypoints", "## 核心要点"),
        ("annotations", "## 对话批注"),
        ("scores", "## 评分"),
    ]
    for key, heading in labels:
        content = (sections or {}).get(key, "").strip()
        body += f"{heading}\n\n{content or '无'}\n\n---\n\n"
    return _frontmatter("data", "视频洞察, 分析报告", src, now) + body.rstrip() + "\n"


def import_to_obsidian(title: str, body: str, source: str = "",
                       import_dir=None, vault_dir=None):
    """
    把笔记写入 Obsidian 库，返回 (笔记绝对路径, obsidian:// URI)

    Args:
        title: 笔记标题（用于文件名）
        body: Markdown 正文（含 frontmatter）
        source: 来源（URL 或文件路径），写入 frontmatter
        import_dir: 导入目录（默认 OBSIDIAN_IMPORT_DIR）
        vault_dir: 库根目录（默认 OBSIDIAN_VAULT_DIR）
    """
    vault = Path(vault_dir) if vault_dir else OBSIDIAN_VAULT_DIR
    if vault is None or not vault.joinpath(".obsidian").is_dir():
        raise RuntimeError(
            "未找到 Obsidian 库，请在 .env 中设置 OBSIDIAN_VAULT 指向库目录"
        )
    if import_dir:
        target_dir = Path(import_dir)
    elif OBSIDIAN_IMPORT_DIR is not None and vault == OBSIDIAN_VAULT_DIR:
        target_dir = OBSIDIAN_IMPORT_DIR
    else:
        target_dir = vault / "视频洞察"
    target_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    safe = _safe_stem(title)
    base = target_dir / f"{safe}_{now:%Y%m%d_%H%M%S}"
    note_path = target_dir / f"{base.name}.md"
    i = 1
    while note_path.exists():
        note_path = target_dir / f"{base.name}_{i}.md"
        i += 1
    note_path.write_text(body, encoding="utf-8")

    rel = note_path.relative_to(vault).as_posix()
    # 与 Obsidian「复制 obsidian URL」一致：路径分隔符编码为 %2F
    uri = ("obsidian://open?vault=" + quote(vault.name) +
           "&file=" + quote(rel, safe=""))
    return str(note_path), uri
