import logging

from pydantic import BaseModel, Field

from app.finance_agent.config import get_qwen_model
from app.finance_agent.repository import upsert_user_profile

logger = logging.getLogger(__name__)


# 仅当用户消息命中以下关键词时，才调用模型提取画像，避免每轮都消耗 token。
PROFILE_TRIGGER_KEYWORDS = (
    "叫我",
    "我叫",
    "我是",
    "名字",
    "性别",
    "我喜欢",
    "我习惯",
    "偏好",
    "习惯",
    "以后",
    "不要",
    "预算",
    "目标",
    "记住",
)


class ProfileUpdate(BaseModel):
    nickname: str = Field(default="", description="用户昵称。未知则空字符串。")
    gender: str = Field(default="", description="用户性别偏好。未知则空字符串。")
    habits: str = Field(default="", description="消费习惯或偏好。未知则空字符串。")
    has_update: bool = Field(default=False, description="这条消息是否包含新的画像信息。")


PROFILE_UPDATE_PROMPT = """
你是记账助手的用户画像提取器。
请从用户消息中提取画像增量信息，只返回结构化结果。

字段规则：
- nickname：仅当用户明确表达称呼或名字时填写。
- gender：仅当用户明确表达性别时填写。
- habits：仅当用户表达稳定消费习惯、偏好、禁忌时填写，保持一句中文。
- has_update：只要上述任一字段有新信息，则为 true。
"""


def _hits_trigger(user_message: str) -> bool:
    text = (user_message or "").strip()
    if not text:
        return False
    return any(keyword in text for keyword in PROFILE_TRIGGER_KEYWORDS)


def update_profile_from_message(user_id: str, thread_id: str, user_message: str) -> None:
    """每轮对话后尝试增量更新用户画像（以 user_id 为主，同时记录 thread_id）。

    仅在消息命中画像关键词时才调用模型，命中后失败也不影响主流程。画像不在前端展示，仅后台积累。
    """
    user_id = (user_id or "").strip()
    if not user_id:
        return

    if not _hits_trigger(user_message):
        # 未命中关键词：不调用模型，仅确保画像行存在并更新最近会话。
        upsert_user_profile(user_id, thread_id=thread_id)
        return

    try:
        model = get_qwen_model().with_structured_output(ProfileUpdate)
        extracted = model.invoke(
            [
                {"role": "system", "content": PROFILE_UPDATE_PROMPT},
                {"role": "user", "content": user_message},
            ]
        )
    except Exception as exc:  # 画像是增值功能，失败不应中断对话
        logger.warning("用户画像提取失败 user_id=%s: %s", user_id, exc)
        upsert_user_profile(user_id, thread_id=thread_id)
        return

    if not extracted.has_update:
        upsert_user_profile(user_id, thread_id=thread_id)
        return

    upsert_user_profile(
        user_id,
        thread_id=thread_id,
        nickname=extracted.nickname.strip(),
        gender=extracted.gender.strip(),
        habits=extracted.habits.strip(),
    )
