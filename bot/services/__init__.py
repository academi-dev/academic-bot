"""
Paquete de servicios HTTP para Academic Bot.

Contiene los clientes para comunicarse con academic-api y academic-rag.
"""

from bot.services.api_client import (
    AcademicApiClient,
    ApiAuthError,
    ApiClientError,
    ApiConflictError,
    ApiConnectionError,
    ApiNotFoundError,
    ApiValidationError,
    api_client,
)
from bot.services.rag_client import (
    AcademicRagClient,
    RagClientError,
    RagConnectionError,
    rag_client,
)

__all__ = [
    "AcademicApiClient",
    "AcademicRagClient",
    "ApiAuthError",
    "ApiClientError",
    "ApiConflictError",
    "ApiConnectionError",
    "ApiNotFoundError",
    "ApiValidationError",
    "RagClientError",
    "RagConnectionError",
    "api_client",
    "rag_client",
]
