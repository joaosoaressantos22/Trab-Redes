# Matrix BFF Client (Trabalho de Redes)

Este projeto é um cliente do protocolo [Matrix](https://matrix.org) estruturado sob o padrão **Backend-for-Frontend (BFF)**. O projeto foi desenvolvido como trabalho acadêmico da disciplina de Redes de Computadores com o objetivo de comprovar o domínio sobre a pilha TCP/IP, sockets e parsing de protocolos de aplicação na mão.

## Características e Restrições Técnicas

Para fins acadêmicos e para demonstrar o conhecimento nos níveis da camada de transporte e aplicação do modelo OSI, este projeto obedece à rigorosa restrição de não utilizar bibliotecas HTTP de alto nível (como `requests` ou `aiohttp`) no núcleo da comunicação do backend com o servidor Matrix.

- **Pilha Bare-Metal (Socket TCP / TLS):** Toda a comunicação com o Homeserver Matrix (ex: login, sync, envio de mensagens e mídias) é feita abrindo conexões de socket TCP diretas (`asyncio.open_connection`) com contexto SSL/TLS nativo.
- **Parsing Manual HTTP/1.1:** O código constrói os headers de requisição manualmente e realiza o parsing da resposta HTTP lendo o stream de bytes em busca do limite `\r\n\r\n`.
- **Tratamento de Cargas Dinâmicas:** Implementação própria para ler as respostas respeitando o `Content-Length` e o complexo `Transfer-Encoding: chunked`.
- **I/O Assíncrono Não Bloqueante:** A arquitetura L4 foi desenhada usando a biblioteca `asyncio` do Python. Isso permite abrir múltiplas streams e realizar *long-polling* (rota `/sync` do Matrix) simultaneamente, sem travar a thread principal.
- **BFF com Interface Web:** O front-end (`index.html`) é uma página que conecta via WebSocket com o gateway Python, recebendo atualizações das salas em tempo real e enviando dados sem a necessidade de recarregar.

## Estrutura do Projeto

- `index.html` - Interface do usuário (Frontend Web Client). Se conecta a ponte (BFF) via WebSocket.
- `matrix_async_core.py` / `async_matrix_client.py` - Núcleo assíncrono bare-metal que manipula os sockets TCP para interagir com a API do Matrix.
- `http_parser.py` - Tratamento de streams brutos de texto para o protocolo HTTP.
- `main.py` - Interface simplificada de terminal em modo texto (síncrona / multi-thread) para testes imediatos.

## Como Executar

### Pré-requisitos

- **Python 3.7+**
- O projeto usa predominantemente a biblioteca padrão do Python (`socket`, `ssl`, `asyncio`, `json`, `threading`).
- Instalar dependências de WebSockets se for rodar o servidor BFF completo para o frontend `index.html`.

### Executando em Modo Terminal (CLI)

```bash
python main.py
```
*(Abra o `main.py` para configurar seu usuário, senha e ID da sala antes de rodar)*.

### Executando a Interface Web (BFF)

1. Suba o servidor WebSocket/BFF (necessário rodar o script responsável por ouvir a porta `8765`).
2. Abra o arquivo `index.html` em seu navegador.
3. Preencha seu usuário e senha.
4. Preencha o `ID da Sala` (*Room ID*). Observe que Room IDs no Matrix começam com o caractere `!` e não com `#`.
5. Clique em **Conectar & Autenticar**.
