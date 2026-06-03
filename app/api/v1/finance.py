from pathlib import Path
from uuid import uuid4
from datetime import datetime
import json
import re
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from langchain_core.messages import ToolMessage
from pydantic import BaseModel

from app.finance_agent.finance_agent import finance_agent
from app.finance_agent.memory import add_user_memory, build_memory_prompt
from app.finance_agent.profile_manager import update_profile_from_message
from app.finance_agent.repository import (
    create_user_identity,
    delete_transaction,
    get_user_identity_by_access_code,
    list_transactions,
    update_transaction,
)
from app.finance_agent.tools import import_bill_tool, import_image_bill_tool


router = APIRouter()

UPLOAD_DIR = Path("resources/uploads")
CSV_EXCEL_EXTENSIONS = {".csv", ".xlsx", ".xls"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


class FinanceChatRequest(BaseModel):
    message: str
    user_id: str
    thread_id: str = ""
    sticker_enabled: bool = True


class FinanceTransactionUpdateRequest(BaseModel):
    amount: float | None = None
    merchant: str | None = None
    description: str | None = None
    category: str | None = None
    payment_method: str | None = None
    transaction_time: str | None = None


class FinanceAccessCodeLoginRequest(BaseModel):
    access_code: str


def _normalize_access_code(value: str) -> str:
    return (value or "").strip().upper()


def _resolve_thread_id(value: str) -> str:
    clean = (value or "").strip()
    return clean if clean else f"thread_{uuid4().hex}"


def _as_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                chunks.append(item.get("text", ""))
        return "".join(chunks)
    return str(content or "")


def _parse_json_content(value: Any) -> dict[str, Any] | None:
    text = _as_text(value).strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_HTML_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")
_JSON_OBJECT_RE = re.compile(r"\{[^{}]*\}")
_EMPTY_ARRAY_RE = re.compile(r"\[[\s,]*\]")
_MULTI_BLANK_RE = re.compile(r"\n{3,}")


def _clean_assistant_text(text: str) -> str:
    """清洗助手回复，确保聊天气泡只显示纯文本。

    去掉模型偶尔复述的工具原始 JSON、代码块与 HTML 标签，避免聊天框出现脏内容。
    结构化结果（记账明细、表情包）由前端通过独立 SSE 事件单独渲染。
    """
    if not text:
        return ""

    cleaned = _CODE_FENCE_RE.sub("", text)

    # 反复从内层剥离 JSON 对象，兼容任意嵌套
    previous = None
    while previous != cleaned:
        previous = cleaned
        cleaned = _JSON_OBJECT_RE.sub("", cleaned)

    cleaned = _EMPTY_ARRAY_RE.sub("", cleaned)
    cleaned = _HTML_TAG_RE.sub("", cleaned)
    cleaned = _MULTI_BLANK_RE.sub("\n\n", cleaned)
    return cleaned.strip()


def _iter_text_chunks(text: str, chunk_size: int = 18):
    if not text:
        return
    for idx in range(0, len(text), chunk_size):
        yield text[idx : idx + chunk_size]


def _sse(event: str, data: dict[str, Any]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


def _parse_datetime_input(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


@router.post("/finance/import")
async def import_finance_file(file: UploadFile = File(...)):
    """上传账单文件或截图，并导入数据库。"""
    original_name = file.filename or ""
    suffix = Path(original_name).suffix.lower()

    if suffix not in CSV_EXCEL_EXTENSIONS and suffix not in IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"暂不支持的文件类型: {suffix}")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved_path = UPLOAD_DIR / f"{uuid4().hex}{suffix}"
    saved_path.write_bytes(await file.read())

    if suffix in CSV_EXCEL_EXTENSIONS:
        result = import_bill_tool.invoke({"file_path": str(saved_path)})
    else:
        result = import_image_bill_tool.invoke({"image_path": str(saved_path)})

    return {
        "filename": original_name,
        "saved_path": str(saved_path),
        "result": result,
    }


@router.post("/finance/auth/register")
async def register_finance_access_code():
    identity = create_user_identity()
    return {
        "access_code": identity.access_code,
        "user_id": identity.user_id,
    }


@router.post("/finance/auth/login")
async def login_finance_access_code(request: FinanceAccessCodeLoginRequest):
    access_code = _normalize_access_code(request.access_code)
    identity = get_user_identity_by_access_code(access_code)
    if identity is None:
        raise HTTPException(status_code=404, detail="访问码不存在")
    return {
        "access_code": identity.access_code,
        "user_id": identity.user_id,
    }


@router.post("/finance/chat")
async def chat_with_finance_agent(request: FinanceChatRequest):
    """向智能记账 Agent 提问。"""
    thread_id = _resolve_thread_id(request.thread_id)
    user_id = request.user_id.strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="缺少 user_id")

    runtime_hint = (
        f"运行时参数：user_id={user_id}; "
        f"thread_id={thread_id}; "
        f"sticker_enabled={str(request.sticker_enabled).lower()}。"
    )
    user_message = build_memory_prompt(user_id, request.message)
    response = finance_agent.invoke(
        {"messages": [{"role": "system", "content": runtime_hint}, {"role": "user", "content": user_message}]},
        {"configurable": {"thread_id": thread_id}},
    )
    answer = _clean_assistant_text(_as_text(response["messages"][-1].content))
    add_user_memory(user_id, thread_id, request.message, answer)
    update_profile_from_message(user_id, thread_id, request.message)
    return {"answer": answer, "thread_id": thread_id}


@router.post("/finance/chat/stream")
async def chat_with_finance_agent_stream(request: FinanceChatRequest):
    """SSE 流式对话：先 text，再 bill_saved，再 sticker。"""
    thread_id = _resolve_thread_id(request.thread_id)
    user_id = request.user_id.strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="缺少 user_id")

    runtime_hint = (
        f"运行时参数：user_id={user_id}; "
        f"thread_id={thread_id}; "
        f"sticker_enabled={str(request.sticker_enabled).lower()}。"
    )
    user_message = build_memory_prompt(user_id, request.message)
    response = finance_agent.invoke(
        {"messages": [{"role": "system", "content": runtime_hint}, {"role": "user", "content": user_message}]},
        {"configurable": {"thread_id": thread_id}},
    )

    messages = response.get("messages", [])
    final_text = _clean_assistant_text(_as_text(messages[-1].content)) if messages else ""
    bill_payload = None
    sticker_payload = None

    for msg in messages:
        if isinstance(msg, ToolMessage) and getattr(msg, "name", "") == "record_transactions_tool":
            bill_payload = _parse_json_content(msg.content) or {"ok": False, "message": _as_text(msg.content)}
        if isinstance(msg, ToolMessage) and getattr(msg, "name", "") == "send_sticker_tool":
            sticker_payload = _parse_json_content(msg.content) or {"ok": False, "message": _as_text(msg.content)}

    if not final_text:
        final_text = "好的，已处理完成。" if bill_payload else "好的。"

    add_user_memory(user_id, thread_id, request.message, final_text)
    update_profile_from_message(user_id, thread_id, request.message)

    def event_stream():
        yield _sse("meta", {"thread_id": thread_id, "sticker_enabled": request.sticker_enabled})

        for part in _iter_text_chunks(final_text):
            yield _sse("text", {"delta": part})

        if bill_payload:
            yield _sse("bill_saved", bill_payload)

        if sticker_payload and sticker_payload.get("ok") and not sticker_payload.get("skipped"):
            yield _sse("sticker", sticker_payload)

        yield _sse("done", {"ok": True})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/finance/transactions")
async def get_finance_transactions(limit: int = 30, keyword: str = "", category: str = ""):
    records = list_transactions(limit=limit, keyword=keyword, category=category)
    return {
        "count": len(records),
        "items": [
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
        ],
    }


@router.patch("/finance/transactions/{transaction_id}")
async def patch_finance_transaction(transaction_id: int, request: FinanceTransactionUpdateRequest):
    updated = update_transaction(
        transaction_id,
        amount=abs(float(request.amount)) if request.amount is not None else None,
        merchant=request.merchant,
        description=request.description,
        category=request.category,
        payment_method=request.payment_method,
        transaction_time=_parse_datetime_input(request.transaction_time),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="账单不存在")

    return {
        "id": updated.id,
        "transaction_time": str(updated.transaction_time) if updated.transaction_time else "",
        "merchant": updated.merchant or "",
        "description": updated.description or "",
        "amount": updated.amount,
        "category": updated.category,
        "payment_method": updated.payment_method or "",
    }


@router.delete("/finance/transactions/{transaction_id}")
async def remove_finance_transaction(transaction_id: int):
    deleted = delete_transaction(transaction_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="账单不存在")
    return {"ok": True, "transaction_id": transaction_id}
