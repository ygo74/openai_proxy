from .domain_exception import DomainException


class ValidationError(DomainException):
    """Raised when domain validation fails."""
    pass