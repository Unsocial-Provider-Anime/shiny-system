import logging
import os
from typing import Any

from supabase import Client

logger = logging.getLogger(__name__)


class TokenLimitExceeded(Exception):
    def __init__(self, reset_at: str) -> None:
        super().__init__("The daily token limit has been reached.")
        self.reset_at = reset_at


def _token_limit() -> int:
    try:
        limit = int(os.getenv("DAILY_TOKEN_LIMIT", "20000"))
    except ValueError as error:
        raise RuntimeError("DAILY_TOKEN_LIMIT must be a positive integer.") from error
    if limit <= 0:
        raise RuntimeError("DAILY_TOKEN_LIMIT must be a positive integer.")
    return limit


def _rpc_row(response: Any) -> dict[str, Any]:
    data = response.data
    if isinstance(data, dict):
        return data
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    raise RuntimeError("Token usage database operation returned no record.")


def _estimate_reservation(messages: list[dict[str, Any]], max_tokens: int) -> int:
    prompt_bytes = sum(
        len(content.encode("utf-8"))
        for message in messages
        if isinstance((content := message.get("content")), str)
    )
    return prompt_bytes + len(messages) * 8 + max_tokens


def _settle(
    database: Client,
    user_id: int,
    reserved_tokens: int,
    actual_tokens: int,
) -> None:
    database.rpc(
        "settle_user_token_usage",
        {
            "p_user_id": user_id,
            "p_reserved_tokens": reserved_tokens,
            "p_actual_tokens": actual_tokens,
        },
    ).execute()


def create_chat_completion(
    client: Any,
    database: Client | None,
    user_id: int | None,
    **request: Any,
) -> Any:
    if database is None or user_id is None:
        return client.chat.completions.create(**request)

    reserved_tokens = _estimate_reservation(request["messages"], request["max_tokens"])
    reservation = _rpc_row(
        database.rpc(
            "reserve_user_token_usage",
            {
                "p_user_id": user_id,
                "p_daily_limit": _token_limit(),
                "p_reserved_tokens": reserved_tokens,
            },
        ).execute()
    )
    if not reservation.get("allowed"):
        raise TokenLimitExceeded(str(reservation.get("reset_at", "")))

    try:
        response = client.chat.completions.create(**request)
    except Exception:
        try:
            _settle(database, user_id, reserved_tokens, reserved_tokens)
        except Exception:
            logger.exception("Could not settle failed AI request token reservation.")
        raise

    usage = getattr(response, "usage", None)
    actual_tokens = getattr(usage, "total_tokens", None)
    if not isinstance(actual_tokens, int) or actual_tokens < 0:
        actual_tokens = reserved_tokens
    try:
        _settle(database, user_id, reserved_tokens, actual_tokens)
    except Exception as error:
        logger.exception("Could not settle AI request token usage.")
        raise RuntimeError("AI token usage could not be recorded.") from error
    return response