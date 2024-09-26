remote_server := CHANGEME
remote_wheel_dir=/shared/wheels  # CHANGEME

get_value = $(shell sed -n "s/\($1 \?= \?\)\(.*\)/\2/p" pyproject.toml)
pkg_name := $(call get_value,name)
modules := $(pkg_name)
version := $(call get_value,version)
wheel := $(pkg_name)-$(version)-py3-none-any.whl
docker_image := $(pkg_name)
image_file := $(pkg_name).tar
remote_docker_compose := /shared/dock/$(pkg_name)/docker-compose.yml
registry_docker_compose := /shared/dock/registry/docker-compose.yml


define remote_command
	docker compose -f $(remote_docker_compose) down && \
	docker compose -f $(remote_docker_compose) pull && \
	docker compose -f $(remote_docker_compose) up -d && \
	docker compose -f $(registry_docker_compose) exec -it registry /bin/registry garbage-collect /etc/docker/registry/config.yml && \
	docker container prune -f && \
	docker image prune -f
endef


.PHONY: server
server:
	make build && \
	scp "dist/$(wheel)" $(remote_server):$(remote_wheel_dir) && \
	ssh $(remote_server) "pip3 uninstall -y $(pkg_name) && pip3 install $(remote_wheel_dir)/$(wheel)" && \
	ssh pulsar "pip3 uninstall -y $(pkg_name) && pip3 install $(remote_wheel_dir)/$(wheel)"

.PHONY: build
build:
	make fix && python -m build

.PHONY: docker
docker:
	make fix && \
	docker compose down && \
	docker compose build && \
	docker compose push && \
	ssh pulsar "$(remote_command)"

.PHONY: fix
fix:
	source venv/bin/activate && \
	pyright $(modules) && \
	pycln -a $(modules) && \
	isort --profile black $(modules) && \
	black $(modules)




