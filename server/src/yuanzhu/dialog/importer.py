"""聊天记录文本导入器（spec 3.3 降级路径：企微挂起期的数据先行）

支持企微/微信导出的常见文本格式：
    2026-09-01 09:00:33 张三
    消息内容（可多行，直到下一条时间行）

非消息行（分隔线/撤回提示等）跳过并计数。
"""
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

# 时间行：2026-09-01 09:00:33 张三 / 09:00 张三
TIME_LINE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2}(?::\d{2})?)\s+(\S+)\s*$"
)


def parse_chat_text(
    text: str, chat_name: str = "导入会话", return_skipped: bool = False
) -> Any:
    """解析聊天记录文本 → buffer 消息形态（与企微回调同构）"""
    messages: List[Dict[str, Any]] = []
    skipped = 0
    current: Dict[str, Any] | None = None

    for line in text.splitlines():
        m = TIME_LINE.match(line.strip())
        if m:
            if current:
                messages.append(current)
            date_str, time_str, name = m.groups()
            try:
                ts = int(datetime.fromisoformat(f"{date_str}T{time_str}").replace(
                    tzinfo=timezone.utc).timestamp())
            except ValueError:
                ts = None
            current = {
                "from": {"name": name, "user_id": None},
                "chat": {"chat_id": f"import:{chat_name}", "name": chat_name},
                "msgtype": "text",
                "text": {"content": ""},
                "timestamp": ts,
            }
            continue

        stripped = line.strip()
        is_noise = bool(stripped) and (
            stripped.startswith(chr(0x2014) * 3) or stripped.startswith("---")
            or "撤回了一条消息" in stripped or "加入了群聊" in stripped
            or "以下为新消息" in stripped
        )

        if is_noise:
            skipped += 1
        elif current is not None:
            # 消息体行（含空行保留结构）
            current["text"]["content"] += (chr(10) if current["text"]["content"] else "") + line.rstrip()
        elif stripped:
            skipped += 1  # 头部噪音（无法识别的杂行）

    if current:
        messages.append(current)

    # 内容为空的消息丢弃（纯分隔）
    messages = [m for m in messages if m["text"]["content"].strip()]

    if return_skipped:
        return messages, skipped
    return messages
