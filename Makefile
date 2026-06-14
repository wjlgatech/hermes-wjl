# wjlgatech/hermes-wjl — convenience targets to keep `main` locked to official
# Hermes (NousResearch/hermes-agent:main). The hourly GitHub Action does this
# automatically; these are the manual, always-reliable path.
.PHONY: sync merge help

help: ## Show these targets
	@grep -E '^[a-z]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/ —/' | sort

sync: ## Pull the latest official Hermes into main:   make sync
	@bash scripts/wjl-sync-upstream.sh

merge: ## Sync upstream THEN merge a feature:   make merge BRANCH=feat/foo
	@test -n "$(BRANCH)" || { echo "usage: make merge BRANCH=<feature-branch>"; exit 1; }
	@bash scripts/wjl-merge-feature.sh "$(BRANCH)"
