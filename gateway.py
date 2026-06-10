import asyncio
import websockets
import json
import base64
import logging
from matrix_client import BareMetalAsyncClient
from exceptions import BFFError, MatrixConnectionError, MatrixAPIError

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("GatewayBFF")

async def loop_de_sincronizacao(ws, cliente_matrix):
    primeira_sincronizacao = True
    try:
        while True:
            try:
                dados = await cliente_matrix.sync(timeout_ms=30000)
                
                if "rooms" in dados and "join" in dados["rooms"]:
                    salas_iniciais = []
                    
                    for sala_id, dados_sala in dados["rooms"]["join"].items():
                        # Extrai o nome da sala no primeiro sync para popular o menu lateral
                        if primeira_sincronizacao:
                            nome_sala = sala_id
                            estado_eventos = dados_sala.get("state", {}).get("events", [])
                            for ev in estado_eventos:
                                if ev.get("type") == "m.room.name":
                                    nome_sala = ev.get("content", {}).get("name", sala_id)
                            salas_iniciais.append({"id": sala_id, "nome": nome_sala})

                        # Processa a timeline para eventos em tempo real
                        eventos = dados_sala.get("timeline", {}).get("events", [])
                        for ev in eventos:
                            if ev.get("type") == "m.room.message" and not primeira_sincronizacao:
                                msg_type = ev["content"].get("msgtype", "")
                                remetente = ev.get("sender")
                                payload = {
                                    "tipo": "mensagem", "sala": sala_id, "remetente": remetente,
                                    "texto": ev["content"].get("body", ""), "timestamp": ev.get("origin_server_ts", 0),
                                    "propria": remetente == cliente_matrix.user_id
                                }
                                if msg_type in ["m.image", "m.audio", "m.video", "m.file"]:
                                    payload["url"] = ev["content"].get("url", "")
                                await ws.send(json.dumps(payload))
                                
                    if primeira_sincronizacao:
                        await ws.send(json.dumps({"tipo": "salas_iniciais", "salas": salas_iniciais}))
                        
                primeira_sincronizacao = False
            except MatrixAPIError as e:
                logger.error(f"Erro L7 no Sync: {e}")
                await asyncio.sleep(5)
            except MatrixConnectionError as e:
                logger.error(f"Erro de Conexão L4 no Sync: {e}")
                await ws.send(json.dumps({"tipo": "erro", "mensagem": "Conexão L4 com Homeserver perdida."}))
                break
    except asyncio.CancelledError:
        logger.info("Loop de sincronização cancelado.")

def formatar_evento_mensagem(ev, user_id):
    msg_type = ev["content"].get("msgtype", "")
    remetente = ev.get("sender")
    return {
        "remetente": remetente,
        "texto": ev["content"].get("body", ""),
        "timestamp": ev.get("origin_server_ts", 0),
        "propria": remetente == user_id,
        "url": ev["content"].get("url", "") if msg_type in ["m.image", "m.audio", "m.video", "m.file"] else ""
    }

async def roteador_ws(ws):
    cliente = None
    task_sync = None
    addr = ws.remote_address
    logger.info(f"Nova conexão WebSocket de {addr}")
    
    try:
        async for msg_str in ws:
            comando = json.loads(msg_str)
            acao = comando.get("acao")

            try:
                if acao == "login":
                    hs_target = comando.get("homeserver", "localhost:8008")
                    cliente = BareMetalAsyncClient(hs_target)
                    sucesso = await cliente.login(comando["usuario"], comando["senha"])
                    await ws.send(json.dumps({
                        "tipo": "status", "sucesso": sucesso, "user_id": cliente.user_id if sucesso else None,
                        "mensagem": "Autenticado com sucesso" if sucesso else "Credenciais recusadas."
                    }))
                    if sucesso:
                        if task_sync: task_sync.cancel()
                        task_sync = asyncio.create_task(loop_de_sincronizacao(ws, cliente))
                
                elif acao == "criar_sala" and cliente:
                    resp = await cliente.criar_sala(comando.get("nome"), comando.get("alias"))
                    await ws.send(json.dumps({"tipo": "sala_criada", "room_id": resp.get("room_id")}))
                    
                elif acao == "entrar_sala" and cliente:
                    resp = await cliente.entrar_sala(comando.get("referencia"))
                    await ws.send(json.dumps({"tipo": "sala_entrou", "room_id": resp.get("room_id")}))
                    
                elif acao == "buscar_historico" and cliente:
                    sala_id = comando.get("sala")
                    resp = await cliente.buscar_historico(sala_id)
                    eventos_brutos = resp.get("chunk", [])
                    mensagens = [formatar_evento_mensagem(ev, cliente.user_id) for ev in reversed(eventos_brutos) if ev.get("type") == "m.room.message"]
                    await ws.send(json.dumps({"tipo": "historico", "sala": sala_id, "mensagens": mensagens}))

                elif acao == "enviar" and cliente and cliente.access_token:
                    await cliente.enviar_mensagem(comando["sala"], comando["texto"])
                        
                elif acao == "enviar_midia" and cliente and cliente.access_token:
                    dados_bytes = base64.b64decode(comando["base64"])
                    mxc_uri = await cliente.upload_midia(dados_bytes, comando["mime_type"], comando["nome_arquivo"])
                    if mxc_uri:
                        await cliente.enviar_mensagem_midia(comando["sala"], mxc_uri, comando["mime_type"], comando["nome_arquivo"])
                        await ws.send(json.dumps({"tipo": "status_midia", "sucesso": True, "mensagem": "Ficheiro despachado"}))
                    else:
                        raise BFFError("Servidor Matrix não retornou MXC URI.")
                            
                elif acao == "baixar_midia" and cliente and cliente.access_token:
                    mxc = comando.get("mxc")
                    dados_bytes, mime_type = await cliente.baixar_midia(mxc)
                    if dados_bytes and mime_type:
                        b64 = base64.b64encode(dados_bytes).decode('utf-8')
                        await ws.send(json.dumps({"tipo": "midia_baixada", "mxc": mxc, "mime_type": mime_type, "base64": b64}))

            except BFFError as e:
                logger.warning(f"BFF Exception: {str(e)}")
                await ws.send(json.dumps({"tipo": "erro", "mensagem": str(e)}))
            except Exception as e:
                logger.error(f"Erro Crítico não tratado: {str(e)}")
                await ws.send(json.dumps({"tipo": "erro", "mensagem": "Erro interno no Gateway L7."}))

    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Conexão WebSocket fechada: {addr}")
    finally:
        if task_sync: task_sync.cancel()

async def main():
    porta = 8765
    logger.info(f"Gateway L4/L7 operando na porta {porta}...")
    async with websockets.serve(roteador_ws, "0.0.0.0", porta, max_size=52428800):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())