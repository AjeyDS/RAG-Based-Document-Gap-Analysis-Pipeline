"""Authentication routes: login, logout, and current-user profile."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.rag_api.auth import verify_password, create_session, delete_session, get_user_by_username
from src.rag_api.dependencies import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(req: LoginRequest) -> dict:
    """Authenticate a user and return a session token with user context."""
    row = get_user_by_username(req.username)
    if not row:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_id, password_hash, role = row
    if not verify_password(req.password, password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_session(user_id)
    return {"token": token, "user_id": user_id, "username": req.username, "role": role}


@router.post("/logout")
def logout(request: Request, _: dict = Depends(get_current_user)) -> dict:
    """Revoke the caller's session token."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        delete_session(auth_header.split(" ", 1)[1])
    return {"message": "Logged out"}


@router.get("/me")
def get_me(user: dict = Depends(get_current_user)) -> dict:
    """Return the current authenticated user's profile."""
    return {"user_id": user["user_id"], "username": user["username"], "role": user["role"]}
