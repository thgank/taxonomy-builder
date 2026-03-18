# QA Workspace

This directory stores QA artifacts that should live with the codebase but do
not belong inside a single service. The goal is to keep black-box,
cross-service, and research-oriented testing assets versioned alongside the
application.

## Why `qa/` lives inside this repository

- `api-service` already contains backend tests in `src/test`
- `worker-service` already contains worker tests in `tests`
- the project depends on coordinated versions of API, worker, web app, and
  infrastructure
- assignment deliverables require reproducible evidence tied to the same
  codebase revision

For this project, keeping QA assets inside the monorepo is simpler and more
reliable than maintaining a separate QA repository.

## Structure

- `docs/` - strategy notes, test matrix, assignment-ready QA documents
- `k6/` - load and smoke scenarios for API-level testing
- `manual/` - manual checklists and exploratory scenarios
- `postman/` - Postman collection and local environment template
- `test-data/` - guidance for small reproducible sample files

## Existing automated tests in the repo

- `api-service/src/test` - Spring Boot tests for API and service logic
- `worker-service/tests` - pytest coverage for ingestion, taxonomy building,
  evaluation, and consumer behavior

## Quick start

1. Start the stack:

```bash
docker compose up --build -d
```

2. Confirm service health:

- API: `http://localhost:8080/swagger-ui.html`
- Worker: `http://localhost:8081/health`
- RabbitMQ UI: `http://localhost:15672`

3. Import the Postman files from `qa/postman/`.

4. Run a k6 smoke script:

```bash
k6 run qa/k6/core-api-smoke.js
```

5. Use the manual checklist in `qa/manual/core-workflow-checklist.md` for
end-to-end validation and evidence collection.

## Recommended next additions

- UI end-to-end tests once the main web flows stabilize
- CI workflow to run service tests plus lightweight QA smoke checks
- small sanitized sample files under `qa/test-data/`
