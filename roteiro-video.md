# Roteiro Detalhado de Apresentação em Vídeo (MC714 — Trabalho 2)

> **Duração Total:** ~5 minutos (com participação obrigatória dos 2 integrantes da dupla).  
> **Objetivo:** Demonstrar de ponta a ponta a arquitetura, a execução correta dos algoritmos distribuídos em operação normal, a tolerância a falhas com detecção/recuperação e a avaliação experimental com métricas de desempenho.

---

## 1. Visão Geral e Divisão de Papéis

| Bloco | Tempo | Apresentador Sugerido | O que Mostrar na Tela | Foco Principal |
|---|---|---|---|---|
| **Bloco 1: Introdução & Arquitetura** | ~0:45 | Integrante A | Navegador ou VS Code com slide/diagrama (`docs/images/slide-one-pager.png` ou `docs/visualizar-diagramas.html`) | Apresentação da dupla, escopo de ingressos distribuídos e arquitetura de nós. |
| **Bloco 2: Subida do Cluster & Health** | ~0:45 | Integrante A | Terminal com Docker Compose e saídas JSON do `curl` | Subida do cluster (1 API, 4 nós Postgres, 3 helpers) e verificação dos endpoints de saúde. |
| **Bloco 3: Algoritmos em Operação Normal** | ~1:30 | Integrante B | Terminal executando requisições `curl` e consulta SQL no Postgres | Ordenação causal de Lamport, Exclusão Mútua de Ricart-Agrawala e 2PC atômico com log durável. |
| **Bloco 4: Injeção de Falha & Recuperação** | ~1:00 | Integrante B | Terminal dividindo comandos de parada de nó e monitoramento do detector | Crash de nó com `docker compose stop`, detecção automática pelo Heartbeat e restauração. |
| **Bloco 5: Avaliação Experimental & Conclusão** | ~1:00 | Integrantes A e B | Terminal com execução do `pytest` e tabela formatada do `experiments.csv` | Validação formal dos 15 testes e análise de latência (p50, p95, p99) e vazão multithread. |

---

## 2. Guia de Execução e Apresentação Bloco a Bloco

---

### Bloco 1: Introdução & Arquitetura (~0:45)

#### Como preparar a tela:
- Deixe aberta a imagem [`docs/images/slide-one-pager.png`](docs/images/slide-one-pager.png) ou o arquivo interativo [`docs/visualizar-diagramas.html`](docs/visualizar-diagramas.html) em tela cheia no navegador.
- Como referência adicional dos diagramas individuais, utilize [`docs/diagrama-trabalho-mc714.md`](docs/diagrama-trabalho-mc714.md).

#### Como falar e apresentar:
1. **Apresentação inicial:** *"Olá, somos [Nome 1, RA 1] e [Nome 2, RA 2], e este é o vídeo de demonstração do Trabalho 2 da disciplina MC714 - Sistemas Distribuídos."*
2. **Contextualização do problema:** *"Implementamos um sistema distribuído de venda de ingressos com API multithread em Python, projetado para operar sobre múltiplos nós lógicos independentes, garantindo integridade sob concorrência e tolerância a falhas."*
3. **Explicação da arquitetura apontando no diagrama:**
   - **Camada de Aplicação:** *"Temos a API FastAPI que recebe as requisições dos clientes, gerencia concorrência e coordena os algoritmos."*
   - **Camada de Persistência:** *"Um cluster PostgreSQL com 1 nó Primary e 3 Réplicas configuradas com streaming replication física (WAL), garantindo replicação de dados."*
   - **Nós Lógicos Distribuídos:** *"Três nós helpers autônomos (`helper-node-1`, `2` e `3`) rodando em processos isolados para atuar ativamente nos algoritmos de ordenação, exclusão mútua e consenso."*

---

### Bloco 2: Subida do Cluster & Verificação de Saúde (~0:45)

