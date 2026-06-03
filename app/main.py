import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import finance
from app.common.logger import setup_logging
from app.finance_agent.tables import create_tables


setup_logging()

app = FastAPI(
    title="Finance Agent API",
    description="面向个人消费管理的可审核智能记账 Agent",
    version="0.1.0",
)


@app.on_event("startup")
def on_startup() -> None:
    create_tables()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(finance.router, prefix="/api/v1", tags=["智能记账"])

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir, html=True), name="static")


@app.get("/", include_in_schema=False)
async def serve_finance_home():
    finance_page = os.path.join(static_dir, "finance.html")
    if os.path.exists(finance_page):
        return FileResponse(finance_page)
    return {"message": "Finance Agent API is running", "status": "ok"}


@app.get("/{path:path}", include_in_schema=False)
async def serve_frontend(path: str):
    if path.startswith("api/"):
        return JSONResponse({"error": "Not Found"}, status_code=404)

    file_path = os.path.join(static_dir, path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)

    finance_page = os.path.join(static_dir, "finance.html")
    if os.path.exists(finance_page):
        return FileResponse(finance_page)

    return {"message": "Finance Agent API is running", "status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8001, reload=True)
