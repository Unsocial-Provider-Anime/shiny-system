import json
import os

from openai import OpenAI
from pydantic import ValidationError

from app.schemas.course import CourseDraftProposal, CourseDraftRequest
from app.services.openai_client import OpenAIModel, get_openai_client


class CourseGenerationError(Exception):
    pass


class ProviderConfigurationError(CourseGenerationError):
    pass


def generate_course_draft(
    request: CourseDraftRequest,
    client: OpenAI | None = None,
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

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": (
                    "Create a complete mini-course proposal. Return only JSON "
                    "matching this structure: title, description, "
                    "default_presentation_format, plan. The plan must contain "
                    "overview, target_audience, assumptions, learning_outcomes, "
                    "prerequisites, modules, milestones, and capstone. Each "
                    "module has module_id, title, description, and lessons. "
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
        max_tokens=5000,
    )
    if not response.choices:
        raise CourseGenerationError("The AI provider returned no response choices.")

    content = response.choices[0].message.content
    if not content:
        raise CourseGenerationError("The AI provider returned an empty response.")

    try:
        payload = json.loads(content)
        return CourseDraftProposal.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as error:
        raise CourseGenerationError(
            "The AI provider returned a course proposal that failed validation."
        ) from error
