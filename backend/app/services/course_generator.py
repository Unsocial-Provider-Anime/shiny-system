import json
import logging
import os

from openai import OpenAI
from pydantic import ValidationError

from app.schemas.course import CourseDraftProposal, CourseDraftRequest
from app.services.openai_client import OpenAIModel, get_openai_client
from app.services.token_usage import create_chat_completion

logger = logging.getLogger(__name__)


class CourseGenerationError(Exception):
    pass


class ProviderConfigurationError(CourseGenerationError):
    pass


def generate_course_draft(
    request: CourseDraftRequest,
    client: OpenAI | None = None,
    *,
    database: object | None = None,
    user_id: int | None = None,
) -> CourseDraftProposal:
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
                    "Create a complete mini-course proposal. Return only JSON "
                    "matching this structure: title, description, "
                    "default_presentation_format, plan. Use strings for "
                    "overview, target_audience, and capstone; milestones, "
                    "assumptions, learning_outcomes, and prerequisites must "
                    "be arrays of strings. The plan must contain "
                    "overview, target_audience, assumptions, learning_outcomes, "
                    "prerequisites, modules, milestones, and capstone. Each "
                    "module has module_id, title, description, and lessons. "
                    "Keep the course compact: use at most three modules and "
                    "two lessons per module, and keep descriptions and "
                    "objectives concise. If no time budget is provided, assume "
                    "a 60-minute mini-course. "
                    "Each lesson has lesson_id, title, purpose, two or three "
                    "observable objectives, key_topics, suggested_activity "
                    "(title, description, presentation_format), completion_check, "
                    "prerequisite_lesson_ids, and optional estimated_minutes. "
                    "Use only these presentation formats: text-and-images, "
                    "interactive-simulations, interactive-role-play-activities, "
                    "games, animations, slides-based, online-coding. Sequence "
                    "prerequisites first, use observable outcomes and active "
                    "practice, scale the scope to the requested time budget, "
                    "and state important assumptions. Do not invent sources."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    request.model_dump(exclude_none=True),
                    ensure_ascii=True,
                ),
            },
        ],
        response_format={"type": "json_object"},
        max_tokens=8192,
    )
    if not response.choices:
        raise CourseGenerationError("The AI provider returned no response choices.")

    choice = response.choices[0]
    content = choice.message.content
    if not content:
        raise CourseGenerationError("The AI provider returned an empty response.")

    logger.info(
        "Course generation provider response (provider=%s, model=%s, "
        "finish_reason=%s):\n%s",
        provider,
        getattr(response, "model", model_name),
        getattr(choice, "finish_reason", None),
        content,
    )

    if getattr(choice, "finish_reason", None) == "length":
        logger.warning(
            "Course generation response was truncated at the provider's "
            "output token limit (model=%s).",
            getattr(response, "model", model_name),
        )
        raise CourseGenerationError(
            "The AI provider truncated the course proposal at its output limit."
        )

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as error:
        logger.warning(
            "Course generation response was not valid JSON "
            "(finish_reason=%s, line=%s, column=%s).",
            getattr(choice, "finish_reason", None),
            error.lineno,
            error.colno,
        )
        raise CourseGenerationError(
            "The AI provider returned a course proposal that failed validation."
        ) from error

    try:
        return CourseDraftProposal.model_validate(payload)
    except ValidationError as error:
        logger.warning(
            "Course generation response failed schema validation: %s",
            error.errors(include_input=False, include_url=False),
        )
        raise CourseGenerationError(
            "The AI provider returned a course proposal that failed validation."
        ) from error
