import os
from typing import Annotated

from fastapi import Depends, FastAPI
from starlette.middleware.sessions import SessionMiddleware
from supabase import Client

from app.api.auth import router as auth_router
from app.api.courses import router as courses_router
from app.database.supabase import get_supabase_client
from app.api.learning_sessions import router as learning_sessions_router

session_secret = os.getenv("SESSION_SECRET")
if not session_secret:
    raise RuntimeError("SESSION_SECRET must be set before starting the backend")

app_environment = os.getenv("APP_ENV", "development").lower()

app = FastAPI()
app.include_router(courses_router)
app.include_router(auth_router)
app.include_router(learning_sessions_router)
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret,
    session_cookie="session",
    same_site="lax",
    https_only=app_environment != "development",
    max_age=60 * 60 * 24 * 7,
)


@app.get("/")
def read_root():
    return {"message": "OK"}


@app.get("/health")
def health(supabase_client: Annotated[Client, Depends(get_supabase_client)]):
    try:
        response = supabase_client.table("user").select("created_at").execute()
        return {"status": "OK", "detail": response}
    except Exception as e:
        return {"status": "Error", "detail": str(e)}
