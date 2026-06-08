import socket
import ssl

def criar_conexao_segura(host, porta=443, timeout=35.0):
    """
    Cria um socket TCP (L4) e o envolve em um contexto TLS (L6).
    O timeout é ligeiramente superior a 30s para acomodar o long-polling do /sync.
    """
    # Cria o contexto SSL padrão do sistema operacional
    contexto_tls = ssl.create_default_context()
    
    # Cria o Socket TCP puro (IPv4, Stream de bytes)
    sock_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock_tcp.settimeout(timeout)
    
    # Encapsula o socket TCP no TLS
    sock_seguro = contexto_tls.wrap_socket(sock_tcp, server_hostname=host)
    
    # Estabelece a conexão (Three-way handshake + TLS Handshake)
    sock_seguro.connect((host, porta))
    
    return sock_seguro