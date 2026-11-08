import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from supabase import Client

from app.database.supabase import get_supabase_client
from app.schemas.course import (
    CourseDraftProposal,
    CourseDraftRequest,
    CourseUpdateRequest,
)
from app.services.course_generator import (
    CourseGenerationError,
    ProviderConfigurationError,
    generate_course_draft,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["courses"])
Database = Annotated[Client, Depends(get_supabase_client)]


def _session_user_id(request: Request) -> int | None:
    user_id = request.session.get("user_id")
    if isinstance(user_id, bool):
        return None
    if isinstance(user_id, int) and user_id > 0:
        return user_id
    return None


def require_user_id(request: Request) -> int:
    user_id = _session_user_id(request)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "authentication_required", "message": "Sign in required."},
        )
    return user_id


AuthenticatedUser = Annotated[int, Depends(require_user_id)]


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
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Course database operation failed: %s", operation)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "database_operation_failed",
                "message": "The course could not be loaded or saved.",
            },
        ) from error


def _get_course(database: Client, course_id: UUID) -> dict[str, Any] | None:
    response = _database_call(
        "get course",
        lambda: (
            database.table("courses")
            .select("*")
            .eq("id", str(course_id))
            .limit(1)
            .execute()
        ),
    )
    rows = _rows(response)
    return rows[0] if rows else None


def _get_version(database: Client, version_id: str | None) -> dict[str, Any] | None:
    if not version_id:
        return None
    response = _database_call(
        "get course version",
        lambda: (
            database.table("course_versions")
            .select("id, version_number, plan, created_at")
            .eq("id", version_id)
            .limit(1)
            .execute()
        ),
    )
    rows = _rows(response)
    return rows[0] if rows else None


def _course_response(
    course: dict[str, Any],
    version: dict[str, Any] | None,
) -> dict[str, Any]:
    result = {
        key: course.get(key)
        for key in (
            "id",
            "title",
            "description",
            "status",
            "default_presentation_format",
            "created_at",
            "updated_at",
            "published_at",
        )
    }
    result["version_number"] = version.get("version_number") if version else None
    result["plan"] = version.get("plan") if version else None
    return result


def _call_save_draft(
    database: Client,
    user_id: int,
    proposal: CourseDraftProposal,
    course_id: UUID | None = None,
) -> dict[str, Any]:
    response = _database_call(
        "save course draft",
        lambda: database.rpc(
            "save_course_draft",
            {
                "p_created_by": user_id,
                "p_title": proposal.title,
                "p_description": proposal.description,
                "p_default_presentation_format": proposal.default_presentation_format,
                "p_plan": proposal.plan.model_dump(mode="json"),
                "p_course_id": str(course_id) if course_id else None,
            },
        ).execute(),
    )
    rows = _rows(response)
    if not rows:
        logger.error("Saving a course draft returned no version record.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "invalid_database_response",
                "message": "The course could not be saved.",
            },
        )
    return rows[0]


@router.post("/course-drafts", response_model=CourseDraftProposal)
def create_course_draft(
    request: CourseDraftRequest,
    _user_id: AuthenticatedUser,
) -> CourseDraftProposal:
    try:
        return generate_course_draft(request)
    except ProviderConfigurationError as error:
        logger.error("Course generation is not configured: %s", error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "course_generation_unavailable",
                "message": "Course generation is not configured.",
            },
        ) from error
    except CourseGenerationError as error:
        logger.warning("Course generation returned invalid content: %s", error)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "invalid_generated_course",
                "message": "The generated course could not be validated. Please retry.",
            },
        ) from error
    except Exception as error:
        logger.exception("Course generation provider request failed.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "course_generation_failed",
                "message": "Course generation failed. Please retry.",
            },
        ) from error


@router.post("/courses", status_code=status.HTTP_201_CREATED)
def save_course(
    proposal: CourseDraftProposal,
    user_id: AuthenticatedUser,
    database: Database,
) -> dict[str, Any]:
    record = _call_save_draft(database, user_id, proposal)
    return {
        "course_id": record["course_id"],
        "version_id": record["version_id"],
        "version_number": record["version_number"],
        "status": "draft",
    }


