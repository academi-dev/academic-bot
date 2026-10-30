"""
Almacenamiento en memoria para tokens de autenticación JWT.

Asocia cada chat_id de Telegram con su token de acceso y metadatos de usuario.
"""

from typing import Any, Dict, Optional


class AuthStorage:
    """
    Gestor de sesiones en memoria para usuarios de Telegram.
    
    Almacena tokens JWT y datos básicos del usuario autenticado mapeados por chat_id.
    """

    def __init__(self) -> None:
        """Inicializa el almacén de sesiones vacío."""
        self._tokens: Dict[int, str] = {}
        self._users: Dict[int, Dict[str, Any]] = {}

    def set_token(
        self,
        chat_id: int,
        token: str,
        user_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Almacena el token JWT y opcionalmente los datos del usuario para un chat_id.

        Args:
            chat_id: Identificador único del chat de Telegram.
            token: Token JWT de autenticación.
            user_info: Diccionario con información del usuario (nombre, email, id).
        """
        self._tokens[chat_id] = token
        if user_info is not None:
            self._users[chat_id] = user_info
        else:
            self._users.setdefault(chat_id, {})

    def get_token(self, chat_id: int) -> Optional[str]:
        """
        Obtiene el token JWT almacenado para un chat_id.

        Args:
            chat_id: Identificador del chat.

        Returns:
            El token JWT como string o None si no existe sesión activa.
        """
        return self._tokens.get(chat_id)

    def get_user_info(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """
        Obtiene los datos del usuario asociados a un chat_id.

        Args:
            chat_id: Identificador del chat.

        Returns:
            Diccionario con datos del usuario o None si no existen.
        """
        return self._users.get(chat_id)

    def is_authenticated(self, chat_id: int) -> bool:
        """
        Verifica si un chat_id cuenta con un token de sesión almacenado.

        Args:
            chat_id: Identificador del chat.

        Returns:
            True si está autenticado, False en caso contrario.
        """
        return chat_id in self._tokens and bool(self._tokens[chat_id])

    def remove_token(self, chat_id: int) -> bool:
        """
        Elimina la sesión y el token almacenados para un chat_id (logout).

        Args:
            chat_id: Identificador del chat.

        Returns:
            True si se eliminó una sesión existente, False si no existía.
        """
        token_existed = chat_id in self._tokens
        self._tokens.pop(chat_id, None)
        self._users.pop(chat_id, None)
        return token_existed

    def clear(self) -> None:
        """Limpia todas las sesiones almacenadas en memoria (útil para pruebas)."""
        self._tokens.clear()
        self._users.clear()


# Instancia singleton para uso general en manejadores
auth_storage = AuthStorage()
