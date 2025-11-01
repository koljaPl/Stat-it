import asyncio
import os
import re
from typing import Dict, Any, Optional

from telethon import TelegramClient
from telethon.tl.functions.users import GetFullUserRequest
from telethon.errors import (
    UsernameNotOccupiedError,
    PhoneNumberInvalidError,
    UserIdInvalidError,
    PeerIdInvalidError,
    UsernameNotModifiedError
)
from telethon.tl.types import User


class TelegramUserFetcher:
    """
    Asynchronous Telegram User Information Fetcher using Telethon (Client API).

    This class provides a secure, optimized way to retrieve comprehensive user
    information from Telegram by username, user ID, or phone number.

    Features:
    - Supports '@username', 'username', user_id (str/int), phone ('+123...', '123...').
    - Automatic normalization and resolution fallback (username -> phone -> ID).
    - Full user profile including bio, status, premium status, photos.
    - Async context manager for easy resource management.
    - Comprehensive error handling with detailed messages.
    - Persistent session for performance (no re-auth each time).

    Setup:
    1. Get API_ID and API_HASH: https://my.telegram.org
    2. Set env vars: TELEGRAM_API_ID=..., TELEGRAM_API_HASH=...
    3. pip install telethon

    Usage:
        async def main():
            async with TelegramUserFetcher() as fetcher:
                info = await fetcher.get_user_info('@durov')
                print(info['first_name'])  # 'Pavel'

        asyncio.run(main())
    """

    def __init__(
        self,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        session_name: str = 'tg_user_fetcher'
    ):
        """
        Initialize the fetcher.

        Args:
            api_id (int, optional): Telegram API ID. Defaults to TELEGRAM_API_ID env.
            api_hash (str, optional): Telegram API Hash. Defaults to TELEGRAM_API_HASH env.
            session_name (str): Session file name for persistent auth.
        """
        self.api_id = api_id or int(os.getenv('TELEGRAM_API_ID', 0))
        self.api_hash = api_hash or os.getenv('TELEGRAM_API_HASH', '')
        if not self.api_id or not self.api_hash:
            raise ValueError('API_ID and API_HASH must be provided via args or env vars.')

        self.session_name = session_name
        self.client: Optional[TelegramClient] = None

    async def __aenter__(self):
        """Async context manager entry: start client."""
        await self._ensure_started()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit: stop client."""
        await self._stop()

    async def _ensure_started(self):
        """Ensure client is started (idempotent)."""
        if self.client is None:
            self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
            await self.client.start()
        elif not self.client.is_connected():
            await self.client.connect()
            if not self.client.is_user_authorized():
                await self.client.start()

    async def _stop(self):
        """Safely disconnect client."""
        if self.client and self.client.is_connected():
            await self.client.disconnect()

    async def get_user_info(self, identifier: str) -> Dict[str, Any]:
        """
        Fetch comprehensive user information.

        Automatically tries:
        1. Username ('@user' or 'user')
        2. Phone number
        3. User ID

        Returns dict with all available fields or {'error': True, 'message': str}.

        Args:
            identifier (str): User identifier.

        Returns:
            Dict[str, Any]: User info.

        Raises:
            ValueError: If identifier is empty/invalid after normalization.
        """
        try:
            await self._ensure_started()

            norm_identifier = self._normalize_identifier(identifier)
            entity = await self._resolve_entity(norm_identifier)

            full_response = await self.client(GetFullUserRequest(id=entity))
            full_user = full_response.full_user

            return self._format_user_info(entity, full_user)

        except Exception as e:
            return {
                'error': True,
                'message': f'Failed to fetch user info for "{identifier}": {str(e)}',
                'identifier': identifier
            } finally:
            # No stop here, let context manager handle

    def _normalize_identifier(self, identifier: str) -> str:
        """Normalize: strip spaces, lowercase, remove extra."""
        if not identifier:
            raise ValueError('Identifier cannot be empty')
        # Remove spaces, lowercase
        norm = re.sub(r'\s+', '', identifier.lower())
        # Remove leading @ or + if present (but preserve for phone/ID detection)
        return norm

    async def _resolve_entity(self, identifier: str) -> User:
        """Resolve entity with fallback strategies."""
        errors = []

        # 1. Try as username (@user or user)
        try:
            return await self.client.get_entity(identifier)
        except (UsernameNotOccupiedError, UsernameNotModifiedError) as e:
            errors.append(f'Username failed: {e}')
        except Exception as e:
            if 'USERNAME_NOT_OCCUPIED' in str(e):
                pass  # Expected
            else:
                errors.append(f'Username error: {e}')

        # 2. Extract digits and try as phone
        phone_digits = re.sub(r'[^\d]', '', identifier)
        if len(phone_digits) >= 10:
            phone = '+' + phone_digits
            try:
                return await self.client.get_entity(phone)
            except (PhoneNumberInvalidError, PeerIdInvalidError) as e:
                errors.append(f'Phone failed: {e}')
            except Exception as e:
                errors.append(f'Phone error: {e}')

        # 3. Try as user ID (pure digits)
        if re.match(r'^\d+$', identifier):
            try:
                uid = int(identifier)
                return await self.client.get_entity(uid)
            except (UserIdInvalidError, ValueError) as e:
                errors.append(f'ID failed: {e}')
            except Exception as e:
                errors.append(f'ID error: {e}')

        raise ValueError(f'Cannot resolve "{identifier}". Tried: {"; ".join(errors)}')

    @staticmethod
    def _format_user_info(user: User, full_user: Any) -> Dict[str, Any]:
        """Format entity + full_user into clean dict."""
        info: Dict[str, Any] = {
            'id': user.id,
            'access_hash': user.access_hash,
            'first_name': user.first_name or None,
            'last_name': user.last_name or None,
            'username': user.username,
            'phone': getattr(user, 'phone', None),
            'is_bot': user.bot,
            'is_premium': getattr(user, 'premium', False),
            'is_verified': user.verified,
            'is_scam': getattr(user, 'scam', False),
            'status': str(user.status) if hasattr(user.status, '__str__') else None,
            'about': getattr(full_user, 'about', None),
            'profile_photos_count': len(full_user.profile_photos) if full_user.profile_photos else 0,
            'has_video_profile_photo': getattr(full_user, 'has_presentation', False),  # Approx
        }

        # Photo info (first photo details)
        if full_user.profile_photos:
            photo = full_user.profile_photos[0]
            info['profile_photo'] = {
                'id': photo.id,
                'dc_id': photo.dc_id,
                'has_stickers': photo.has_stickers,
                'sizes': [{'w': s.w, 'h': s.h, 'type': s.type} for s in photo.sizes]
            }

        return info