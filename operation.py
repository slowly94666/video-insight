# -*- coding: utf-8 -*-
"""
Video Insight — 操作抽象层
统一管理后台操作的启动 / 取消 / 状态恢复，消除线程样板代码

解决问题：
  1. 线程样板重复（原来 5 份 ~150 行）
  2. 操作互斥（防止同时跑多个操作）
  3. 线程安全的 UI 编组入口
"""

import threading
from dataclasses import dataclass, field
from enum import Enum, auto


class OpState(Enum):
    """操作状态"""
    RUNNING   = auto()
    DONE      = auto()
    CANCELLED = auto()
    ERROR     = auto()


class CancelledError(Exception):
    """用户取消操作时抛出，由 OperationRunner 捕获"""
    pass


@dataclass
class Operation:
    """一个后台操作的生命周期"""
    cancel_event: threading.Event
    state: OpState = OpState.RUNNING
    error_message: str = ""


class OperationRunner:
    """
    操作运行器 — 单例式管理当前操作

    用法:
        runner = OperationRunner(ui_call=app._ui_call)
        runner.on_state_change(app._on_op_state_change)

        # 启动操作
        runner.start(self._pipeline_thread, url)

        # 操作函数签名: fn(op, check, *args)
        def _pipeline_thread(self, op, check, url):
            check()  # 被取消则抛出 CancelledError
            ...
            path = download(..., cancel_event=op.cancel_event)
            check()
            ...

        # 取消
        runner.cancel()
    """

    def __init__(self, ui_call):
        """
        Args:
            ui_call: fn -> root.after(0, fn)，所有状态回调都通过它编组到主线程
        """
        self._ui_call = ui_call
        self._on_state_change = None   # callback(OpState)
        self._current: Operation | None = None

    # ── 公共接口 ──

    def on_state_change(self, callback):
        """注册操作状态变更回调（在主线程执行）"""
        self._on_state_change = callback

    @property
    def is_running(self) -> bool:
        return self._current is not None and self._current.state == OpState.RUNNING

    def start(self, fn, *args) -> bool:
        """
        启动操作（互斥：同时只能有一个运行）

        Returns:
            True 如果启动成功，False 如果有操作正在运行
        """
        if self.is_running:
            return False
        op = Operation(cancel_event=threading.Event())
        self._current = op
        self._emit_state(OpState.RUNNING)
        threading.Thread(target=self._wrap, args=(op, fn) + args, daemon=True).start()
        return True

    def cancel(self):
        """取消当前操作"""
        if self._current and self._current.state == OpState.RUNNING:
            self._current.cancel_event.set()

    # ── 内部 ──

    def _wrap(self, op, fn, *args):
        """包装用户函数：自动处理取消/异常/状态恢复"""
        def check():
            if op.cancel_event.is_set():
                raise CancelledError()

        try:
            fn(op, check, *args)
            # 正常返回 → DONE（user 可能手动改成 ERROR，保留）
            if op.state == OpState.RUNNING:
                op.state = OpState.DONE
        except CancelledError:
            op.state = OpState.CANCELLED
        except Exception as e:
            op.state = OpState.ERROR
            op.error_message = str(e)
        finally:
            self._emit_state(op.state)

    def _emit_state(self, state):
        """编组到主线程通知状态变更"""
        if self._on_state_change is not None:
            self._ui_call(lambda s=state: self._on_state_change(s))