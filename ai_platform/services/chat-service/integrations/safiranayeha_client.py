"""
Safiranayeha API Client

Handles authentication and user data retrieval from the Safiranayeha platform.
"""
import httpx
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class SafiranayehaUserData(BaseModel):
    """User data from Safiranayeha API."""
    # Personal Information
    phone_number: Optional[str] = Field(None, alias="phoneNumber")
    full_name: Optional[str] = Field(None, alias="fullName")
    gender: Optional[str] = None
    birth_month: Optional[int] = Field(None, alias="birthMonth")
    birth_year: Optional[int] = Field(None, alias="birthYear")

    # Residence Information
    province: Optional[str] = None
    city: Optional[str] = None

    # Activity Information
    registered_actions: Optional[list] = Field(None, alias="registeredActions")
    score: Optional[int] = None
    pending_reports: Optional[int] = Field(None, alias="pendingReports")
    level: Optional[str] = None
    my_actions: Optional[list] = Field(None, alias="myActions")
    saved_actions: Optional[list] = Field(None, alias="savedActions")
    saved_content: Optional[list] = Field(None, alias="savedContent")
    achievements: Optional[list] = None

    # Additional fields
    user_id: Optional[str] = Field(None, alias="userId")
    username: Optional[str] = None
    email: Optional[str] = None
    profile_image: Optional[str] = Field(None, alias="profileImage")
    is_verified: Optional[bool] = Field(None, alias="isVerified")
    created_at: Optional[str] = Field(None, alias="createdAt")

    model_config = ConfigDict(populate_by_name=True)


