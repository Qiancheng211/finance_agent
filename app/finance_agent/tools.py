import json
from datetime import datetime

import pandas as pd
from langchain.tools import tool
from pydantic import BaseModel, Field

from app.finance_agent.ai_classifier import apply_categories
from app.finance_agent.deduplicator import split_duplicate_records
from app.finance_agent.image_parser import image_transactions_to_records, parse_bill_image
from app.finance_agent.models import TransactionRecord
from app.finance_agent.parser import build_transaction_hash, normalize_records, read_bill_file
from app.finance_agent.repository import (
    delete_transaction,
    get_existing_hashes,
    list_recent_transactions,
    list_transactions,
    save_transactions,
    sum_amount_by_category,
    sum_amount_by_merchant,
    update_transaction,
)
from app.finance_agent.sticker_agent import pick_sticker_payload


class ImportBillInput(BaseModel):
    """导入账单工具的输入参数"""

    file_path: str = Field(description="本地账单文件路径，支持 CSV、Excel 文件")
class ImportImageBillInput(BaseModel):
    """导入截图账单工具的输入参数"""

    image_path: str = Field(description="本地账单截图路径，支持 PNG、JPG、JPEG、WEBP")


class QueryTransactionsInput(BaseModel):
    """查询交易工具的输入参数"""

    query_type: str = Field(description="查询类型，可选 recent、category_sum、merchant_sum")
    keyword: str = Field(default="", description="查询关键词。category_sum 时填分类名，merchant_sum 时填商户关键词")
    limit: int = Field(default=10, description="recent 查询时返回的记录数量")


class ConversationEntry(BaseModel):
    amount: float = Field(description="金额，必须是正数")
    merchant: str = Field(default="", description="商户或交易对象，可为空")
    description: str = Field(default="", description="交易说明，可为空")
    payment_method: str = Field(default="", description="支付方式，可为空")
    transaction_time: str = Field(default="", description="交易时间，ISO 字符串；为空时默认当前时间")
    income_expense_type: str = Field(default="expense", description="收支类型，默认 expense")


class RecordTransactionsInput(BaseModel):
    thread_id: str = Field(description="会话 ID，用于画像和审计关联")
    entries: list[ConversationEntry] = Field(default_factory=list, description="从对话抽取出的交易列表")


class ListTransactionsInput(BaseModel):
    limit: int = Field(default=30, description="返回记录条数")
    keyword: str = Field(default="", description="按商户或描述模糊搜索")
    category: str = Field(default="", description="按分类过滤")


class UpdateTransactionInput(BaseModel):
    transaction_id: int = Field(description="要修改的账单 ID")
    amount: float | None = Field(default=None, description="新金额")
    merchant: str | None = Field(default=None, description="新商户")
    description: str | None = Field(default=None, description="新说明")
    category: str | None = Field(default=None, description="新分类")
    payment_method: str | None = Field(default=None, description="新支付方式")
    transaction_time: str | None = Field(default=None, description="新时间，ISO 字符串")


class DeleteTransactionInput(BaseModel):
    transaction_id: int = Field(description="要删除的账单 ID")


class SendStickerInput(BaseModel):
    enabled: bool = Field(default=True, description="是否允许发表情包。false 时必须直接跳过")
    context: str = Field(default="", description="记账结果上下文，供表情包 Agent 选择风格")


def _parse_iso_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return pd.to_datetime(value).to_pydatetime()
    except Exception:
        return None


