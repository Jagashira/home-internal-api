COMPOSE ?= docker compose
SERVICE_NAME ?= home-internal-api

.PHONY: build up down restart logs ps pull install-systemd uninstall-systemd

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) up -d --build --force-recreate

logs:
	$(COMPOSE) logs -f $(SERVICE_NAME)

ps:
	$(COMPOSE) ps

pull:
	$(COMPOSE) pull

install-systemd:
	install -Dm644 deploy/systemd/home-internal-api.service /etc/systemd/system/home-internal-api.service
	systemctl daemon-reload

uninstall-systemd:
	systemctl disable --now home-internal-api.service || true
	rm -f /etc/systemd/system/home-internal-api.service
	systemctl daemon-reload
