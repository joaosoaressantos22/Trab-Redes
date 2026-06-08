import json
import time
from network import criar_conexao_segura
from http_parser import enviar_requisicao, receber_resposta

class MatrixClient:
    def __init__(self, homeserver_url):
        # Ex: "matrix.org" (sem https://)
        self.host = homeserver_url
        self.access_token = None
        self.next_batch = None

    def _executar_chamada(self, metodo, caminho, payload_dict=None):
        """Abre o socket, envia a requisição HTTP construída na mão, recebe e fecha."""
        sock = criar_conexao_segura(self.host)
        
        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
            
        corpo_str = json.dumps(payload_dict) if payload_dict else None
        
        enviar_requisicao(sock, self.host, metodo, caminho, corpo_str, headers)
        headers_resp, corpo_resp = receber_resposta(sock)
        
        sock.close() # Implementação bare-metal focada em Connection: close
        
        if corpo_resp:
            try:
                return json.loads(corpo_resp)
            except json.JSONDecodeError:
                return {}
        return {}

    def login(self, usuario, senha):
        payload = {
            "type": "m.login.password",
            "identifier": {"type": "m.id.user", "user": usuario},
            "password": senha
        }
        resposta = self._executar_chamada("POST", "/_matrix/client/v3/login", payload)
        
        # LINHA ADICIONADA PARA DEBUG DE REDE
        print(f"[Debug L7] Resposta do Servidor: {resposta}")
        
        if "access_token" in resposta:
            self.access_token = resposta["access_token"]
            return True
        return False

    def sync(self, timeout_ms=30000):
        caminho = f"/_matrix/client/v3/sync?timeout={timeout_ms}"
        if self.next_batch:
            caminho += f"&since={self.next_batch}"

        resposta = self._executar_chamada("GET", caminho)
        
        if "next_batch" in resposta:
            self.next_batch = resposta["next_batch"]
            
        return resposta

    def enviar_mensagem(self, room_id, texto):
        # TxnId precisa ser único para cada mensagem enviada
        txn_id = str(int(time.time() * 1000))
        caminho = f"/_matrix/client/v3/rooms/{room_id}/send/m.room.message/{txn_id}"
        
        payload = {
            "msgtype": "m.text",
            "body": texto
        }
        return self._executar_chamada("PUT", caminho, payload)