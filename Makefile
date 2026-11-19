# One command reproduces everything:  make   (or, without make: bash scripts/reproduce.sh)
# Creates .venv, downloads + hash-checks the raw CSVs, builds and tests every layer,
# reconciles the headline numbers, and generates dbt docs with the lineage graph.
.PHONY: all setup data deps build verify recommendation ontology story targets prove-tests experiments docs clean
all setup data deps build verify recommendation ontology story targets prove-tests experiments docs clean:
	bash scripts/reproduce.sh $@
