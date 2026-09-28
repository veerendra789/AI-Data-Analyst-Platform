# Signal AI Data Analyst Platform

Signal is a production-oriented analytics workspace for turning CSV data into inspectable answers. Users can upload private datasets, profile quality, ask natural-language questions, inspect the generated read-only SQL, visualize results, forecast trends, and generate grounded reports.

## Problem statement

Analysts often lose time moving between spreadsheets, SQL editors, notebooks, and presentation tools. Signal keeps the workflow in one accountable surface: every answer is tied to an owned dataset, bounded SQL query, returned rows, and a visible explanation.

## Features

- Authenticated private workspaces with Argon2 passwords and JWT sessions
- CSV upload validation, preview, schema inference, ownership enforcement, and deletion
- Data quality profiling, distributions, category summaries, correlations, and outlier detection
- Natural-language analysis with deterministic development mode or an OpenAI-compatible provider
- Read-only DuckDB SQL validation with query timeout and result bounds
- Responsive charts, result tables, SQL inspection, and follow-up analysis history
- Forecasting, observational root-cause analysis, and structured grounded reports
- Redis caching, rate limiting, asynchronous report jobs, and PostgreSQL persistence
- Dashboard workspace summary, report history, profile page, loading states, error states, and mobile navigation
- AI Data Structurer for reviewing and saving cleaned CSV datasets before analysis

## Phase 1 foundation

- React + TypeScript + Vite frontend shell
- Tailwind CSS styling with React Router, TanStack Query, Axios, Recharts, and Lucide dependencies ready
- FastAPI backend with OpenAPI documentation, CORS configuration, authentication, CSV datasets, and DuckDB analysis
- PostgreSQL and Redis services provisioned through Docker Compose
- Environment variable template and persistent upload/processed data directories
- Separate frontend and backend Docker images

Future phases will add richer profiling, anomaly detection, forecasting, reporting, caching, and background processing.

## Database migrations

From the `backend` directory, with PostgreSQL running and `DATABASE_URL` configured:

```powershell
alembic upgrade head
```

The initial migration creates `users`, `datasets`, `dataset_columns`, `queries`, `chat_messages`, `analysis_results`, `reports`, and `visualizations`.

## Authentication

