class BFFError(Exception):
    """Exceção base para o ecossistema BFF."""
    pass

class HTTPParsingError(BFFError):
    """Erro no parsing do protocolo L7 (HTTP/1.1)."""
    pass

class MatrixConnectionError(BFFError):
    """Erro na camada de transporte L4 (Socket TCP/TLS)."""
    pass

class MatrixAPIError(BFFError):
    """Erro retornado pela API do Homeserver Matrix (HTTP >= 400)."""
    def __init__(self, status_code, message, payload=None):
        self.status_code = status_code
        self.payload = payload or {}
        super().__init__(f"Matrix API Error {status_code}: {message}")