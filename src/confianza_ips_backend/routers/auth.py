from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..api.dependencies import AuthenticationServiceDependency
from ..audit import record_audit
from ..db import get_db
from ..models import User
from ..schemas import LoginRequest, TokenResponse, UserResponse, UserUpdate
from ..security import CurrentUser, auth_metadata, is_agent_request

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    authentication: AuthenticationServiceDependency,
) -> TokenResponse:
    result = authentication.login(payload.email, payload.password)
    return TokenResponse(access_token=result.access_token, expires_in=result.expires_in)


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser) -> User:
    return user


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: UserUpdate, user: CurrentUser, request: Request, db: Session = Depends(get_db)
) -> User:
    before = {"full_name": user.full_name}
    user.full_name = payload.full_name.strip()
    record_audit(
        db,
        user,
        "update",
        "user",
        user.id,
        before=before,
        after={"full_name": user.full_name},
        metadata=auth_metadata(request),
    )
    db.commit()
    db.refresh(user)
    return user


@router.post("/logout")
def logout(
    user: CurrentUser,
    request: Request,
    authentication: AuthenticationServiceDependency,
) -> dict[str, str]:
    if is_agent_request(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El token del agente no puede cerrar la sesión interna",
        )
    authentication.logout(user)
    return {"message": "Sesión cerrada"}
