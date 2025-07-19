from src.ygo74.fastapi_openai_rag.domain.exceptions.domain_exception import DomainException

class EntityNotFoundError(DomainException):
    """Raised when an entity is not found."""

    def __init__(self, entity_type: str, identifier: str):
        """Initialize exception.

        Args:
            entity_type (str): Type of entity that was not found
            identifier (str): Identifier used to search for the entity
        """
        self.entity_type = entity_type
        self.identifier = identifier
        super().__init__(f"{entity_type} with identifier '{identifier}' not found")

