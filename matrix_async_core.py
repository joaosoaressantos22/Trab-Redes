import asyncio
import ssl
import json
import time
import urllib.parse

class BareMetalAsyncClient:
    def __init__(self, host):
        self.host = host
        self.access_token = None
        self.next_batch = None
        self.contexto_tls = ssl.create_default_context()

    async def _executar_http(self, metodo, caminho, corpo_bytes=b"", content_type="application/json", timeout_leitura=35.0, retornar_bytes=False):
        reader, writer = await asyncio.open_connection(self.host, 443, ssl=self.contexto_tls)
        
        headers = {
            "Host": self.host,
            "Connection": "close",
            "User-Agent": "BareMetal-Async/1.4"
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
            
        if corpo_bytes:
            headers["Content-Length"] = str(len(corpo_bytes))
            headers["Content-Type"] = content_type

        req = f"{metodo} {caminho} HTTP/1.1\r\n"
        for k, v in headers.items():
            req += f"{k}: {v}\r\n"
        req += "\r\n"
        
        writer.write(req.encode('utf-8') + corpo_bytes)
        await writer.drain()

        buffer = b""
        headers_texto = ""
        while True:
            while b"\r\n\r\n" not in buffer:
                try:
                    chunk = await asyncio.wait_for(reader.read(4096), timeout=timeout_leitura)
                    if not chunk: break
                    buffer += chunk
                except asyncio.TimeoutError:
                    break
            
            if b"\r\n\r\n" not in buffer:
                writer.close()
                await writer.wait_closed()
                return (None, None) if retornar_bytes else {}

            headers_bytes, resto_buffer = buffer.split(b"\r\n\r\n", 1)
            headers_texto = headers_bytes.decode('utf-8', errors='ignore')
            
            primeira_linha = headers_texto.split("\r\n")[0]
            if primeira_linha.startswith("HTTP/1.1 1"):
                buffer = resto_buffer
                continue
            else:
                buffer = resto_buffer
                break

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
                        chunk = await asyncio.wait_for(reader.read(4096), timeout=timeout_leitura)
                        if not chunk: break
                        buffer += chunk
                    except asyncio.TimeoutError:
                        break
                if not buffer or b"\r\n" not in buffer: break
                
                tamanho_hex, buffer = buffer.split(b"\r\n", 1)
                tamanho = int(tamanho_hex.decode('utf-8').strip(), 16)
                if tamanho == 0: break
                
                bytes_req = tamanho + 2 
                while len(buffer) < bytes_req:
                    try:
                        chunk = await asyncio.wait_for(reader.read(4096), timeout=timeout_leitura)
                        if not chunk: break
                        buffer += chunk
                    except asyncio.TimeoutError:
                        break
                    
                corpo_final += buffer[:tamanho]
                buffer = buffer[bytes_req:]
        else:
            while len(buffer) < content_length:
                try:
                    chunk = await asyncio.wait_for(reader.read(4096), timeout=timeout_leitura)
                    if not chunk: break
                    buffer += chunk
                except asyncio.TimeoutError:
                    break
            corpo_final = buffer[:content_length]

        writer.close()
        await writer.wait_closed()

        if retornar_bytes:
            mime_type = "application/octet-stream"
            for linha in headers_texto.split("\r\n"):
                if linha.lower().startswith("content-type:"):
                    mime_type = linha.split(":", 1)[1].strip()
            return corpo_final, mime_type

        try:
            return json.loads(corpo_final.decode('utf-8', errors='ignore'))
        except json.JSONDecodeError:
            return {}

    async def login(self, usuario, senha):
        payload = json.dumps({"type": "m.login.password", "identifier": {"type": "m.id.user", "user": usuario}, "password": senha}).encode('utf-8')
        resp = await self._executar_http("POST", "/_matrix/client/v3/login", corpo_bytes=payload)
        if "access_token" in resp:
            self.access_token = resp["access_token"]
            self.user_id = resp.get("user_id") # Armazena para identificar mensagens próprias
            return True
        return False

    async def sync(self, timeout_ms=30000):
        caminho = f"/_matrix/client/v3/sync?timeout={timeout_ms}"
        if self.next_batch:
            caminho += f"&since={self.next_batch}"
        resp = await self._executar_http("GET", caminho, timeout_leitura=(timeout_ms/1000) + 5)
        if "next_batch" in resp:
            self.next_batch = resp["next_batch"]
        return resp

    async def enviar_mensagem(self, room_id, texto):
        txn_id = str(int(time.time() * 1000))
        caminho = f"/_matrix/client/v3/rooms/{room_id}/send/m.room.message/{txn_id}"
        payload = json.dumps({"msgtype": "m.text", "body": texto}).encode('utf-8')
        return await self._executar_http("PUT", caminho, corpo_bytes=payload)

    async def upload_midia(self, dados_bytes, mime_type, filename="ficheiro"):
        filename_seguro = urllib.parse.quote(filename)
        caminho = f"/_matrix/media/v3/upload?filename={filename_seguro}"
        resp = await self._executar_http("POST", caminho, corpo_bytes=dados_bytes, content_type=mime_type)
        return resp.get("content_uri")

    async def enviar_mensagem_midia(self, room_id, mxc_uri, mime_type, filename):
        txn_id = str(int(time.time() * 1000))
        caminho = f"/_matrix/client/v3/rooms/{room_id}/send/m.room.message/{txn_id}"
        msg_type = "m.file"
        if mime_type.startswith("image/"): msg_type = "m.image"
        elif mime_type.startswith("audio/"): msg_type = "m.audio"
        elif mime_type.startswith("video/"): msg_type = "m.video"

        payload = json.dumps({
            "msgtype": msg_type,
            "body": filename,
            "url": mxc_uri,
            "info": {"mimetype": mime_type}
        }).encode('utf-8')
        return await self._executar_http("PUT", caminho, corpo_bytes=payload)

    async def baixar_midia(self, mxc_uri):
        if not mxc_uri.startswith("mxc://"): return None, None
        partes = mxc_uri[6:].split("/")
        if len(partes) != 2: return None, None
        caminho = f"/_matrix/client/v1/media/download/{partes[0]}/{partes[1]}"
        return await self._executar_http("GET", caminho, retornar_bytes=True)