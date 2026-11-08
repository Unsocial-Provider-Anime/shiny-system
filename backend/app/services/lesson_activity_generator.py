import json
import logging
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

logger = logging.getLogger(__name__)


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
        max_tokens=5000,
    )
    if not response.choices:
        raise CourseGenerationError("The AI provider returned no response choices.")

    choice = response.choices[0]
    finish_reason = getattr(choice, "finish_reason", None)
    if finish_reason == "length":
        logger.warning(
            "Lesson activity response was truncated at the provider's output "
            "token limit (provider=%s, model=%s).",
            provider,
            getattr(response, "model", model_name),
        )
        raise CourseGenerationError(
            "The AI provider truncated the lesson activity at its output limit."
        )

    content = choice.message.content
    if not content:
        raise CourseGenerationError("The AI provider returned an empty response.")

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as error:
        logger.warning(
            "Lesson activity response was not valid JSON "
            "(provider=%s, model=%s, finish_reason=%s, line=%s, column=%s).",
            provider,
            getattr(response, "model", model_name),
            finish_reason,
            error.lineno,
            error.colno,
        )
        raise CourseGenerationError(
            "The AI provider returned a lesson activity that failed validation."
        ) from error

    try:
        return GeneratedLessonActivity.model_validate(payload)
    except ValidationError as error:
        logger.warning(
            "Lesson activity response failed schema validation "
            "(provider=%s, model=%s, finish_reason=%s): %s",
            provider,
            getattr(response, "model", model_name),
            finish_reason,
            error.errors(include_input=False, include_url=False),
        )
        raise CourseGenerationError(
            "The AI provider returned a lesson activity that failed validation."
        ) from error
