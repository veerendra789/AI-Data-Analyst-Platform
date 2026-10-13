# Production Deployment Guide — Signal AI Data Analyst Platform

This guide provides step-by-step instructions for deploying the **Signal AI Data Analyst Platform** to production using **Supabase** (Database, Auth, Storage), **Vercel** (FastAPI Backend), and **Firebase Hosting** (React Frontend).

---

## 1. Production Environment Variables Matrix

| Variable Name | Environment | Category | Secret? | Description | Recommended Value / Example |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `VITE_API_BASE_URL` | Frontend | Build Variable | No | Production backend FastAPI URL | `https://ai-data-analyst-backend.vercel.app` |
| `VITE_SUPABASE_URL` | Frontend | Build Variable | No | Supabase Project API URL | `https://azfaieuwnhgjbedfeybl.supabase.co` |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Frontend | Build Variable | No | Supabase Anon / Publishable Key | `eyJhbGciOi...` (Anon Key) |
| `SUPABASE_URL` | Backend | Runtime Secret | No | Supabase Project API URL | `https://azfaieuwnhgjbedfeybl.supabase.co` |
| `SUPABASE_SECRET_KEY` | Backend | Runtime Secret | **YES** | Supabase Service Role Key | `eyJhbGciOi...` (Service Role Key) |
| `CORS_ORIGINS` | Backend | Runtime Setting | No | Comma-separated HTTPS origins | `https://data-analystics-6557e.web.app,https://data-analysis.veerendra.tech` |
| `REDIS_URL` | Backend | Runtime Secret | **YES** | Managed Redis connection string | `redis://default:password@us1-managed.upstash.io:6379/0` |
| `LLM_API_KEY` | Backend | Runtime Secret | **YES** | OpenAI/Claude API Key (optional) | `sk-proj-...` |
| `APP_ENV` | Backend | Runtime Setting | No | Set to `production` in live deployment | `production` |

> [!WARNING]
> Never expose `SUPABASE_SECRET_KEY` or `LLM_API_KEY` to the frontend browser context or prefix them with `VITE_`.

---

## 2. Supabase Infrastructure Setup

### Step 2.1: Execute Database Migration
1. Log into your [Supabase Dashboard](https://supabase.com/dashboard).
2. Select your project (`azfaieuwnhgjbedfeybl`).
3. Open the **SQL Editor** from the left navigation panel.
4. Copy and paste the entire contents of [`supabase/migrations/0001_application_schema.sql`](file:///c:/ai_data_analyst_platform/supabase/migrations/0001_application_schema.sql).
5. Click **Run**.
6. Verify that the 5 application tables were created:
   - `public.profiles`
   - `public.datasets`
   - `public.analyses`
   - `public.reports`
   - `public.structuring_jobs`

### Step 2.2: Verify Private Storage Bucket
1. In the Supabase Dashboard, navigate to **Storage**.
2. Confirm the private bucket `datasets` exists:
   - **Public Access**: `Disabled` (Private bucket)
   - **File Size Limit**: `50 MB` (52,428,800 bytes)
   - **Allowed MIME Types**: `text/csv`, `application/csv`, `application/vnd.ms-excel`, `text/plain`
3. Verify RLS policies are enabled under **Storage Rules**:
   - `dataset_objects_select_own`
   - `dataset_objects_insert_own`
   - `dataset_objects_update_own`
   - `dataset_objects_delete_own`

---

## 3. Backend Deployment (Vercel)

### Step 3.1: Configure Vercel Project Secrets
Set the following environment variables in your Vercel Project Settings (**Settings > Environment Variables**):
- `SUPABASE_URL` = `https://azfaieuwnhgjbedfeybl.supabase.co`
- `SUPABASE_SECRET_KEY` = `<your-service-role-key>`
- `CORS_ORIGINS` = `https://data-analystics-6557e.web.app,https://data-analysis.veerendra.tech`
- `REDIS_URL` = `<your-managed-redis-url>`
- `APP_ENV` = `production`
- `LLM_API_KEY` = `<your-openai-api-key>` (optional)

### Step 3.2: Deploy via Vercel CLI
From your local terminal, navigate to the `backend/` directory:
```bash
cd backend
vercel link
vercel deploy --prod
```

---

## 4. Frontend Deployment (Firebase Hosting)

### Step 4.1: Configure Environment Variables
Ensure `.env` or CI build secrets contain:
```ini
VITE_API_BASE_URL=https://<your-vercel-deployment-domain>.vercel.app
VITE_SUPABASE_URL=https://azfaieuwnhgjbedfeybl.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=<your-supabase-anon-key>
```

### Step 4.2: Build and Deploy to Firebase Hosting
```bash
cd frontend
npm ci
npm run build
cd ..
firebase deploy --only hosting --project data-analystics-6557e --non-interactive
```

---

## 5. Post-Deployment Production Smoke Test Checklist

Once both services are deployed, perform the following verification:

1. Open `https://data-analystics-6557e.web.app` in an Incognito window.
2. Click **Register** and create a new test user (e.g. `test-user-1@example.com`).
3. Verify automatic user profile creation in Supabase PostgreSQL.
4. Upload a raw CSV file in **Data Structurer** or **Datasets**.
5. Run automated data profiling and inspect metrics.
6. Ask a natural-language question in **AI Data Analyst** (e.g. "What is the total value by category?").
7. Confirm SQL query generation, DuckDB read-only execution, and chart rendering.
8. Generate an async report and download the clean output CSV.
9. Log out, create a second user (`test-user-2@example.com`), and verify that User B **cannot** view, download, or query User A's datasets or reports.
