from pathlib import Path
from typing import Any
import pandas as pd
from app.finance_agent.models import TransactionRecord
import hashlib


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def read_bill_file(file_path: str) -> list[dict[str, Any]]:  
    #"""读取 CSV / Excel 账单文件，返回原始行数据列表"""
    path = Path(file_path)   #把字符串转换为path字串,可以用path.xx操作

    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    suffix = path.suffix.lower()  #获取文件后缀,lower可以转小写

    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"暂不支持的文件类型: {suffix}")

    if suffix == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)


    df = df.fillna("") #处理空值.把所有空值都替换成空字符串 ""

    return df.to_dict(orient="records")   #它把表格转成列表字典,最后返回list[dict[str, Any]],一行 = 一个字典
    


def normalize_records(records: list[dict], source: str = "unknown") -> list[TransactionRecord]:  
     #这里的表示默认是unknown
     result = []  #保存转化的结果
     for row in records:    #传入的record,一行一行的
        transaction = TransactionRecord(
            transaction_time=_parse_datetime(_pick(row, ["交易时间", "时间", "付款时间", "创建时间"])),
            merchant=_pick(row, ["交易对方", "商户", "商家", "对方户名", "收款方", "付款方"]),
            description=_pick(row, ["商品说明", "商品", "交易说明", "备注", "摘要"]),
            amount=_parse_amount(_pick(row, ["金额", "金额(元)", "交易金额", "支出", "收入"])),
            income_expense_type=_parse_income_expense_type(_pick(row, ["收/支", "收支类型", "交易类型"])),
            payment_method=_pick(row, ["支付方式", "付款方式", "账户", "银行卡"]),
            source=source,
            raw_data=row,
            
        )
        transaction.raw_hash = build_transaction_hash(transaction)
        result.append(transaction)
    
     return result






def _pick(row: dict, keys: list[str]) -> str:   #从多个候选字段选一个不是空的
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""

def _parse_amount(value: str) -> float:  #"""把金额转成正数 float"""
    if not value:
        return 0.0

    text = str(value).strip()    #转字符串,并去掉空格
    text = text.replace("¥", "").replace("￥", "")
    text = text.replace(",", "").replace("元", "")
    text = text.replace("+", "").replace("-", "")
    try:    
        return abs(float(text))  #abs绝对值,float字符串转小数
    except ValueError:
        return 0.0

def _parse_income_expense_type(value: str) -> str:
    """解析收入/支出/转账"""
    text = str(value).strip()

    if "支" in text or "消费" in text or "付款" in text:
        return "expense"

    if "收" in text or "收入" in text or "退款" in text:
        return "income"

    if "转账" in text or "转" in text:
        return "transfer"

    return "unknown"


def _parse_datetime(value: str):
    """解析时间"""
    if not value:
        return None

    try:
        return pd.to_datetime(value).to_pydatetime()
    except Exception:
        return None

def build_transaction_hash(transaction: TransactionRecord) -> str:
    #"""根据关键字段生成交易去重指纹"""
    raw = "|".join([
    str(transaction.transaction_time or ""),
    transaction.merchant or "",
    transaction.description or "",
    str(transaction.amount),
    transaction.income_expense_type,
    transaction.payment_method or "",
    transaction.source or "",
    ])

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()