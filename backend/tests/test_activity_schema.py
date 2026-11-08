import unittest

from pydantic import ValidationError

from app.schemas.activity import GeneratedLessonActivity


class ActivitySchemaTests(unittest.TestCase):
    def test_validates_each_supported_format(self) -> None:
        contents = {
            "text-and-images": {
                "type": "text-and-images",
                "content": "A concise explanation.",
                "image_descriptions": [],
            },
            "interactive-simulations": {
                "type": "interactive-simulations",
                "scenario": "A deployment is failing.",
                "choices": [
                    {"label": "Inspect logs", "consequence": "Find the error."},
                    {"label": "Retry blindly", "consequence": "The failure repeats."},
                ],
                "learning_point": "Use evidence to diagnose failures.",
            },
            "interactive-role-play-activities": {
                "type": "interactive-role-play-activities",
                "scenario": "Discuss a project risk.",
                "learner_role": "Developer",
                "partner_role": "Product manager",
                "opening_prompt": "How should we handle this risk?",
                "response_choices": [
                    {"response": "Explain the impact.", "feedback": "Clear and useful."},
                    {"response": "Ignore it.", "feedback": "The risk remains."},
                ],
            },
            "games": {
                "type": "games",
                "objective": "Choose the best test.",
                "instructions": "Select one answer.",
                "challenge": "A function rejects empty input.",
                "choices": [
                    {
                        "label": "Test empty input",
                        "is_correct": True,
                        "feedback": "This checks the boundary case.",
                    },
                    {
                        "label": "Test an unrelated feature",
                        "is_correct": False,
                        "feedback": "This misses the behavior.",
                    },
                ],
            },
            "animations": {
                "type": "animations",
                "scenes": [
                    {
                        "title": "Input",
                        "visual_description": "A request enters the system.",
                        "narration": "The request arrives.",
                    },
                    {
                        "title": "Validation",
                        "visual_description": "The input is checked.",
                        "narration": "Validation checks its shape.",
                    },
                ],
            },
            "slides-based": {
                "type": "slides-based",
                "slides": [
                    {"title": "Concept", "content": "A test checks behavior."},
                    {"title": "Practice", "content": "Write one focused assertion."},
                ],
            },
            "online-coding": {
                "type": "online-coding",
                "instructions": "Complete the function.",
                "starter_code": "def add(a, b):\n    ",
                "expected_code": "def add(a, b):\n    return a + b",
                "explanation": "Return the sum of both inputs.",
            },
        }

        for presentation_format, content in contents.items():
            with self.subTest(presentation_format=presentation_format):
                activity = GeneratedLessonActivity.model_validate(
                    {
                        "presentation_format": presentation_format,
                        "content": content,
                    }
                )
                self.assertEqual(activity.presentation_format, content["type"])

    def test_rejects_mismatched_format_and_content(self) -> None:
        with self.assertRaises(ValidationError):
            GeneratedLessonActivity.model_validate(
                {
                    "presentation_format": "slides-based",
                    "content": {
                        "type": "text-and-images",
                        "content": "This is not a slide deck.",
                        "image_descriptions": [],
                    },
                }
            )

    def test_game_requires_correct_and_incorrect_choices(self) -> None:
        with self.assertRaises(ValidationError):
            GeneratedLessonActivity.model_validate(
                {
                    "presentation_format": "games",
                    "content": {
                        "type": "games",
                        "objective": "Choose an answer.",
                        "instructions": "Select one.",
                        "challenge": "A challenge.",
                        "choices": [
                            {
                                "label": "Only answer",
                                "is_correct": True,
                                "feedback": "Correct.",
                            },
                            {
                                "label": "Also correct",
                                "is_correct": True,
                                "feedback": "Correct too.",
                            },
                        ],
                    },
                }
            )


if __name__ == "__main__":
    unittest.main()
