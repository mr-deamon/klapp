"""API client for KLAPP."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp
import async_timeout

_LOGGER = logging.getLogger(__name__)

API_BASE_URL = "https://api.klapp.mobi"
TIMEOUT = 10


class KlappAuthError(Exception):
    """Exception raised for authentication errors."""


class KlappConnectionError(Exception):
    """Exception raised for connection errors."""


class KlappAPI:
    """KLAPP API client.

    Parameters:
        email: Account email.
        password: Account password.
        lookback_days: Number of days to look back when querying unread messages.
            This value is used to compute the `from_date` sent to the server.
            The default is defined externally (in const.py) and injected here.
    """

    def __init__(self, email: str, password: str, lookback_days: int) -> None:
        """Initialize the API client with provided lookback window."""
        self.email = email
        self.password = password
        self.lookback_days = lookback_days
        self._token: str | None = None
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def authenticate(self) -> str:
        """Authenticate with KLAPP API and return token."""
        session = await self._get_session()
        
        try:
            async with async_timeout.timeout(TIMEOUT):
                response = await session.post(
                    f"{API_BASE_URL}/v2/authenticate",
                    json={
                        "email": self.email,
                        "password": self.password,
                        "grant_type": "authenticate",
                    },
                )
                
                if response.status == 401:
                    raise KlappAuthError("Invalid credentials")
                
                if response.status != 200:
                    raise KlappConnectionError(f"HTTP {response.status}")
                
                data = await response.json()
                self._token = data.get("refresh_token")
                
                if not self._token:
                    raise KlappAuthError("No token in response")
                
                return self._token
                
        except aiohttp.ClientError as err:
            raise KlappConnectionError(f"Connection error: {err}") from err
        except TimeoutError as err:
            raise KlappConnectionError("Request timeout") from err

    async def get_unread_messages(self) -> list[dict[str, Any]]:
        """Get unread messages since a dynamic from_date based on `lookback_days`.

        The time constraint is pushed to the server using the "from_date" field
        (UTC now - `self.lookback_days`). This reduces bandwidth and avoids
        client-side filtering complexity.
        """
        if not self._token:
            await self.authenticate()
        
        session = await self._get_session()
        
        try:
            async with async_timeout.timeout(TIMEOUT):
                # Server-side time filtering: dynamic lookback in days
                from_date = (datetime.now(timezone.utc) - timedelta(days=self.lookback_days)).isoformat(timespec="seconds")

                response = await session.post(
                    f"{API_BASE_URL}/v4/messages/parent",
                    params={"include_drafts": "true"},
                    headers={
                        "accept": "application/json",
                        "authorization": f"Bearer {self._token}",
                        "user-role": "parent",
                    },
                    json={
                        "skip": 0,
                        "classes": [],
                        "active": True,
                        "archived": False,
                        "trash_bin": False,
                        "only_unread": True,
                        "only_absences": False,
                        "sent_by_me": False,
                        "sent_to_me": False,
                        "only_personal": False,
                        "only_drafts": False,
                        "only_pinned": False,
                        "query": "",
                        "from_date": from_date,
                    },
                )

                if response.status == 401:
                    # Token expired, re-authenticate
                    await self.authenticate()
                    return await self.get_unread_messages()
                
                if response.status != 200:
                    raise KlappConnectionError(f"HTTP {response.status}")
                
                messages = await response.json()

                # Fetch full details for each unread message returned by server
                detailed_messages: list[dict[str, Any]] = []
                for msg in messages:
                    msg_id = msg.get("id")
                    if not msg_id:
                        continue
                    full_message = await self.get_message_details(msg_id)
                    detailed_messages.append(full_message)

                return detailed_messages

        except aiohttp.ClientError as err:
            raise KlappConnectionError(f"Connection error: {err}") from err
        except TimeoutError as err:
            raise KlappConnectionError("Request timeout") from err

    async def get_message_details(self, message_id: str) -> dict[str, Any]:
        """Get full details of a specific message."""
        if not self._token:
            await self.authenticate()
        
        session = await self._get_session()
        
        try:
            async with async_timeout.timeout(TIMEOUT):
                response = await session.get(
                    f"{API_BASE_URL}/v4/messages/{message_id}/parent",
                    params={"include_drafts": "true"},
                    headers={
                        "accept": "application/json",
                        "authorization": f"Bearer {self._token}",
                        "user-role": "parent",
                    },
                )
                
                if response.status == 401:
                    await self.authenticate()
                    return await self.get_message_details(message_id)
                
                if response.status != 200:
                    raise KlappConnectionError(f"HTTP {response.status}")
                
                return await response.json()
                
        except aiohttp.ClientError as err:
            raise KlappConnectionError(f"Connection error: {err}") from err
        except TimeoutError as err:
            raise KlappConnectionError("Request timeout") from err

    async def mark_message_as_read(self, message_id: str) -> None:
        """Mark a message as read."""
        if not self._token:
            await self.authenticate()
        
        session = await self._get_session()
        
        try:
            async with async_timeout.timeout(TIMEOUT):
                response = await session.post(
                    f"{API_BASE_URL}/v3/messages/read-request",
                    headers={
                        "accept": "application/json",
                        "authorization": f"Bearer {self._token}",
                    },
                    json={"messages": [message_id]},
                )
                
                if response.status == 401:
                    await self.authenticate()
                    return await self.mark_message_as_read(message_id)
                
                if response.status != 200:
                    raise KlappConnectionError(f"HTTP {response.status}")
                
        except aiohttp.ClientError as err:
            raise KlappConnectionError(f"Connection error: {err}") from err
        except TimeoutError as err:
            raise KlappConnectionError("Request timeout") from err

    async def mark_messages_as_read(self, message_ids: list[str]) -> None:
        """Mark multiple messages as read in a single request.

        The API endpoint accepts a list of IDs. If the list is empty this
        returns immediately. Any auth failure will trigger re-auth and retry once.
        """
        if not message_ids:
            return
        if not self._token:
            await self.authenticate()

        session = await self._get_session()

        try:
            async with async_timeout.timeout(TIMEOUT):
                response = await session.post(
                    f"{API_BASE_URL}/v3/messages/read-request",
                    headers={
                        "accept": "application/json",
                        "authorization": f"Bearer {self._token}",
                    },
                    json={"messages": message_ids},
                )

                if response.status == 401:
                    await self.authenticate()
                    return await self.mark_messages_as_read(message_ids)

                if response.status != 200:
                    raise KlappConnectionError(f"HTTP {response.status}")

        except aiohttp.ClientError as err:
            raise KlappConnectionError(f"Connection error: {err}") from err
        except TimeoutError as err:
            raise KlappConnectionError("Request timeout") from err

    async def close(self) -> None:
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()
