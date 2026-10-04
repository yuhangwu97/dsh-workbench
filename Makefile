.PHONY: test build-python build-typescript docker

TEST_ENV = PYTHONPATH=packages/python

test:
	$(TEST_ENV) python3 -m pytest tests -q
	cd packages/typescript && npm test

build-python:
	python3 -m pip wheel --no-deps --wheel-dir /tmp/dsh-workbench-dist packages/python

build-typescript:
	cd packages/typescript && npm run build && npm pack --dry-run

docker:
	docker build --pull=false -t dsh-workbench:local .
