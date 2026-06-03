from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field

IncomeExpenseType = Literal["income", "expense","transfer","unknown"]


class TransactionRecord(BaseModel):   
    #统一后的交易记录结构
    transaction_time: Optional[datetime] = Field(default=None, description="交易时间")
    merchant: Optional[str] = Field(default="", description="商户或交易对象")
    description: Optional[str] = Field(default="", description="交易说明")
    amount: float = Field(default=0.0, description="交易金额，统一为正数")
    income_expense_type: IncomeExpenseType = Field(default="unknown", description="收支类型")
    category: str = Field(default="未分类", description="消费分类")
    category_confidence: float = Field(default=0.0, description="分类置信度")
    category_reason: str = Field(default="", description="分类原因")
    payment_method: Optional[str] = Field(default="", description="支付方式")
    source: Optional[str] = Field(default="", description="账单来源，如 alipay/wechat/screenshot")
    raw_hash: str = Field(default="", description="交易去重指纹")
    raw_data: dict = Field(default_factory=dict, description="原始行数据，方便追溯")
    