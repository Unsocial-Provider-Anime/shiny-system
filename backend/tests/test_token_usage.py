import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.token_usage import TokenLimitExceeded, create_chat_completion


class TokenUsageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = MagicMock()
        self.database.rpc.return_value.execute.return_value.data = [
            {"allowed": True, "used_tokens": 60, "reset_at": "2026-11-10T12:00:00Z"}
        ]
        self.client = MagicMock()
        self.client.chat.completions.create.return_value = SimpleNamespace(
            usage=SimpleNamespace(total_tokens=60)
        )

    @patch.dict("os.environ", {"DAILY_TOKEN_LIMIT": "20000"})
    def test_reserves_then_reconciles_actual_usage(self) -> None:
        response = create_chat_completion(
            self.client,
            self.database,
            7,
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=100,
        )

        self.assertEqual(response.usage.total_tokens, 60)
        self.assertEqual(
            self.database.rpc.call_args_list[0].args[0], "reserve_user_token_usage"
        )
        self.assertEqual(
            self.database.rpc.call_args_list[1].args[0], "settle_user_token_usage"
        )
        self.assertEqual(
            self.database.rpc.call_args_list[1].args[1]["p_actual_tokens"], 60
        )

    @patch.dict("os.environ", {"DAILY_TOKEN_LIMIT": "20000"})
    def test_does_not_call_provider_when_reservation_is_denied(self) -> None:
        self.database.rpc.return_value.execute.return_value.data = [
            {"allowed": False, "used_tokens": 20000, "reset_at": "tomorrow"}
        ]

        with self.assertRaises(TokenLimitExceeded) as error:
            create_chat_completion(
                self.client,
                self.database,
                7,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=100,
            )

        self.assertEqual(error.exception.reset_at, "tomorrow")
        self.client.chat.completions.create.assert_not_called()
        self.database.rpc.assert_called_once()