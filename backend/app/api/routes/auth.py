"""Mock authentication routes for the Buildathon."""
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/auth", tags=["auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

# Mock database of users matching docs/BUILDATHON_PLAN.md
USERS = {
    "moneypal_admin": {
        "password": "admin123",
        "role": "admin",
        "full_name": "Moneypal Administrator",
        "email": "admin@moneypal.com"
    },
    "gicc_admin": {
        "password": "admin123",
        "role": "gicc_admin",
        "full_name": "GICC Administrator",
        "email": "admin@gicc.com"
    },
    "gicc_policy": {
        "password": "policy123",
        "role": "gicc_policy",
        "full_name": "GICC Policy Maker",
        "email": "policy@gicc.com"
    },
    "gicc_director": {
        "password": "director123",
        "role": "gicc_director",
        "full_name": "GICC Director",
        "email": "director@gicc.com"
    },
}

@router.post("/login/")
def login(req: LoginRequest):
    user = USERS.get(req.username)
    if not user or user["password"] != req.password:
        raise HTTPException(401, "Invalid username or password.")
    # Return mock token containing username
    return {
        "access": f"mock-token-{req.username}",
        "refresh": "mock-refresh-token"
    }

@router.post("/session/refresh/")
def refresh():
    return {
        "access": "mock-token-refresh",
        "refresh": "mock-refresh-token"
    }

@router.get("/users/")
def list_users():
    """Demo user directory for the platform administration panel (no passwords)."""
    return [
        {"username": username, "role": u["role"], "full_name": u["full_name"], "email": u["email"]}
        for username, u in USERS.items()
    ]


@router.get("/me/")
def me(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    token = authorization.split(" ")[1]
    username = token.replace("mock-token-", "")
    user = USERS.get(username)
    if not user:
        raise HTTPException(401, "Invalid token")
    return {
        "username": username,
        "role": user["role"],
        "full_name": user["full_name"],
        "email": user["email"],
        "is_staff": user["role"] == "admin"
    }
