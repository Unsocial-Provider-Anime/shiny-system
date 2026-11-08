import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.schemas.course import CourseDraftRequest
from app.services.course_generator import (
    CourseGenerationError,
    generate_course_draft,
)


def valid_proposal() -> dict[str, object]:
    return {
        "title": "Testing fundamentals",
        "description": "A short course about testing.",
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


class CourseGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = MagicMock()
        self.client.chat.completions.create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps(valid_proposal()))
                )
            ]
        )

    def test_validates_structured_provider_response(self) -> None:
        proposal = generate_course_draft(
            CourseDraftRequest(topic="Testing"), self.client
        )

        self.assertEqual(proposal.title, "Testing fundamentals")
        self.client.chat.completions.create.assert_called_once()
        call = self.client.chat.completions.create.call_args.kwargs
        self.assertEqual(call["response_format"], {"type": "json_object"})

    def test_rejects_malformed_provider_content(self) -> None:
        self.client.chat.completions.create.return_value.choices[0].message.content = (
            '{"title":"incomplete"}'
        )

        with self.assertRaises(CourseGenerationError):
            generate_course_draft(CourseDraftRequest(topic="Testing"), self.client)

    def test_rejects_non_json_provider_content(self) -> None:
        self.client.chat.completions.create.return_value.choices[0].message.content = (
            "not json"
        )

        with self.assertRaises(CourseGenerationError):
            generate_course_draft(CourseDraftRequest(topic="Testing"), self.client)

    def test_rejects_missing_provider_content(self) -> None:
        self.client.chat.completions.create.return_value.choices[0].message.content = (
            None
        )

        with self.assertRaises(CourseGenerationError):
            generate_course_draft(CourseDraftRequest(topic="Testing"), self.client)


if __name__ == "__main__":
    unittest.main()