#### Como preparar a tela:
- Mude para uma janela de terminal limpa com fonte grande e legível.

#### Comandos a executar:
1. **Subir o ambiente:**
   ```bash
   docker compose up -d
   docker compose ps
   ```
2. **Demonstrar os endpoints de saúde e papéis dos nós:**
   ```bash
   # 1. Liveness básico da API
   curl -s http://localhost:8000/health | jq .

   # 2. Prontidão do banco: valida se há exatamente 1 primary e 3 réplicas sincronizadas
   curl -s http://localhost:8000/ready | jq .

   # 3. Telemetria e latências de replicação de cada nó do banco
   curl -s http://localhost:8000/databases | jq .

   # 4. Detector de falhas por Heartbeat: lista todos os nós monitorados
   curl -s http://localhost:8000/cluster/health | jq .
   ```

#### O que destacar na narração:
- *"Vejam que todos os 8 contêineres subiram saudáveis na rede interna `mc714-net`."*
- *"O endpoint `/ready` confirma que o primary está recebendo escritas e as 3 réplicas estão conectadas com lag de replicação em milissegundos."*
- *"O endpoint `/cluster/health` mostra o detector ativo, com todos os nós com `is_alive: true` e zero falhas de ping."*

---

### Bloco 3: Algoritmos Distribuídos em Operação Normal (~1:30)

#### 3.1. Ordenação Causal de Eventos (Relógio Lógico de Lamport)
- **Comandos:**
  ```bash
  # Emite o primeiro evento local
  curl -s -X POST http://localhost:8000/events/ordered \
    -H "Content-Type: application/json" \
    -d '{"event_name": "checkout_iniciado", "payload": {"user_id": 1}}' | jq .

  # Emite o segundo evento causalmente posterior
  curl -s -X POST http://localhost:8000/events/ordered \
    -H "Content-Type: application/json" \
    -d '{"event_name": "pagamento_confirmado", "payload": {"valor": 120}}' | jq .

  # Consulta a ordem causal no cluster
  curl -s http://localhost:8000/events/ordered | jq .
  ```
- **O que destacar:** *"A cada evento emitido, o relógio lógico de Lamport avança (`tick`), propaga o timestamp para os nós réplicas (`update`) e persiste no banco na ordem estrita (`lamport_clock` e desempate por `node_id`)."*

#### 3.2. Exclusão Mútua Distribuída (Ricart-Agrawala)
- **Comando:**
  ```bash
  curl -s -X POST http://localhost:8000/tickets/buy-mutex \
    -H "Content-Type: application/json" \
    -d '{"user_id": 1, "event_id": 1, "quantity": 2}' | jq .
  ```
- **O que destacar:** *"Para debitar os ingressos sem condição de corrida, o coordenador entra em estado `WANTED`, envia mensagens `REQUEST` com timestamp de Lamport para todos os nós helpers, aguarda a autorização (`REPLY`) de todos e executa a dedução na seção crítica (`HELD`), liberando o recurso logo em seguida."*

#### 3.3. Compromisso Atômico (Two-Phase Commit - 2PC)
- **Comando 1 (Transação com Sucesso - Commit unânime):**
  ```bash
  curl -s -X POST http://localhost:8000/tickets/buy-2pc \
    -H "Content-Type: application/json" \
    -d '{"user_id": 1, "event_id": 1, "quantity": 3}' | jq .
  ```
- **Comando 2 (Inspecionar a auditoria durável no PostgreSQL):**
  ```bash
  docker exec mc714-postgres-primary psql -U tickets -d tickets -c \
    "SELECT tx_id, state, payload, updated_at FROM two_phase_transactions ORDER BY created_at DESC LIMIT 2;"
  ```
- **Comando 3 (Cenário de Rejeição/Abort):**
  ```bash
  curl -s -X POST http://localhost:8000/tickets/buy-2pc \
    -H "Content-Type: application/json" \
    -d '{"user_id": 1, "event_id": 1, "quantity": 99}' | jq .
  ```
