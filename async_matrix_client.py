import json
import time
from async_network import criar_conexao_segura_async, enviar_requisicao_async, receber_resposta_async

class AsyncMatrixClient:
    def __init__(self, homeserver_url):
        self.host = homeserver_url
        self.access_token = None
        self.next_batch = None

    async def _executar_chamada(self, metodo, caminho, payload_dict=None):
        reader, writer = await criar_conexao_segura_async(self.host)
        
        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
            
        corpo_str = json.dumps(payload_dict) if payload_dict else None
        
        await enviar_requisicao_async(writer, self.host, metodo, caminho, corpo_str, headers)
        headers_resp, corpo_resp = await receber_resposta_async(reader)
        
        writer.close()
        await writer.wait_closed()
        
        if corpo_resp:
            try:
                return json.loads(corpo_resp)
            except json.JSONDecodeError:
                return {}
        return {}

    async def sync(self, timeout_ms=30000):
        caminho = f"/_matrix/client/v3/sync?timeout={timeout_ms}"
        if self.next_batch:
            caminho += f"&since={self.next_batch}"

        resposta = await self._executar_chamada("GET", caminho)
        if "next_batch" in resposta:
            self.next_batch = resposta["next_batch"]
        return resposta