# MC714 — Ambiente Docker (ingressos)

Ambiente de referência para o Trabalho 2: **1 API FastAPI** e **PostgreSQL em primary + 3 réplicas** (streaming replication). Visível no **Docker Desktop** como projeto `mc714-tickets`.

Escritas no **primary** (`postgres-primary`) são replicadas para **`postgres-replica-1`**, **`postgres-replica-2`** e **`postgres-replica-3`**.

## Pré-requisitos

- Docker Desktop ou Docker Engine + Docker Compose v2

## Subir o ambiente

```bash
cd distributed-algorithm
chmod +x db/replica/replica-entrypoint.sh db/init/00-replication.sh
docker compose build
docker compose up -d
docker compose ps
```

Na **primeira** subida, cada réplica executa `pg_basebackup` do primary (pode levar ~1 minuto até ficarem healthy).

Se você usou a versão anterior (3 Postgres independentes), **apague os volumes antigos**:

```bash
docker compose down -v
docker compose up -d
```

### Verificação rápida

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
curl http://localhost:8000/databases
```

Em `/databases`, espere **1 nó** com `"role": "primary"` e **3** com `"role": "replica"`.

Teste de replicação:

```bash
docker exec mc714-postgres-primary psql -U tickets -d tickets -c \
  "UPDATE events SET tickets_remaining = 7 WHERE id = 1;"
docker exec mc714-postgres-replica-2 psql -U tickets -d tickets -c \
  "SELECT tickets_remaining FROM events WHERE id = 1;"
```

Os quatro devem mostrar o mesmo valor (possível atraso de milissegundos nas réplicas).

### Parar e resetar dados

```bash
docker compose down
docker compose down -v   # remove volumes (primary reinicializa schema + seed)
```

## Serviços e portas

| Serviço        | Contêiner                   | Host → contêiner | Papel              |
|----------------|-----------------------------|------------------|--------------------|
| API            | `mc714-api`                 | 8000 → 8000      | Aplicação          |
| PostgreSQL     | `mc714-postgres-primary`    | 5432 → 5432      | **Primary** (RW)   |
| Réplica 1      | `mc714-postgres-replica-1`| 5433 → 5432      | Standby (RO*)      |
| Réplica 2      | `mc714-postgres-replica-2`| 5434 → 5432      | Standby (RO*)      |
| Réplica 3      | `mc714-postgres-replica-3`| 5435 → 5432      | Standby (RO*)      |
| pgAdmin        | `mc714-pgadmin`           | 5050 → 80        | UI web (dev)       |

\* Réplicas aceitam leitura em hot standby; a API usará o primary para escrita quando houver endpoints de compra.

Rede Docker: `mc714-net`.

## Credenciais (somente desenvolvimento)

**PostgreSQL (aplicação):**

- Usuário: `tickets`
- Senha: `tickets_dev`
- Banco: `tickets`

**Replicação (interno):**

- Usuário: `replicator`
- Senha: `replicator_dev`

**pgAdmin:**

- URL: http://localhost:5050
- E-mail: `admin@example.com`
- Senha: `admin_dev`

### Registrar servidores no pgAdmin

Use o **nome do serviço** como host:

| Nome sugerido | Host                 | Porta |
|---------------|----------------------|-------|
| primary       | `postgres-primary`   | 5432  |
| replica-1     | `postgres-replica-1` | 5432  |
| replica-2     | `postgres-replica-2` | 5432  |
| replica-3     | `postgres-replica-3` | 5432  |

Usuário/senha: `tickets` / `tickets_dev`.

## `psql` a partir do host

```bash
PGPASSWORD=tickets_dev psql -h localhost -p 5432 -U tickets -d tickets   # primary
PGPASSWORD=tickets_dev psql -h localhost -p 5433 -U tickets -d tickets   # réplica 1
PGPASSWORD=tickets_dev psql -h localhost -p 5434 -U tickets -d tickets   # réplica 2
PGPASSWORD=tickets_dev psql -h localhost -p 5435 -U tickets -d tickets   # réplica 3
```

Verificar papel:

```sql
SELECT pg_is_in_recovery();  -- false = primary, true = réplica
```

No primary, ver slots/conexões de replicação:

```sql
SELECT application_name, state, sync_state FROM pg_stat_replication;
```

## Modelo de dados

Scripts em [`db/init/`](db/init/) (somente no **primary** na primeira inicialização):

- **`users`** — compradores
- **`events`** — shows (`total_tickets`, `tickets_remaining`)
- **`ticket_purchase_events`** — tentativas/registros de compra

Seed: três usuários e o evento **Show MC714** com **10 ingressos**.

## Variáveis da API

| Variável       | Padrão                                              |
|----------------|-----------------------------------------------------|
| `DB_PRIMARY`   | `postgres-primary`                                  |
| `DB_REPLICAS`  | `postgres-replica-1,postgres-replica-2,postgres-replica-3` |
| `DB_PORT`      | `5432`                                              |
| `DB_USER`      | `tickets`                                           |
| `DB_PASSWORD`  | `tickets_dev`                                       |
| `DB_NAME`      | `tickets`                                           |

## Próximos passos (experimento MC714)

1. **Race condition:** `POST /purchase` escrevendo só no **primary** sem locking adequado — medir oversell; comparar leituras nas **réplicas** ( eventual consistência ).
2. **Sobrecarga:** carga concorrente na API → saturar conexões/WAL no primary e observar `replication_lag_ms` em `/databases`.
3. **Falhas:** parar uma réplica (`docker stop mc714-postgres-replica-1`) e verificar recuperação ao subir de novo (`pg_basebackup` só na primeira init; reinício usa dados existentes).

A API ainda **não** expõe `POST /purchase`; apenas health checks e status de replicação.
