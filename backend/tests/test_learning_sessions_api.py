import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.api.auth import router as auth_router
from app.api.courses import require_user_id
from app.api.learning_sessions import router as learning_sessions_router
from app.database.supabase import get_supabase_client
from app.schemas.activity import GeneratedLessonActivity

COURSE_ID = str(uuid4())
VERSION_ID = str(uuid4())
SESSION_ID = str(uuid4())


def plan_data() -> dict[str, object]:
    lesson = {
        "title": "First lesson",
        "purpose": "Learn the first concept.",
        "objectives": ["Explain the concept.", "Recognize an example."],
        "key_topics": ["Basics"],
        "suggested_activity": {
            "title": "Read an example",
            "description": "Review a short example.",
            "presentation_format": "text-and-images",
        },
        "completion_check": "Explain the concept.",
    }
    return {
        "overview": "A short course.",
        "target_audience": "Beginners",
        "learning_outcomes": ["Explain the basics."],
        "modules": [
            {
                "module_id": "basics",
                "title": "Basics",
                "description": "The basics.",
                "lessons": [
                    {**lesson, "lesson_id": "first"},
                    {
                        **lesson,
                        "lesson_id": "second",
                        "title": "Second lesson",
                    },
                ],
            }
        ],
        "capstone": "Apply the concepts.",
    }


class FakeDatabase:
    def __init__(self) -> None:
        self.table_data: dict[str, list[dict[str, object]]] = {
            "user": [],
            "courses": [
                {
                    "id": COURSE_ID,
                    "title": "Testing fundamentals",
                    "description": "A course about testing.",
                    "status": "published",
                    "visibility": "public",
                    "created_by": 7,
                    "published_version_id": VERSION_ID,
                }
            ],
            "course_versions": [
                {
                    "id": VERSION_ID,
                    "course_id": COURSE_ID,
                    "version_number": 1,
                    "plan": plan_data(),
                }
            ],
            "learning_sessions": [],
            "lesson_progress": [],
            "activities": [],
            "course_access": [],
        }
        self.rpc_calls: list[tuple[str, dict[str, object]]] = []

    def table(self, name: str) -> "FakeQuery":
        return FakeQuery(self, name)

    def rpc(self, name: str, params: dict[str, object]) -> "FakeRpc":
        self.rpc_calls.append((name, params))
        if name == "start_learning_session":
            session = {
                "id": SESSION_ID,
                "user_id": params["p_user_id"],
                "course_id": params["p_course_id"],
                "course_version_id": params["p_course_version_id"],
                "status": "active",
                "current_module_id": params["p_first_module_id"],
                "current_lesson_id": params["p_first_lesson_id"],
                "started_at": "2026-11-08T10:00:00Z",
                "updated_at": "2026-11-08T10:00:00Z",
                "completed_at": None,
            }
            existing = next(
                (
                    row
                    for row in self.table_data["learning_sessions"]
                    if row["user_id"] == params["p_user_id"]
                    and row["course_id"] == params["p_course_id"]
                    and row["status"] == "active"
                ),
                None,
            )
            if existing is not None:
                session = existing
            else:
                self.table_data["learning_sessions"].append(session)
            return FakeRpc([session])
        if name == "complete_learning_lesson":
            session = next(
                (
                    row
                    for row in self.table_data["learning_sessions"]
                    if row["id"] == params["p_session_id"]
                    and row["user_id"] == params["p_user_id"]
                ),
                None,
            )
            if session is None:
                return FakeRpc([])
            lesson_id = str(params["p_lesson_id"])
            self.table_data["lesson_progress"].append(
                {
                    "session_id": session["id"],
                    "lesson_id": lesson_id,
                    "status": "completed",
                    "completed_at": "2026-11-08T10:05:00Z",
                }
            )
            if lesson_id == "first":
                session["current_lesson_id"] = "second"
            else:
                session["status"] = "completed"
                session["current_module_id"] = None
                session["current_lesson_id"] = None
                session["completed_at"] = "2026-11-08T10:05:00Z"
            return FakeRpc([session])
        return FakeRpc([])


