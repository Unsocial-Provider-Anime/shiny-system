import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict, ValidationError
from supabase import Client

from app.api.courses import can_access_course, require_user_id
from app.database.supabase import get_supabase_client
from app.schemas.activity import (
    CheckCodingAnswerRequest,
    CodingAnswerResponse,
    CodingContent,
    GeneratedLessonActivity,
    GenerateLessonActivityRequest,
    LessonActivityResponse,
)
from app.schemas.course import CoursePlan
from app.schemas.interaction import (
    GeneratedQuiz,
    GenerateInteractionRequest,
    QuizInteractionResponse,
    SubmitQuizAnswerRequest,
)
from app.services.course_generator import (
    CourseGenerationError,
    ProviderConfigurationError,
)
from app.services.lesson_activity_generator import generate_lesson_activity
from app.services.quiz_generator import generate_quiz
from app.services.token_usage import TokenLimitExceeded

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/learning-sessions", tags=["learning sessions"])
Database = Annotated[Client, Depends(get_supabase_client)]
AuthenticatedUser = Annotated[int, Depends(require_user_id)]


class StartSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course_id: UUID


def _rows(response: Any) -> list[dict[str, Any]]:
    data = response.data
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    return []


def _database_call(operation: str, action: Any) -> Any:
    try:
        return action()
    except Exception as error:
        logger.exception("Learning session database operation failed: %s", operation)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "learning_session_operation_failed",
                "message": "The learning session could not be loaded or saved.",
            },
        ) from error


def _course(database: Client, course_id: str) -> dict[str, Any] | None:
    response = _database_call(
        "load course",
        lambda: (
            database.table("courses")
            .select(
                "id, title, description, status, visibility, created_by, "
                "published_version_id"
            )
            .eq("id", course_id)
            .limit(1)
            .execute()
        ),
    )
    rows = _rows(response)
    return rows[0] if rows else None


def _version(database: Client, version_id: str) -> dict[str, Any] | None:
    response = _database_call(
        "load course version",
        lambda: (
            database.table("course_versions")
            .select("id, course_id, version_number, plan")
            .eq("id", version_id)
            .limit(1)
            .execute()
        ),
    )
    rows = _rows(response)
    return rows[0] if rows else None


def _plan(version: dict[str, Any]) -> CoursePlan:
    try:
        return CoursePlan.model_validate(version["plan"])
    except (KeyError, TypeError, ValueError, ValidationError) as error:
        logger.exception(
            "Published course version %s has an invalid plan.", version.get("id")
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "invalid_course_plan",
                "message": "The course plan is unavailable.",
            },
        ) from error


def _session(
    database: Client,
    session_id: UUID,
    user_id: int,
) -> dict[str, Any] | None:
    response = _database_call(
        "load owned session",
        lambda: (
            database.table("learning_sessions")
            .select("*")
            .eq("id", str(session_id))
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        ),
    )
    rows = _rows(response)
    return rows[0] if rows else None


def _ensure_session_course_access(
    database: Client,
    session: dict[str, Any],
    user_id: int,
) -> dict[str, Any]:
    course = _course(database, session["course_id"])
    if course is None:
        logger.error("Learning session %s references a missing course.", session["id"])
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "invalid_learning_session",
                "message": "The learning session is unavailable.",
            },
        )
    if not can_access_course(database, course, user_id):
        raise HTTPException(status_code=404, detail="Learning session not found.")
    return course


