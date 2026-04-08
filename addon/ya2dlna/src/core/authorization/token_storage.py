"""Хранилище токенов, передаваемых через API."""

from typing import Optional


class TokenStorage:
    """Класс для хранения токенов, переданных через API."""
    
    def __init__(self):
        self._ya_music_token: Optional[str] = None
    
    @property
    def ya_music_token(self) -> Optional[str]:
        return self._ya_music_token
    
    @ya_music_token.setter
    def ya_music_token(self, value: Optional[str]) -> None:
        self._ya_music_token = value
    
    def clear(self) -> None:
        """Очистить все токены."""
        self._ya_music_token = None


# Глобальный экземпляр хранилища токенов
token_storage = TokenStorage()