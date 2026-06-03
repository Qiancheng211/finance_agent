import logging
import os
from pathlib import Path
import re
from typing import Any

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / "app" / ".env")
load_dotenv(ROOT_DIR / ".env")

MEM0_LOCAL_DIR = ROOT_DIR / "resources" / "mem0_home"
MEM0_LOCAL_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MEM0_DIR", str(MEM0_LOCAL_DIR))
os.environ.setdefault("MEM0_TELEMETRY", "False")

logger = logging.getLogger(__name__)

_memory_client = None
_client_failed = False
_client_unavailable_logged = False

_MEMORY_KEYWORDS = (
    "以后",
    "记住",
    "偏好",
    "习惯",
    "预算",
    "目标",
    "提醒我",
    "叫我",
    "我是",
    "我叫",
    "我喜欢",
    "我希望",
    "不要",
    "都算",
    "归类",
    "分类",
)

_STRONG_MEMORY_INTENTS = (
    "以后",
    "记住",
    "提醒我",
    "叫我",
    "我喜欢",
    "我希望",
    "不要",
    "都算",
    "归类",
    "分类",
    "预算",
    "目标",
)

_TRANSACTION_WORDS = (
    "花了",
    "花费",
    "买了",
    "消费",
    "付款",
    "支付",
    "转账",
    "收入",
    "记账",
)

_AMOUNT_RE = re.compile(r"\d+(?:\.\d+)?\s*(元|块|rmb|￥|¥)")


def _get_memory_client():
    """Lazy-create Mem0 client so the app still runs when Mem0 is not configured."""
    global _memory_client, _client_failed, _client_unavailable_logged

    if _memory_client is not None:
        return _memory_client
    if _client_failed:
        return None

    api_key = os.getenv("MEM0_API_KEY")
    if not api_key:
        if not _client_unavailable_logged:
            logger.info("Mem0 is not enabled because MEM0_API_KEY is missing.")
            _client_unavailable_logged = True
        return None

    try:
        from mem0 import MemoryClient

        _memory_client = MemoryClient(api_key=api_key)
        return _memory_client
    except Exception as exc:
        _client_failed = True
        logger.warning("Mem0 client init failed, long-term memory disabled: %s", exc)
        return None


def _read_memory_text(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if not isinstance(item, dict):
        return str(item).strip()

    for key in ("memory", "text", "content"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    nested = item.get("metadata")
    if isinstance(nested, dict):
        value = nested.get("memory") or nested.get("text")
        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def _looks_like_transaction_only(user_message: str) -> bool:
    text = user_message.strip().lower()
    if not text:
        return False

    has_amount = bool(_AMOUNT_RE.search(text))
    has_transaction_word = any(word in text for word in _TRANSACTION_WORDS)
    has_strong_memory_intent = any(word in text for word in _STRONG_MEMORY_INTENTS)
    return has_amount and has_transaction_word and not has_strong_memory_intent


def search_user_memories(user_id: str, query: str, limit: int = 5) -> str:
    """Search memories related to the current user message."""
    client = _get_memory_client()
    if client is None or not query.strip() or not user_id.strip():
        return ""

    try:
        response = client.search(
            query=query,
            filters={"user_id": user_id},
            top_k=limit,
        )
    except Exception as exc:
        logger.warning("Mem0 search failed: %s", exc)
        return ""

    raw_items = response.get("results", response) if isinstance(response, dict) else response
    if not isinstance(raw_items, list):
        return ""

    lines: list[str] = []
    for item in raw_items[:limit]:
        text = _read_memory_text(item)
        if text:
            lines.append(f"- {text}")

    return "\n".join(lines)


def add_user_memory(user_id: str, thread_id: str, user_message: str, assistant_message: str = "") -> bool:
    """Ask Mem0 to extract durable user preferences from the latest turn."""
    clean_message = user_message.strip()
    if not clean_message or not user_id.strip():
        return False
    if not any(keyword in clean_message for keyword in _MEMORY_KEYWORDS):
        return False
    if _looks_like_transaction_only(clean_message):
        return False

    client = _get_memory_client()
    if client is None:
        return False

    messages = [{"role": "user", "content": clean_message}]
    if assistant_message.strip():
        messages.append({"role": "assistant", "content": assistant_message})

    try:
        client.add(
            messages=messages,
            user_id=user_id,
            metadata={"app": "finance_agent", "thread_id": thread_id},
        )
        return True
    except Exception as exc:
        logger.warning("Mem0 add failed: %s", exc)
        return False


def build_memory_prompt(user_id: str, user_message: str) -> str:
    """Build a compact prompt section that injects relevant long-term memory."""
    memories = search_user_memories(user_id, user_message)
    if not memories:
        return user_message

    return f"""# 用户长期记忆
以下是和本次问题可能相关的长期记忆。请优先遵守这些偏好、分类规则和预算目标；如果和用户本次明确表达冲突，以本次表达为准。
{memories}

# 用户本次问题
{user_message}
"""