@router.get("/courses")
def list_published_courses(
    database: Database,
    search: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
) -> list[dict[str, Any]]:
    def query_courses() -> Any:
        query = (
            database.table("courses")
            .select("*")
            .eq("status", "published")
            .order("published_at", desc=True)
            .limit(100)
        )
        if search:
            query = query.ilike("title", f"%{search}%")
        return query.execute()

    courses = _rows(_database_call("list published courses", query_courses))
    version_ids = [course["published_version_id"] for course in courses]
    versions_by_id: dict[str, dict[str, Any]] = {}
    if version_ids:
        response = _database_call(
            "load published course plans",
            lambda: (
                database.table("course_versions")
                .select("id, version_number, plan")
                .in_("id", version_ids)
                .execute()
            ),
        )
        versions_by_id = {row["id"]: row for row in _rows(response)}
    return [
        _course_response(
            course,
            versions_by_id.get(course.get("published_version_id")),
        )
        for course in courses
    ]


@router.get("/courses/{course_id}")
def get_course(
    course_id: UUID,
    request: Request,
    database: Database,
) -> dict[str, Any]:
    course = _get_course(database, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")

    if course["status"] == "published":
        version_id = course.get("published_version_id")
    elif course["status"] == "draft" and _session_user_id(request) == course.get(
        "created_by"
    ):
        version_id = course.get("current_version_id")
    else:
        raise HTTPException(status_code=404, detail="Course not found.")

    version = _get_version(database, version_id)
    if version is None:
        logger.error("Course %s references a missing plan version.", course_id)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "invalid_course_version",
                "message": "The course plan is unavailable.",
            },
        )
    return _course_response(course, version)


@router.patch("/courses/{course_id}")
def update_course(
    course_id: UUID,
    update: CourseUpdateRequest,
    user_id: AuthenticatedUser,
    database: Database,
) -> dict[str, Any]:
    course = _get_course(database, course_id)
    if (
        course is None
        or course.get("created_by") != user_id
        or course.get("status") != "draft"
    ):
        raise HTTPException(status_code=404, detail="Draft course not found.")

    version = _get_version(database, course.get("current_version_id"))
    if version is None:
        logger.error("Draft course %s has no current plan version.", course_id)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "invalid_course_version",
                "message": "The course plan is unavailable.",
            },
        )

    proposal = CourseDraftProposal(
        title=update.title if update.title is not None else course["title"],
        description=(
            update.description
            if update.description is not None
            else course["description"]
        ),
        default_presentation_format=(
            update.default_presentation_format
            if update.default_presentation_format is not None
            else course["default_presentation_format"]
        ),
        plan=update.plan if update.plan is not None else version["plan"],
    )
    record = _call_save_draft(database, user_id, proposal, course_id)
    return {
        "course_id": record["course_id"],
        "version_id": record["version_id"],
        "version_number": record["version_number"],
        "status": "draft",
    }


@router.post("/courses/{course_id}/publish")
def publish_course(
    course_id: UUID,
    user_id: AuthenticatedUser,
    database: Database,
) -> dict[str, Any]:
    course = _get_course(database, course_id)
    if (
        course is None
        or course.get("created_by") != user_id
        or course.get("status") != "draft"
    ):
        raise HTTPException(status_code=404, detail="Draft course not found.")

    response = _database_call(
        "publish course",
        lambda: database.rpc(
            "publish_course",
            {"p_course_id": str(course_id), "p_created_by": user_id},
        ).execute(),
    )
    courses = _rows(response)
    if not courses:
        raise HTTPException(status_code=404, detail="Draft course not found.")
    course = courses[0]
    version = _get_version(database, course.get("published_version_id"))
    if version is None:
        logger.error("Published course %s has no published plan version.", course_id)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "invalid_course_version",
                "message": "The course plan is unavailable.",
            },
        )
    return _course_response(course, version)
