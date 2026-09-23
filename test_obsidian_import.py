# -*- coding: utf-8 -*-
"""
Obsidian 导入自测脚本 — 用临时目录验证，不写入真实库

运行:
    python test_obsidian_import.py
"""
import tempfile
from pathlib import Path

import obsidian_import as oi


def main():
    tmp = Path(tempfile.mkdtemp(prefix="obsidian_test_"))
    (tmp / ".obsidian").mkdir()

    # 转录笔记
    body = oi.compose_transcript_note("测试视频", "这是转录内容。", "https://example.com/v/123")
    path, uri = oi.import_to_obsidian("测试视频", body,
                                      source="https://example.com/v/123",
                                      vault_dir=tmp)
    print("转录笔记已写入:", path)
    print("obsidian URI :", uri)

    # 分析笔记
    sections = {
        "headline": "一句话核心",
        "summary": "摘要内容",
        "analysis": "完整分析",
        "facts": "| 1 | 声称 | 事实 | 高 | 依据 |",
        "keypoints": "1. 要点一\n2. 要点二",
        "annotations": "> 原文\n批注",
        "scores": "质量: 85/100 | 可信度: 78/100",
    }
    body2 = oi.compose_analysis_note("测试视频", sections, "https://example.com/v/123")
    path2, uri2 = oi.import_to_obsidian("测试视频", body2,
                                        source="https://example.com/v/123",
                                        vault_dir=tmp)
    print("分析笔记已写入:", path2)
    print("obsidian URI :", uri2)
    print()
    print(Path(path2).read_text(encoding="utf-8"))
    print("OK — 导入逻辑正常")


if __name__ == "__main__":
    main()
