from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..db import get_db
from ..models import User
from ..schemas import LoginRequest, TokenResponse, UserResponse
from ..security import CurrentUser, create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not user.active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas"
        )
    token, expires_in = create_access_token(user)
    record_audit(db, user, "login", "user", user.id)
    db.commit()
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser) -> User:
    return user


@router.post("/logout")
def logout(user: CurrentUser, db: Session = Depends(get_db)) -> dict[str, str]:
    user.session_version += 1
    record_audit(db, user, "logout", "user", user.id)
    db.commit()
    return {"message": "Sesión cerrada"}
