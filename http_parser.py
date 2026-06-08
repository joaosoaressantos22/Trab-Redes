def enviar_requisicao(sock, host, metodo, caminho, corpo_str=None, headers_extras=None):
    """
    Constrói a string HTTP/1.1 bruta e a envia via TCP.
    """
    if headers_extras is None:
        headers_extras = {}
        
    headers = {
        "Host": host,
        "Connection": "close", # Força o fechamento do socket após a resposta simplificando o estado
        "User-Agent": "BareMetal-Matrix-Client/1.0"
    }
    headers.update(headers_extras)

    corpo_bytes = b""
    if corpo_str:
        corpo_bytes = corpo_str.encode('utf-8')
        headers["Content-Length"] = str(len(corpo_bytes))
        headers["Content-Type"] = "application/json"

    # Monta a requisição
    req = f"{metodo} {caminho} HTTP/1.1\r\n"
    for chave, valor in headers.items():
        req += f"{chave}: {valor}\r\n"
    req += "\r\n" # Linha em branco separando headers do body

    # Transmite para a camada de transporte
    sock.sendall(req.encode('utf-8') + corpo_bytes)

def receber_resposta(sock):
    """
    Máquina de estados avançada: Suporta tanto Content-Length quanto Transfer-Encoding: chunked.
    """
    buffer = b""
    
    # --- ESTADO 1: Lendo Cabeçalhos ---
    while b"\r\n\r\n" not in buffer:
        try:
            pedaco = sock.recv(4096)
            if not pedaco:
                break
            buffer += pedaco
        except TimeoutError:
            break

    if b"\r\n\r\n" not in buffer:
        return None, None

    headers_bytes, buffer = buffer.split(b"\r\n\r\n", 1)
    headers_texto = headers_bytes.decode('utf-8', errors='ignore')

    # Identificando o formato de transferência
    content_length = 0
    is_chunked = False
    
    for linha in headers_texto.split("\r\n"):
        linha_lower = linha.lower()
        if linha_lower.startswith("content-length:"):
            content_length = int(linha_lower.split(":")[1].strip())
        elif linha_lower.startswith("transfer-encoding:") and "chunked" in linha_lower:
            is_chunked = True

    corpo_bytes = b""

    # --- ESTADO 2: Lendo o Corpo (Body) ---
    if is_chunked:
        # Decodificador de Transfer-Encoding: chunked
        while True:
            # 1. Lê até encontrar o \r\n que separa o tamanho hex do dado
            while b"\r\n" not in buffer:
                pedaco = sock.recv(4096)
                if not pedaco: break
                buffer += pedaco
                
            if not buffer: break
            
            tamanho_hex_bytes, buffer = buffer.split(b"\r\n", 1)
            # Converte o tamanho de hexadecimal para inteiro
            tamanho_chunk = int(tamanho_hex_bytes.decode('utf-8').strip(), 16)
            
            # Se o tamanho for 0, o servidor terminou de enviar
            if tamanho_chunk == 0:
                break
                
            # 2. Lê os dados do chunk atual + o \r\n do final do chunk
            bytes_necessarios = tamanho_chunk + 2 
            while len(buffer) < bytes_necessarios:
                pedaco = sock.recv(4096)
                if not pedaco: break
                buffer += pedaco
                
            # Extrai os dados puros (ignorando o \r\n final)
            corpo_bytes += buffer[:tamanho_chunk]
            # Corta o buffer para o próximo ciclo
            buffer = buffer[bytes_necessarios:] 
            
    else:
        # Decodificador Padrão (Content-Length)
        while len(buffer) < content_length:
            try:
                pedaco = sock.recv(4096)
                if not pedaco: break
                buffer += pedaco
            except TimeoutError:
                break
        corpo_bytes = buffer[:content_length]

    corpo_texto = corpo_bytes.decode('utf-8', errors='ignore')
    return headers_texto, corpo_texto