# CFAW News development

- This is a standalone Python/React project. Runtime code must not depend on the legacy competition platform.
- Keep domain rules independent from HTTP/UI: immutable evidence, goal versions, no late publication after cancellation, explicit approval, idempotent calendar writes.
- `baseline` is lexical retrieval, not LLM reasoning. Never present fixture or mocked results as live-model validation.
- Preserve `data/archive/articles.json` and migration provenance. Curator summaries, publisher quotes and model explanations are different evidence types.
- Keep credentials and local user data out of Git. Do not read or copy another project's credentials.
- Run `python -m ruff check backend tests evals`, `python -m pytest -q`, `python evals/run_baseline.py`, and `npm run build` in `frontend` for relevant changes.
- Frontend `dist` is generated. Change source and rebuild.
- API is a local single-user starter. Do not claim authentication, production deployment, durable checkpoints, vector retrieval or algorithm gains before implementing and verifying them.
