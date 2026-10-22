from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from ..application.services.authentication import AuthenticationService
from ..db import get_db
from ..infrastructure.persistence.repositories import SqlAlchemyUserRepository


def get_authentication_service(
    db: Annotated[Session, Depends(get_db)],
) -> AuthenticationService:
    return AuthenticationService(
        users=SqlAlchemyUserRepository(db),
        db=db,
    )


AuthenticationServiceDependency = Annotated[
    AuthenticationService,
    Depends(get_authentication_service),
]
