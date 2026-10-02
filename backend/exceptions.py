"""Excepciones de dominio y de integraciones externas."""


class BackendError(Exception):
    """Error base controlado por la API."""


class ConfigurationError(BackendError):
    """Falta una configuracion requerida."""


class BanxicoError(BackendError):
    """Error al consultar o validar una respuesta de Banxico."""


class MongoDBError(BackendError):
    """Error al consultar o escribir en MongoDB."""