Authentication endpoints:

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me` (Bearer token required)

Passwords are hashed with Argon2. JWT access tokens use `JWT_SECRET`, and the backend exposes `require_roles(...)` for role-protected endpoints. The frontend protects `/dashboard`, persists the access token for the session, and provides logout at the top right of the workspace.

## Dataset management

Phase 4 supports authenticated CSV dataset management:

- `POST /api/datasets/upload`
- `GET /api/datasets`
- `GET /api/datasets/{dataset_id}`
- `GET /api/datasets/{dataset_id}/preview`
- `DELETE /api/datasets/{dataset_id}`

Uploads are validated as UTF-8 CSV files, limited by `MAX_UPLOAD_SIZE`, stored with UUID-based server filenames, and associated with the authenticated owner. The frontend provides the dataset list at `/datasets` and the dataset detail/preview view at `/datasets/{id}`.

## AI Data Structuring and Preparation

The protected `/data-preparation` page and `/api/data-preparation` API prepare raw CSV files before analysis. The workflow preserves the original upload, detects schema and quality concerns, proposes reviewable transformations, previews proposed changes, and writes a separate cleaned CSV artifact.

Supported deterministic checks include missing values, duplicate rows and headers, empty or constant columns, whitespace, capitalization variants, numeric text with recognized currency symbols or separators, ambiguous dates, invalid values, and potential outliers. Column names can be standardized to safe unique identifiers, while identifier-like values such as IDs, postal codes, phone numbers, and product codes remain strings to preserve leading zeros.

Users must approve transformations before they are applied. Available operations include approved renames, type conversion, whitespace trimming, explicit category mappings, duplicate-row removal, reviewed missing-value strategies, recognized numeric parsing, and selected column removal. Ambiguous dates require an explicit format choice; imputation and placeholder markers are never applied by default. Previews are limited to 100 rows, preparation analysis supports up to 250,000 rows and 300 columns, and CSV upload limits continue to follow the existing server configuration.

After applying changes, users can compare before-and-after statistics, download the cleaned CSV, or save it to Datasets. Saving uses the existing dataset metadata, ownership, storage, profiling, DuckDB, analyst, chart, forecast, and report workflows, with a `source_preparation_id` lineage reference. The preparation session stores metadata and server-side artifact paths rather than full datasets in PostgreSQL. The current version supports UTF-8 CSV only and does not use an LLM for row-level cleaning; deterministic preparation remains available when an LLM provider is unavailable.

API operations are `POST /api/data-preparation/analyze`, `GET /api/data-preparation/{id}`, `GET /api/data-preparation/{id}/preview`, `POST /api/data-preparation/{id}/preview`, `POST /api/data-preparation/{id}/apply`, `POST /api/data-preparation/{id}/save`, `GET /api/data-preparation/{id}/download`, and `DELETE /api/data-preparation/{id}`. All operations require authentication and are scoped to the owning user.

## AI Analyst

The analysis workflow is available at `POST /api/analysis/query` and requires a bearer token. It retrieves the owned dataset schema, asks the configured provider for structured SQL, validates the SQL as read-only, executes it against the owned CSV through DuckDB, and generates chart metadata plus an explanation from the returned rows. Chat history is available at `GET /api/analysis/history/{dataset_id}`.

Set `LLM_PROVIDER=development` for local deterministic verification. Set `LLM_PROVIDER=openai-compatible`, `LLM_API_KEY`, `LLM_MODEL`, and optionally `LLM_BASE_URL` to use a compatible production LLM endpoint. The frontend analyst route is `/datasets/{id}/analyst`.

## Data intelligence

Milestone 3 adds authenticated data profiling and anomaly detection:

- `POST /api/analysis/eda/{dataset_id}`
- `POST /api/analysis/anomalies/{dataset_id}` with `{ "column": "numeric_column" }`

Profiling returns quality totals, missing percentages, duplicate rows, inferred numeric/categorical/date columns, numeric statistics, category summaries, correlations, distributions, and IQR outlier information. Anomaly detection uses a seeded Isolation Forest when the selected numeric data is suitable and returns anomaly scores and records. DuckDB analytical queries are read-only, limited to the registered dataset view, bounded to 500 result rows, and interrupted after `QUERY_TIMEOUT_SECONDS` (default 10 seconds).

Milestone 5 advanced analysis endpoints:

- `POST /api/analysis/forecast/{dataset_id}` with `date_column`, `target_column`, and optional `periods`
- `POST /api/analysis/root-cause/{dataset_id}` with a question and optional metric/dimension columns

Forecasting uses a chronological linear trend model and returns historical and future values. Root-cause analysis reports observed averages and associated dimensions while explicitly avoiding unsupported causal claims. Dataset pages render responsive Recharts views for result charts, EDA distributions, category counts, and forecasts.

## Reporting and background processing

Milestone 6 adds authenticated reporting at `/api/reports` and the frontend Reports page at `/reports`:

- `POST /api/reports/generate` creates a grounded structured report synchronously.
- `POST /api/reports/jobs` starts asynchronous report generation.
- `GET /api/reports/jobs/{job_id}` returns `PENDING`, `PROCESSING`, `COMPLETED`, or `FAILED` for the owning user.
- `GET /api/reports` lists report history with pagination.

Reports contain dataset overview, quality metrics, numeric metrics, distributions, outliers, grounded findings, saved analysis insights, and an automatically generated forecast when the dataset has usable date and numeric columns. Redis stores cache entries, rate-limit counters, and job state; local memory remains a development fallback when Redis is unavailable. Analytical cache keys include the authenticated user, dataset identity, and normalized request parameters.

Dataset listing supports `offset` and bounded `limit` parameters. Expensive analysis, EDA, anomaly, forecast, root-cause, and report endpoints are rate limited. API errors include an `error.code` and safe `error.message` without exposing stack traces.

For deployment, set `APP_ENV=production` and replace the placeholder `JWT_SECRET` and `POSTGRES_PASSWORD` values. Production mode rejects placeholder or short JWT secrets at startup. The Compose frontend synchronizes its persistent dependency volume before starting Vite.

## Run locally

The most reproducible path is Docker Compose. For a host-native development loop, first start PostgreSQL and Redis with Compose, then use host-compatible overrides for the backend:

```powershell
Copy-Item .env.example .env
docker compose up -d postgres redis

# Host-native backend values; Docker service names are not resolvable from Windows.
$env:DATABASE_URL="postgresql+psycopg://analyst:change-this-development-password@localhost:5432/ai_data_analyst"
$env:REDIS_URL="redis://localhost:6379/0"
$env:UPLOAD_DIRECTORY="data/uploads"

python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

In one terminal, from the repository root:

```powershell
.venv\Scripts\Activate.ps1
uvicorn app.main:app --app-dir backend --reload --port 8000
```

In a second terminal:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Run `alembic upgrade head` from `backend` when managing the host-native database manually. The backend container runs this migration automatically on startup.

Open the frontend at http://localhost:5173 and the API docs at http://localhost:8000/docs.

## Docker

Docker Compose starts the frontend, backend, PostgreSQL, and Redis services:

