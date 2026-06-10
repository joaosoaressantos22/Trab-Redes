#!/bin/bash

# Mapeamento de Arquivos
GATEWAY_SCRIPT="src/gateway.py"
INDEX_HTML="web/index.html"

echo "[BFF] Iniciando Gateway L4/L7..."

# Inicia o servidor Python em background e captura o PID
python3 $GATEWAY_SCRIPT &
GATEWAY_PID=$!

# Aguarda 1 segundo para garantir o bind do socket na porta 8765
sleep 1

echo "[BFF] Renderizando Camada de Interface no navegador padrão..."

# Determina o acionador do navegador de acordo com o SO
if command -v xdg-open > /dev/null; then
    xdg-open $INDEX_HTML
elif command -v open > /dev/null; then
    open $INDEX_HTML
else
    echo "[!] Abertura automática não suportada. Acesse $INDEX_HTML manualmente."
fi

# Armadilha de sinais: encerra o processo background do Python ao fechar o terminal (Ctrl+C)
trap "echo -e '\n[BFF] Encerrando Gateway L4/L7 e liberando porta...'; kill $GATEWAY_PID; exit" INT TERM EXIT

# Trava a execução do script no PID do Python, permitindo a visualização contínua dos logs (stdout/stderr)
wait $GATEWAY_PID