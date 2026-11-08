# MC714 — Trabalho 2: Algoritmos Distribuídos

Implementação de algoritmos distribuídos em Python com **FastAPI Multithread**, **PostgreSQL Cluster (Primary + 3 Réplicas)** e nós **Helpers** independentes.

---

## Como Subir o Ambiente

```bash
docker compose build
docker compose up -d
```

Verifique se os serviços estão prontos:
```bash
curl http://localhost:8000/health
```

---

## Como Testar os Cenários

Você pode testar cada algoritmo de duas formas: **via testes automatizados** (rápido, sem Docker) ou **manualmente via HTTP/Docker**.

### 1. Testes Automatizados Isolados (`pytest`)

Execute a partir da pasta `trabalho2`:

- **Relógio de Lamport (ordenação causal):**
  ```bash
  python3 -m pytest tests/unit/test_lamport.py -v
  ```
- **Exclusão Mútua (Ricart-Agrawala):**
  ```bash
  python3 -m pytest tests/unit/test_ricart_agrawala.py -v
  ```
- **Two-Phase Commit (2PC):**
  ```bash
  python3 -m pytest tests/unit/test_2pc.py -v
  ```
- **Detector de Falhas (Heartbeat):**
  ```bash
  python3 -m pytest tests/unit/test_heartbeat.py -v
  ```
- **Concorrência e Integração Multithread:**
  ```bash
  python3 -m pytest tests/integration/test_distributed_api.py -v
  ```
- **Todos os testes de uma vez:**
  ```bash
  python3 -m pytest tests/unit tests/integration -v
  ```

---

### 2. Testes Manuais com o Cluster Ativo

#### A. Ordenação de Eventos (Lamport)
Publique eventos e confira a ordem causal persistida no banco:
```bash
# Publicar eventos
curl -X POST http://localhost:8000/events/ordered -H "Content-Type: application/json" -d '{"event_name": "checkout_iniciado"}'
curl -X POST http://localhost:8000/events/ordered -H "Content-Type: application/json" -d '{"event_name": "pagamento_aprovado"}'

# Consultar na ordem total (clock ASC, node_id ASC)
curl http://localhost:8000/events/ordered
```

#### B. Exclusão Mútua Distribuída (Ricart-Agrawala)
Compra concorrente de ingressos protegida por seção crítica distribuída:
```bash
curl -X POST http://localhost:8000/tickets/buy-mutex \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "event_id": 1, "quantity": 2}'
```

#### C. Two-Phase Commit (2PC)
- **Cenário de Sucesso (Commit):**
  ```bash
  curl -X POST http://localhost:8000/tickets/buy-2pc \
    -H "Content-Type: application/json" \
    -d '{"user_id": 1, "event_id": 1, "quantity": 2}'
  ```
- **Cenário de Rejeição/Falha (Abort):**
  Comprar mais de 50 ingressos faz os participantes rejeitarem a transação atômica:
  ```bash
  curl -X POST http://localhost:8000/tickets/buy-2pc \
    -H "Content-Type: application/json" \
    -d '{"user_id": 1, "event_id": 1, "quantity": 99}'
  ```
- **Auditar o log durável do 2PC no Postgres:**
  ```bash
  docker exec -it mc714-postgres-primary psql -U tickets -d tickets -c "SELECT tx_id, state, payload FROM two_phase_transactions;"
  ```

#### D. Injeção e Detecção de Falhas (Heartbeat)
1. Veja todos os nós saudáveis:
   ```bash
   curl http://localhost:8000/cluster/health
   ```
2. Simule a queda de um nó helper:
   ```bash
   docker stop mc714-helper-3
   ```
3. Aguarde ~6s e consulte novamente: `helper-node-3` será detectado como `"is_alive": false`.
4. Recupere o nó:
   ```bash
   docker start mc714-helper-3
   ```

---

## Benchmark e Avaliação Experimental

Para rodar os ensaios de desempenho com variação de concorrência (1, 5, 10, 20 threads) e coletar métricas de latência (**p50, p95, p99**) e vazão (req/s):

```bash
./scripts/run_experiments.sh
```

Os resultados serão salvos automaticamente em `results/experiments.csv`.

---

## Relatório LaTeX (IEEE)

```bash
# 1. Regenerar dados (cluster ativo + permissão Docker)
./scripts/run_experiments.sh
python3 scripts/measure_heartbeat_sim.py   # ou relatorio/scripts/measure_heartbeat.sh com Docker

# 2. Tabelas e PDF
cd relatorio && make all
```

Saída: `relatorio/relatorio.pdf` e cópia em `relatorio_mc714_trabalho2.pdf`. Preencher na capa os links do GitLab e do vídeo antes da entrega.

### Overleaf

Pasta pronta para upload: [`relatorio-overleaf/`](relatorio-overleaf/) (use `main.tex` como documento principal). Para atualizar a partir de novos experimentos:

```bash
./relatorio/scripts/sync_overleaf.sh
zip -r relatorio-overleaf.zip relatorio-overleaf -x '*.aux' -x '*.log'
```
