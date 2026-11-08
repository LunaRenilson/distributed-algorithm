# MC714 Trabalho 2 — pacote Overleaf

Pasta **autocontida** para enviar ao [Overleaf](https://www.overleaf.com) (upload ZIP ou cópia do projeto).

## Como usar no Overleaf

1. **Novo projeto** → **Upload Project** → compacte esta pasta em um `.zip` e envie.
2. Defina o **Main document** como `main.tex` (Menu → Main document).
3. **Compiler:** pdfLaTeX.
4. Compile (Recompile).

## Conteúdo

| Arquivo / pasta | Função |
|-----------------|--------|
| `main.tex` | Documento principal (igual a `relatorio.tex`) |
| `relatorio.tex` | Cópia para edição local opcional |
| `ieeeextras.sty` | Macros `\pendente{}` e `\medir{}` |
| `referencias.bib` | Bibliografia |
| `IEEEtran.cls`, `IEEEtran.bst` | Classe IEEE (já incluídas; o Overleaf também costuma ter) |
| `dados/*.tex` | Tabelas (ambiente, experimentos, heartbeat) |
| `figuras/*.png` | Diagramas do relatório |

## Atualizar tabelas a partir do repositório

No clone do projeto (com Docker e benchmark rodados):

```bash
./relatorio/scripts/sync_overleaf.sh
```

Reenvie o ZIP ao Overleaf ou sincronize os arquivos em `dados/` e `figuras/`.

## Antes de entregar

Substitua na seção *Informações de entrega* os `\pendente{...}` pelos links reais do GitLab e do vídeo.