def _full_session(
    database: Client,
    session: dict[str, Any],
    user_id: int,
) -> dict[str, Any]:
    course = _course(database, session["course_id"])
    version = _version(database, session["course_version_id"])
    if (
        course is None
        or version is None
        or version.get("course_id") != session["course_id"]
    ):
        logger.error(
            "Learning session %s references a missing course version.", session["id"]
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "invalid_learning_session",
                "message": "The learning session is unavailable.",
            },
        )
    if not can_access_course(database, course, user_id):
        raise HTTPException(status_code=404, detail="Learning session not found.")
    plan = _plan(version)
    progress_response = _database_call(
        "load lesson progress",
        lambda: (
            database.table("lesson_progress")
            .select("lesson_id, status, completed_at")
            .eq("session_id", session["id"])
            .execute()
        ),
    )
    return {
        **session,
        "course": {
            "id": course["id"],
            "title": course["title"],
            "description": course["description"],
        },
        "version_number": version["version_number"],
        "plan": plan.model_dump(mode="json"),
        "completed_lessons": _rows(progress_response),
    }


def _is_current_lesson(session: dict[str, Any], lesson_id: str) -> bool:
    return (
        session.get("status") == "active"
        and session.get("current_lesson_id") == lesson_id
    )


def _ensure_lesson_reviewable(
    database: Client,
    session: dict[str, Any],
    lesson_id: str,
) -> None:
    if _is_current_lesson(session, lesson_id):
        return
    response = _database_call(
        "load lesson progress",
        lambda: (
            database.table("lesson_progress")
            .select("lesson_id")
            .eq("session_id", session["id"])
            .eq("lesson_id", lesson_id)
            .limit(1)
            .execute()
        ),
    )
    if not _rows(response):
        raise HTTPException(
            status_code=409,
            detail="This lesson is neither current nor completed.",
        )


def _quiz_interaction_response(row: dict[str, Any]) -> dict[str, Any]:
    try:
        quiz = GeneratedQuiz.model_validate(row["content"])
        selected_option = row.get("selected_option")
        response = QuizInteractionResponse(
            id=row["id"],
            session_id=row["session_id"],
            lesson_id=row["lesson_id"],
            kind=row["kind"],
            action=row["action"],
            question=quiz.question,
            options=quiz.options,
            selected_option=selected_option,
            is_correct=(
                selected_option == quiz.correct_option
                if selected_option is not None
                else None
            ),
            explanation=quiz.explanation if selected_option is not None else None,
            created_at=row["created_at"],
        )
        return response.model_dump(mode="json")
    except (KeyError, TypeError, ValueError, ValidationError) as error:
        logger.exception("Stored quiz interaction %s is invalid.", row.get("id"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "invalid_learning_interaction",
                "message": "The learning interaction is unavailable.",
            },
        ) from error


def _lesson_activity_response(row: dict[str, Any]) -> dict[str, Any]:
    activity = GeneratedLessonActivity.model_validate(
        {
            "presentation_format": row["presentation_format"],
            "content": row["content"],
        }
    )
    content = activity.content.model_dump(mode="json")
    if isinstance(activity.content, CodingContent):
        content.pop("expected_code")
    return LessonActivityResponse.model_validate(
        {
            **row,
            "presentation_format": activity.presentation_format,
            "content": content,
        }
    ).model_dump(mode="json")


def _normalize_code(code: str) -> str:
    lines = [
        line.rstrip()
        for line in code.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


@router.post("", status_code=status.HTTP_201_CREATED)
def start_learning_session(
    payload: StartSessionRequest,
    user_id: AuthenticatedUser,
    database: Database,
) -> dict[str, Any]:
    course_id = str(payload.course_id)
    course = _course(database, course_id)
    if (
        course is None
        or course.get("status") != "published"
        or not can_access_course(database, course, user_id)
    ):
        raise HTTPException(status_code=404, detail="Published course not found.")

    version_id = course.get("published_version_id")
    version = _version(database, version_id) if version_id else None
    if version is None or version.get("course_id") != course_id:
        logger.error("Published course %s has no valid published version.", course_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "invalid_course_version",
                "message": "The course plan is unavailable.",
            },
        )
    plan = _plan(version)
    first_module = plan.modules[0]
    first_lesson = first_module.lessons[0]
    response = _database_call(
        "start session",
        lambda: database.rpc(
            "start_learning_session",
            {
                "p_user_id": user_id,
                "p_course_id": course_id,
                "p_course_version_id": version_id,
                "p_first_module_id": first_module.module_id,
                "p_first_lesson_id": first_lesson.lesson_id,
            },
        ).execute(),
    )
    sessions = _rows(response)
    if not sessions:
        logger.error("Starting session for course %s returned no session.", course_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "invalid_database_response",
                "message": "The learning session could not be started.",
            },
        )
    session = _session(database, UUID(sessions[0]["id"]), user_id)
    if session is None:
        raise HTTPException(
            status_code=500, detail="The learning session could not be loaded."
        )
    return _full_session(database, session, user_id)


