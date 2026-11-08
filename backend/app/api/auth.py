import logging
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from supabase import Client

from app.api.courses import require_user_id
from app.database.supabase import get_supabase_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
Database = Annotated[Client, Depends(get_supabase_client)]
AuthenticatedUser = Annotated[int, Depends(require_user_id)]
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    email: Annotated[str, Field(min_length=3, max_length=254)]


def _email(value: str) -> str:
    normalized = value.lower()
    if not EMAIL_PATTERN.fullmatch(normalized):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Enter a valid email address.",
        )
    return normalized


def _rows(response: Any) -> list[dict[str, Any]]:
    data = response.data
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    return []


def _find_user(database: Client, email: str) -> dict[str, Any] | None:
    try:
        response = (
            database.table("user")
            .select("id, email")
            .eq("email", email)
            .limit(1)
            .execute()
        )
    except Exception as error:
        logger.exception("Email-only authentication lookup failed.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to sign in right now.",
        ) from error
    rows = _rows(response)
    return rows[0] if rows else None


def _sign_in(request: Request, user: dict[str, Any]) -> dict[str, Any]:
    request.session["user_id"] = user["id"]
    return {"message": "Signed in", "user": {"email": user["email"]}}


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_email(
    payload: EmailRequest,
    request: Request,
    database: Database,
) -> dict[str, Any]:
    email = _email(payload.email)
    existing_user = _find_user(database, email)
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    try:
        response = database.table("user").insert({"email": email}).execute()
    except Exception as error:
        logger.exception("Email-only account registration failed.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create an account right now.",
        ) from error
    rows = _rows(response)
    if not rows:
        logger.error("Account registration returned no user record.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create an account right now.",
        )
    return _sign_in(request, rows[0])


@router.post("/login")
def login_email(
    payload: EmailRequest,
    request: Request,
    database: Database,
) -> dict[str, Any]:
    user = _find_user(database, _email(payload.email))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account exists for this email.",
        )
    return _sign_in(request, user)


@router.post("/logout")
def logout(request: Request) -> dict[str, str]:
    request.session.clear()
    return {"message": "Signed out"}


@router.get("/me")
def get_current_user(user_id: AuthenticatedUser, database: Database) -> dict[str, Any]:
    try:
        response = (
            database.table("user")
            .select("id, email")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
    except Exception as error:
        logger.exception("Loading the signed-in user failed.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load your account right now.",
        ) from error
    rows = _rows(response)
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in required.",
        )
    return {"user": {"email": rows[0]["email"]}}