@tool(args_schema=ImportBillInput)
def import_bill_tool(file_path: str) -> str:
    """导入账单文件，完成读取、字段标准化、去重、AI 分类并写入数据库，返回导入摘要。"""
    raw_records = read_bill_file(file_path)
    normalized_records = normalize_records(raw_records)

    existing_hashes = get_existing_hashes()
    new_records, duplicate_records = split_duplicate_records(
        normalized_records,
        existing_hashes=existing_hashes,
    )

    categorized_records = apply_categories(new_records)
    saved_count = save_transactions(categorized_records)

    lines = [
        "账单导入完成。",
        f"原始记录数：{len(raw_records)}",
        f"新增记录数：{len(categorized_records)}",
        f"重复记录数：{len(duplicate_records)}",
        f"成功入库数：{saved_count}",
        "",
        "分类结果预览：",
    ]
    for record in categorized_records[:5]:
        lines.append(
            f"- {record.transaction_time} | {record.merchant} | {record.amount}元 | {record.category}"
        )

    return "\n".join(lines)



@tool(args_schema=ImportImageBillInput)
def import_image_bill_tool(image_path: str) -> str:
    """导入账单截图，使用视觉模型识别交易信息，完成去重、AI 分类和入库。"""
    image_result = parse_bill_image(image_path)
    normalized_records = image_transactions_to_records(image_result)

    existing_hashes = get_existing_hashes()
    new_records, duplicate_records = split_duplicate_records(
        normalized_records,
        existing_hashes=existing_hashes,
    )

    categorized_records = apply_categories(new_records)
    saved_count = save_transactions(categorized_records)

    lines = [
        "截图账单导入完成。",
        f"识别记录数：{len(normalized_records)}",
        f"新增记录数：{len(categorized_records)}",
        f"重复记录数：{len(duplicate_records)}",
        f"成功入库数：{saved_count}",
        "",
        "识别与分类结果预览：",
    ]

    for record in categorized_records[:5]:
        lines.append(
            f"- {record.transaction_time} | {record.merchant} | {record.amount}元 | {record.category}"
        )

    return "\n".join(lines)


@tool(args_schema=QueryTransactionsInput)
def query_transactions_tool(query_type: str, keyword: str = "", limit: int = 10) -> str:
    """查询交易记录，支持最近交易、按分类统计金额、按商户关键词统计金额。"""
    if query_type == "recent":
        records = list_recent_transactions(limit=limit)

        if not records:
            return "暂时没有交易记录。"

        lines = ["最近交易记录："]
        for record in records:
            lines.append(
                f"- {record.transaction_time} | {record.merchant} | {record.amount}元 | {record.category}"
            )
        return "\n".join(lines)

    if query_type == "category_sum":
        if not keyword:
            return "请提供要统计的分类名称。"
        total = sum_amount_by_category(keyword)
        return f"{keyword} 分类总金额为：{total:.2f} 元。"

    if query_type == "merchant_sum":
        if not keyword:
            return "请提供商户关键词。"
        total = sum_amount_by_merchant(keyword)
        return f"商户包含“{keyword}”的交易总金额为：{total:.2f} 元。"

    return "不支持的查询类型，请使用 recent、category_sum 或 merchant_sum。"


