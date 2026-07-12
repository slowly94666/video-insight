# -*- coding: utf-8 -*-
"""
Video Insight — 主题色彩管理
集中定义 UI 配色，一处修改全局生效
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ColorScheme:
    """UI 色彩方案（不可变，确保一致性）"""

    # ── 背景层 ──
    bg_primary: str         # 窗口主背景
    bg_card: str            # 卡片/面板背景
    bg_input: str           # 输入框背景
    bg_log: str             # 日志面板背景

    # ── 文字层 ──
    text_primary: str       # 主文字
    text_secondary: str     # 次要文字 / 标签
    text_dim: str           # 最弱文字 / 占位符

    # ── 语义色 ──
    accent: str             # 强调色（主按钮 / 进行中）
    success: str            # 成功
    danger: str             # 失败 / 停止
    warning: str            # 警告

    # ── 流程指示器 ──
    flow_active_bg: str
    flow_active_fg: str
    flow_done_bg: str
    flow_done_fg: str
    flow_cancelled_bg: str
    flow_cancelled_fg: str
    flow_idle_bg: str
    flow_idle_fg: str

    # ── 边框 / 分隔 ──
    border: str
    divider: str


# ═══════════════════════════════════════════
# 预设主题
# ═══════════════════════════════════════════

DARK = ColorScheme(
    # 背景
    bg_primary="#1e1e1e",
    bg_card="#2d2d2d",
    bg_input="#3c3c3c",
    bg_log="#1a1a1a",
    # 文字
    text_primary="#cccccc",
    text_secondary="#888888",
    text_dim="#555555",
    # 语义
    accent="#007acc",
    success="#4ec9b0",
    danger="#f44747",
    warning="#cca700",
    # 流程指示器
    flow_active_bg="#1a3a5c",
    flow_active_fg="#4fc1ff",
    flow_done_bg="#1a3a2a",
    flow_done_fg="#4ec9b0",
    flow_cancelled_bg="#3a1a1a",
    flow_cancelled_fg="#f44747",
    flow_idle_bg="#2d2d2d",
    flow_idle_fg="#555555",
    # 边框
    border="#3c3c3c",
    divider="#3c3c3c",
)

LIGHT = ColorScheme(
    # 背景
    bg_primary="#f5f5f5",
    bg_card="#ffffff",
    bg_input="#ffffff",
    bg_log="#fafafa",
    # 文字
    text_primary="#333333",
    text_secondary="#888888",
    text_dim="#bbbbbb",
    # 语义
    accent="#2563eb",
    success="#16a34a",
    danger="#dc2626",
    warning="#d97706",
    # 流程指示器
    flow_active_bg="#dbeafe",
    flow_active_fg="#1d4ed8",
    flow_done_bg="#dcfce7",
    flow_done_fg="#15803d",
    flow_cancelled_bg="#fee2e2",
    flow_cancelled_fg="#dc2626",
    flow_idle_bg="#eeeeee",
    flow_idle_fg="#999999",
    # 边框
    border="#e5e5e5",
    divider="#e5e5e5",
)

# 当前使用的主题
THEME = LIGHT