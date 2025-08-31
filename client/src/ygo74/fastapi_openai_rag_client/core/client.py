"""API client for FastAPI OpenAI RAG proxy."""
import json
import logging
from typing import Optional, Dict, Any, List, Tuple, Union
import requests
from urllib.parse import urljoin

from .auth import AuthContext

logger = logging.getLogger(__name__)


class ApiException(Exception):
    """Exception raised for API errors."""

    def __init__(self, status_code: int, message: str, details: Optional[Dict[str, Any]] = None):
        """Initialize API exception.

        Args:
            status_code: HTTP status code
            message: Error message
            details: Additional error details
        """
        self.status_code = status_code
        self.message = message
        self.details = details
        super().__init__(f"API Error {status_code}: {message}")


class ApiClient:
    """API client for FastAPI OpenAI RAG proxy.

    Handles requests to the API with proper authentication.
    """

    def __init__(self, auth_context: AuthContext):
        """Initialize API client.

        Args:
            auth_context: Authentication context
        """
        self.auth = auth_context

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        raw_response: bool = False
    ) -> Any:
        """Make API request with authentication.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (relative to base URL)
            params: URL parameters
            data: Form data
            json_data: JSON request body
            raw_response: If True, return raw Response object

        Returns:
            API response data

        Raises:
            ApiException: If API returns error
        """
        url = urljoin(self.auth.get_api_url(), endpoint)
        headers = self.auth.get_auth_headers()
        headers["Content-Type"] = "application/json"

        try:
            response = requests.request(
                method,
                url,
                params=params,
                data=data,
                json=json_data,
                headers=headers
            )

            if raw_response:
                return response

            # Handle non-2xx responses
            if not response.ok:
                try:
                    error_data = response.json()
                    message = error_data.get("detail", response.reason)
                except ValueError:
                    message = response.text or response.reason
                    error_data = None

                raise ApiException(response.status_code, message, error_data)

            # Return JSON data if available, otherwise text
            if response.content:
                try:
                    return response.json()
                except ValueError:
                    return response.text

            return None

        except requests.RequestException as e:
            logger.error(f"Request error: {e}")
            raise ApiException(500, f"Request error: {str(e)}")

    # Group API methods
    def list_groups(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """Get list of groups.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of group objects
        """
        return self._make_request("GET", "/v1/admin/groups", params={"skip": skip, "limit": limit})

    def get_group(self, group_id: int) -> Dict[str, Any]:
        """Get group by ID.

        Args:
            group_id: Group ID

        Returns:
            Group object
        """
        return self._make_request("GET", f"/v1/admin/groups/{group_id}")

    def create_group(self, name: str, description: Optional[str] = None) -> Dict[str, Any]:
        """Create new group.

        Args:
            name: Group name
            description: Group description

        Returns:
            Created group object
        """
        data = {
            "name": name,
            "description": description
        }
        return self._make_request("POST", "/v1/admin/groups", json_data=data)

    def update_group(
        self,
        group_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update existing group.

        Args:
            group_id: Group ID
            name: New group name
            description: New group description

        Returns:
            Updated group object
        """
        data = {}
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description

        return self._make_request("PUT", f"/v1/admin/groups/{group_id}", json_data=data)

    def delete_group(self, group_id: int) -> Dict[str, Any]:
        """Delete group.

        Args:
            group_id: Group ID

        Returns:
            Deletion status
        """
        return self._make_request("DELETE", f"/v1/admin/groups/{group_id}")

    # Model API methods
    def list_models(
        self,
        skip: int = 0,
        limit: int = 100,
        status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get list of models.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            status_filter: Filter models by status

        Returns:
            List of model objects
        """
        params = {"skip": skip, "limit": limit}
        if status_filter:
            params["status_filter"] = status_filter

        return self._make_request("GET", "/v1/admin/models", params=params)

    def refresh_models(self) -> List[Dict[str, Any]]:
        """Refresh models from all configured providers.
        Returns:
            List of refreshed model objects
        """
        return self._make_request("POST", "/v1/admin/models/refresh")


    def get_model(self, model_id: int) -> Dict[str, Any]:
        """Get model by ID.

        Args:
            model_id: Model ID

        Returns:
            Model object
        """
        return self._make_request("GET", f"/v1/admin/models/{model_id}")

    def create_model(
        self,
        url: str,
        name: str,
        technical_name: str,
        provider: str,
        capabilities: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create new model.

        Args:
            url: Model URL
            name: Display name
            technical_name: Technical name
            provider: LLM provider name
            capabilities: Model capabilities

        Returns:
            Created model object
        """
        data = {
            "url": url,
            "name": name,
            "technical_name": technical_name,
            "provider": provider,
            "capabilities": capabilities or {}
        }
        return self._make_request("POST", "/v1/admin/models", json_data=data)

    def update_model(
        self,
        model_id: int,
        url: Optional[str] = None,
        name: Optional[str] = None,
        technical_name: Optional[str] = None,
        provider: Optional[str] = None,
        capabilities: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Update existing model.

        Args:
            model_id: Model ID
            url: Model URL
            name: Display name
            technical_name: Technical name
            provider: LLM provider name
            capabilities: Model capabilities

        Returns:
            Updated model object
        """
        data = {}
        if url is not None:
            data["url"] = url
        if name is not None:
            data["name"] = name
        if technical_name is not None:
            data["technical_name"] = technical_name
        if provider is not None:
            data["provider"] = provider
        if capabilities is not None:
            data["capabilities"] = capabilities

        return self._make_request("PUT", f"/v1/admin/models/{model_id}", json_data=data)

    def delete_model(self, model_id: int) -> Dict[str, Any]:
        """Delete model.

        Args:
            model_id: Model ID

        Returns:
            Deletion status
        """
        return self._make_request("DELETE", f"/v1/admin/models/{model_id}")

    def update_model_status(self, model_id: int, status: str) -> Dict[str, Any]:
        """Update model status.

        Args:
            model_id: Model ID
            status: New status

        Returns:
            Updated model object
        """
        data = {"status": status}
        return self._make_request("PATCH", f"/v1/admin/models/{model_id}/status", json_data=data)

    def add_model_to_group(self, model_id: int, group_id: int) -> Dict[str, Any]:
        """Add model to group.

        Args:
            model_id: Model ID
            group_id: Group ID

        Returns:
            Association status
        """
        return self._make_request("POST", f"/v1/admin/models/{model_id}/groups/{group_id}")

    def remove_model_from_group(self, model_id: int, group_id: int) -> Dict[str, Any]:
        """Remove model from group.

        Args:
            model_id: Model ID
            group_id: Group ID

        Returns:
            Disassociation status
        """
        return self._make_request("DELETE", f"/v1/admin/models/{model_id}/groups/{group_id}")

    # User API methods
    def list_users(
        self,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """Get list of users.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            active_only: If True, return only active users

        Returns:
            List of user objects
        """
        params = {"skip": skip, "limit": limit, "active_only": active_only}
        return self._make_request("GET", "/v1/admin/users", params=params)

    def get_user(self, user_id: str) -> Dict[str, Any]:
        """Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User object
        """
        return self._make_request("GET", f"/v1/admin/users/{user_id}")

    def get_user_token_usage(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get token usage statistics for a user.

        Args:
            user_id: User ID
            days: Number of days to look back for statistics

        Returns:
            Dictionary containing token usage statistics
        """
        params = {"days": days}
        return self._make_request("GET", f"/v1/admin/users/{user_id}/token-usage", params=params)

    def get_user_token_usage_details(self, user_id: str, days: int = 30, limit: int = 100) -> List[Dict[str, Any]]:
        """Get detailed token usage records for a user.

        Args:
            user_id: User ID
            days: Number of days to look back for statistics
            limit: Maximum number of records to return

        Returns:
            List of token usage detail records
        """
        params = {"days": days, "limit": limit}
        return self._make_request("GET", f"/v1/admin/users/{user_id}/token-usage/details", params=params)

    def get_user_by_username(self, username: str) -> Dict[str, Any]:
        """Get user by username.

        Args:
            username: Username

        Returns:
            User object
        """
        return self._make_request("GET", f"/v1/admin/users/username/{username}")

    def create_user(
        self,
        username: str,
        email: Optional[str] = None,
        groups: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create new user.

        Args:
            username: Username
            email: Email address
            groups: List of group names

        Returns:
            Created user object
        """
        data = {
            "username": username,
            "email": email,
            "groups": groups
        }
        return self._make_request("POST", "/v1/admin/users", json_data=data)

    def update_user(
        self,
        user_id: str,
        username: Optional[str] = None,
        email: Optional[str] = None,
        groups: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Update existing user.

        Args:
            user_id: User ID
            username: New username
            email: New email address
            groups: New list of group names

        Returns:
            Updated user object
        """
        data = {}
        if username is not None:
            data["username"] = username
        if email is not None:
            data["email"] = email
        if groups is not None:
            data["groups"] = groups

        return self._make_request("PUT", f"/v1/admin/users/{user_id}", json_data=data)

    def delete_user(self, user_id: str) -> Dict[str, Any]:
        """Delete user.

        Args:
            user_id: User ID

        Returns:
            Deletion status
        """
        return self._make_request("DELETE", f"/v1/admin/users/{user_id}")

    def deactivate_user(self, user_id: str) -> Dict[str, Any]:
        """Deactivate user.

        Args:
            user_id: User ID

        Returns:
            Updated user object
        """
        return self._make_request("POST", f"/v1/admin/users/{user_id}/deactivate")

    def create_api_key(
        self,
        user_id: str,
        name: Optional[str] = None,
        expires_at: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create new API key for user.

        Args:
            user_id: User ID
            name: Key name
            expires_at: Expiration date (ISO format)

        Returns:
            API key information
        """
        data = {}
        if name is not None:
            data["name"] = name
        if expires_at is not None:
            data["expires_at"] = expires_at

        return self._make_request("POST", f"/v1/admin/users/{user_id}/api-keys", json_data=data)
