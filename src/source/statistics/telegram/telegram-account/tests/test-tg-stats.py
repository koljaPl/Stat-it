import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from telethon.tl.types import User, UserStatusOnline, Photo
from stat-telegram-account import TelegramUserFetcher  # Замени на import

@pytest.mark.asyncio
class TestTelegramUserFetcher:
    @pytest.fixture
    def fetcher(self):
        fetcher = TelegramUserFetcher(api_id=123, api_hash='hash')
        fetcher.client = AsyncMock()
        fetcher._ensure_started = AsyncMock()
        return fetcher

    @pytest.mark.parametrize('identifier,expected_type', [
        ('@durov', 'username'),
        ('durov', 'username'),
        ('+1234567890', 'phone'),
        ('1234567890', 'phone'),
        ('123456789', 'id'),
    ])
    async def test_normalize_identifier(self, fetcher, identifier, expected_type):
        norm = fetcher._normalize_identifier(identifier)
        assert isinstance(norm, str)
        assert len(norm) > 0

    @patch.object(TelegramUserFetcher, '_ensure_started')
    @patch('telethon.TelegramClient.get_entity', new_callable=AsyncMock)
    async def test_get_user_info_success_username(self, mock_get_entity, mock_start, fetcher):
        # Mock user
        mock_user = MagicMock(spec=User)
        mock_user.id = 123
        mock_user.first_name = 'Test'
        mock_get_entity.return_value = mock_user

        mock_full = MagicMock()
        mock_full.full_user = MagicMock(about='Bio')
        with patch.object(fetcher.client, 'GetFullUserRequest') as mock_full_call:
            mock_full_call.return_value = AsyncMock(return_value=mock_full)

            info = await fetcher.get_user_info('@testuser')

        assert not info['error']
        assert info['id'] == 123
        assert info['first_name'] == 'Test'

    @patch.object(TelegramUserFetcher, '_ensure_started')
    async def test_get_user_info_error(self, mock_start, fetcher):
        with patch.object(fetcher.client, 'get_entity') as mock_get:
            mock_get.side_effect = Exception('Not found')

            info = await fetcher.get_user_info('invalid')

        assert info['error'] is True
        assert 'invalid' in info['message']

# Запуск: pytest test-tg-stats.py -v