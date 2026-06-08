import threading
import time
from async_matrix_client import MatrixClient

# Configurações do Usuário (Altere para os seus dados de teste)
HOMESERVER = "matrix-client.matrix.org"
USUARIO = "redes2026" # Ex: username (sem o @ e sem o :matrix.org)
SENHA = "@Redes2026@@"
SALA_ID = "!iHZGVNZVKCbAUbRpfc:matrix.org" # Começa com ! e não com #

def thread_escuta_sync(cliente):
    """Roda em background para buscar novas mensagens."""
    print("[Sync] Iniciando escuta em background...")
    while True:
        try:
            # Mantém o socket TCP aberto esperando o servidor
            dados = cliente.sync(timeout_ms=30000)
            
            # Navegação no JSON para extrair mensagens de texto da sala específica
            if "rooms" in dados and "join" in dados["rooms"]:
                salas = dados["rooms"]["join"]
                if SALA_ID in salas:
                    eventos = salas[SALA_ID]["timeline"]["events"]
                    for evento in eventos:
                        if evento.get("type") == "m.room.message":
                            remetente = evento.get("sender")
                            texto = evento["content"].get("body", "")
                            print(f"\n[Nova Mensagem] {remetente}: {texto}")
        except Exception as e:
            # Em caso de queda de rede, aguarda um pouco e tenta o long-polling novamente
            time.sleep(5)

def iniciar_app():
    cliente = MatrixClient(HOMESERVER)
    print("Autenticando na Camada de Aplicação...")
    if not cliente.login(USUARIO, SENHA):
        print("Falha no login. Verifique as credenciais.")
        return

    print("Login com sucesso. Token obtido.")

    # Inicia a Thread para isolar o /sync
    t = threading.Thread(target=thread_escuta_sync, args=(cliente,), daemon=True)
    t.start()

    # Loop principal para envio de mensagens (Interface Textual Simples)
    print("Digite sua mensagem e pressione Enter para enviar.")
    while True:
        try:
            # Aguarda input do usuário
            msg = input()
            if msg.strip():
                cliente.enviar_mensagem(SALA_ID, msg)
        except KeyboardInterrupt:
            print("\nEncerrando cliente...")
            break

if __name__ == "__main__":
    iniciar_app()