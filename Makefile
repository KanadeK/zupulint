.PHONY: bootstrap lint format-check typecheck test test-frontend test-e2e build package docs docker-build security schema-check verify

bootstrap:
	uv sync --frozen --all-extras --dev
	corepack pnpm install --frozen-lockfile

lint:
	uv run ruff check src tests scripts
	corepack pnpm --dir apps/web lint

format-check:
	uv run ruff format --check src tests scripts
	corepack pnpm --dir apps/web format:check

typecheck:
	uv run mypy src scripts tests
	corepack pnpm --dir apps/web typecheck

test:
	uv run pytest
	uv run python scripts/check_coverage.py

test-frontend:
	corepack pnpm --dir apps/web test:coverage

test-e2e:
	corepack pnpm --dir apps/web exec playwright install --with-deps chromium
	corepack pnpm --dir apps/web e2e

build:
	corepack pnpm --dir apps/web build
	uv run python scripts/sync_web_assets.py
	uv build

package: build
	uv run python scripts/package_release.py

docs:
	uv run mkdocs build --strict

docker-build:
	docker build -t zupulint:local .

security:
	uv run pip-audit --skip-editable
	corepack pnpm --dir apps/web audit --prod --registry=https://registry.npmjs.org --audit-level high
	uv run python scripts/secret_scan.py

schema-check:
	uv run python scripts/verify_release.py

verify: lint format-check typecheck test test-frontend test-e2e build package docs docker-build security schema-check
	uv run python scripts/smoke_test.py
	git diff --check
