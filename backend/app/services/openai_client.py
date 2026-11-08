import os

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
from typing import Literal

load_dotenv()


class OpenAIModel(BaseModel):
    model: Literal["deepseek", "kimi"]


def get_openai_client(model: OpenAIModel) -> tuple[OpenAI, str]:
    if model.model == "deepseek":
        prefix = "DEEPSEEK"
    else:
        prefix = "KIMI"

    api_key = os.getenv(f"{prefix}_API_KEY")
    base_url = os.getenv(f"{prefix}_BASE_URL")
    model_name = os.getenv(f"{prefix}_MODEL")
    if not api_key or not base_url or not model_name:
        raise ValueError(
            f"{prefix.title()} API key, base URL, and model must be configured."
        )

    openai_client = OpenAI(api_key=api_key, base_url=base_url, timeout=30.0)
    return openai_client, model_name
