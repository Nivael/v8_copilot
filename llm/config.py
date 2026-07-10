from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from settings import DATA_ROOT


MODEL_ENV = "V8_OPENAI_MODEL"
LOCAL_SECRETS_FILE = Path(os.environ.get(
    "V8_LOCAL_SECRETS_FILE",
    DATA_ROOT / "local_secrets" / "v8_copilot.env",
)).expanduser().resolve()


class LLMConfigurationError(RuntimeError):
    pass


def load_local_secrets() -> None:
    load_dotenv(LOCAL_SECRETS_FILE, override=False)


def resolve_model(explicit_model: str | None = None) -> str:
    if explicit_model:
        return explicit_model
    load_local_secrets()
    model = os.getenv(MODEL_ENV, "").strip()
    if not model:
        raise LLMConfigurationError(
            f"缺少 {MODEL_ENV}；请在 local_secrets/v8_copilot.env 固定模型名"
        )
    return model
