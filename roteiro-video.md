# Roteiro de Demonstração em Vídeo (MC714 — Trabalho 2)

> **Duração recomendada:** ~5 minutos (com participação dos dois integrantes da dupla, conforme as diretrizes da disciplina).  
> **Objetivo:** Demonstrar a arquitetura, execução normal, exclusão mútua concorrente, transação atômica (2PC), injeção/recuperação de falhas e análise experimental.

---

## 1. Visão Geral da Sequência

| Bloco | Tempo Estimado | Foco da Apresentação |
|---|---|---|
| **Bloco 1: Introdução & Arquitetura** | ~0:45 | Apresentação da dupla, propósito do sistema (ingressos distribuídos) e arquitetura ([`docs/diagrama-trabalho-mc714.md`](docs/diagrama-trabalho-mc714.md)). |
| **Bloco 2: Subida do Cluster & Health** | ~0:45 | Inicialização com Docker Compose e verificação de nós de banco e helpers. |
| **Bloco 3: Algoritmos em Execução Normal** | ~1:30 | Ordenação causal por Lamport, Exclusão Mútua (Ricart-Agrawala) e Two-Phase Commit (2PC). |
| **Bloco 4: Injeção de Falha & Recuperação** | ~1:00 | Simulação de crash de nó (`helper-node-1`), detecção via Heartbeat e recuperação pós-restart. |
| **Bloco 5: Avaliação Experimental & Conclusão** | ~1:00 | Execução dos testes automatizados (`pytest`) e geração dos percentis do benchmark em CSV. |

---

## 2. Passo a Passo com Comandos para Demonstração

### Bloco 1: Apresentação da Arquitetura (~0:45)
- **O que falar:** Nome e RA da dupla. Explicar brevemente que o sistema consiste em uma API FastAPI multithread coordenando um cluster PostgreSQL (Primary + 3 Réplicas com streaming replication) e 3 nós helpers autônomos para algoritmos distribuídos.
- **O que mostrar:** Abrir [`docs/visualizar-diagramas.html`](docs/visualizar-diagramas.html) no navegador ou o PNG [`docs/images/slide-one-pager.png`](docs/images/slide-one-pager.png) (roteiro + arquitetura + endpoints, 16:9). Índice completo: [`docs/diagrama-trabalho-mc714.md`](docs/diagrama-trabalho-mc714.md).

---

### Bloco 2: Inicialização do Cluster & Verificação de Saúde (~0:45)
- **Terminal:** Subir os contêineres e verificar o estado:
  ```bash
  docker compose up -d
  docker compose ps
  ```
- **Demonstrar os endpoints de prontidão:**
  ```bash
  # Liveness da API
  curl -s http://localhost:8000/health | jq .

  # Estado e papéis das instâncias de banco (1 primary, 3 replicas)
  curl -s http://localhost:8000/ready | jq .
  curl -s http://localhost:8000/databases | jq .

  # Telemetria do detector de falhas ativo
  curl -s http://localhost:8000/cluster/health | jq .
  ```

---

### Bloco 3: Algoritmos Distribuídos em Operação Normal (~1:30)

#### 3.1. Ordenação Causal de Eventos (Relógio Lógico de Lamport)
- **Publicar eventos em sequência:**
  ```bash
  curl -s -X POST http://localhost:8000/events/ordered \
    -H "Content-Type: application/json" \
    -d '{"event_name": "checkout_iniciado", "payload": {"user": 1}}' | jq .

  curl -s -X POST http://localhost:8000/events/ordered \
    -H "Content-Type: application/json" \
    -d '{"event_name": "pagamento_aprovado", "payload": {"valor": 100}}' | jq .
  ```
- **Consultar a ordem total estrita gerada:**
  ```bash
  curl -s http://localhost:8000/events/ordered | jq .
  ```
  *(Destacar que os eventos possuem `lamport_clock` crescente e ordenação determinística).*

#### 3.2. Exclusão Mútua Distribuída (Ricart-Agrawala)
- **Executar requisição de compra protegida por seção crítica:**
  ```bash
  curl -s -X POST http://localhost:8000/tickets/buy-mutex \
    -H "Content-Type: application/json" \
    -d '{"user_id": 1, "event_id": 1, "quantity": 2}' | jq .
  ```
  *(Explicar que o nó coordenador enviou REQUEST aos helpers réplicas, aguardou confirmação por timestamps de Lamport e liberou a seção crítica registrando `critical_section_ms`).*

#### 3.3. Compromisso Atômico (Two-Phase Commit - 2PC)
- **Cenário de Sucesso (Commit unânime):**
  ```bash
  curl -s -X POST http://localhost:8000/tickets/buy-2pc \
    -H "Content-Type: application/json" \
    -d '{"user_id": 1, "event_id": 1, "quantity": 3}' | jq .
  ```
- **Inspecionar a persistência durável do log 2PC no banco primário:**
  ```bash
  docker exec mc714-postgres-primary psql -U tickets -d tickets -c \
    "SELECT tx_id, state, payload, updated_at FROM two_phase_transactions ORDER BY created_at DESC LIMIT 2;"
  ```
  *(Mostrar o estado `COMMITTED` registrado no log durável).*

---

### Bloco 4: Injeção de Falha, Detecção e Recuperação (~1:00)

#### 4.1. Injetar a Falha (Crash-Stop de um Nó Helper)
- **Derrubar um nó auxiliar:**
  ```bash
  docker compose stop helper-node-1
  ```

#### 4.2. Demonstrar Detecção da Falha (Heartbeat Failure Detector)
- **Consultar o status de saúde após timeout de pings:**
  ```bash
  sleep 6
  curl -s http://localhost:8000/cluster/health | jq .
  ```
  *(Destacar na tela que `helper-node-1` passou para `"is_alive": false` com `missed_count >= 3`).*

#### 4.3. Recuperação do Cluster
- **Reiniciar o nó e verificar o restabelecimento:**
  ```bash
  docker compose start helper-node-1
  sleep 4
  curl -s http://localhost:8000/cluster/health | jq .
  ```
  *(Mostrar que o nó voltou automaticamente para `"is_alive": true` e `missed_count: 0`).*

---

### Bloco 5: Testes Automatizados & Avaliação de Desempenho (~1:00)

#### 5.1. Execução dos Testes Automatizados
- **Rodar a suíte completa (unitários + integração):**
  ```bash
  python3 -m pytest tests/unit tests/integration -v
  ```
  *(Mostrar os 15 testes passando em frações de segundo).*

#### 5.2. Execução do Benchmark Multithread
- **Disparar o ensaio experimental:**
  ```bash
  python3 scripts/benchmark.py --host http://localhost:8000 --output results/experiments.csv --reqs 30
  ```
- **Apresentar o arquivo CSV gerado com os percentis:**
  ```bash
  column -s, -t < results/experiments.csv | head -n 15
  ```
  *(Destacar as colunas de concorrência: 1, 5, 10 e 20 threads com vazão req/s e latências p50, p95 e p99).*

---

## 3. Checklist Rápido Pré-Gravação

- [ ] Contêineres reconstruídos limpos: `docker compose down -v && docker compose up -d`
- [ ] Utilitário `jq` instalado (facilita leitura formatada no terminal; se não tiver, pode omitir `| jq .`)
- [ ] Terminais com fonte grande e legível para a gravação
- [ ] Ambos os integrantes com microfone configurado
