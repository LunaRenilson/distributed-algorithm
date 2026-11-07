# MC714 — Trabalho 2: Implementação de Algoritmos Distribuídos

Ambiente de referência e implementação do Trabalho 2 para a disciplina **MC714 (Sistemas Distribuídos)**:
- **API FastAPI Multithread** atuando como coordenador e gateway público.
- **Cluster PostgreSQL (Primary + 3 Réplicas)** com streaming replication física.
- **Nós Helpers Distribuídos (`helper-node-1`, `helper-node-2`, `helper-node-3`)** participando ativamente dos protocolos distribuídos.

---

## Algoritmos Distribuídos Implementados

1. **Ordenação de Eventos (Relógio Lógico de Lamport)**
   - Implementado em `app/algorithms/lamport.py`.
   - Ordenação causal e ordem total determinística com desempate lexicográfico por `node_id`.
   - Propagação de avanços de relógio entre nós e persistência ordenada no PostgreSQL.
   - Endpoints: `POST /events/ordered` e `GET /events/ordered`.

2. **Exclusão Mútua Distribuída (Ricart-Agrawala)**
   - Implementado em `app/algorithms/ricart_agrawala.py`.
   - Sem coordenador central de trava; estados `RELEASED`, `WANTED` e `HELD`.
   - Troca de mensagens `REQUEST`/`REPLY` com timestamps de Lamport e enfileiramento de respostas postergadas (`deferred_replies`).
   - Endpoint: `POST /tickets/buy-mutex`.

3. **Compromisso Atômico (Two-Phase Commit - 2PC)**
   - Implementado em `app/algorithms/two_phase_commit.py`.
   - Fases de `PREPARE` (votação paralela com todos os participantes) e `COMMIT`/`ABORT` (*all-or-nothing*).
   - Log durável de transações distribuídas no banco de dados (`two_phase_transactions`).
   - Endpoint: `POST /tickets/buy-2pc`.

4. **Detecção de Falhas (Heartbeat Failure Detector)**
   - Implementado em `app/algorithms/heartbeat.py`.
   - Monitoramento ativo com contagem de pings perdidos (`max_missed`) e timeouts configuráveis.
   - Endpoint: `GET /cluster/health`.

---

## Como Executar o Ambiente

### Pré-requisitos
- Docker Engine e Docker Compose v2 (ou Docker Desktop)
- Python 3.12+ (para executar os scripts de teste e experimentos localmente)

### 1. Subir o Cluster
```bash
chmod +x db/replica/replica-entrypoint.sh db/init/00-replication.sh scripts/*.sh
docker compose build
docker compose up -d
docker compose ps
```

### 2. Verificar a Saúde do Cluster
```bash
# Health check da API
curl http://localhost:8000/health

# Status de replicação dos nós de banco
curl http://localhost:8000/ready
curl http://localhost:8000/databases

# Status do detector de falhas distribuído
curl http://localhost:8000/cluster/health
```

---

## Testando os Algoritmos Distribuídos

### 1. Ordenação com Lamport
```bash
# Publicar eventos com ordenação causal
curl -X POST http://localhost:8000/events/ordered \
  -H "Content-Type: application/json" \
  -d '{"event_name": "compra_iniciada", "payload": {"user": 1}}'

# Listar eventos na ordem total estrita de Lamport
curl http://localhost:8000/events/ordered
```

### 2. Compra com Exclusão Mútua Distribuída (Ricart-Agrawala)
```bash
curl -X POST http://localhost:8000/tickets/buy-mutex \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "event_id": 1, "quantity": 2}'
```

### 3. Compra Atômica com Two-Phase Commit (2PC)
```bash
curl -X POST http://localhost:8000/tickets/buy-2pc \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "event_id": 1, "quantity": 2}'
```

---

## Executando os Testes Automatizados

A suíte possui testes unitários (12 testes cobrindo todas as propriedades teóricas dos algoritmos) e testes de integração:

```bash
# Executa todos os testes unitários e de integração
PYTHONPATH=server python3 -m pytest tests/unit tests/integration -v
```

---

## Avaliação Experimental e Benchmarking

O script de experimentos automatizados varia a concorrência multithread (1, 5, 10, 20 threads), calcula métricas de vazão (req/s), taxa de sucesso e percentis de latência (p50, p95, p99):

```bash
# Execução direta com o cluster ativo
./scripts/run_experiments.sh
```

Os resultados detalhados são gerados automaticamente em `results/experiments.csv`.
