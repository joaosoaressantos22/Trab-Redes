import asyncio
import ssl
import json
import time
import urllib.parse
import socket
from http_parser import HttpProtocolHandler
from exceptions import MatrixConnectionError, MatrixAPIError, HTTPParsingError

class BareMetalAsyncClient:
    """
    Cliente Matrix focado na manipulação direta de sockets TCP.
    Depende estritamente do HttpProtocolHandler para bypass de bibliotecas HTTP.
    """
    def __init__(self, host_port):
        if ":" in host_port:
            self.host, porta_str = host_port.split(":", 1)
            self.port = int(porta_str)
        else:
            self.host = host_port
            self.port = 443 # Padrão HTTPS para instâncias públicas (ex: matrix.org)
            
        self.access_token = None
        self.next_batch = None
        self.user_id = None
        self.usar_tls = self.port == 443
        self.contexto_tls = ssl.create_default_context() if self.usar_tls else None

    async def _executar_http(self, metodo, caminho, corpo_bytes=b"", content_type="application/json", timeout_leitura=35.0, retornar_bytes=False):
        try:
            reader, writer = await asyncio.open_connection(self.host, self.port, ssl=self.contexto_tls)
        except (ConnectionRefusedError, socket.gaierror, asyncio.TimeoutError) as e:
            raise MatrixConnectionError(f"Falha de conexão L4 com {self.host}:{self.port} - {str(e)}")
        
        req_bytes = HttpProtocolHandler.build_request(
            method=metodo, path=caminho, host=self.host, 
            access_token=self.access_token, body_bytes=corpo_bytes, content_type=content_type
        )
        
        writer.write(req_bytes)
        await writer.drain()

        try:
            status_code, headers_texto, corpo_final = await HttpProtocolHandler.parse_response(reader, timeout_leitura)
        finally:
            writer.close()
            await writer.wait_closed()

        if status_code >= 400:
            erro_msg = "Erro desconhecido L7"
            payload_erro = {}
            if corpo_final:
                try:
                    payload_erro = json.loads(corpo_final.decode('utf-8'))
                    erro_msg = payload_erro.get("error", erro_msg)
                except json.JSONDecodeError:
                    erro_msg = corpo_final.decode('utf-8', errors='ignore')[:100]
            raise MatrixAPIError(status_code, erro_msg, payload_erro)

        if retornar_bytes:
            mime_type = "application/octet-stream"
            for linha in headers_texto.split("\r\n"):
                if linha.lower().startswith("content-type:"):
                    mime_type = linha.split(":", 1)[1].strip()
            return corpo_final, mime_type

        if not corpo_final:
            return {}

        try:
            return json.loads(corpo_final.decode('utf-8', errors='ignore'))
        except json.JSONDecodeError as e:
            raise HTTPParsingError(f"Falha ao decodificar JSON L7: {str(e)}")

    async def login(self, usuario, senha):
        payload = json.dumps({
            "type": "m.login.password", 
            "identifier": {"type": "m.id.user", "user": usuario}, 
            "password": senha
        }).encode('utf-8')
        
        resp = await self._executar_http("POST", "/_matrix/client/v3/login", corpo_bytes=payload)
        
        if "access_token" in resp:
            self.access_token = resp["access_token"]
            self.user_id = resp.get("user_id")
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

    async def criar_sala(self, nome, alias_local):
        corpo = {"preset": "public_chat", "name": nome}
        if alias_local:
            corpo["room_alias_name"] = alias_local
        payload = json.dumps(corpo).encode('utf-8')
        return await self._executar_http("POST", "/_matrix/client/v3/createRoom", corpo_bytes=payload)

    async def entrar_sala(self, room_id_or_alias):
        caminho_seguro = urllib.parse.quote(room_id_or_alias)
        return await self._executar_http("POST", f"/_matrix/client/v3/join/{caminho_seguro}")

    async def buscar_historico(self, room_id, limit=50):
        # Direção backward ('b') a partir do ponto atual conhecido da sala.
        caminho = f"/_matrix/client/v3/rooms/{room_id}/messages?dir=b&limit={limit}"
        return await self._executar_http("GET", caminho)

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
            "msgtype": msg_type, "body": filename, "url": mxc_uri, "info": {"mimetype": mime_type}
        }).encode('utf-8')
        return await self._executar_http("PUT", caminho, corpo_bytes=payload)

    async def baixar_midia(self, mxc_uri):
        if not mxc_uri.startswith("mxc://"): raise HTTPParsingError("MXC URI Inválida")
        partes = mxc_uri[6:].split("/")
        if len(partes) != 2: raise HTTPParsingError("MXC URI Malformada")
        caminho = f"/_matrix/client/v1/media/download/{partes[0]}/{partes[1]}"
        return await self._executar_http("GET", caminho, retornar_bytes=True)