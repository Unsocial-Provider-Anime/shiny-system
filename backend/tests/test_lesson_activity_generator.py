import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.schemas.course import CoursePlan
from app.services.course_generator import CourseGenerationError
from app.services.lesson_activity_generator import generate_lesson_activity


def plan_data() -> dict[str, object]:
    return {
        "overview": "Learn testing fundamentals.",
        "target_audience": "Beginners",
        "learning_outcomes": ["Write a basic test."],
        "modules": [
            {
                "module_id": "basics",
                "title": "Basics",
                "description": "Core concepts.",
                "lessons": [
                    {
                        "lesson_id": "first",
                        "title": "Assertions",
                        "purpose": "Learn how assertions verify behavior.",
                        "objectives": [
                            "Explain an assertion.",
                            "Choose an assertion for a behavior.",
                        ],
                        "key_topics": ["Assertions"],
                        "suggested_activity": {
                            "title": "Inspect an example",
                            "description": "Review a small test.",
                            "presentation_format": "text-and-images",
                        },
                        "completion_check": "Describe what an assertion checks.",
                    }
                ],
            }
        ],
        "capstone": "Test a small function.",
    }


class LessonActivityGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = MagicMock()
        self.client.chat.completions.create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "presentation_format": "text-and-images",
                                "content": {
                                    "type": "text-and-images",
                                    "content": "An assertion checks expected behavior.",
                                    "image_descriptions": [],
                                },
                            }
                        )
                    )
                )
            ]
        )
        self.plan = CoursePlan.model_validate(plan_data())

    def test_validates_structured_activity_response(self) -> None:
        module = self.plan.modules[0]
        activity = generate_lesson_activity(
            "Testing fundamentals",
            self.plan,
            module,
            module.lessons[0],
            self.client,
        )

        self.assertEqual(activity.content.type, "text-and-images")
        self.assertIn("assertion", activity.content.content)
        call = self.client.chat.completions.create.call_args.kwargs
        self.assertEqual(call["response_format"], {"type": "json_object"})

    def test_rejects_malformed_activity_response(self) -> None:
        self.client.chat.completions.create.return_value.choices[0].message.content = (
            '{"presentation_format":"slides-based"}'
        )
        module = self.plan.modules[0]

        with self.assertRaises(CourseGenerationError):
            generate_lesson_activity(
                "Testing fundamentals",
                self.plan,
                module,
                module.lessons[0],
                self.client,
            )

    def test_generates_requested_format_and_assistance_action(self) -> None:
        slides = {
            "presentation_format": "slides-based",
            "content": {
                "type": "slides-based",
                "slides": [
                    {"title": "The idea", "content": "Assertions check behavior."},
                    {"title": "An example", "content": "Compare actual and expected."},
                ],
            },
        }
        self.client.chat.completions.create.return_value.choices[0].message.content = (
            json.dumps(slides)
        )
        module = self.plan.modules[0]

        activity = generate_lesson_activity(
            "Testing fundamentals",
            self.plan,
            module,
            module.lessons[0],
            self.client,
            presentation_format="slides-based",
            action="answer-question",
            question="Why do assertions matter?",
        )

        self.assertEqual(activity.presentation_format, "slides-based")
        request = json.loads(
            self.client.chat.completions.create.call_args.kwargs["messages"][1][
                "content"
            ]
        )
        self.assertEqual(request["action"], "answer-question")
        self.assertEqual(request["learner_question"], "Why do assertions matter?")
        self.assertEqual(request["requested_format"], "slides-based")

    def test_rejects_truncated_activity_response(self) -> None:
        self.client.chat.completions.create.return_value.choices[0].finish_reason = (
            "length"
        )
        module = self.plan.modules[0]

        with self.assertRaisesRegex(CourseGenerationError, "truncated"):
            generate_lesson_activity(
                "Testing fundamentals",
                self.plan,
                module,
                module.lessons[0],
                self.client,
            )


if __name__ == "__main__":
    unittest.main()
