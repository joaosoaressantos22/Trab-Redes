#!/bin/bash

echo "[Infra] Verificando chave de federação L4 (matrix_key.pem)..."

# Previne o erro de criar um diretório com o nome do arquivo montado
if [ -d "matrix_key.pem" ]; then
    sudo rm -rf matrix_key.pem
fi

# Gera a chave apenas se ela ainda não existir
if [ ! -f "matrix_key.pem" ]; then
    sudo docker run --rm --entrypoint="" -v "$(pwd)":/mnt matrixdotorg/dendrite-monolith:latest /usr/bin/generate-keys --private-key /mnt/matrix_key.pem
fi

echo "[Infra] Inicializando PostgreSQL e Homeserver Dendrite..."
sudo docker compose up -d

echo "[Infra] Aguardando a pipeline do servidor estabilizar na porta 8008..."
sleep 10

echo "[Infra] Provisionando usuário de teste L7 (admin/admin)..."
sudo docker exec bff_matrix_dendrite /usr/bin/create-account -config /etc/dendrite/dendrite.yaml -username admin -password admin > /dev/null 2>&1

echo "[Infra] Infraestrutura Local provisionada com sucesso."
echo "[Infra] -> Homeserver: localhost:8008"
echo "[Infra] -> Credenciais geradas: Usuário: admin | Senha: admin"
echo "[Infra] Execute o run.sh para iniciar o Gateway BFF."