@router.get("")
def list_learning_sessions(
    user_id: AuthenticatedUser,
    database: Database,
) -> list[dict[str, Any]]:
    response = _database_call(
        "list sessions",
        lambda: (
            database.table("learning_sessions")
            .select("*")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .limit(100)
            .execute()
        ),
    )
    sessions = []
    for row in _rows(response):
        course = _course(database, row["course_id"])
        if course is None:
            sessions.append(_full_session(database, row, user_id))
        elif can_access_course(database, course, user_id):
            sessions.append(_full_session(database, row, user_id))
    return sessions


@router.get("/{session_id}")
def get_learning_session(
    session_id: UUID,
    user_id: AuthenticatedUser,
    database: Database,
) -> dict[str, Any]:
    session = _session(database, session_id, user_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Learning session not found.")
    return _full_session(database, session, user_id)


@router.post(
    "/{session_id}/lessons/{lesson_id}/activities",
    response_model=LessonActivityResponse,
)
def create_lesson_activity(
    session_id: UUID,
    lesson_id: Annotated[
        str,
        Path(
            min_length=1,
            max_length=80,
            pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
        ),
    ],
    user_id: AuthenticatedUser,
    database: Database,
    payload: GenerateLessonActivityRequest | None = Body(default=None),
) -> dict[str, Any]:
    session = _session(database, session_id, user_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Learning session not found.")
    _ensure_session_course_access(database, session, user_id)
    _ensure_lesson_reviewable(database, session, lesson_id)

    course = _course(database, session["course_id"])
    version = _version(database, session["course_version_id"])
    if (
        course is None
        or version is None
        or version.get("course_id") != session["course_id"]
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "invalid_learning_session",
                "message": "The learning session is unavailable.",
            },
        )
    plan = _plan(version)
    target_module = next(
        (
            module
            for module in plan.modules
            if any(lesson.lesson_id == lesson_id for lesson in module.lessons)
        ),
        None,
    )
    target_lesson = (
        next(
            lesson for lesson in target_module.lessons if lesson.lesson_id == lesson_id
        )
        if target_module
        else None
    )
    if target_module is None or target_lesson is None:
        raise HTTPException(status_code=409, detail="This lesson is not in the course.")

    existing_response = _database_call(
        "load lesson activity",
        lambda: (
            database.table("activities")
            .select("*")
            .eq("session_id", str(session_id))
            .eq("lesson_id", lesson_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        ),
    )
    existing_activities = _rows(existing_response)
    generation_request = payload or GenerateLessonActivityRequest()
    if (
        existing_activities
        and not generation_request.regenerate
        and generation_request.action == "teach"
    ):
        try:
            return _lesson_activity_response(existing_activities[0])
        except (KeyError, TypeError, ValueError, ValidationError) as error:
            logger.exception(
                "Stored lesson activity for session %s is invalid.", session_id
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "code": "invalid_lesson_activity",
                    "message": "The lesson activity is unavailable.",
                },
            ) from error

    try:
        activity = generate_lesson_activity(
            course["title"],
            plan,
            target_module,
            target_lesson,
            presentation_format=(
                generation_request.presentation_format
                or target_lesson.suggested_activity.presentation_format
            ),
            action=generation_request.action,
            question=generation_request.question,
            user_id=user_id,
            database=database,
        )
    except TokenLimitExceeded as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "daily_token_limit_reached",
                "message": "Your daily AI token limit has been reached.",
                "reset_at": error.reset_at,
            },
        ) from error
    except ProviderConfigurationError as error:
        logger.error("Lesson activity generation is not configured: %s", error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "lesson_activity_generation_unavailable",
                "message": "Lesson activity generation is not configured.",
            },
        ) from error
    except CourseGenerationError as error:
        logger.warning("Lesson activity generation returned invalid content: %s", error)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "invalid_generated_lesson_activity",
                "message": "The lesson activity could not be validated. Please retry.",
            },
        ) from error
    except Exception as error:
        logger.exception("Lesson activity provider request failed.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "lesson_activity_generation_failed",
                "message": "Lesson activity generation failed. Please retry.",
            },
        ) from error

    inserted = _database_call(
        "save lesson activity",
        lambda: (
            database.table("activities")
            .insert(
                {
                    "session_id": str(session_id),
                    "lesson_id": lesson_id,
                    "presentation_format": activity.presentation_format,
                    "content": activity.content.model_dump(mode="json"),
                }
            )
            .execute()
        ),
    )
    rows = _rows(inserted)
    if not rows:
        logger.error("Saving activity for session %s returned no record.", session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "invalid_database_response",
                "message": "The lesson activity could not be saved.",
            },
        )
    try:
        return _lesson_activity_response(rows[0])
    except (KeyError, TypeError, ValueError, ValidationError) as error:
        logger.exception("Saved lesson activity for session %s is invalid.", session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "invalid_lesson_activity",
                "message": "The lesson activity could not be loaded.",
            },
        ) from error