class FakeQuery:
    def __init__(self, database: FakeDatabase, table: str) -> None:
        self.database = database
        self.table_name = table
        self.filters: list[tuple[str, object]] = []
        self.insert_data: dict[str, object] | None = None

    def select(self, *_args: object) -> "FakeQuery":
        return self

    def eq(self, field: str, value: object) -> "FakeQuery":
        self.filters.append((field, value))
        return self

    def order(self, *_args: object, **_kwargs: object) -> "FakeQuery":
        return self

    def limit(self, *_args: object) -> "FakeQuery":
        return self

    def insert(self, data: dict[str, object]) -> "FakeQuery":
        self.insert_data = data
        return self

    def execute(self) -> SimpleNamespace:
        table_rows = self.database.table_data[self.table_name]
        if self.insert_data is not None:
            row = {**self.insert_data, "id": 42}
            if self.table_name == "activities":
                row["id"] = str(uuid4())
                row["created_at"] = "2026-11-08T10:00:00Z"
            table_rows.append(row)
            return SimpleNamespace(data=[row])
        rows = [
            row
            for row in table_rows
            if all(row.get(field) == value for field, value in self.filters)
        ]
        return SimpleNamespace(data=rows)


class FakeRpc:
    def __init__(self, data: object) -> None:
        self.data = data

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=self.data)


