# Status da coleta (ambiente de build do relatório)

Durante a geração do relatório, o daemon Docker não estava acessível ao usuário
(`permission denied` em `/var/run/docker.sock`). O `experiments.csv` atual
reflete uma execução anterior com **API/banco indisponíveis** (taxa de sucesso
0\% em Lamport/2PC) ou **estoque esgotado** (mutex).

**Ação necessária antes da entrega:**

```bash
newgrp docker   # ou adicionar o usuário ao grupo docker
docker compose up -d --build
./scripts/run_experiments.sh
cd relatorio && make dados pdf copy
```

Após isso, substituir a Tabela de desempenho no PDF e remover o marcador
`\pendente` das repetições em `dados/ambiente.tex`.
