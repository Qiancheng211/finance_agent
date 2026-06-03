import json
import random
from pathlib import Path

from langchain.agents import create_agent
from pydantic import BaseModel, Field

from app.finance_agent.config import get_qwen_model


class StickerPick(BaseModel):
    keyword: str = Field(description="用于选图的关键词")
    mood: str = Field(description="情绪关键词，如震惊、庆祝、无语")
    caption: str = Field(description="表情包文案，保持搞怪风格")


STICKER_SYSTEM_PROMPT = """
你是搞怪表情包挑选 Agent。
根据用户记账上下文，返回一个适合的关键词和吐槽文案。
要点：
- 语义相关，但搞怪优先。
- 文案简短，不超过 20 字。
- 禁止输出敏感、攻击性内容。
"""

_PLACEHOLDER_STICKERS = [
    "https://placehold.co/320x240/png?text=%E8%AE%B0%E8%B4%A6%E6%88%90%E5%8A%9F",
    "https://placehold.co/320x240/png?text=%E4%BB%8A%E5%A4%A9%E5%8F%88%E8%8A%B1%E9%92%B1",
    "https://placehold.co/320x240/png?text=%E8%8D%92%E5%94%90%E4%BD%86%E5%90%88%E7%90%86",
]

# 本地表情包目录：把图片文件放进 app/static/stickers/ 即可被自动选用。
# 命名建议：文件名包含 mood 或 keyword（如 庆祝.png、震惊_无语.gif），便于按情绪匹配。
STICKER_DIR = Path(__file__).resolve().parents[1] / "static" / "stickers"
STICKER_URL_PREFIX = "/static/stickers"
_SUPPORTED_STICKER_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def _list_local_stickers() -> list[Path]:
    if not STICKER_DIR.exists():
        return []
    return [
        path
        for path in STICKER_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in _SUPPORTED_STICKER_EXTS
    ]


def resolve_sticker_url(keyword: str = "", mood: str = "") -> str:
    """根据情绪/关键词解析表情包 URL。

    优先匹配本地 app/static/stickers/ 目录下文件名包含 mood 或 keyword 的图片；
    没有命中则在本地随机挑选；本地目录为空时回退到占位图（接入真实图片前的 MVP 兜底）。
    """
    local_files = _list_local_stickers()
    if local_files:
        for token in (mood, keyword):
            token = (token or "").strip().lower()
            if not token:
                continue
            for path in local_files:
                if token in path.stem.lower():
                    return f"{STICKER_URL_PREFIX}/{path.name}"
        return f"{STICKER_URL_PREFIX}/{random.choice(local_files).name}"

    return random.choice(_PLACEHOLDER_STICKERS)


def create_sticker_agent():
    return create_agent(
        model=get_qwen_model(),
        tools=[],
        system_prompt=STICKER_SYSTEM_PROMPT,
    )


sticker_agent = create_sticker_agent()


def pick_sticker_payload(context: str) -> str:
    """返回表情包占位结果 JSON 字符串。"""
    structured = get_qwen_model().with_structured_output(StickerPick)
    chosen = structured.invoke(
        [
            {"role": "system", "content": STICKER_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ]
    )
    payload = {
        "ok": True,
        "keyword": chosen.keyword,
        "mood": chosen.mood,
        "caption": chosen.caption,
        "sticker_url": resolve_sticker_url(keyword=chosen.keyword, mood=chosen.mood),
    }
    return json.dumps(payload, ensure_ascii=False)
