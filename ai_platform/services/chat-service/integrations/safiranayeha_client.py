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
    BASE_URL = "https://api.safiranayeha.ir"
    LOGIN_ENDPOINT = "/api/AI/AILogin"
    USER_DATA_ENDPOINT = "/api/AI/GetAIUserData"
    ACTION_DETAILS_ENDPOINT = "/api/Home/GetOneAction"
    ACTION_LIST_ENDPOINT = "/api/Action/GetActionList"
    MY_ACTIONS_ENDPOINT = "/api/Profile/GetMyActions"
    CONTENT_LIST_ENDPOINT = "/api/Contents/GetContentList"

    # Credentials (from requirements)
    USERNAME = "AI"
    PASSWORD = "2025@GmAiL.com"

    # Token caching
    _token: Optional[str] = None
    _token_expiry: Optional[datetime] = None
    _token_ttl = timedelta(hours=1)  # Assume token valid for 1 hour
    
    # Manual token override (for testing or when provided by user)
    _manual_token: Optional[str] = None

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

    def set_manual_token(self, token: str):
        """
        Set a manual token (bypasses login).
        
        Args:
            token: JWT token string
        """
        self._manual_token = token
        logger.info("Manual token set for Safiran API client")
    
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
        # Return manual token if set
        if self._manual_token:
            logger.debug("Using manual Safiranayeha token")
            return self._manual_token
        
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

        # Swagger specifies PATCH method for AILogin.
        # Official doc mentions POST, but API actually uses PATCH.
        # Try multiple methods for maximum compatibility.
        login_methods = [
            ("PATCH with query params", lambda: client.patch(url, params=credentials)),
            ("POST with query params", lambda: client.post(url, params=credentials)),
            ("POST with JSON body", lambda: client.post(url, json=credentials)),
            ("GET with query params", lambda: client.get(url, params=credentials)),
        ]

        last_error = None
        for method_name, method_func in login_methods:
            try:
                logger.info(f"Attempting login with {method_name}: {url}")
                response = await method_func()

                # Check if successful
                if response.status_code == 200:
                    # Response format: {"data":null,"isSuccess":true,"message":"jwt_token"}
                    try:
                        response_data = response.json()
                        if isinstance(response_data, dict) and "message" in response_data:
                            token = response_data["message"]
                        else:
                            token = response.text.strip().strip('"')
                    except:
                        token = response.text.strip().strip('"')

                    # Cache token
                    self._token = token
                    self._token_expiry = datetime.now() + self._token_ttl

                    logger.info(f"✅ Successfully logged in to Safiranayeha API using {method_name}")
                    logger.debug(f"Token: {token[:30]}...")

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

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        require_auth: bool = True,
    ) -> Dict[str, Any]:
        """
        Send request to Safiran API with optional bearer auth.
        Retries once on 401 with force-refreshed token.
        """
        client = await self._get_http_client()
        url = f"{self.BASE_URL}{endpoint}"
        headers: Dict[str, str] = {}

        if require_auth:
            token = await self.login()
            headers["Authorization"] = f"Bearer {token}"

        response = await client.request(
            method.upper(),
            url,
            params=params,
            json=json_data,
            headers=headers,
        )
        if response.status_code == 401 and require_auth:
            token = await self.login(force_refresh=True)
            headers["Authorization"] = f"Bearer {token}"
            response = await client.request(
                method.upper(),
                url,
                params=params,
                json=json_data,
                headers=headers,
            )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.warning(
                "Safiranayeha API error: %s %s -> %s body=%s",
                method, url, e.response.status_code,
                (e.response.text or "")[:500],
            )
            raise
        if not response.text:
            return {}
        try:
            return response.json()
        except Exception:
            return {"raw": response.text}

    async def get_user_data(self, user_id: str) -> Dict[str, Any]:
        """
        Get user data from Safiranayeha API (GET /api/AI/GetAIUserData).

        Args:
            user_id: User ID from encrypted parameter

        Returns:
            User data dictionary (inner "data" object when API returns { data, isSuccess, message, statusCode })

        Raises:
            httpx.HTTPError: If API request fails
        """
        try:
            logger.info(f"Fetching user data for user_id={user_id}")
            raw = await self._request(
                method="GET",
                endpoint=self.USER_DATA_ENDPOINT,
                params={"UserId": user_id},
                require_auth=True,
            )
            # API returns { data: { fullName, province, ... }, isSuccess, message, statusCode }
            user_data = raw.get("data", raw) if isinstance(raw, dict) else raw
            if isinstance(user_data, dict):
                # Normalize API typos for consistent context keys
                if "mounthOfBirth" in user_data and "birthMonth" not in user_data:
                    user_data["birthMonth"] = user_data["mounthOfBirth"]
                if "reseredActionCount" in user_data and "registeredActionCount" not in user_data:
                    user_data["registeredActionCount"] = user_data["reseredActionCount"]
            logger.info(f"Successfully fetched user data: {list(user_data.keys()) if isinstance(user_data, dict) else 'n/a'}")
            return user_data if isinstance(user_data, dict) else {}
        except Exception as e:
            logger.warning("Safiranayeha GetAIUserData failed for user_id=%s: %s", user_id, e, exc_info=False)
            return {}

    async def get_action_details(self, action_id: int) -> Dict[str, Any]:
        """Get action details by id from Home/GetOneAction."""
        try:
            return await self._request(
                method="GET",
                endpoint=self.ACTION_DETAILS_ENDPOINT,
                params={"id": action_id},
                require_auth=True,
            )
        except Exception as e:
            logger.warning(f"Failed to fetch action details for id={action_id}: {e}")
            return {}

    async def get_action_list(self, **filters: Any) -> Dict[str, Any]:
        """Get filtered action list from Action/GetActionList."""
        params = {k: v for k, v in filters.items() if v is not None}
        try:
            return await self._request(
                method="GET",
                endpoint=self.ACTION_LIST_ENDPOINT,
                params=params,
                require_auth=True,
            )
        except Exception as e:
            logger.warning(f"Failed to fetch action list: {e}")
            return {}

    async def get_my_actions(self, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Get current user's actions from Profile/GetMyActions."""
        try:
            return await self._request(
                method="GET",
                endpoint=self.MY_ACTIONS_ENDPOINT,
                params={"PageNumber": page, "PageSize": page_size},
                require_auth=True,
            )
        except Exception as e:
            logger.warning(f"Failed to fetch my actions: {e}")
            return {}

    async def get_content_list(self, **filters: Any) -> Dict[str, Any]:
        """Get filtered content list from Contents/GetContentList."""
        params = {k: v for k, v in filters.items() if v is not None}
        try:
            return await self._request(
                method="GET",
                endpoint=self.CONTENT_LIST_ENDPOINT,
                params=params,
                require_auth=True,
            )
        except Exception as e:
            logger.warning(f"Failed to fetch content list: {e}")
            return {}

    async def get_user_data_typed(self, user_id: str) -> Optional[SafiranayehaUserData]:
        """
        Get user data as typed model. Returns None if the API call fails.
        """
        try:
            data = await self.get_user_data(user_id)
            return SafiranayehaUserData(**data) if data else None
        except Exception as e:
            logger.warning("get_user_data_typed failed for user_id=%s: %s", user_id, e)
            return None

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

        # Field mapping: API field -> context field (includes GetAIUserData response shape)
        field_mapping = {
            # Personal Information
            "phoneNumber": "user_phone",
            "phone_number": "user_phone",
            "fullName": "user_full_name",
            "full_name": "user_full_name",
            "gender": "user_gender",
            "birthMonth": "user_birth_month",
            "birth_month": "user_birth_month",
            "mounthOfBirth": "user_birth_month",
            "birthYear": "user_birth_year",
            "birth_year": "user_birth_year",
            "yearOfBirth": "user_birth_year",

            # Residence Information
            "province": "user_province",
            "city": "user_city",

            # Activity Information (GetAIUserData: doneActionCount, score, reseredActionCount, level)
            "registeredActions": "user_registered_actions",
            "registered_actions": "user_registered_actions",
            "reseredActionCount": "user_registered_action_count",
            "registeredActionCount": "user_registered_action_count",
            "doneActionCount": "user_done_action_count",
            "done_action_count": "user_done_action_count",
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
