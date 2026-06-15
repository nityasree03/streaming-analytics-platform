# Streamlit Dashboard

## Running

```bash
streamlit run dashboard/app.py
```

Requires Postgres reachable at `localhost:5433` (the host-mapped port from
docker-compose.yml).

## AI-Powered "Ask a Question" Feature

The dashboard includes a natural-language-to-SQL feature powered by the
Anthropic API (Claude). To enable it, set the `ANTHROPIC_API_KEY`
environment variable before running Streamlit:

```bash
export ANTHROPIC_API_KEY="your-key-here"
streamlit run dashboard/app.py
```

Without this variable set, the dashboard runs normally but the "Ask a
Question" section will display a message indicating the feature requires
an API key.

### How it works
1. User types a question in plain English (e.g. "Which feature is used most often?")
2. The question + database schema description are sent to Claude, which
   generates a read-only SQL `SELECT` query
3. The query is validated (must start with SELECT/WITH, must not contain
   data-modifying keywords like INSERT/UPDATE/DELETE/DROP)
4. The validated query is executed against Postgres in a read-only
   transaction
5. Results are displayed as a table, alongside the generated SQL for
   transparency

### Safety design
LLM-generated SQL is never trusted blindly. Three layers of defense:
- **Prompt-level**: the system prompt instructs the model to generate
  only read-only SELECT/WITH queries against a documented schema
- **Validation-level**: generated SQL is checked against a denylist of
  data/schema-modifying keywords (INSERT, UPDATE, DELETE, DROP, ALTER,
  TRUNCATE, GRANT, CREATE, etc.) before execution
- **Database-level**: queries run inside a `SET TRANSACTION READ ONLY`
  transaction, so even a query that slipped through validation could not
  modify data
