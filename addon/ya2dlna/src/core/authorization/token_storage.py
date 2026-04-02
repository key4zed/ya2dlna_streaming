"""Хранилище токенов, передаваемых через API."""

from typing import Optional


class TokenStorage:
    """Класс для хранения токенов, переданных через API."""
    
    def __init__(self):
        self._x_token: Optional[str] = None
        self._cookie: Optional[str] = None
        self._ya_music_token: Optional[str] = None
    
    @property
    def x_token(self) -> Optional[str]:
        return self._x_token
    
    @x_token.setter
    def x_token(self, value: Optional[str]) -> None:
        self._x_token = value
    
    @property
    def cookie(self) -> Optional[str]:
        return self._cookie
    
    @cookie.setter
    def cookie(self, value: Optional[str]) -> None:
        self._cookie = value
    
    @property
    def ya_music_token(self) -> Optional[str]:
        return self._ya_music_token
    
    @ya_music_token.setter
    def ya_music_token(self, value: Optional[str]) -> None:
        self._ya_music_token = value
    
    def clear(self) -> None:
        """Очистить все токены."""
        self._x_token = None
        self._cookie = None
        self._ya_music_token = None


# Глобальный экземпляр хранилища токенов
token_storage = TokenStorage()