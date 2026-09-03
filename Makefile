.PHONY: data install analysis clean

DATA_URL := https://raw.githubusercontent.com/datasets/s-and-p-500-companies-financials/main/data/constituents-financials.csv
DATA_FILE := data/raw/sp500_constituents_financials.csv

data: $(DATA_FILE)

$(DATA_FILE):
	@mkdir -p data/raw
	curl -fsSL $(DATA_URL) -o $@
	@echo "fetched $$(wc -l < $@) lines"

install:
	pip install -r requirements.txt

analysis: $(DATA_FILE)
	python -m src.run_analysis

clean:
	rm -rf outputs/figures/*.png outputs/tables/*.csv outputs/metrics.json data/processed/*