class LearningSessionApiTests(unittest.TestCase):
    def make_client(
        self,
        user_id: int | None,
        database: FakeDatabase,
    ) -> TestClient:
        app = FastAPI()
        app.add_middleware(SessionMiddleware, secret_key="test-session-secret")
        app.include_router(auth_router)
        app.include_router(learning_sessions_router)
        if user_id is not None:
            app.dependency_overrides[require_user_id] = lambda: user_id
        app.dependency_overrides[get_supabase_client] = lambda: database
        return TestClient(app)

    def test_start_requires_authentication(self) -> None:
        database = FakeDatabase()
        with self.make_client(None, database) as client:
            response = client.post(
                "/api/v1/learning-sessions",
                json={"course_id": COURSE_ID},
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(database.rpc_calls, [])

    def test_start_pins_published_version_and_initial_lesson(self) -> None:
        database = FakeDatabase()
        with self.make_client(42, database) as client:
            response = client.post(
                "/api/v1/learning-sessions",
                json={"course_id": COURSE_ID},
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["course_version_id"], VERSION_ID)
        self.assertEqual(response.json()["current_lesson_id"], "first")
        self.assertEqual(
            database.rpc_calls[0],
            (
                "start_learning_session",
                {
                    "p_user_id": 42,
                    "p_course_id": COURSE_ID,
                    "p_course_version_id": VERSION_ID,
                    "p_first_module_id": "basics",
                    "p_first_lesson_id": "first",
                },
            ),
        )

    def test_start_reuses_the_learners_active_session(self) -> None:
        database = FakeDatabase()
        first_client = self.make_client(42, database)
        second_client = self.make_client(42, database)
        with first_client, second_client:
            first = first_client.post(
                "/api/v1/learning-sessions",
                json={"course_id": COURSE_ID},
            )
            second = second_client.post(
                "/api/v1/learning-sessions",
                json={"course_id": COURSE_ID},
            )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(len(database.table_data["learning_sessions"]), 1)

    def test_restricted_course_cannot_be_started_without_access(self) -> None:
        database = FakeDatabase()
        database.table_data["courses"][0]["visibility"] = "restricted"
        with self.make_client(42, database) as client:
            response = client.post(
                "/api/v1/learning-sessions",
                json={"course_id": COURSE_ID},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(database.rpc_calls, [])

    def test_restricted_course_can_be_started_by_an_added_learner(self) -> None:
        database = FakeDatabase()
        database.table_data["courses"][0]["visibility"] = "restricted"
        database.table_data["course_access"].append(
            {"course_id": COURSE_ID, "user_id": 42}
        )
        with self.make_client(42, database) as client:
            response = client.post(
                "/api/v1/learning-sessions",
                json={"course_id": COURSE_ID},
            )

        self.assertEqual(response.status_code, 201)

    def test_course_owner_can_start_a_learner_session_for_restricted_course(
        self,
    ) -> None:
        database = FakeDatabase()
        database.table_data["courses"][0]["visibility"] = "restricted"
        database.table_data["courses"][0]["created_by"] = 42
        with self.make_client(42, database) as client:
            response = client.post(
                "/api/v1/learning-sessions",
                json={"course_id": COURSE_ID},
            )

        self.assertEqual(response.status_code, 201)

    def test_revoked_course_access_hides_an_existing_session(self) -> None:
        database = FakeDatabase()
        database.table_data["courses"][0]["visibility"] = "restricted"
        database.table_data["course_access"].clear()
        database.table_data["learning_sessions"].append(
            {
                "id": SESSION_ID,
                "user_id": 42,
                "course_id": COURSE_ID,
                "course_version_id": VERSION_ID,
                "status": "active",
                "current_module_id": "basics",
                "current_lesson_id": "first",
            }
        )
        with self.make_client(42, database) as client:
            response = client.get(f"/api/v1/learning-sessions/{SESSION_ID}")

        self.assertEqual(response.status_code, 404)

    def test_session_is_not_visible_to_another_learner(self) -> None:
        database = FakeDatabase()
        database.table_data["learning_sessions"].append(
            {
                "id": SESSION_ID,
                "user_id": 7,
                "course_id": COURSE_ID,
                "course_version_id": VERSION_ID,
                "status": "active",
                "current_module_id": "basics",
                "current_lesson_id": "first",
            }
        )
        with self.make_client(42, database) as client:
            response = client.get(f"/api/v1/learning-sessions/{SESSION_ID}")

        self.assertEqual(response.status_code, 404)

    def test_completing_a_lesson_saves_progress_and_advances(self) -> None:
        database = FakeDatabase()
        database.table_data["learning_sessions"].append(
            {
                "id": SESSION_ID,
                "user_id": 42,
                "course_id": COURSE_ID,
                "course_version_id": VERSION_ID,
                "status": "active",
                "current_module_id": "basics",
                "current_lesson_id": "first",
            }
        )
        with self.make_client(42, database) as client:
            response = client.post(
                f"/api/v1/learning-sessions/{SESSION_ID}/lessons/first/complete"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["current_lesson_id"], "second")
        self.assertEqual(
            response.json()["completed_lessons"][0]["lesson_id"],
            "first",
        )

    def test_activity_generation_is_saved_and_reused(self) -> None:
        database = FakeDatabase()
        database.table_data["learning_sessions"].append(
            {
                "id": SESSION_ID,
                "user_id": 42,
                "course_id": COURSE_ID,
                "course_version_id": VERSION_ID,
                "status": "active",
                "current_module_id": "basics",
                "current_lesson_id": "first",
            }
        )
        activity = {
            "presentation_format": "text-and-images",
            "content": {
                "type": "text-and-images",
                "content": "## A clear explanation\n\nA worked example.",
                "image_descriptions": ["A simple diagram of the concept."],
            },
        }
        with (
            self.make_client(42, database) as client,
            patch(
                "app.api.learning_sessions.generate_lesson_activity",
                return_value=GeneratedLessonActivity.model_validate(activity),
            ) as generate,
        ):
            first = client.post(
                f"/api/v1/learning-sessions/{SESSION_ID}/lessons/first/activities"
            )
            second = client.post(
                f"/api/v1/learning-sessions/{SESSION_ID}/lessons/first/activities"
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["content"], activity["content"])
        self.assertEqual(second.json(), first.json())
        generate.assert_called_once()
        self.assertEqual(len(database.table_data["activities"]), 1)

    def test_activity_generation_only_allows_the_current_lesson(self) -> None:
        database = FakeDatabase()
        database.table_data["learning_sessions"].append(
            {
                "id": SESSION_ID,
                "user_id": 42,
                "course_id": COURSE_ID,
                "course_version_id": VERSION_ID,
                "status": "active",
                "current_module_id": "basics",
                "current_lesson_id": "first",
            }
        )
        with (
            self.make_client(42, database) as client,
            patch("app.api.learning_sessions.generate_lesson_activity") as generate,
        ):
            response = client.post(
                f"/api/v1/learning-sessions/{SESSION_ID}/lessons/second/activities"
            )

        self.assertEqual(response.status_code, 409)
        generate.assert_not_called()

    def test_activity_generation_requires_session_ownership(self) -> None:
        database = FakeDatabase()
        database.table_data["learning_sessions"].append(
            {
                "id": SESSION_ID,
                "user_id": 7,
                "course_id": COURSE_ID,
                "course_version_id": VERSION_ID,
                "status": "active",
                "current_module_id": "basics",
                "current_lesson_id": "first",
            }
        )
        with (
            self.make_client(42, database) as client,
            patch("app.api.learning_sessions.generate_lesson_activity") as generate,
        ):
            response = client.post(
                f"/api/v1/learning-sessions/{SESSION_ID}/lessons/first/activities"
            )

        self.assertEqual(response.status_code, 404)
        generate.assert_not_called()

    def test_email_registration_creates_a_demo_session_without_password(self) -> None:
        database = FakeDatabase()
        with self.make_client(None, database) as client:
            response = client.post(
                "/api/v1/auth/register",
                json={"email": "Learner@Example.com"},
            )
            profile = client.get("/api/v1/auth/me")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["user"]["email"], "learner@example.com")
        self.assertEqual(profile.json()["user"]["email"], "learner@example.com")
        self.assertEqual(database.table_data["user"][0]["email"], "learner@example.com")

    def test_email_login_requires_an_existing_email_account(self) -> None:
        database = FakeDatabase()
        with self.make_client(None, database) as client:
            response = client.post(
                "/api/v1/auth/login",
                json={"email": "missing@example.com"},
            )

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
