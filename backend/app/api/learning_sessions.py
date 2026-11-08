import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict, ValidationError
from supabase import Client

from app.api.courses import require_user_id
from app.database.supabase import get_supabase_client
from app.schemas.course import CoursePlan

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
            .select("id, title, description, status, published_version_id")
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


def _full_session(
    database: Client,
    session: dict[str, Any],
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


@router.post("", status_code=status.HTTP_201_CREATED)
def start_learning_session(
    payload: StartSessionRequest,
    user_id: AuthenticatedUser,
    database: Database,
) -> dict[str, Any]:
    course_id = str(payload.course_id)
    course = _course(database, course_id)
    if course is None or course.get("status") != "published":
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
    return _full_session(database, session)


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
    return [_full_session(database, row) for row in _rows(response)]


@router.get("/{session_id}")
def get_learning_session(
    session_id: UUID,
    user_id: AuthenticatedUser,
    database: Database,
) -> dict[str, Any]:
    session = _session(database, session_id, user_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Learning session not found.")
    return _full_session(database, session)


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
    return _full_session(database, updated_session)
