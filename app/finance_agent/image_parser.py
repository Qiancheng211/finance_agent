import base64
from pathlib import Path

from pydantic import BaseModel, Field

from app.finance_agent.config import get_qwen_model
import pandas as pd

from app.finance_agent.models import TransactionRecord
from app.finance_agent.parser import build_transaction_hash

class ImageTransaction(BaseModel):
    """图片中识别出的交易信息"""

    transaction_time: str | None = Field(default=None, description="交易时间，如果看不清则为 null")
    merchant: str | None = Field(default=None, description="商户、收款方或付款方")
    description: str | None = Field(default=None, description="交易说明")
    amount: float = Field(default=0.0, description="交易金额，统一为正数")
    income_expense_type: str = Field(default="unknown", description="income、expense、transfer、unknown")
    payment_method: str | None = Field(default=None, description="支付方式")
    source: str = Field(default="screenshot", description="来源，固定为 screenshot")
    confidence: float = Field(default=0.0, description="识别置信度，0 到 1")


class ImageTransactionList(BaseModel):
    """图片交易识别结果"""

    transactions: list[ImageTransaction] = Field(default_factory=list, description="图片中识别出的交易列表")


IMAGE_PARSE_PROMPT = """
# 身份
你是一个个人记账截图识别助手。

# 任务
从用户上传的付款截图、转账截图、账单截图中提取交易信息。

# 输出要求
请使用结构化输出，返回图片中能识别出的所有交易。

# 字段规则
- transaction_time：交易时间，看不清则为 null。
- merchant：商户、收款方或付款方，看不清则为 null。
- description：交易说明，看不清则为 null。
- amount：交易金额，必须是正数；看不清则为 0。
- income_expense_type：只能是 income、expense、transfer、unknown。
- payment_method：支付方式，例如支付宝、微信、银行卡；看不清则为 null。
- source：固定为 screenshot。
- confidence：识别置信度，0 到 1。

# 注意事项
- 不要编造图片中不存在的信息。
- 如果图片不是账单或付款截图，transactions 返回空列表。
- 如果一张图里有多笔交易，请返回多条。
"""


def encode_image_to_base64(image_path: str) -> tuple[str, str]:
    """读取图片并转成 base64"""
    path = Path(image_path)

    if not path.exists():
        raise FileNotFoundError(f"图片不存在: {image_path}")

    suffix = path.suffix.lower()
    mime_type_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }

    mime_type = mime_type_map.get(suffix)
    if mime_type is None:
        raise ValueError(f"暂不支持的图片类型: {suffix}")

    image_b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
    return image_b64, mime_type


def parse_bill_image(image_path: str) -> ImageTransactionList:
    """使用视觉模型识别账单截图"""
    image_b64, mime_type = encode_image_to_base64(image_path)

    model = get_qwen_model(model_name="qwen-vl-plus")
    structured_model = model.with_structured_output(ImageTransactionList)

    return structured_model.invoke([
        {
            "role": "system",
            "content": IMAGE_PARSE_PROMPT,
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "base64": image_b64,
                    "mime_type": mime_type,
                },
                {
                    "type": "text",
                    "text": "请识别这张图片中的交易信息。",
                },
            ],
        },
    ])




from app.finance_agent.models import TransactionRecord
from app.finance_agent.parser import build_transaction_hash


def image_transactions_to_records(image_result: ImageTransactionList) -> list[TransactionRecord]:
    """把图片识别结果转换成统一交易记录"""
    records: list[TransactionRecord] = []

    for item in image_result.transactions:
        transaction_time = None
        if item.transaction_time:
            try:
                transaction_time = pd.to_datetime(item.transaction_time).to_pydatetime()
            except Exception:
                transaction_time = None

        record = TransactionRecord(
            transaction_time=transaction_time,
            merchant=item.merchant or "",
            description=item.description or "",
            amount=item.amount,
            income_expense_type=item.income_expense_type,
            payment_method=item.payment_method or "",
            source=item.source,
            raw_data=item.model_dump(),
        )

        record.raw_hash = build_transaction_hash(record)
        records.append(record)

    return records