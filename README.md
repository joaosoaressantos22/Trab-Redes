# Matrix BFF Client L4/L7

## Descrição
Breve descrição do projeto e dos desafios abordados.
Este projeto consiste no desenvolvimento de um sistema de envio de mensagens utilizando o protocolo descentralizado Matrix, estruturado sob o padrão Backend-for-Frontend (BFF). O maior desafio abordado é a implementação integral da comunicação de rede na Camada de Transporte e Aplicação (L4/L7) de forma "bare-metal", sem o uso de bibliotecas HTTP de alto nível, exigindo a manipulação manual de sockets, TLS assíncrono e parsing de dados fragmentados (chunked).

## Tecnologias Utilizadas
**Linguagem de programação utilizada:**
* Python 3.8+ (Servidor Gateway/BFF)
* JavaScript ES6 Vanilla (Cliente Web)

**Bibliotecas/Frameworks utilizados:**
* Nativas (Python): `asyncio`, `socket`, `ssl`, `json`
* Terceiros (Python): `websockets` (apenas para comunicação local Client-BFF)
* Infraestrutura: Docker e Docker Compose (Homeserver Dendrite e PostgreSQL)

## Como Executar

### Requisitos
Lista de dependências necessárias:
* Docker e Docker Compose instalados no sistema
* Python 3.8 ou superior
* Terminal compatível (Bash no Linux/macOS ou WSL no Windows)

### Instruções de Execução
1. Clone o repositório:
`git clone https://github.com/joaosoaressantos22/Trab-Redes.git`

2. Instale as dependências:
`pip install websockets`

3. Execute o servidor (Infraestrutura Matrix local):
`./setup_infra.sh`

4. Execute o cliente (Gateway BFF e Interface UI):
`./run.sh`

## Como Testar
Para testar a aplicação no ambiente local:
1. Aguarde a inicialização da infraestrutura e a abertura automática do navegador.
2. No ecrã de autenticação, insira `localhost:8008` como Homeserver.
3. Utilize as credenciais de teste locais geradas pelo script (Usuário: `admin`, Senha: `admin`).
4. Para testar o envio de multimédia, clique no ícone de anexo e selecione um ficheiro; a aplicação converterá a matriz de bytes em memória e fará o envio assíncrono.
5. Para testar a federação (comunicação externa), insira `matrix.org` no campo Homeserver e clique em "Explorar" para carregar as salas públicas através do túnel L4 com injeção SNI.

## Funcionalidades Implementadas
* Gestão manual de Sockets TCP não bloqueantes (`asyncio.open_connection`).
* *Parser* HTTP/1.1 rigoroso com tratamento dinâmico de `Content-Length` e decodificação de `Transfer-Encoding: chunked`.
* Encapsulamento SSL/TLS dinâmico com injeção de cabeçalhos SNI.
* Envio e recepção de mensagens de texto e ficheiros multimédia (Imagens, Áudios, Vídeos).
* Criação de salas e ingresso em salas externas via alias ou ID.

## Possíveis Melhorias Futuras
* Implementação de Criptografia Ponta-a-Ponta (E2EE) utilizando o padrão arquitetural Sans-I/O para manter a separação estrita da rede.
* Adição de persistência em cache local (SQLite) no Gateway BFF para diminuir as chamadas recursivas ao Homeserver em sincronizações longas.
