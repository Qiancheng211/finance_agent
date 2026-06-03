# Finance Agent

面向个人消费管理场景的智能记账 Agent。项目支持自然语言记账、CSV/Excel 账单导入、付款截图识别、账单查询与改删、长期记忆和用户画像等能力，目标是把传统 CRUD 记账系统升级为可对话、可审核、可追溯的 AI 应用。

> 当前项目用于学习、作品集和简历展示。请不要把真实账单、真实 API Key 或数据库连接串提交到公开仓库。

## 功能

- 自然语言记账：支持单笔和多笔消费录入。
- CSV/Excel 导入：基于结构化解析器读取账单文件，不走向量化文档检索。
- 付款截图识别：调用 Qwen 视觉模型抽取交易时间、商户、金额等字段。
- AI 分类：使用 Few-shot + structured output 对交易记录做消费分类。
- 去重入库：基于 `raw_hash` 过滤重复交易。
- 账单管理：提供查询、修改、删除等 REST API。
- 长期记忆：使用 mem0 保存用户偏好、分类规则、预算目标和交互风格。
- 前端审核：静态页面支持账单列表、筛选、编辑、删除和 SSE 对话展示。
- 表情包反馈：记账成功后可返回本地或占位表情包。

## 技术栈

- Python 3.13+
- FastAPI
- LangChain / LangGraph Checkpointer
- Qwen / DashScope OpenAI-compatible API
- PostgreSQL
- SQLAlchemy
- pandas / openpyxl
- mem0
- Server-Sent Events

## 项目结构

```text
app/
  api/v1/finance.py          # Finance API and SSE endpoints
  common/logger.py           # Logging setup
  finance_agent/
    ai_classifier.py         # AI transaction category classifier
    config.py                # Model and environment config
    db.py                    # SQLAlchemy engine/session
    deduplicator.py          # Duplicate transaction filtering
    finance_agent.py         # LangChain create_agent entry
    image_parser.py          # Vision model screenshot parser
    memory.py                # mem0 long-term memory wrapper
    models.py                # Pydantic transaction models
    parser.py                # CSV/Excel parser and normalization
    profile_manager.py       # User profile extraction
    repository.py            # Database access layer
    sticker_agent.py         # Sticker selection helper
    tables.py                # SQLAlchemy table definitions
    tools.py                 # LangChain tools
  static/
    finance.html             # Frontend demo page
    stickers/                # Optional local sticker assets
resources/
  sample_bill.csv            # Demo CSV bill
  test_bill.png              # Demo screenshot bill
docs/
  v1_manual_test_plan.md     # Manual regression checklist
```

## Environment

Copy `app/.env.example` to `app/.env` and fill in your own values.

```env
DASHSCOPE_API_KEY=
BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com

MEM0_API_KEY=

FINANCE_DATABASE_URL=<your-sqlalchemy-postgresql-url>
```

Notes:

- `DASHSCOPE_API_KEY` is required for the Qwen text and vision model flow.
- `FINANCE_DATABASE_URL` is required for business data persistence.
- `MEM0_API_KEY` is optional. Without it, the app still runs, but long-term memory is disabled.
- `.env`, local uploads, logs, mem0 cache and database files are ignored by `.gitignore`.

## Run

Install dependencies:

```bash
uv sync
```

Start the server:

```bash
uv run python -m app.main
```

Open:

- Frontend: `http://127.0.0.1:8001/`
- API docs: `http://127.0.0.1:8001/docs`

## Core APIs

Register an access code:

```http
POST /api/v1/finance/auth/register
```

Login with an access code:

```http
POST /api/v1/finance/auth/login
```

SSE chat:

```http
POST /api/v1/finance/chat/stream
```

Request body:

```json
{
  "message": "今天中午吃饭20，晚上奶茶15，打车28，帮我记账",
  "user_id": "user_xxx",
  "thread_id": "thread_xxx",
  "sticker_enabled": true
}
```

Transaction APIs:

```http
GET /api/v1/finance/transactions?limit=30&keyword=&category=
PATCH /api/v1/finance/transactions/{transaction_id}
DELETE /api/v1/finance/transactions/{transaction_id}
```

## Important Limitations

- CSV/Excel is parsed as structured transaction data. It is not loaded with LangChain document loaders or embedded into a vector database.
- The app uses mem0 for long-term memory retrieval. It does not self-host Chroma, FAISS, Milvus or pgvector.
- The current SSE endpoint streams the final response in chunks after the Agent run completes. It is suitable for frontend streaming display, but it is not token-level model streaming.
- Access-code based identity is a demo mechanism. For production, add real authentication and user-level authorization.
- Before public release, verify that transaction ownership filtering matches your database schema and demo requirements.


