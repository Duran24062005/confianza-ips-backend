class ApplicationError(Exception):
    """Base exception for errors that can be translated by the API layer."""


class DatabaseNotReadyError(ApplicationError):
    """Raised when the application database cannot serve the use case."""


class InvalidCredentialsError(ApplicationError):
    """Raised when a login cannot be authenticated."""
