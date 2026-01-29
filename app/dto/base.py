"""
Base DTO classes and validation helpers

Data Transfer Objects for serializing/deserializing HTTP requests and responses.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass


class ValidationError(Exception):
    """Exception raised when DTO validation fails."""
    pass


@dataclass
class BaseDTO:
    """
    Base class for all DTOs.

    Provides common serialization/deserialization methods.
    """

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert DTO to dictionary.

        Returns:
            Dictionary representation of DTO
        """
        raise NotImplementedError("Subclasses must implement to_dict()")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseDTO':
        """
        Create DTO from dictionary.

        Args:
            data: Dictionary with DTO data

        Returns:
            DTO instance

        Raises:
            ValidationError: If data is invalid
        """
        raise NotImplementedError("Subclasses must implement from_dict()")

    def validate(self) -> None:
        """
        Validate DTO data.

        Raises:
            ValidationError: If validation fails
        """
        pass  # Override in subclasses if needed


def require_field(data: Dict[str, Any], field: str) -> Any:
    """
    Require a field in data dictionary.

    Args:
        data: Dictionary to check
        field: Required field name

    Returns:
        Field value

    Raises:
        ValidationError: If field is missing

    Examples:
        >>> data = {"name": "test"}
        >>> require_field(data, "name")
        'test'
        >>> require_field(data, "missing")
        ValidationError: Missing required field: missing
    """
    if field not in data:
        raise ValidationError(f"Missing required field: {field}")
    return data[field]


def get_field(data: Dict[str, Any], field: str, default: Any = None) -> Any:
    """
    Get field from data dictionary with default.

    Args:
        data: Dictionary to check
        field: Field name
        default: Default value if field is missing

    Returns:
        Field value or default

    Examples:
        >>> data = {"name": "test"}
        >>> get_field(data, "name")
        'test'
        >>> get_field(data, "missing", "default")
        'default'
    """
    return data.get(field, default)


def require_nested_field(data: Dict[str, Any], *path: str) -> Any:
    """
    Require a nested field in data dictionary.

    Args:
        data: Dictionary to check
        *path: Path to nested field (e.g., "request", "intent", "name")

    Returns:
        Nested field value

    Raises:
        ValidationError: If any part of path is missing

    Examples:
        >>> data = {"request": {"intent": {"name": "TestIntent"}}}
        >>> require_nested_field(data, "request", "intent", "name")
        'TestIntent'
    """
    current = data
    for i, key in enumerate(path):
        if not isinstance(current, dict) or key not in current:
            field_path = ".".join(path[:i+1])
            raise ValidationError(f"Missing required field: {field_path}")
        current = current[key]
    return current


def get_nested_field(data: Dict[str, Any], *path: str, default: Any = None) -> Any:
    """
    Get nested field from data dictionary with default.

    Args:
        data: Dictionary to check
        *path: Path to nested field
        default: Default value if any part of path is missing

    Returns:
        Nested field value or default

    Examples:
        >>> data = {"request": {"intent": {"name": "TestIntent"}}}
        >>> get_nested_field(data, "request", "intent", "name")
        'TestIntent'
        >>> get_nested_field(data, "missing", "path", default="default")
        'default'
    """
    current = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current
