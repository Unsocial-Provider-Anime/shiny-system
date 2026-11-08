import os

from fastapi import FastAPI, Depends
from starlette.middleware.sessions import SessionMiddleware
from supabase import Client
from app.database.supabase import get_supabase_client
from typing import Annotated

session_secret = os.getenv("SESSION_SECRET")
if not session_secret:
    raise RuntimeError("SESSION_SECRET must be set before starting the backend")

app_environment = os.getenv("APP_ENV", "development").lower()

app = FastAPI()
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
        # Perform a simple query to check the database connection
        response = supabase_client.table("user").select("created_at").execute()
        return {"status": "OK", "detail": response}
    except Exception as e:
        return {"status": "Error", "detail": str(e)}
