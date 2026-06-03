from pydantic import BaseModel, Field

from app.finance_agent.config import get_qwen_model
from app.finance_agent.models import TransactionRecord


class TransactionCategory(BaseModel):
    """AI 对单条交易的分类结果"""

    category: str = Field(description="分类名称，如餐饮、交通、学习、娱乐、购物、转账、收入、其他")
    confidence: float = Field(description="置信度，0 到 1")
    reason: str = Field(description="分类理由")


CATEGORY_EXAMPLES = [
    {
        "input": {
            "merchant": "瑞幸咖啡",
            "description": "拿铁",
            "amount": 18.9,
            "income_expense_type": "expense",
        },
        "output": {
            "category": "餐饮",
            "confidence": 0.98,
            "reason": "商户和说明都与咖啡消费相关。",
        },
    },
    {
        "input": {
            "merchant": "地铁",
            "description": "通勤",
            "amount": 4.0,
            "income_expense_type": "expense",
        },
        "output": {
            "category": "交通",
            "confidence": 0.95,
            "reason": "商户和说明都指向日常通勤。",
        },
    },
    {
        "input": {
            "merchant": "张三",
            "description": "转账",
            "amount": 500,
            "income_expense_type": "transfer",
        },
        "output": {
            "category": "转账",
            "confidence": 0.9,
            "reason": "说明中明确出现转账。",
        },
    },
]


def build_examples_prompt() -> str:
    """把 few-shot 示例列表转换成 prompt 文本"""
    parts = []

    for index, example in enumerate(CATEGORY_EXAMPLES, start=1):
        input_data = example["input"]
        output_data = example["output"]

        parts.append(
            f"""
<example id="{index}">
输入：
商户/对象：{input_data.get("merchant", "")}
说明：{input_data.get("description", "")}
金额：{input_data.get("amount", "")}
收支类型：{input_data.get("income_expense_type", "")}

输出：
category: {output_data.get("category", "")}
confidence: {output_data.get("confidence", "")}
reason: {output_data.get("reason", "")}
</example>
""".strip()
        )

    return "\n\n".join(parts)


CATEGORY_SYSTEM_PROMPT_TEMPLATE = """
# 身份
你是一个个人消费记账分类助手，负责把交易记录分类为适合个人财务分析的消费类别。

# 任务
根据用户提供的交易信息，判断这笔交易最合适的分类，并给出置信度和简短理由。

# 可选分类
你只能从以下分类中选择一个：
- 餐饮
- 交通
- 学习
- 娱乐
- 购物
- 转账
- 收入
- 医疗
- 居住
- 其他

# 判断规则
- 如果收支类型是 income，优先考虑“收入”。
- 如果交易对象或说明包含咖啡、奶茶、餐厅、外卖、饭店等，归为“餐饮”。
- 如果包含地铁、公交、打车、火车、机票等，归为“交通”。
- 如果包含课程、书籍、教材、考试、学习平台等，归为“学习”。
- 如果包含电影、游戏、会员、演出、音乐、视频等，归为“娱乐”。
- 如果包含淘宝、京东、拼多多、超市、便利店等，归为“购物”。
- 如果包含房租、水电、物业、宽带等，归为“居住”。
- 如果包含医院、药店、挂号、体检等，归为“医疗”。
- 如果是朋友之间转入转出、红包、银行卡互转，归为“转账”。
- 如果无法判断，归为“其他”。

# 置信度规则
- 0.90-1.00：分类依据非常明确。
- 0.70-0.89：分类较可能正确，但信息不完整。
- 0.40-0.69：只能根据有限线索推测。
- 0.00-0.39：基本无法判断，应归为“其他”。

# 输出要求
- 必须使用结构化输出。
- 不要编造没有出现在交易记录中的信息。
- reason 用一句中文说明依据，尽量简短。

# 示例
{examples}
"""


def build_category_system_prompt() -> str:
    """构建分类系统提示词"""
    return CATEGORY_SYSTEM_PROMPT_TEMPLATE.format(
        examples=build_examples_prompt()
    )


def classify_transaction(record: TransactionRecord) -> TransactionCategory:
    """使用 AI 对单条交易分类"""
    model = get_qwen_model()
    structured_model = model.with_structured_output(TransactionCategory)

    user_input = f"""
请对下面这条交易进行分类：

交易时间：{record.transaction_time}
商户/对象：{record.merchant}
说明：{record.description}
金额：{record.amount}
收支类型：{record.income_expense_type}
支付方式：{record.payment_method}
来源：{record.source}
"""

    return structured_model.invoke([
        {"role": "system", "content": build_category_system_prompt()},
        {"role": "user", "content": user_input},
    ])


def classify_transactions(records: list[TransactionRecord]) -> list[TransactionCategory]:
    """批量分类交易记录"""
    return [classify_transaction(record) for record in records]


def apply_categories(records: list[TransactionRecord]) -> list[TransactionRecord]:
    """对交易记录进行 AI 分类，并把结果写回记录"""
    for record in records:
        category_result = classify_transaction(record)
        record.category = category_result.category
        record.category_confidence = category_result.confidence
        record.category_reason = category_result.reason
    
    return records