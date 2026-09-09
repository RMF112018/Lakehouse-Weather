SHELL := /bin/bash

.PHONY: help bootstrap validate gate1 up down logs backup health submodules

help:
	@printf '%s\n' \
	  'make bootstrap   - initialize local directories and submodules' \
	  'make validate    - validate repository/config structure' \
	  'make gate1       - run RF/USB acceptance test' \
	  'make up          - start application stack after Gate 1 passes' \
	  'make down        - stop application stack' \
	  'make logs        - tail application logs' \
	  'make backup      - archive persistent WeeWX data' \
	  'make health      - check service health' \
	  'make submodules  - sync/update pinned upstream submodules'

bootstrap:
	./scripts/bootstrap.sh

validate:
	./scripts/validate.sh

gate1:
	./scripts/gate1-rf-test.sh

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

backup:
	./scripts/backup.sh

health:
	./scripts/healthcheck.sh

submodules:
	git submodule sync --recursive
	git submodule update --init --recursive
