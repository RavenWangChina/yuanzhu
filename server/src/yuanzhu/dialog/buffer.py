"""消息内存缓冲（合规：原文只驻内存，绝不落库）"""
from collections import deque
from typing import Any, Dict, List


class MessageBuffer:
    """环形缓冲：企微回调的原始消息流（容量上限防内存失控）"""

    def __init__(self, maxlen: int = 2000):
        self.maxlen = maxlen
        self._buf: deque = deque(maxlen=maxlen)

    def push(self, message: Dict[str, Any]) -> None:
        self._buf.append(message)

    def recent(self, n: int = 100) -> List[Dict[str, Any]]:
        return list(self._buf)[-n:]

    def __len__(self) -> int:
        return len(self._buf)

    def clear(self) -> None:
        self._buf.clear()


# 进程级单例（v0.1 单机模式；企业模式多进程时换 Redis，挂账）
message_buffer = MessageBuffer()
