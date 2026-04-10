from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from src.rag_api.auth import verify_password, create_session, delete_session, _get_connection

router = APIRouter(prefix="/api/auth", tags=["auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(req: LoginRequest):
    conn = _get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id, password_hash, role FROM users WHERE username = %s;", (req.username,))
                row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user_id, password_hash, role = row
    if not verify_password(req.password, password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_session(user_id)
    return {
        "token": token,
        "user_id": user_id,
        "username": req.username,
        "role": role
    }

@router.post("/logout")
def logout(request: Request):
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        delete_session(token)
    return {"message": "Logged out"}

from src.rag_api.dependencies import get_current_user

@router.get("/me")
def get_me(user: dict = Depends(get_current_user)):
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "role": user["role"]
    }
