# Initial Test Matrix

This matrix maps the highest-risk modules to the first test assets prepared in
the repository.

| Module | Priority | Primary risk | Initial test coverage |
| --- | --- | --- | --- |
| Job orchestration and pipeline flow | Critical | Job stuck in `QUEUED/RUNNING`, invalid params, status drift | Existing API tests, Postman requests, manual checklist, k6 polling |
| Taxonomy building and quality evaluation | Critical | Invalid graph, failed quality gate, low-value output | Existing worker tests, manual checklist |
| Document ingestion and chunking | High | Unsupported files, empty text, chunk errors | Existing worker tests, Postman upload request, manual checklist |
| RabbitMQ service integration | High | Message routing/retry/DLQ failures | Existing worker tests, manual end-to-end run |
| Taxonomy API and manual editing | Medium-High | Broken tree/search/export/edit operations | Postman requests, manual checklist, future UI e2e |
| Frontend navigation and workflow visibility | Medium | Usability issues, missing state refresh, broken actions | Manual checklist, future UI e2e |

## Current strategy

- Keep unit/integration tests close to the service code
- Use `qa/postman/` for repeatable API smoke/regression collections
- Use `qa/k6/` for low-cost load checks of critical endpoints
- Use `qa/manual/` for evidence-oriented end-to-end validation

## CI direction

The intended CI split is:

1. `api-service` tests
2. `worker-service` tests
3. `web-app` lint + typecheck + build
4. optional smoke checks against a composed environment