@router.get(
    "/{session_id}/lessons/{lesson_id}/activities",
    response_model=list[LessonActivityResponse],
)
def list_lesson_activities(
    session_id: UUID,
    lesson_id: Annotated[
        str,
        Path(
            min_length=1,
            max_length=80,
            pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
        ),
    ],
    user_id: AuthenticatedUser,
    database: Database,
) -> list[dict[str, Any]]:
    session = _session(database, session_id, user_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Learning session not found.")
    _ensure_session_course_access(database, session, user_id)
    _ensure_lesson_reviewable(database, session, lesson_id)
    response = _database_call(
        "list lesson activities",
        lambda: (
            database.table("activities")
            .select("*")
            .eq("session_id", str(session_id))
            .eq("lesson_id", lesson_id)
            .order("created_at", desc=True)
            .execute()
        ),
    )
    try:
        return [_lesson_activity_response(row) for row in _rows(response)]
    except (KeyError, TypeError, ValueError, ValidationError) as error:
        logger.exception(
            "Stored lesson activity for session %s is invalid.", session_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "invalid_lesson_activity",
                "message": "The lesson activity is unavailable.",
            },
        ) from error


@router.post(
    "/{session_id}/lessons/{lesson_id}/activities/{activity_id}/check",
    response_model=CodingAnswerResponse,
)
def check_coding_answer(
    session_id: UUID,
    lesson_id: Annotated[
        str,
        Path(
            min_length=1,
            max_length=80,
            pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
        ),
    ],
    activity_id: UUID,
    payload: CheckCodingAnswerRequest,
    user_id: AuthenticatedUser,
    database: Database,
) -> dict[str, Any]:
    session = _session(database, session_id, user_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Learning session not found.")
    _ensure_session_course_access(database, session, user_id)
    _ensure_lesson_reviewable(database, session, lesson_id)
    response = _database_call(
        "load coding activity",
        lambda: (
            database.table("activities")
            .select("presentation_format, content")
            .eq("id", str(activity_id))
            .eq("session_id", str(session_id))
            .eq("lesson_id", lesson_id)
            .limit(1)
            .execute()
        ),
    )
    rows = _rows(response)
    if not rows:
        raise HTTPException(status_code=404, detail="Lesson activity not found.")
    try:
        activity = GeneratedLessonActivity.model_validate(
            {
                "presentation_format": rows[0]["presentation_format"],
                "content": rows[0]["content"],
            }
        )
    except (KeyError, TypeError, ValueError, ValidationError) as error:
        logger.exception("Stored lesson activity %s is invalid.", activity_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "invalid_lesson_activity",
                "message": "The lesson activity is unavailable.",
            },
        ) from error
    if not isinstance(activity.content, CodingContent):
        raise HTTPException(
            status_code=409, detail="This activity is not a coding exercise."
        )

    is_correct = _normalize_code(payload.code) == _normalize_code(
        activity.content.expected_code
    )
    return CodingAnswerResponse(
        is_correct=is_correct,
        message=(
            "Correct. Your code matches the expected completion."
            if is_correct
            else "Not quite. Check your implementation and try again."
        ),
        solution=(activity.content.expected_code if payload.reveal_solution else None),
    ).model_dump(mode="json")


