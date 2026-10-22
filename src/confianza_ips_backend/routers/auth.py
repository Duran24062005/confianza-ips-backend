from fastapi import APIRouter

from ..api.dependencies import AuthenticationServiceDependency
from ..models import User
from ..schemas import LoginRequest, TokenResponse, UserResponse
from ..security import CurrentUser

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


@router.post("/logout")
def logout(
    user: CurrentUser,
    authentication: AuthenticationServiceDependency,
) -> dict[str, str]:
    authentication.logout(user)
    return {"message": "Sesión cerrada"}
