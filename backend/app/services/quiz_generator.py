import json
import os

from openai import OpenAI
from pydantic import ValidationError

from app.schemas.course import LessonPlan, ModulePlan
from app.schemas.interaction import GeneratedQuiz
from app.services.course_generator import (
    CourseGenerationError,
    ProviderConfigurationError,
)
from app.services.openai_client import OpenAIModel, get_openai_client
from app.services.token_usage import create_chat_completion


def generate_quiz(
    course_title: str,
    module: ModulePlan,
    lesson: LessonPlan,
    client: OpenAI | None = None,
    *,
    user_id: int | None = None,
    database: object | None = None,
) -> GeneratedQuiz:
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

    response = create_chat_completion(
        client,
        database,
        user_id,
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": (
                    "Create one concise multiple-choice quiz question grounded "
                    "in the provided lesson. Return only JSON with question, "
                    "options (two to four answer strings), correct_option "
                    "(zero-based index), and explanation. Include exactly one "
                    "correct option. Make distractors plausible and ensure the "
                    "explanation teaches the underlying concept. Do not include "
                    "content unrelated to the lesson."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "course_title": course_title,
                        "module": module.model_dump(mode="json"),
                        "lesson": lesson.model_dump(mode="json"),
                    },
                    ensure_ascii=True,
                ),
            },
        ],
        response_format={"type": "json_object"},
        max_tokens=1200,
    )
    if not response.choices:
        raise CourseGenerationError("The AI provider returned no response choices.")

    content = response.choices[0].message.content
    if not content:
        raise CourseGenerationError("The AI provider returned an empty response.")

    try:
        return GeneratedQuiz.model_validate(json.loads(content))
    except (json.JSONDecodeError, ValidationError) as error:
        raise CourseGenerationError(
            "The AI provider returned a quiz that failed validation."
        ) from error
