import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.api.courses import require_user_id, router
from app.database.supabase import get_supabase_client

COURSE_ID = str(uuid4())


def valid_proposal() -> dict[str, object]:
    return {
        "title": "Testing fundamentals",
        "description": "A short course about testing.",
        "default_presentation_format": "text-and-images",
        "plan": {
            "overview": "Learn core testing techniques.",
            "target_audience": "Beginners",
            "learning_outcomes": ["Write a basic test."],
            "modules": [
                {
                    "module_id": "basics",
                    "title": "Basics",
                    "description": "Core concepts.",
                    "lessons": [
                        {
                            "lesson_id": "first-test",
                            "title": "Write a first test",
                            "purpose": "Practice a minimal test.",
                            "objectives": [
                                "Identify an assertion.",
                                "Write a test case.",
                            ],
                            "key_topics": ["Assertions"],
                            "suggested_activity": {
                                "title": "Inspect an example",
                                "description": "Review a small test.",
                                "presentation_format": "text-and-images",
                            },
                            "completion_check": "Describe what the assertion checks.",
                        }
                    ],
                }
            ],
            "capstone": "Test a small function.",
        },
    }


class FakeDatabase:
    def __init__(self, table_data: dict[str, object] | None = None):
        self.table_data = table_data or {}
        self.rpc_calls: list[tuple[str, dict[str, object]]] = []

    def table(self, name: str) -> "FakeQuery":
        return FakeQuery(self.table_data.get(name, []))

    def rpc(self, name: str, params: dict[str, object]) -> "FakeRpc":
        self.rpc_calls.append((name, params))
        return FakeRpc(
            [{"course_id": COURSE_ID, "version_id": str(uuid4()), "version_number": 1}]
        )


class FakeQuery:
    def __init__(self, data: object):
        self.data = data

    def select(self, *_args: object) -> "FakeQuery":
        return self

    def eq(self, *_args: object) -> "FakeQuery":
        return self

    def limit(self, *_args: object) -> "FakeQuery":
        return self

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=self.data)


class FakeRpc:
    def __init__(self, data: object):
        self.data = data

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=self.data)


class CourseApiTests(unittest.TestCase):
    def make_client(
        self,
        user_id: int | None,
        database: FakeDatabase | None = None,
    ) -> TestClient:
        app = FastAPI()
        app.add_middleware(SessionMiddleware, secret_key="test-session-secret")
        app.include_router(router)
        if user_id is not None:
            app.dependency_overrides[require_user_id] = lambda: user_id
        if database is not None:
            app.dependency_overrides[get_supabase_client] = lambda: database
        return TestClient(app)

    def test_generation_requires_authentication(self) -> None:
        with self.make_client(None) as client:
            response = client.post(
                "/api/v1/course-drafts",
                json={"topic": "Testing fundamentals"},
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json()["detail"]["code"],
            "authentication_required",
        )

    def test_saves_a_proposed_course_as_a_draft_version(self) -> None:
        database = FakeDatabase()
        with self.make_client(42, database) as client:
            response = client.post("/api/v1/courses", json=valid_proposal())

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "draft")
        self.assertEqual(database.rpc_calls[0][0], "save_course_draft")
        self.assertEqual(database.rpc_calls[0][1]["p_created_by"], 42)

    def test_cannot_edit_another_authors_draft(self) -> None:
        database = FakeDatabase(
            {
                "courses": [
                    {
                        "id": COURSE_ID,
                        "created_by": 7,
                        "status": "draft",
                    }
                ]
            }
        )
        with self.make_client(42, database) as client:
            response = client.patch(
                f"/api/v1/courses/{COURSE_ID}",
                json={"title": "Changed title"},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(database.rpc_calls, [])

    def test_cannot_publish_another_authors_draft(self) -> None:
        database = FakeDatabase(
            {
                "courses": [
                    {
                        "id": COURSE_ID,
                        "created_by": 7,
                        "status": "draft",
                    }
                ]
            }
        )
        with self.make_client(42, database) as client:
            response = client.post(f"/api/v1/courses/{COURSE_ID}/publish")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(database.rpc_calls, [])

    def test_generation_returns_validated_proposal_without_saving_it(self) -> None:
        with self.make_client(42) as client, patch(
            "app.api.courses.generate_course_draft"
        ) as generate:
            generate.return_value = valid_proposal()
            response = client.post(
                "/api/v1/course-drafts",
                json={"topic": "Testing fundamentals"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Testing fundamentals")
        generate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
