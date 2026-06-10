import asyncio
from exceptions import HTTPParsingError, MatrixConnectionError

class HttpProtocolHandler:
    @staticmethod
    def build_request(method, path, host, access_token=None, body_bytes=b"", content_type="application/json"):
        headers = {
            "Host": host,
            "Connection": "close",
            "User-Agent": "BareMetal-Async-Matrix/3.0"
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
            
        if body_bytes:
            headers["Content-Length"] = str(len(body_bytes))
            headers["Content-Type"] = content_type

        req = f"{method} {path} HTTP/1.1\r\n"
        for k, v in headers.items():
            req += f"{k}: {v}\r\n"
        req += "\r\n"
        
        return req.encode('utf-8') + body_bytes

    @staticmethod
    async def parse_response(reader, timeout=35.0):
        buffer = b""
        headers_texto = ""
        
        while True:
            while b"\r\n\r\n" not in buffer:
                try:
                    chunk = await asyncio.wait_for(reader.read(4096), timeout=timeout)
                    if not chunk:
                        raise HTTPParsingError("Conexão TCP fechada prematuramente antes do limite dos headers.")
                    buffer += chunk
                except asyncio.TimeoutError:
                    raise MatrixConnectionError("Timeout na leitura L4 (Headers).")
            
            headers_bytes, resto_buffer = buffer.split(b"\r\n\r\n", 1)
            headers_texto = headers_bytes.decode('utf-8', errors='ignore')
            
            primeira_linha = headers_texto.split("\r\n")[0]
            if primeira_linha.startswith("HTTP/1.1 1"):
                buffer = resto_buffer
                continue
            else:
                buffer = resto_buffer
                break

        try:
            status_code = int(primeira_linha.split(" ")[1])
        except IndexError:
            raise HTTPParsingError(f"Falha ao extrair status code da linha: {primeira_linha}")

        content_length = 0
        is_chunked = False
        
        for linha in headers_texto.split("\r\n"):
            l_lower = linha.lower()
            if l_lower.startswith("content-length:"):
                content_length = int(l_lower.split(":")[1].strip())
            elif l_lower.startswith("transfer-encoding:") and "chunked" in l_lower:
                is_chunked = True

        corpo_final = b""
        
        if is_chunked:
            while True:
                while b"\r\n" not in buffer:
                    try:
                        chunk = await asyncio.wait_for(reader.read(4096), timeout=timeout)
                        if not chunk: raise HTTPParsingError("EOF durante leitura de Chunked Transfer.")
                        buffer += chunk
                    except asyncio.TimeoutError:
                        raise MatrixConnectionError("Timeout na leitura L4 (Chunked Payload).")
                
                tamanho_hex, buffer = buffer.split(b"\r\n", 1)
                tamanho_str = tamanho_hex.decode('utf-8').strip()
                if not tamanho_str: continue
                
                try:
                    tamanho = int(tamanho_str, 16)
                except ValueError:
                    raise HTTPParsingError(f"Tamanho de chunk inválido: {tamanho_str}")
                    
                if tamanho == 0: break
                
                bytes_req = tamanho + 2 
                while len(buffer) < bytes_req:
                    try:
                        chunk = await asyncio.wait_for(reader.read(4096), timeout=timeout)
                        if not chunk: raise HTTPParsingError("EOF durante corpo do Chunk.")
                        buffer += chunk
                    except asyncio.TimeoutError:
                        raise MatrixConnectionError("Timeout na leitura L4 (Chunked Body).")
                    
                corpo_final += buffer[:tamanho]
                buffer = buffer[bytes_req:]
        else:
            while len(buffer) < content_length:
                try:
                    chunk = await asyncio.wait_for(reader.read(4096), timeout=timeout)
                    if not chunk: raise HTTPParsingError("EOF antes de atingir Content-Length.")
                    buffer += chunk
                except asyncio.TimeoutError:
                    raise MatrixConnectionError("Timeout na leitura L4 (Content-Length).")
            corpo_final = buffer[:content_length]

        return status_code, headers_texto, corpo_final