@router.get("/{session_id}/interactions", response_model=list[QuizInteractionResponse])
def list_learning_interactions(
    session_id: UUID,
    user_id: AuthenticatedUser,
    database: Database,
) -> list[dict[str, Any]]:
    session = _session(database, session_id, user_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Learning session not found.")
    _ensure_session_course_access(database, session, user_id)
    response = _database_call(
        "list learning interactions",
        lambda: (
            database.table("learning_interactions")
            .select("*")
            .eq("session_id", str(session_id))
            .order("created_at")
            .execute()
        ),
    )
    return [_quiz_interaction_response(row) for row in _rows(response)]


@router.post(
    "/{session_id}/interactions",
    status_code=status.HTTP_201_CREATED,
    response_model=QuizInteractionResponse,
)
def create_learning_interaction(
    session_id: UUID,
    payload: GenerateInteractionRequest,
    user_id: AuthenticatedUser,
    database: Database,
) -> dict[str, Any]:
    session = _session(database, session_id, user_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Learning session not found.")
    _ensure_session_course_access(database, session, user_id)
    lesson_id = payload.lesson_id or session.get("current_lesson_id")
    if not lesson_id:
        raise HTTPException(status_code=409, detail="There is no current lesson.")
    _ensure_lesson_reviewable(database, session, lesson_id)

    course = _course(database, session["course_id"])
    version = _version(database, session["course_version_id"])
    if (
        course is None
        or version is None
        or version.get("course_id") != session["course_id"]
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "invalid_learning_session",
                "message": "The learning session is unavailable.",
            },
        )
    plan = _plan(version)
    target_module = next(
        (
            module
            for module in plan.modules
            if any(lesson.lesson_id == lesson_id for lesson in module.lessons)
        ),
        None,
    )
    target_lesson = (
        next(
            (
                lesson
                for lesson in target_module.lessons
                if lesson.lesson_id == lesson_id
            ),
            None,
        )
        if target_module
        else None
    )
    if target_module is None or target_lesson is None:
        raise HTTPException(status_code=409, detail="This lesson is not in the course.")

    try:
        quiz = generate_quiz(
            course["title"],
            target_module,
            target_lesson,
            user_id=user_id,
            database=database,
        )
    except TokenLimitExceeded as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "daily_token_limit_reached",
                "message": "Your daily AI token limit has been reached.",
                "reset_at": error.reset_at,
            },
        ) from error
    except ProviderConfigurationError as error:
        logger.error("Quiz generation is not configured: %s", error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "quiz_generation_unavailable",
                "message": "Quiz generation is not configured.",
            },
        ) from error
    except CourseGenerationError as error:
        logger.warning("Quiz generation returned invalid content: %s", error)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "invalid_generated_quiz",
                "message": "The quiz could not be validated. Please retry.",
            },
        ) from error
    except Exception as error:
        logger.exception("Quiz provider request failed.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "quiz_generation_failed",
                "message": "Quiz generation failed. Please retry.",
            },
        ) from error

    inserted = _database_call(
        "save learning interaction",
        lambda: (
            database.table("learning_interactions")
            .insert(
                {
                    "session_id": str(session_id),
                    "lesson_id": lesson_id,
                    "kind": payload.kind,
                    "action": payload.action,
                    "content": quiz.model_dump(mode="json"),
                    "selected_option": None,
                }
            )
            .execute()
        ),
    )
    rows = _rows(inserted)
    if not rows:
        logger.error("Saving quiz for session %s returned no record.", session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "invalid_database_response",
                "message": "The quiz could not be saved.",
            },
        )
    return _quiz_interaction_response(rows[0])


