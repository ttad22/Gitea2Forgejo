.PHONY: help test journal-demo

help:                                ## Show this help text.
	@awk 'BEGIN {FS = ":.*?## "}; /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

test:                                ## Run the full pytest suite from the repo root.
	python3 -m pytest tests/ -q

journal-demo:                        ## Print a sample journal trace and verify its hash chain.
	python3 scripts/journal_demo.py
