Relatório de Decisões Arquiteturais e de Implementação
Contexto: O sistema adota o padrão Backend-for-Frontend (BFF) focado em concorrência assíncrona e encapsulamento manual de protocolos de rede.

1. Transporte e Protocolo (Pilha Bare-Metal L4/L7)

Decisão: Substituição de sockets bloqueantes tradicionais por streams não-bloqueantes com asyncio e envoltório TLS nativo.

Justificativa: Cumprir a restrição absoluta de não usar bibliotecas HTTP de alto nível (requests, aiohttp) entre o BFF e o Homeserver. A máquina de estados implementada manualmente interpreta os bytes brutos do TCP, processando ativamente cabeçalhos provisórios e delimitadores L7 complexos como Transfer-Encoding: chunked e Content-Length.

2. Orquestração e Concorrência no Gateway (BFF)

Decisão: O Gateway Python atua como um servidor de WebSockets bidirecional gerido pelo loop de eventos do asyncio.

Justificativa: Garantir o gerenciamento assíncrono L4 sem travar a thread de execução do servidor. Isso permite que a rotina de long-polling (/sync do Matrix) rode eternamente em background enquanto o servidor continua aceitando requisições L7 instantâneas (envio de mensagens e mídia) de múltiplos clientes simultaneamente.

3. Tratamento Agnostico de Multimídia

Decisão: Conversão ponta-a-ponta de matrizes de bytes em memória, com o Frontend codificando arquivos I/O para Base64 via WebSocket e o Gateway decodificando para bytes puros L4.

Justificativa: O parser da Camada de Transporte L4 foi desenhado para ser cego ao conteúdo (textos ou matrizes multimidia). Essa escolha arquitetural permitiu enviar vídeos e áudios nativamente sem necessitar de bibliotecas de empacotamento RESTful no Python, delegando o render exclusivamente à Camada de Interface (tags HTML5 nativas).

4. Camada de Interface (SPA Frontend Web)

Decisão: Criação de uma Single Page Application reativa em Vanilla JavaScript sem uso de bundlers ou frameworks pesados.

Justificativa: Isola toda a complexidade do protocolo Matrix no backend. O Frontend atua como um "terminal burro" que apenas renderiza JSONs polidos (como timestamps traduzidos e URLs resolvidas) enviados pelo Gateway via WebSockets.

5. Estratégia de Criptografia (Preparação E2EE)

Decisão Arquitetural: Escolha do padrão Sans-I/O (usando bibliotecas como matrix-nio em modo puramente lógico).

Justificativa: A criptografia é uma característica muito desejável a uma aplicação de comunicação, mas implementá-la em baixo nível seria muito complexo. A abordagem Sans-I/O usa a biblioteca externa como um mero "calculador matemático", enquanto as chamadas de rede resultantes continuam a ser despachadas obrigatoriamente pela nossa infraestrutura L4 em TCP puro. Isso manterá o rigor acadêmico L4/L7 imaculado.