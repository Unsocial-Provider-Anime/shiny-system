import json
import os

from openai import OpenAI
from pydantic import ValidationError

from app.schemas.activity import GeneratedLessonActivity
from app.schemas.course import CoursePlan, LessonPlan, ModulePlan
from app.services.course_generator import (
    CourseGenerationError,
    ProviderConfigurationError,
)
from app.services.openai_client import OpenAIModel, get_openai_client


def generate_lesson_activity(
    course_title: str,
    plan: CoursePlan,
    module: ModulePlan,
    lesson: LessonPlan,
    client: OpenAI | None = None,
) -> GeneratedLessonActivity:
    provider = os.getenv("AI_PROVIDER", "deepseek")
    try:
        model = OpenAIModel(model=provider)
    except ValidationError as error:
        raise ProviderConfigurationError(
            "AI_PROVIDER must be deepseek or kimi."
        ) from error

    if client is None:
        try:
            client, model_name = get_openai_client(model)
        except ValueError as error:
            raise ProviderConfigurationError(str(error)) from error
    else:
        model_name = os.getenv(
            "DEEPSEEK_MODEL" if model.model == "deepseek" else "KIMI_MODEL",
            "configured-test-model",
        )

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": (
                    "Create a clear, self-contained lesson activity for the "
                    "provided learner and lesson. Return only JSON with "
                    "presentation_format='text-and-images' and a content "
                    "object containing type='text-and-images', content "
                    "(Markdown lesson material), and image_descriptions (zero "
                    "to four concise descriptions of helpful illustrations). "
                    "Use accurate explanations, concrete examples, and "
                    "formatting that supports learning. Do not include raw "
                    "HTML, scripts, external image URLs, or invented sources."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "course_title": course_title,
                        "course_overview": plan.overview,
                        "learning_outcomes": plan.learning_outcomes,
                        "module": module.model_dump(mode="json"),
                        "lesson": lesson.model_dump(mode="json"),
                    },
                    ensure_ascii=True,
                ),
            },
        ],
        response_format={"type": "json_object"},
        max_tokens=3000,
    )
    if not response.choices:
        raise CourseGenerationError("The AI provider returned no response choices.")

    content = response.choices[0].message.content
    if not content:
        raise CourseGenerationError("The AI provider returned an empty response.")

    try:
        payload = json.loads(content)
        return GeneratedLessonActivity.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as error:
        raise CourseGenerationError(
            "The AI provider returned a lesson activity that failed validation."
        ) from error
