"""Хранилище токенов, передаваемых через API."""

from typing import Optional


class TokenStorage:
    """Класс для хранения токенов, переданных через API."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._x_token: Optional[str] = None
            cls._instance._cookie: Optional[str] = None
            cls._instance._ya_music_token: Optional[str] = None
        return cls._instance
    
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


token_storage = TokenStorage()