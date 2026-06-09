import asyncio
import ssl

async def criar_conexao_segura_async(host, porta=443):
    """
    Estabelece stream assíncrono TCP encapsulado em TLS.
    Retorna os objetos StreamReader e StreamWriter.
    """
    contexto_tls = ssl.create_default_context()
    
    # Cria a conexão de forma não bloqueante
    reader, writer = await asyncio.open_connection(
        host, porta, ssl=contexto_tls
    )
    return reader, writer

async def enviar_requisicao_async(writer, host, metodo, caminho, corpo_str=None, headers_extras=None):
    """
    Constrói e transmite os bytes da requisição sem bloquear o loop de eventos.
    """
    if headers_extras is None:
        headers_extras = {}
        
    headers = {
        "Host": host,
        "Connection": "close",
        "User-Agent": "BareMetal-Async-Matrix-Client/1.0"
    }
    headers.update(headers_extras)

    corpo_bytes = b""
    if corpo_str:
        corpo_bytes = corpo_str.encode('utf-8')
        headers["Content-Length"] = str(len(corpo_bytes))
        headers["Content-Type"] = "application/json"

    req = f"{metodo} {caminho} HTTP/1.1\r\n"
    for chave, valor in headers.items():
        req += f"{chave}: {valor}\r\n"
    req += "\r\n"

    # Transmissão assíncrona para a camada de transporte
    writer.write(req.encode('utf-8') + corpo_bytes)
    await writer.drain()

async def receber_resposta_async(reader):
    """
    Parseia a resposta HTTP/1.1 através de um stream não bloqueante.
    """
    buffer = b""
    
    # ESTADO 1: Lendo Cabeçalhos
    while b"\r\n\r\n" not in buffer:
        try:
            pedaco = await asyncio.wait_for(reader.read(4096), timeout=35.0)
            if not pedaco:
                break
            buffer += pedaco
        except asyncio.TimeoutError:
            break

    if b"\r\n\r\n" not in buffer:
        return None, None

    headers_bytes, buffer = buffer.split(b"\r\n\r\n", 1)
    headers_texto = headers_bytes.decode('utf-8', errors='ignore')

    content_length = 0
    is_chunked = False
    
    for linha in headers_texto.split("\r\n"):
        linha_lower = linha.lower()
        if linha_lower.startswith("content-length:"):
            content_length = int(linha_lower.split(":")[1].strip())
        elif linha_lower.startswith("transfer-encoding:") and "chunked" in linha_lower:
            is_chunked = True

    corpo_bytes = b""

    # ESTADO 2: Lendo o Corpo (Body)
    if is_chunked:
        while True:
            while b"\r\n" not in buffer:
                pedaco = await asyncio.wait_for(reader.read(4096), timeout=35.0)
                if not pedaco: break
                buffer += pedaco
                
            if not buffer: break
            
            tamanho_hex_bytes, buffer = buffer.split(b"\r\n", 1)
            tamanho_chunk = int(tamanho_hex_bytes.decode('utf-8').strip(), 16)
            
            if tamanho_chunk == 0:
                break
                
            bytes_necessarios = tamanho_chunk + 2 
            while len(buffer) < bytes_necessarios:
                pedaco = await asyncio.wait_for(reader.read(4096), timeout=35.0)
                if not pedaco: break
                buffer += pedaco
                
            corpo_bytes += buffer[:tamanho_chunk]
            buffer = buffer[bytes_necessarios:] 
            
    else:
        while len(buffer) < content_length:
            try:
                pedaco = await asyncio.wait_for(reader.read(4096), timeout=35.0)
                if not pedaco: break
                buffer += pedaco
            except asyncio.TimeoutError:
                break
        corpo_bytes = buffer[:content_length]

    corpo_texto = corpo_bytes.decode('utf-8', errors='ignore')
    return headers_texto, corpo_texto