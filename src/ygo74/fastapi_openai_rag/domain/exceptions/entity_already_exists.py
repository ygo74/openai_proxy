from src.ygo74.fastapi_openai_rag.domain.exceptions.domain_exception import DomainException

class EntityAlreadyExistsError(DomainException):
    """Raised when trying to create an entity that already exists."""

    def __init__(self, entity_type: str, identifier: str):
        """Initialize exception.

        Args:
            entity_type (str): Type of entity that already exists
            identifier (str): Identifier that caused the conflict
        """
        self.entity_type = entity_type
        self.identifier = identifier
        super().__init__(f"{entity_type} with identifier '{identifier}' already exists")

