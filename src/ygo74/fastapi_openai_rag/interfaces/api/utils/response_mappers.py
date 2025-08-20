"""Utility functions for mapping domain models to API response models."""
from datetime import datetime
from typing import List, TypeVar, Type, Generic, Any, Dict, get_type_hints, get_origin, get_args

from pydantic import BaseModel, create_model

T = TypeVar('T')
R = TypeVar('R', bound=BaseModel)

def map_to_response_model(domain_model: Any, response_model_class: Type[R]) -> R:
    """Map domain model to API response model.

    Args:
        domain_model: Domain model instance
        response_model_class: Pydantic model class for response

    Returns:
        Instance of response model
    """
    # Get all fields from the response model
    response_fields = get_type_hints(response_model_class)

    # Build kwargs for response model initialization
    kwargs = {}

    for field_name, field_type in response_fields.items():
        # Special handling for mapped fields
        if field_name == "groups" and hasattr(domain_model, "groups") and isinstance(domain_model.groups, list):
            # Handle mapping groups to list of names
            kwargs[field_name] = [group.name for group in domain_model.groups] if domain_model.groups else []
        else:
            # Normal field mapping - get from domain model if available
            if hasattr(domain_model, field_name):
                kwargs[field_name] = getattr(domain_model, field_name)

    return response_model_class(**kwargs)

def map_to_response_model_list(domain_models: List[Any], response_model_class: Type[R]) -> List[R]:
    """Map list of domain models to list of API response models.

    Args:
        domain_models: List of domain model instances
        response_model_class: Pydantic model class for response

    Returns:
        List of response model instances
    """
    return [map_to_response_model(model, response_model_class) for model in domain_models]
