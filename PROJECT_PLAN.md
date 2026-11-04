## Planejamento do Projeto – Banco de Dados Distribuído (MC714)

### 1. Propósito do projeto e serviços
| Serviço | Papel | Motivo |
|---|---|---|
| **api** (FastAPI) | Expor API HTTP/2 multithread. Orquestra os algoritmos distribuídos e interage com o cliente. | Única camada de lógica que precisamos escrever. |
| **postgres‑primary** | Banco PostgreSQL que armazena os dados da aplicação e o log de *Two‑Phase Commit* (2PC). | Persistência durável e ponto de origem da replicação. |
| **postgres‑replica‑1 / 2 / 3** | Réplicas de leitura mantidas por streaming replication. | Fornecem alta disponibilidade e atuam como nós lógicos dos algoritmos. |
| **pgadmin** (opcional) | Interface web para inspeção do banco. | Facilita debugging, não participa dos algoritmos. |
| **helpers (side‑car)** | Pequenos scripts Python que rodam dentro de cada réplica. Eles recebem e respondem a mensagens de Lamport, Ricart‑Agrawala e 2PC. | Transformam a réplica em um nó ativo do sistema distribuído. |

### 2. Algoritmos e sua aplicação
| Algoritmo | Ideia resumida | Onde é usado no projeto |
|---|---|---|
| **Lamport Logical Clock** | Cada nó mantém um contador inteiro; ao enviar/receber mensagens ele o incrementa. | `lamport.py` – o **api** incrementa o relógio antes de registrar um evento e o helper atualiza seu relógio ao receber `POST /lamport/event`. |
| **Ricart‑Agrawala (exclusão mútua)** | Um nó pede permissão a todos os outros usando timestamps; entra na seção crítica só após receber a maioria dos "OK". | `ricart_agrawala.py` – o **api** solicita lock via `POST /mutex/request` ao helper de cada réplica; o helper responde com `OK` quando todos concordam. |
| **Two‑Phase Commit (2PC)** | Coordenador envia fase *prepare* para todos os participantes; se todos aceitam, envia *commit*, caso contrário *abort*. | `two_phase_commit.py` – o **api** age como coordenador, grava um registro *prepare* na tabela `two_phase_log` (primary) e chama `/tx/prepare`, `/tx/commit` ou `/tx/abort` nos helpers. |
| **Primary‑Backup replication (PostgreSQL)** | O primary grava os dados e replica de forma (quase) síncrona para as réplicas. | Configurada no `compose.yaml`. O 2PC garante que a escrita só é considerada concluída quando o primary e as réplicas confirmam o commit. |
| **Heartbeat / SWIM (detecção de falhas)** | Verifica periodicamente se os nós ainda estão vivos; SWIM faz isso via gossip. | `heartbeat.py` – o helper executa `SELECT 1` contra seu PostgreSQL e notifica o **api** em caso de falha. Opcionalmente, pode ser habilitado um detector SWIM. |

### 3. Integração das partes (pipeline)
```mermaid
flowchart LR
    subgraph Client
        C[Cliente (HTTP)]
    end

    subgraph API
        A1[FastAPI (multithread)]
        A2[LamportClock]
        A3[Ricart‑Agrawala]
        A4[Two‑Phase Commit]
        A5[Heartbeat / SWIM]
    end

    subgraph DBCluster
        P[Postgres Primary]
        R1[Replica‑1]
        R2[Replica‑2]
        R3[Replica‑3]
    end

    subgraph Helpers
        H1[Side‑car – Replica‑1]
        H2[Side‑car – Replica‑2]
        H3[Side‑car – Replica‑3]
    end

    C -->|request| A1
    A1 -->|increment| A2
    A1 -->|acquire lock (opt)| A3
    A3 -->|REQ/REPLY| H1
    A3 -->|REQ/REPLY| H2
    A3 -->|REQ/REPLY| H3
    A1 -->|start 2PC| A4
    A4 -->|prepare| P
    A4 -->|prepare| H1
    A4 -->|prepare| H2
    A4 -->|prepare| H3
    P -->|replicates| R1 & R2 & R3
    A5 -->|ping| P
    A5 -->|detect fail| H1 & H2 & H3
    P -->|commit| R1 & R2 & R3
    A1 -->|response| C
```

#### Funções dos helpers (side‑car)
1. **Lamport** – recebe `POST /lamport/event`, atualiza seu contador e devolve o timestamp.
2. **Mutex (Ricart‑Agrawala)** – recebe `POST /mutex/request`/`/release`, mantém fila de pedidos, responde `OK` quando a maioria concorda.
3. **2PC participant** – responde a `/tx/prepare` gravando um registro temporário e, após o commit/abort, aplica ou desfaz a operação.
4. **Heartbeat** – executa `SELECT 1` periodicamente; em falha, notifica o **api**.
5. **Comunicação peer‑to‑peer** – conhece os endereços dos outros helpers e troca mensagens de lock/comunicação de falha (SWIM opcional).

### 4. Estrutura de diretórios (novas pastas)
```
project-root/
├─ server/                     # código existente do FastAPI
│   ├─ main.py                # ponto de entrada – será extendido
│   ├─ db.py                  # cliente DB atual
│   ├─ algorithms/
│   │   ├─ __init__.py
│   │   ├─ lamport.py
│   │   ├─ ricart_agrawala.py
│   │   ├─ two_phase_commit.py
│   │   └─ heartbeat.py
│   ├─ schemas/               # modelos Pydantic
│   └─ metrics.py            # Prometheus exporter (opcional)
├─ tests/
│   ├─ unit/                # testes de cada algoritmo
│   └─ integration/         # teste end‑to‑end usando Docker‑Compose
├─ scripts/
│   ├─ run_experiments.sh   # variações de carga e coleta de métricas
│   └─ generate_report.py    # converte CSV em markdown / gráficos
├─ compose.yaml               # será atualizado (porta metrics, side‑car mount)
└─ PROJECT_PLAN.md           # **este documento**
```

### 5. Próximos passos (curto prazo)
1. **Criar o script `mutex_helper.py`** e adicioná‑lo ao `docker‑compose` (montagem de volume).  
2. **Implementar os módulos** `lamport.py`, `ricart_agrawala.py`, `two_phase_commit.py` e `heartbeat.py` dentro de `server/algorithms`.  
3. **Adicionar endpoints** ao `main.py` para `POST /lamport/event`, `POST /mutex/request`, `POST /tx/prepare` …  
4. **Escrever testes unitários** (pytest) para cada algoritmo.  
5. **Atualizar `compose.yaml`** com a porta de métricas (`8001`) e o comando que inicia o side‑car.  
6. **Rodar integração** (`docker compose up -d && pytest -n auto`).  
7. **Coletar métricas** e gerar o relatório final.

> **Aprovação** – Todos os itens acima foram discutidos e confirmados com o professor. Podemos seguir com a implementação.

