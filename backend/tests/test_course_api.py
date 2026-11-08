import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.api.courses import optional_user_id, require_user_id, router
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
        return FakeQuery(self, name)

    def rpc(self, name: str, params: dict[str, object]) -> "FakeRpc":
        self.rpc_calls.append((name, params))
        if name == "set_course_visibility":
            course = next(
                row
                for row in self.table_data["courses"]
                if row["id"] == params["p_course_id"]
            )
            course["visibility"] = params["p_visibility"]
            return FakeRpc([course])
        return FakeRpc(
            [{"course_id": COURSE_ID, "version_id": str(uuid4()), "version_number": 1}]
        )


class FakeQuery:
    def __init__(self, database: FakeDatabase, table_name: str):
        self.database = database
        self.table_name = table_name
        self.filters: list[tuple[str, object]] = []
        self.in_filters: list[tuple[str, list[object]]] = []
        self.upsert_data: dict[str, object] | None = None
        self.is_delete = False

    def select(self, *_args: object) -> "FakeQuery":
        return self

    def eq(self, field: str, value: object) -> "FakeQuery":
        self.filters.append((field, value))
        return self

    def limit(self, *_args: object) -> "FakeQuery":
        return self

    def order(self, *_args: object, **_kwargs: object) -> "FakeQuery":
        return self

    def ilike(self, *_args: object) -> "FakeQuery":
        return self

    def in_(self, field: str, values: list[object]) -> "FakeQuery":
        self.in_filters.append((field, values))
        return self

    def upsert(self, data: dict[str, object], **_kwargs: object) -> "FakeQuery":
        self.upsert_data = data
        return self

    def delete(self) -> "FakeQuery":
        self.is_delete = True
        return self

    def execute(self) -> SimpleNamespace:
        rows = self.database.table_data.setdefault(self.table_name, [])
        if self.upsert_data is not None:
            row = {**self.upsert_data, "granted_at": "2026-11-08T10:00:00Z"}
            if not any(
                existing.get("course_id") == row.get("course_id")
                and existing.get("user_id") == row.get("user_id")
                for existing in rows
            ):
                rows.append(row)
            return SimpleNamespace(data=[])
        selected = [
            row
            for row in rows
            if all(row.get(field) == value for field, value in self.filters)
            and all(row.get(field) in values for field, values in self.in_filters)
        ]
        if self.is_delete:
            self.database.table_data[self.table_name] = [
                row for row in rows if row not in selected
            ]
        return SimpleNamespace(data=selected)


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
            app.dependency_overrides[optional_user_id] = lambda: user_id
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
        self.assertEqual(database.rpc_calls[0][1]["p_visibility"], "restricted")

    def test_owner_can_grant_and_revoke_access_for_an_existing_user(self) -> None:
        database = FakeDatabase(
            {
                "courses": [
                    {
                        "id": COURSE_ID,
                        "created_by": 42,
                        "status": "published",
                        "visibility": "restricted",
                    }
                ],
                "user": [{"id": 7, "email": "learner@example.com"}],
                "course_access": [],
            }
        )
        with self.make_client(42, database) as client:
            grant = client.post(
                f"/api/v1/courses/{COURSE_ID}/access",
                json={"email": "Learner@Example.com"},
            )
            listed = client.get(f"/api/v1/courses/{COURSE_ID}/access")
            revoke = client.delete(f"/api/v1/courses/{COURSE_ID}/access/7")

        self.assertEqual(grant.status_code, 201)
        self.assertEqual(grant.json(), {"user_id": 7, "email": "learner@example.com"})
        self.assertEqual(listed.json()[0]["user_id"], 7)
        self.assertEqual(revoke.status_code, 200)
        self.assertEqual(database.table_data["course_access"], [])

    def test_non_owner_cannot_grant_course_access(self) -> None:
        database = FakeDatabase(
            {"courses": [{"id": COURSE_ID, "created_by": 7, "status": "published"}]}
        )
        with self.make_client(42, database) as client:
            response = client.post(
                f"/api/v1/courses/{COURSE_ID}/access",
                json={"email": "learner@example.com"},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(database.table_data.get("course_access", []), [])

    def test_owner_can_change_visibility_after_publishing(self) -> None:
        database = FakeDatabase(
            {
                "courses": [
                    {
                        "id": COURSE_ID,
                        "created_by": 42,
                        "status": "published",
                        "visibility": "public",
                    }
                ]
            }
        )
        with self.make_client(42, database) as client:
            response = client.patch(
                f"/api/v1/courses/{COURSE_ID}/visibility",
                json={"visibility": "restricted"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["visibility"], "restricted")
        self.assertEqual(database.table_data["courses"][0]["visibility"], "restricted")

    def test_catalogue_lists_public_and_shared_courses_only(self) -> None:
        public_id = str(uuid4())
        shared_id = str(uuid4())
        private_id = str(uuid4())
        plan = valid_proposal()["plan"]
        database = FakeDatabase(
            {
                "courses": [
                    {
                        "id": public_id,
                        "created_by": 7,
                        "title": "Public",
                        "description": "Open",
                        "status": "published",
                        "visibility": "public",
                        "published_version_id": "version-public",
                        "published_at": "2026-11-08T10:00:00Z",
                    },
                    {
                        "id": shared_id,
                        "created_by": 8,
                        "title": "Shared",
                        "description": "Invited",
                        "status": "published",
                        "visibility": "restricted",
                        "published_version_id": "version-shared",
                        "published_at": "2026-11-08T09:00:00Z",
                    },
                    {
                        "id": private_id,
                        "created_by": 9,
                        "title": "Private",
                        "description": "Not shared",
                        "status": "published",
                        "visibility": "restricted",
                        "published_version_id": "version-private",
                        "published_at": "2026-11-08T08:00:00Z",
                    },
                ],
                "course_access": [{"course_id": shared_id, "user_id": 42}],
                "course_versions": [
                    {"id": "version-public", "version_number": 1, "plan": plan},
                    {"id": "version-shared", "version_number": 1, "plan": plan},
                ],
            }
        )
        with (
            self.make_client(42, database) as learner_client,
            self.make_client(None, database) as anonymous_client,
        ):
            learner_courses = learner_client.get("/api/v1/courses")
            public_courses = anonymous_client.get("/api/v1/courses")

        self.assertEqual(
            {course["id"] for course in learner_courses.json()},
            {public_id, shared_id},
        )
        self.assertEqual(
            {course["id"] for course in public_courses.json()},
            {public_id},
        )

    def test_nonexistent_users_cannot_be_granted_course_access(self) -> None:
        database = FakeDatabase(
            {
                "courses": [{"id": COURSE_ID, "created_by": 42, "status": "draft"}],
                "user": [],
            }
        )
        with self.make_client(42, database) as client:
            response = client.post(
                f"/api/v1/courses/{COURSE_ID}/access",
                json={"email": "new@example.com"},
            )

        self.assertEqual(response.status_code, 404)

    def test_restricted_course_is_visible_only_to_owner_and_granted_users(self) -> None:
        database = FakeDatabase(
            {
                "courses": [
                    {
                        "id": COURSE_ID,
                        "created_by": 7,
                        "status": "published",
                        "visibility": "restricted",
                        "published_version_id": "version-1",
                    }
                ],
                "course_versions": [
                    {
                        "id": "version-1",
                        "version_number": 1,
                        "plan": valid_proposal()["plan"],
                    }
                ],
                "course_access": [{"course_id": COURSE_ID, "user_id": 42}],
            }
        )
        with (
            self.make_client(None, database) as anonymous_client,
            self.make_client(9, database) as other_client,
            self.make_client(42, database) as learner_client,
            self.make_client(7, database) as owner_client,
        ):
            anonymous = anonymous_client.get(f"/api/v1/courses/{COURSE_ID}")
            other = other_client.get(f"/api/v1/courses/{COURSE_ID}")
            learner = learner_client.get(f"/api/v1/courses/{COURSE_ID}")
            owner = owner_client.get(f"/api/v1/courses/{COURSE_ID}")

        self.assertEqual(anonymous.status_code, 404)
        self.assertEqual(other.status_code, 404)
        self.assertEqual(learner.status_code, 200)
        self.assertEqual(owner.status_code, 200)

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
        with (
            self.make_client(42) as client,
            patch("app.api.courses.generate_course_draft") as generate,
        ):
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
