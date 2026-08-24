"""Domain exceptions used by application services."""


class DomainException(Exception):
    """Base class for errors raised by HTTP-independent business logic."""


class UserAlreadyExistsError(DomainException):
    """Raised when an email address is already registered."""


class InvalidCredentialsError(DomainException):
    """Raised when authentication credentials are invalid."""


class InactiveUserError(DomainException):
    """Raised when an inactive user tries to authenticate."""


class PortfolioNotFoundError(DomainException):
    """Raised when a portfolio does not exist for its expected owner."""


class PersistenceError(DomainException):
    """Raised when a database operation cannot be completed."""


class InvalidImportTypeError(DomainException):
    """Raised when a portfolio import type is not supported."""


class PortfolioImportError(DomainException):
    """Raised when a broker portfolio file cannot be parsed."""
