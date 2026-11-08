import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.schemas.course import CoursePlan
from app.services.course_generator import CourseGenerationError
from app.services.quiz_generator import generate_quiz


class QuizGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = MagicMock()
        self.client.chat.completions.create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "question": "What does this assertion check?",
                                "options": [
                                    "Expected behavior",
                                    "Code formatting",
                                ],
                                "correct_option": 0,
                                "explanation": "Assertions compare actual and expected behavior.",
                            }
                        )
                    )
                )
            ]
        )
        self.plan = CoursePlan.model_validate(
            {
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
        )

    def test_validates_structured_quiz(self) -> None:
        module = self.plan.modules[0]
        quiz = generate_quiz(
            "Testing fundamentals", module, module.lessons[0], self.client
        )

        self.assertEqual(quiz.correct_option, 0)
        self.assertEqual(len(quiz.options), 2)
        self.assertEqual(
            self.client.chat.completions.create.call_args.kwargs["response_format"],
            {"type": "json_object"},
        )

    def test_rejects_quiz_with_unavailable_correct_option(self) -> None:
        self.client.chat.completions.create.return_value.choices[0].message.content = (
            '{"question":"Q","options":["A","B"],"correct_option":2,'
            '"explanation":"Explanation"}'
        )
        module = self.plan.modules[0]

        with self.assertRaises(CourseGenerationError):
            generate_quiz(
                "Testing fundamentals", module, module.lessons[0], self.client
            )


if __name__ == "__main__":
    unittest.main()
