import os
from pathlib import Path
from dotenv import load_dotenv     #导uv的环境变量
from langchain.chat_models import init_chat_model

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / "app" / ".env")
load_dotenv(ROOT_DIR / ".env")


def get_qwen_model(model_name: str = "qwen3-max"):
    #"""初始化 Qwen 文本模型"""
    return init_chat_model(
        model=model_name,
        model_provider="openai",
        base_url=os.getenv("DASHSCOPE_BASE_URL") or os.getenv("BASE_URL"),
        api_key=os.getenv("DASHSCOPE_API_KEY"),
    )



def get_deepseek_model(model_name: str = "deepseek-chat"):
    """初始化 DeepSeek 文本模型"""
    return init_chat_model(
        model=model_name,
        model_provider="openai",
        base_url=os.getenv("DEEPSEEK_BASE_URL"),
        api_key=os.getenv("DEEPSEEK_API_KEY"),
    )