class SafiranayehaClient:
    """Client for Safiranayeha API integration."""

    # API Configuration
    BASE_URL = "https://api.safiranayeha.ir/api/AI"
    LOGIN_ENDPOINT = "/AILogin"
    USER_DATA_ENDPOINT = "/GetAIUserData"

    # Credentials (from requirements)
    USERNAME = "AI"
    PASSWORD = "2025@GmAiL.com"

    # Token caching
    _token: Optional[str] = None
    _token_expiry: Optional[datetime] = None
    _token_ttl = timedelta(hours=1)  # Assume token valid for 1 hour

    def __init__(self, http_client: Optional[httpx.AsyncClient] = None):
        """
        Initialize Safiranayeha API client.

        Args:
            http_client: Optional httpx client to use (for connection pooling)
        """
        self.http_client = http_client
        self._own_client = http_client is None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(timeout=30.0)
        return self.http_client

    async def close(self):
        """Close HTTP client if we own it."""
        if self._own_client and self.http_client:
            await self.http_client.aclose()
            self.http_client = None

    def _is_token_valid(self) -> bool:
        """Check if cached token is still valid."""
        if not self._token or not self._token_expiry:
            return False
        return datetime.now() < self._token_expiry

    async def login(self, force_refresh: bool = False) -> str:
        """
        Login to Safiranayeha API and get JWT token.

        Args:
            force_refresh: Force token refresh even if cached token is valid

        Returns:
            JWT token string

        Raises:
            httpx.HTTPError: If login fails
        """
        # Return cached token if valid
        if not force_refresh and self._is_token_valid():
            logger.debug("Using cached Safiranayeha token")
            return self._token

        client = await self._get_http_client()

        # Build login URL
        url = f"{self.BASE_URL}{self.LOGIN_ENDPOINT}"
        credentials = {
            "username": self.USERNAME,
            "password": self.PASSWORD
        }

        # Try multiple approaches to handle different API configurations
        login_methods = [
            ("GET with query params", lambda: client.get(url, params=credentials)),
            ("POST with JSON body", lambda: client.post(url, json=credentials)),
            ("POST with form data", lambda: client.post(url, data=credentials)),
            ("POST with query params", lambda: client.post(url, params=credentials)),
        ]

        last_error = None
        for method_name, method_func in login_methods:
            try:
                logger.info(f"Attempting login with {method_name}: {url}")
                response = await method_func()

                # Check if successful
                if response.status_code == 200:
                    # Token is returned directly as string
                    token = response.text.strip().strip('"')  # Remove quotes if present

                    # Cache token
                    self._token = token
                    self._token_expiry = datetime.now() + self._token_ttl

                    logger.info(f"✅ Successfully logged in to Safiranayeha API using {method_name}")
                    logger.debug(f"Token: {token[:20]}...")

                    return token
                else:
                    logger.warning(f"Login attempt with {method_name} returned status {response.status_code}")
                    last_error = f"Status {response.status_code}: {response.text}"

            except httpx.HTTPStatusError as e:
                logger.warning(f"Login attempt with {method_name} failed with status error: {e.response.status_code}")
                last_error = e
                continue
            except httpx.HTTPError as e:
                logger.warning(f"Login attempt with {method_name} failed with HTTP error: {e}")
                last_error = e
                continue
            except Exception as e:
                logger.warning(f"Login attempt with {method_name} failed with unexpected error: {e}")
                last_error = e
                continue

        # All methods failed
        error_msg = f"All login methods failed. Last error: {last_error}"
        logger.error(error_msg)
        raise httpx.HTTPError(error_msg)

    async def get_user_data(self, user_id: str) -> Dict[str, Any]:
        """
        Get user data from Safiranayeha API.

        Args:
            user_id: User ID from encrypted parameter

        Returns:
            User data dictionary

        Raises:
            httpx.HTTPError: If API request fails
        """
        # Ensure we have a valid token
        token = await self.login()

        client = await self._get_http_client()

        # Build user data URL
        url = f"{self.BASE_URL}{self.USER_DATA_ENDPOINT}"
        params = {"UserId": user_id}
        headers = {"Authorization": f"Bearer {token}"}

        try:
            logger.info(f"Fetching user data for user_id={user_id}")
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()

            user_data = response.json()
            logger.info(f"Successfully fetched user data: {list(user_data.keys())}")

            return user_data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                # Token might be expired, retry with fresh token
                logger.warning("Token expired, retrying with fresh token")
                token = await self.login(force_refresh=True)
                headers = {"Authorization": f"Bearer {token}"}

                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                user_data = response.json()
                logger.info(f"Successfully fetched user data on retry")
                return user_data
            else:
                logger.error(f"Failed to fetch user data: {e}")
                raise

    async def get_user_data_typed(self, user_id: str) -> SafiranayehaUserData:
        """
        Get user data as typed model.

        Args:
            user_id: User ID from encrypted parameter

        Returns:
            SafiranayehaUserData instance

        Raises:
            httpx.HTTPError: If API request fails
        """
        data = await self.get_user_data(user_id)
        return SafiranayehaUserData(**data)

    def normalize_user_data_for_context(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize Safiranayeha user data to context manager format.

        Args:
            user_data: Raw user data from API

        Returns:
            Normalized user data for context manager

        Example:
            >>> client = SafiranayehaClient()
            >>> raw_data = await client.get_user_data("123")
            >>> normalized = client.normalize_user_data_for_context(raw_data)
            >>> # Use with context_manager.merge_context(session_id, normalized)
        """
        normalized = {}

        # Field mapping: API field -> context field
        field_mapping = {
            # Personal Information
            "phoneNumber": "user_phone",
            "phone_number": "user_phone",
            "fullName": "user_full_name",
            "full_name": "user_full_name",
            "gender": "user_gender",
            "birthMonth": "user_birth_month",
            "birth_month": "user_birth_month",
            "birthYear": "user_birth_year",
            "birth_year": "user_birth_year",

            # Residence Information
            "province": "user_province",
            "city": "user_city",

            # Activity Information
            "registeredActions": "user_registered_actions",
            "registered_actions": "user_registered_actions",
            "score": "user_score",
            "pendingReports": "user_pending_reports",
            "pending_reports": "user_pending_reports",
            "level": "user_level",
            "myActions": "user_my_actions",
            "my_actions": "user_my_actions",
            "savedActions": "user_saved_actions",
            "saved_actions": "user_saved_actions",
            "savedContent": "user_saved_content",
            "saved_content": "user_saved_content",
            "achievements": "user_achievements",

            # Additional fields
            "userId": "user_id",
            "user_id": "user_id",
            "username": "user_name",
            "email": "user_email",
        }

        for api_field, context_field in field_mapping.items():
            if api_field in user_data and user_data[api_field] is not None:
                value = user_data[api_field]
                # Wrap in standard format
                normalized[context_field] = {"value": value}

        logger.debug(f"Normalized {len(user_data)} fields to {len(normalized)} context fields")
        return normalized


# Global client instance (will be initialized on startup)
_global_client: Optional[SafiranayehaClient] = None


def get_safiranayeha_client() -> SafiranayehaClient:
    """
    Get global Safiranayeha client instance.

    Returns:
        SafiranayehaClient instance
    """
    global _global_client
    if _global_client is None:
        _global_client = SafiranayehaClient()
    return _global_client


def set_safiranayeha_client(client: SafiranayehaClient):
    """Set global Safiranayeha client instance."""
    global _global_client
    _global_client = client


# Example usage
if __name__ == "__main__":
    import asyncio

    async def test_client():
        client = SafiranayehaClient()
        try:
            # Test login
            token = await client.login()
            print(f"✅ Login successful: {token[:30]}...")

            # Test user data (replace with real user_id)
            # user_data = await client.get_user_data("test_user_id")
            # print(f"✅ User data: {user_data}")

        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            await client.close()

    asyncio.run(test_client())