```powershell
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432
- Redis: localhost:6379

Stop services with `docker compose down`. Add `-v` only when you intentionally want to remove the local PostgreSQL volume.

## GitHub Pages frontend deployment

The frontend deploys independently from the backend through `.github/workflows/deploy-frontend.yml` when changes are pushed to `main`, or manually through the GitHub Actions `workflow_dispatch` button. The workflow runs `npm ci`, builds from `frontend/`, copies the Vite entrypoint to `dist/404.html` for React Router fallback handling, and publishes only `frontend/dist` with the official GitHub Pages Actions.

The published custom domain is `https://data-analysis.veerendra.tech/`. The domain is preserved by `frontend/public/CNAME`, and GitHub Pages must be configured with **Source: GitHub Actions** in the repository Pages settings. The Vite base is `/` because this is a custom-domain deployment, not a repository-subpath deployment.

The frontend API client reads `VITE_API_URL`. Local development falls back to `http://localhost:8000`; the GitHub Pages deployment does not provide a backend automatically. Before using authenticated or data-backed features in production, set the repository or `github-pages` environment variable `VITE_API_URL` to the separately deployed HTTPS FastAPI URL. Do not put secrets in the frontend because Vite embeds build-time variables into public assets.

## Demo data

Three ready-to-upload datasets live in [data/samples](data/samples):

- `sales.csv`: 24 realistic orders with dates, products, categories, regions, segments, quantities, prices, and revenue.
- `employees.csv`: workforce, department, role, tenure, performance, and salary data.
- `ecommerce.csv`: channel, device, customer type, category, order, revenue, and conversion data.

Upload `sales.csv` first for the full demonstration path. Try: “What are the top 5 products by revenue?”, then open the chart, table, SQL, forecast, and report.

## Architecture

```mermaid
flowchart LR
	Browser[React + TypeScript] -->|Bearer API requests| API[FastAPI]
	API --> DB[(PostgreSQL)]
	API --> Redis[(Redis cache and jobs)]
	API --> DuckDB[DuckDB over owned CSV]
	API --> Provider[Development or OpenAI-compatible provider]
	Files[(data/uploads)] --> DuckDB
```

```mermaid
sequenceDiagram
	participant User
	participant UI as Analyst UI
	participant API as FastAPI
	participant LLM as Provider
	participant Duck as DuckDB
	User->>UI: Ask a question
	UI->>API: POST /api/analysis/query
	API->>LLM: Request structured SQL
	API->>API: Validate read-only SQL
	API->>Duck: Execute bounded query
	Duck-->>API: Columns and rows
	API->>LLM: Explain supplied result
	API-->>UI: SQL, table, chart, grounded insight
```

```mermaid
erDiagram
	USER ||--o{ DATASET : owns
	DATASET ||--o{ DATASET_COLUMN : contains
	USER ||--o{ QUERY : asks
	DATASET ||--o{ QUERY : receives
	QUERY ||--o| ANALYSIS_RESULT : produces
	USER ||--o{ REPORT : creates
	DATASET ||--o{ REPORT : summarizes
```

## Technology stack

Frontend: React 18, TypeScript, Vite, Tailwind CSS, React Router, Recharts, Axios, Vitest, Testing Library.

Backend: Python 3.12, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, Redis, DuckDB, pandas, NumPy, scikit-learn, PyJWT, Argon2.

## Data flow and security

1. The user authenticates and receives a short-lived JWT.
2. Uploads are checked for CSV type, UTF-8 encoding, safe names, shape consistency, and size limits.
3. Every dataset query is scoped to the authenticated owner, except explicit admin access.
4. The provider receives schema and question context, not arbitrary filesystem access.
5. SQL must begin with `SELECT` or `WITH`, reference only `dataset_data`, contain no comments or destructive operations, and return at most 500 rows.
6. Reports and insights are generated from computed profile data and saved result rows; unsupported causal claims are not presented as facts.

## API documentation

With the backend running, FastAPI provides interactive documentation at http://localhost:8000/docs and the OpenAPI schema at http://localhost:8000/openapi.json. Core endpoint groups are Authentication, Datasets, Data Preparation, Analysis, and Reports. The health probes are `/health` and `/api/health`.

## Screenshots

The primary UI routes are `/login`, `/register`, `/dashboard`, `/datasets`, `/datasets/{id}`, `/data-preparation`, `/datasets/{id}/analyst`, `/reports`, and `/profile`. Run the application locally and capture screenshots from the live workspace for release documentation.

## Future improvements

- Replace the in-process report executor with a durable worker queue for multi-instance deployment.
- Serve a compiled frontend through a production web server instead of the Vite development server.
- Add object storage and signed URLs for large dataset files.
- Add organization-level workspaces, audit logs, and configurable retention policies.

## Environment variables

See `.env.example` for the complete configuration. Replace all development values, especially `POSTGRES_PASSWORD` and `JWT_SECRET`, before deployment.

## Project structure

```text
backend/       FastAPI service
frontend/      React/Vite application
data/          Local upload and processed-data mounts
docker-compose.yml
```

## Verification

```powershell
python -m compileall backend\app
python -m pytest backend\tests
Set-Location frontend
npm run test
npm run lint
npm run build
docker compose config
docker compose up --build
```