@tool(args_schema=RecordTransactionsInput)
def record_transactions_tool(thread_id: str, entries: list[ConversationEntry]) -> str:
    """
    对话记账工具：将主 Agent 从对话抽取出的多笔交易入库。
    返回 JSON 字符串，包含成功/失败明细，便于前端按事件渲染。
    """
    if not entries:
        return json.dumps(
            {
                "ok": False,
                "message": "未提供可入库的账单条目。",
                "saved_count": 0,
                "skipped": [{"reason": "entries 为空"}],
            },
            ensure_ascii=False,
        )

    normalized: list[TransactionRecord] = []
    skipped: list[dict] = []

    for idx, entry in enumerate(entries, start=1):
        if entry.amount is None or float(entry.amount) <= 0:
            skipped.append({"index": idx, "reason": "金额缺失或不合法"})
            continue

        record = TransactionRecord(
            transaction_time=_parse_iso_datetime(entry.transaction_time) or datetime.now(),
            merchant=(entry.merchant or "").strip(),
            description=(entry.description or entry.merchant or "").strip(),
            amount=abs(float(entry.amount)),
            income_expense_type=(entry.income_expense_type or "expense").strip() or "expense",
            payment_method=(entry.payment_method or "").strip(),
            source="chat",
            raw_data={
                "thread_id": thread_id,
                "from": "chat",
                "merchant": entry.merchant,
                "description": entry.description,
                "amount": entry.amount,
                "transaction_time": entry.transaction_time,
            },
        )
        record.raw_hash = build_transaction_hash(record)
        normalized.append(record)

    existing_hashes = get_existing_hashes()
    new_records, duplicate_records = split_duplicate_records(normalized, existing_hashes=existing_hashes)

    categorized_records = apply_categories(new_records)
    saved_count = save_transactions(categorized_records)

    for dup in duplicate_records:
        skipped.append({"reason": "重复记录", "merchant": dup.merchant, "amount": dup.amount})

    return json.dumps(
        {
            "ok": True,
            "thread_id": thread_id,
            "input_count": len(entries),
            "normalized_count": len(normalized),
            "saved_count": saved_count,
            "skipped_count": len(skipped),
            "saved": [
                {
                    "transaction_time": str(item.transaction_time),
                    "merchant": item.merchant,
                    "amount": item.amount,
                    "category": item.category,
                    "category_reason": item.category_reason,
                }
                for item in categorized_records
            ],
            "skipped": skipped,
        },
        ensure_ascii=False,
    )


@tool(args_schema=ListTransactionsInput)
def list_transactions_tool(limit: int = 30, keyword: str = "", category: str = "") -> str:
    """查询已入库账单，支持关键词和分类过滤。"""
    records = list_transactions(limit=limit, keyword=keyword, category=category)
    payload = [
        {
            "id": item.id,
            "transaction_time": str(item.transaction_time) if item.transaction_time else "",
            "merchant": item.merchant or "",
            "description": item.description or "",
            "amount": item.amount,
            "category": item.category,
            "payment_method": item.payment_method or "",
        }
        for item in records
    ]
    return json.dumps({"ok": True, "count": len(payload), "items": payload}, ensure_ascii=False)


@tool(args_schema=UpdateTransactionInput)
def update_transaction_tool(
    transaction_id: int,
    amount: float | None = None,
    merchant: str | None = None,
    description: str | None = None,
    category: str | None = None,
    payment_method: str | None = None,
    transaction_time: str | None = None,
) -> str:
    """修改一条账单记录。"""
    updated = update_transaction(
        transaction_id,
        amount=abs(float(amount)) if amount is not None else None,
        merchant=merchant,
        description=description,
        category=category,
        payment_method=payment_method,
        transaction_time=_parse_iso_datetime(transaction_time or ""),
    )
    if not updated:
        return json.dumps({"ok": False, "message": f"未找到 ID={transaction_id} 的记录"}, ensure_ascii=False)

    return json.dumps(
        {
            "ok": True,
            "item": {
                "id": updated.id,
                "transaction_time": str(updated.transaction_time) if updated.transaction_time else "",
                "merchant": updated.merchant or "",
                "description": updated.description or "",
                "amount": updated.amount,
                "category": updated.category,
                "payment_method": updated.payment_method or "",
            },
        },
        ensure_ascii=False,
    )


@tool(args_schema=DeleteTransactionInput)
def delete_transaction_tool(transaction_id: int) -> str:
    """删除一条账单记录。"""
    deleted = delete_transaction(transaction_id)
    return json.dumps({"ok": deleted, "transaction_id": transaction_id}, ensure_ascii=False)


@tool(args_schema=SendStickerInput)
def send_sticker_tool(enabled: bool = True, context: str = "") -> str:
    """
    表情包工具：受主 Agent 控制执行。
    - enabled=false 时必须跳过，不调用子 Agent。
    - enabled=true 时调用独立表情包 Agent（MVP 占位 URL）。
    """
    if not enabled:
        return json.dumps({"ok": False, "skipped": True, "reason": "sticker disabled"}, ensure_ascii=False)

    return pick_sticker_payload(context=context)
