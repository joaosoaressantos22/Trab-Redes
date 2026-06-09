import asyncio
import websockets
import json
import base64
from matrix_async_core import BareMetalAsyncClient

HOMESERVER = "matrix-client.matrix.org"

async def loop_de_sincronizacao(ws, cliente_matrix):
    primeira_sincronizacao = True
    try:
        while True:
            dados = await cliente_matrix.sync(timeout_ms=30000)
            if "rooms" in dados and "join" in dados["rooms"]:
                for sala_id, dados_sala in dados["rooms"]["join"].items():
                    eventos = dados_sala.get("timeline", {}).get("events", [])
                    for ev in eventos:
                        if ev.get("type") == "m.room.message":
                            if primeira_sincronizacao:
                                continue
                                
                            msg_type = ev["content"].get("msgtype", "")
                            remetente = ev.get("sender")
                            
                            payload = {
                                "tipo": "mensagem",
                                "sala": sala_id,
                                "remetente": remetente,
                                "texto": ev["content"].get("body", ""),
                                "timestamp": ev.get("origin_server_ts", 0),
                                "propria": remetente == cliente_matrix.user_id
                            }
                            
                            if msg_type in ["m.image", "m.audio", "m.video", "m.file"]:
                                payload["url"] = ev["content"].get("url", "")
                                
                            await ws.send(json.dumps(payload))
                            
            primeira_sincronizacao = False
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"[Erro L4/L7 no Sync] {e}")

async def roteador_ws(ws):
    cliente = BareMetalAsyncClient(HOMESERVER)
    task_sync = None
    
    try:
        async for msg_str in ws:
            comando = json.loads(msg_str)
            acao = comando.get("acao")

            if acao == "login":
                sucesso = await cliente.login(comando["usuario"], comando["senha"])
                await ws.send(json.dumps({
                    "tipo": "status", 
                    "sucesso": sucesso, 
                    "user_id": cliente.user_id if sucesso else None
                }))
                if sucesso:
                    task_sync = asyncio.create_task(loop_de_sincronizacao(ws, cliente))
            
            elif acao == "enviar":
                if cliente.access_token:
                    await cliente.enviar_mensagem(comando["sala"], comando["texto"])
                    
            elif acao == "enviar_midia":
                if cliente.access_token:
                    try:
                        dados_bytes = base64.b64decode(comando["base64"])
                        mxc_uri = await cliente.upload_midia(dados_bytes, comando["mime_type"], comando["nome_arquivo"])
                        if mxc_uri:
                            await cliente.enviar_mensagem_midia(comando["sala"], mxc_uri, comando["mime_type"], comando["nome_arquivo"])
                            await ws.send(json.dumps({"tipo": "status_midia", "sucesso": True, "mensagem": "Ficheiro enviado"}))
                        else:
                            await ws.send(json.dumps({"tipo": "status_midia", "sucesso": False, "mensagem": "Falha no servidor Matrix"}))
                    except Exception as e:
                        await ws.send(json.dumps({"tipo": "status_midia", "sucesso": False, "mensagem": str(e)}))
                        
            elif acao == "baixar_midia":
                if cliente.access_token:
                    try:
                        mxc = comando.get("mxc")
                        dados_bytes, mime_type = await cliente.baixar_midia(mxc)
                        if dados_bytes and mime_type and not mime_type.startswith("application/json"):
                            b64 = base64.b64encode(dados_bytes).decode('utf-8')
                            await ws.send(json.dumps({
                                "tipo": "midia_baixada",
                                "mxc": mxc,
                                "mime_type": mime_type,
                                "base64": b64
                            }))
                    except Exception as e:
                        print(f"[Gateway] Falha no stream L7: {e}")

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if task_sync: task_sync.cancel()

async def main():
    print("[Gateway] Inicializando socket assíncrono na porta 8765...")
    async with websockets.serve(roteador_ws, "localhost", 8765, max_size=52428800):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())