@router.post(
    "/{session_id}/interactions/{interaction_id}/answer",
    response_model=QuizInteractionResponse,
)
def submit_learning_interaction_answer(
    session_id: UUID,
    interaction_id: UUID,
    payload: SubmitQuizAnswerRequest,
    user_id: AuthenticatedUser,
    database: Database,
) -> dict[str, Any]:
    session = _session(database, session_id, user_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Learning session not found.")
    _ensure_session_course_access(database, session, user_id)
    response = _database_call(
        "load learning interaction",
        lambda: (
            database.table("learning_interactions")
            .select("*")
            .eq("id", str(interaction_id))
            .eq("session_id", str(session_id))
            .limit(1)
            .execute()
        ),
    )
    rows = _rows(response)
    if not rows:
        raise HTTPException(status_code=404, detail="Learning interaction not found.")
    row = rows[0]
    _ensure_lesson_reviewable(database, session, str(row.get("lesson_id", "")))
    try:
        quiz = GeneratedQuiz.model_validate(row["content"])
    except (KeyError, TypeError, ValueError, ValidationError) as error:
        logger.exception("Stored quiz interaction %s is invalid.", interaction_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "invalid_learning_interaction",
                "message": "The learning interaction is unavailable.",
            },
        ) from error
    if payload.selected_option >= len(quiz.options):
        raise HTTPException(
            status_code=422, detail="Choose one of the available options."
        )
    if row.get("selected_option") is not None:
        raise HTTPException(
            status_code=409, detail="This quiz has already been answered."
        )

    updated = _database_call(
        "save learning interaction answer",
        lambda: (
            database.table("learning_interactions")
            .update({"selected_option": payload.selected_option})
            .eq("id", str(interaction_id))
            .eq("session_id", str(session_id))
            .is_("selected_option", "null")
            .execute()
        ),
    )
    updated_rows = _rows(updated)
    if not updated_rows:
        raise HTTPException(
            status_code=409, detail="This quiz has already been answered."
        )
    return _quiz_interaction_response(updated_rows[0])


@router.post("/{session_id}/lessons/{lesson_id}/complete")
def complete_lesson(
    session_id: UUID,
    lesson_id: Annotated[
        str,
        Path(
            min_length=1,
            max_length=80,
            pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
        ),
    ],
    user_id: AuthenticatedUser,
    database: Database,
) -> dict[str, Any]:
    session = _session(database, session_id, user_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Learning session not found.")
    _ensure_session_course_access(database, session, user_id)
    if session.get("status") != "active":
        raise HTTPException(
            status_code=409, detail="This learning session is complete."
        )
    if session.get("current_lesson_id") != lesson_id:
        raise HTTPException(status_code=409, detail="This is not the current lesson.")

    _database_call(
        "complete lesson",
        lambda: database.rpc(
            "complete_learning_lesson",
            {
                "p_user_id": user_id,
                "p_session_id": str(session_id),
                "p_lesson_id": lesson_id,
            },
        ).execute(),
    )
    updated_session = _session(database, session_id, user_id)
    if updated_session is None:
        raise HTTPException(status_code=404, detail="Learning session not found.")
    return _full_session(database, updated_session, user_id)