- **O que destacar:** 
  - *"No 2PC, o coordenador executa a Fase 1 (`PREPARE`) em paralelo com todos os nós helpers. Quando todos votam `YES`, emite `COMMIT` e grava na tabela `two_phase_transactions`."*
  - *"Quando enviamos uma quantidade inválida (> 50 ingressos), um dos participantes vota `NO`, e o coordenador executa `ABORT`, garantindo semântica de tudo-ou-nada sem inconsistência."*

---

### Bloco 4: Injeção de Falha, Detecção e Recuperação (~1:00)

#### Como demonstrar na prática:
1. **Derrubar um nó auxiliar (simulação de Crash-Stop):**
   ```bash
   docker compose stop helper-node-1
   ```
   - **Narração:** *"Agora vamos simular uma falha real de desligamento abrupto do nó `helper-node-1`."*

2. **Demonstrar a detecção pelo Heartbeat:**
   Aguarde cerca de 6 segundos (tempo para o detector estourar o limite de pings perdidos) e execute:
   ```bash
   curl -s http://localhost:8000/cluster/health | jq .
   ```
   - **Narração:** *"Notem que o detector de falhas identificou a ausência de resposta. O campo `missed_count` atingiu o limite de tolerância e o status de `helper-node-1` mudou automaticamente para `is_alive: false`."*

3. **Restabelecer o nó (Recuperação):**
   ```bash
   docker compose start helper-node-1
   sleep 4
   curl -s http://localhost:8000/cluster/health | jq .
   ```
   - **Narração:** *"Ao reiniciarmos o nó, o detector restabelece o canal de comunicação no próximo ciclo de sondagem e marca o nó novamente como `is_alive: true` com `missed_count: 0`."*

---

### Bloco 5: Avaliação Experimental & Conclusão (~1:00)

#### 5.1. Execução dos Testes Automatizados
- **Comando:**
  ```bash
  python3 -m pytest tests/unit tests/integration -v
  ```
- **O que mostrar:** Destaque na tela que todos os **15 testes automatizados** passaram com 100% de sucesso (validando Lamport, Ricart-Agrawala, 2PC, Heartbeat e concorrência multithread).

#### 5.2. Benchmarking Experimental Multithread
- **Comando:**
  ```bash
  python3 scripts/benchmark.py --host http://localhost:8000 --output results/experiments.csv --reqs 30
  ```
- **Exibir os resultados consolidados:**
  ```bash
  column -s, -t < results/experiments.csv | head -n 15
  ```
- **O que destacar na análise:**
  - *"Avaliamos o comportamento variando os níveis de concorrência com 1, 5, 10 e 20 threads de clientes simultâneos."*
  - *"O relatório exportado em CSV apresenta vazão de requisições por segundo e os percentis de latência p50, p95 e p99."*
  - *"Conforme a concorrência aumenta, observamos o impacto natural da disputa pela seção crítica distribuída e das rodadas de mensagens de consenso."*

#### 5.3. Encerramento:
- *"Com isso, demonstramos a implementação manual e correta de dois pares de algoritmos complementares, a arquitetura com contêineres, testes reproduzíveis e o tratamento de falhas. Obrigado!"*

---

## 3. Checklist Rápido Pré-Gravação

- [ ] Contêineres reconstruídos limpos antes de gravar: `docker compose down -v && docker compose up -d`
- [ ] Utilitário `jq` instalado no ambiente para formatar saídas no terminal (caso não tenha, remova `| jq .`)
- [ ] Terminal com fonte ampliada (tamanho 16 ou superior) e contraste adequado
- [ ] Navegador com a aba [`docs/images/slide-one-pager.png`](docs/images/slide-one-pager.png) ou [`docs/visualizar-diagramas.html`](docs/visualizar-diagramas.html) já carregada
- [ ] Ambos os integrantes posicionados e com áudio testado
