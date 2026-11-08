MAIN = relatorio
LATEX = pdflatex
BIBTEX = bibtex

.PHONY: all clean datos pdf copy

all: pdf copy

pdf: datos
	$(LATEX) $(MAIN).tex
	$(BIBTEX) $(MAIN) || true
	$(LATEX) $(MAIN).tex
	$(LATEX) $(MAIN).tex

datos:
	python3 scripts/csv_to_latex.py -i ../results/experiments.csv -o dados/experiments.tex
	python3 scripts/csv_to_latex.py --summary -i '../results/run[1-3].csv' -o dados/experiments_summary.tex

copy: $(MAIN).pdf
	cp $(MAIN).pdf ../relatorio_mc714_trabalho2.pdf

clean:
	rm -f $(MAIN).aux $(MAIN).bbl $(MAIN).blg $(MAIN).log $(MAIN).out $(MAIN).pdf
