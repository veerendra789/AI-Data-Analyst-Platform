import { useEffect, useState } from "react";
import { ArrowLeft, LoaderCircle, Sparkles } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api from "../services/api";
import type { Dataset, DatasetPreview } from "../types/datasets";
import type { AnomalyResponse, DatasetProfile } from "../types/profiling";
import type { ForecastResponse, RootCauseResponse } from "../types/advancedAnalysis";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export default function DatasetDetailsPage() {
  const { datasetId } = useParams();
  const navigate = useNavigate();
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [profile, setProfile] = useState<DatasetProfile | null>(null);
  const [anomalies, setAnomalies] = useState<AnomalyResponse | null>(null);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [rootCause, setRootCause] = useState<RootCauseResponse | null>(null);
  const [dateColumn, setDateColumn] = useState("");
  const [targetColumn, setTargetColumn] = useState("");
  const [rootQuestion, setRootQuestion] = useState("Why did sales change?");
  const [loadingForecast, setLoadingForecast] = useState(false);
  const [loadingRootCause, setLoadingRootCause] = useState(false);
  const [anomalyColumn, setAnomalyColumn] = useState("");
  const [loadingProfile, setLoadingProfile] = useState(false);
  const [loadingAnomalies, setLoadingAnomalies] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!datasetId) return;
    Promise.all([
      api.get<Dataset>(`/api/datasets/${datasetId}`),
      api.get<DatasetPreview>(`/api/datasets/${datasetId}/preview`),
    ])
      .then(([datasetResponse, previewResponse]) => {
        setDataset(datasetResponse.data);
        setPreview(previewResponse.data);
        setAnomalyColumn(datasetResponse.data.columns.find((column) => ["integer", "float"].includes(column.data_type))?.column_name ?? "");
        setTargetColumn(datasetResponse.data.columns.find((column) => ["integer", "float"].includes(column.data_type))?.column_name ?? "");
        setDateColumn(datasetResponse.data.columns.find((column) => column.data_type === "date")?.column_name ?? "");
      })
      .catch(() => setError("This dataset could not be loaded."));
  }, [datasetId]);

  const runProfile = async () => {
    if (!datasetId) return;
    setLoadingProfile(true);
    setError("");
    try {
      const { data } = await api.post<DatasetProfile>(`/api/analysis/eda/${datasetId}`);
      setProfile(data);
    } catch (requestError: any) {
      setError(requestError.response?.data?.detail ?? "Profiling could not be completed.");
    } finally {
      setLoadingProfile(false);
    }
  };

  const runForecast = async () => {
    if (!datasetId || !dateColumn || !targetColumn) return;
    setLoadingForecast(true); setError("");
    try { const { data } = await api.post<ForecastResponse>(`/api/analysis/forecast/${datasetId}`, { date_column: dateColumn, target_column: targetColumn, periods: 6 }); setForecast(data); }
    catch (requestError: any) { setError(requestError.response?.data?.detail ?? "Forecasting could not be completed."); }
    finally { setLoadingForecast(false); }
  };

  const runRootCause = async () => {
    if (!datasetId || !rootQuestion.trim()) return;
    setLoadingRootCause(true); setError("");
    try { const { data } = await api.post<RootCauseResponse>(`/api/analysis/root-cause/${datasetId}`, { question: rootQuestion }); setRootCause(data); }
    catch (requestError: any) { setError(requestError.response?.data?.detail ?? "Root cause analysis could not be completed."); }
    finally { setLoadingRootCause(false); }
  };

  const runAnomalies = async () => {
    if (!datasetId || !anomalyColumn) return;
    setLoadingAnomalies(true);
    setError("");
    try {
      const { data } = await api.post<AnomalyResponse>(`/api/analysis/anomalies/${datasetId}`, { column: anomalyColumn });
      setAnomalies(data);
    } catch (requestError: any) {
      setError(requestError.response?.data?.detail ?? "Anomaly detection could not be completed.");
    } finally {
      setLoadingAnomalies(false);
    }
  };

  if (error && !dataset) return <main className="flex min-h-screen items-center justify-center bg-paper p-6 text-red-700">{error}</main>;
  if (!dataset || !preview) return <main className="flex min-h-screen items-center justify-center bg-paper"><LoaderCircle className="animate-spin text-moss" /></main>;

  return (
    <main className="min-h-screen bg-paper px-6 py-10 text-ink sm:px-10">
      <div className="mx-auto max-w-6xl">
        <Link className="inline-flex items-center gap-2 text-sm font-semibold text-moss" to="/datasets"><ArrowLeft size={16} />All datasets</Link>
        <header className="mt-8 flex flex-col justify-between gap-4 border-b border-ink/10 pb-7 sm:flex-row sm:items-end">
          <div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-moss">Dataset overview</p><h1 className="mt-2 font-display text-4xl">{dataset.name}</h1><p className="mt-2 text-ink/55">{dataset.original_filename}</p></div>
          <div className="flex items-center gap-3"><Link className="inline-flex items-center gap-2 rounded-lg bg-ink px-4 py-2 text-sm font-semibold text-paper hover:bg-moss" to={`/datasets/${dataset.id}/analyst`}><Sparkles size={16} />AI Analyst</Link><span className="rounded-full bg-moss/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.12em] text-moss">{dataset.status}</span></div>
        </header>
        {error && <p className="mt-6 rounded-lg bg-red-50 p-4 text-sm text-red-700">{error}</p>}
        <div className="mt-8 grid gap-4 sm:grid-cols-4"><Metric label="Rows" value={dataset.row_count.toLocaleString()} /><Metric label="Columns" value={String(dataset.column_count)} /><Metric label="File size" value={`${(dataset.file_size / 1024).toFixed(1)} KB`} /><Metric label="Status" value={dataset.status} /></div>
        <section className="mt-10"><SectionHeading title="Data quality" action={<button className="rounded-lg bg-ink px-4 py-2 text-sm font-semibold text-paper disabled:opacity-50" disabled={loadingProfile} onClick={() => void runProfile()} type="button">{loadingProfile ? "Profiling..." : profile ? "Refresh profile" : "Run profile"}</button>} />{profile ? <div className="mt-4 grid gap-4 sm:grid-cols-4"><Metric label="Missing values" value={`${profile.summary.missing_values} (${profile.summary.missing_percentage}%)`} /><Metric label="Duplicate rows" value={String(profile.summary.duplicate_rows)} /><Metric label="Numeric columns" value={String(profile.summary.numeric_columns.length)} /><Metric label="Date columns" value={String(profile.summary.date_columns.length)} /></div> : <EmptyState text="Run profiling to calculate quality and statistical summaries." />}</section>
        <section className="mt-10"><h2 className="font-display text-2xl">Column information</h2><div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{dataset.columns.map((column) => <div className="rounded-lg border border-ink/10 bg-white p-4" key={column.id}><p className="font-semibold">{column.column_name}</p><p className="mt-1 text-xs uppercase tracking-[0.12em] text-moss">{column.data_type}</p><p className="mt-3 text-sm text-ink/55">{column.unique_count.toLocaleString()} unique · {column.missing_count.toLocaleString()} missing</p></div>)}</div></section>
        {profile && <ProfileSections profile={profile} />}
        <section className="mt-10"><SectionHeading title="Forecasting" action={<div className="flex flex-wrap gap-2"><select className="rounded-lg border border-ink/15 bg-white px-3 py-2 text-sm" value={dateColumn} onChange={(event) => setDateColumn(event.target.value)}><option value="">Date column</option>{dataset.columns.map((column) => <option key={column.id} value={column.column_name}>{column.column_name}</option>)}</select><select className="rounded-lg border border-ink/15 bg-white px-3 py-2 text-sm" value={targetColumn} onChange={(event) => setTargetColumn(event.target.value)}><option value="">Target column</option>{dataset.columns.filter((column) => ["integer", "float"].includes(column.data_type)).map((column) => <option key={column.id} value={column.column_name}>{column.column_name}</option>)}</select><button className="rounded-lg bg-ink px-4 py-2 text-sm font-semibold text-paper disabled:opacity-50" disabled={!dateColumn || !targetColumn || loadingForecast} onClick={() => void runForecast()} type="button">{loadingForecast ? "Forecasting..." : "Forecast"}</button></div>} />{forecast ? <div className="mt-4 rounded-lg border border-ink/10 bg-white p-4"><p className="text-sm text-ink/60">{forecast.model} · {forecast.observations} observations · {forecast.frequency}</p><div className="mt-4 h-64"><ResponsiveContainer height="100%" width="100%"><LineChart data={[...forecast.historical.map((item) => ({ ...item, forecast: null })), ...forecast.forecast.map((item) => ({ ...item, value: null, forecast: item.value }))]}><CartesianGrid stroke="#10211b18" /><XAxis dataKey="date" /><YAxis /><Tooltip /><Line dataKey="value" stroke="#2f6f52" connectNulls /><Line dataKey="forecast" stroke="#d97706" strokeDasharray="5 5" connectNulls /></LineChart></ResponsiveContainer></div></div> : <EmptyState text="Select a date and numeric target column to generate a trend forecast." />}</section>
        <section className="mt-10"><SectionHeading title="Root cause analysis" action={<div className="flex gap-2"><input className="rounded-lg border border-ink/15 px-3 py-2 text-sm" value={rootQuestion} onChange={(event) => setRootQuestion(event.target.value)} /><button className="rounded-lg bg-ink px-4 py-2 text-sm font-semibold text-paper disabled:opacity-50" disabled={loadingRootCause || !rootQuestion.trim()} onClick={() => void runRootCause()} type="button">{loadingRootCause ? "Analyzing..." : "Analyze"}</button></div>} />{rootCause ? <div className="mt-4 rounded-lg border border-ink/10 bg-white p-4"><p className="font-medium">{rootCause.observed_result}</p><p className="mt-2 text-sm text-ink/60">{rootCause.caveat}</p><div className="mt-4 grid gap-3 sm:grid-cols-2">{rootCause.associations.map((item, index) => <div className="rounded-lg bg-paper p-3 text-sm" key={`${item.dimension}-${index}`}><p className="font-semibold">{item.dimension}: {item.value}</p><p className="mt-1 text-ink/60">{item.relationship} {item.mean_metric.toFixed(2)} average, difference {item.difference_from_overall.toFixed(2)}</p></div>)}</div></div> : <EmptyState text="Ask why a metric changed. Results describe associations, not proven causation." />}</section>
        <section className="mt-10"><SectionHeading title="Anomalies" action={<div className="flex gap-2"><select className="rounded-lg border border-ink/15 bg-white px-3 py-2 text-sm" value={anomalyColumn} onChange={(event) => setAnomalyColumn(event.target.value)}><option value="">Select numeric column</option>{dataset.columns.filter((column) => ["integer", "float"].includes(column.data_type)).map((column) => <option key={column.id} value={column.column_name}>{column.column_name}</option>)}</select><button className="rounded-lg bg-ink px-4 py-2 text-sm font-semibold text-paper disabled:opacity-50" disabled={!anomalyColumn || loadingAnomalies} onClick={() => void runAnomalies()} type="button">{loadingAnomalies ? "Scanning..." : "Detect"}</button></div>} />{anomalies ? <div className="mt-4 rounded-lg border border-ink/10 bg-white p-4"><p className="text-sm text-ink/60">{anomalies.number_of_anomalies} anomalies found using {anomalies.model}.</p>{anomalies.anomaly_records.length > 0 && <div className="mt-3 overflow-x-auto"><table className="min-w-full text-left text-sm"><thead><tr>{Object.keys(anomalies.anomaly_records[0]).map((column) => <th className="px-3 py-2 font-semibold" key={column}>{column}</th>)}</tr></thead><tbody>{anomalies.anomaly_records.map((row, index) => <tr className="border-t border-ink/10" key={index}>{Object.entries(row).map(([key, value]) => <td className="px-3 py-2 text-ink/70" key={key}>{String(value ?? "")}</td>)}</tr>)}</tbody></table></div>}</div> : <EmptyState text="Choose a numeric column to scan for unusual records." />}</section>
        <section className="mt-10"><h2 className="font-display text-2xl">Data preview</h2><p className="mt-1 text-sm text-ink/55">Showing {preview.returned_rows} of {preview.total_rows.toLocaleString()} rows</p><div className="mt-4 overflow-x-auto rounded-xl border border-ink/10 bg-white"><table className="min-w-full text-left text-sm"><thead className="border-b border-ink/10 bg-ink/[0.03]"><tr>{preview.columns.map((column) => <th className="whitespace-nowrap px-4 py-3 font-semibold" key={column}>{column}</th>)}</tr></thead><tbody className="divide-y divide-ink/10">{preview.rows.map((row, index) => <tr key={index}>{preview.columns.map((column) => <td className="whitespace-nowrap px-4 py-3 text-ink/70" key={column}>{row[column] ?? ""}</td>)}</tr>)}</tbody></table></div></section>
        <button className="mt-8 rounded-lg border border-ink/15 px-4 py-2 text-sm font-semibold hover:border-red-400 hover:text-red-700" onClick={() => { if (window.confirm(`Delete ${dataset.original_filename}?`)) void api.delete(`/api/datasets/${dataset.id}`).then(() => navigate("/datasets")); }} type="button">Delete dataset</button>
      </div>
    </main>
  );
}

function ProfileSections({ profile }: { profile: DatasetProfile }) { return <><section className="mt-10"><h2 className="font-display text-2xl">Numeric statistics</h2><div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{Object.entries(profile.numeric_statistics).map(([name, stats]) => <div className="rounded-lg border border-ink/10 bg-white p-4" key={name}><p className="font-semibold">{name}</p>{Object.entries(stats).map(([label, value]) => <p className="mt-2 flex justify-between text-sm text-ink/60" key={label}><span>{label.replaceAll("_", " ")}</span><span className="font-medium text-ink">{value ?? "n/a"}</span></p>)}</div>)}</div></section><section className="mt-10"><h2 className="font-display text-2xl">Distributions</h2><div className="mt-4 grid gap-4 lg:grid-cols-2">{Object.entries(profile.distributions).map(([name, bins]) => <div className="rounded-lg border border-ink/10 bg-white p-4" key={name}><p className="font-semibold">{name}</p><div className="mt-3 h-48"><ResponsiveContainer height="100%" width="100%"><BarChart data={bins}><CartesianGrid stroke="#10211b18" /><XAxis dataKey="start" /><YAxis /><Tooltip /><Bar dataKey="count" fill="#2f6f52" /></BarChart></ResponsiveContainer></div></div>)}</div></section><section className="mt-10"><h2 className="font-display text-2xl">Top categories</h2><div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{Object.entries(profile.categorical_summaries).map(([name, summary]) => <div className="rounded-lg border border-ink/10 bg-white p-4" key={name}><p className="font-semibold">{name}</p><div className="mt-3 h-40"><ResponsiveContainer height="100%" width="100%"><BarChart data={summary.top_categories}><CartesianGrid stroke="#10211b18" /><XAxis dataKey="value" /><YAxis /><Tooltip /><Bar dataKey="count" fill="#d97706" /></BarChart></ResponsiveContainer></div></div>)}</div></section></>; }
function SectionHeading({ title, action }: { title: string; action?: React.ReactNode }) { return <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center"><h2 className="font-display text-2xl">{title}</h2>{action}</div>; }
function EmptyState({ text }: { text: string }) { return <div className="mt-4 rounded-lg border border-dashed border-ink/15 p-8 text-center text-sm text-ink/50">{text}</div>; }
function Metric({ label, value }: { label: string; value: string }) { return <div className="border-t-2 border-ink/15 pt-3"><p className="text-sm text-ink/55">{label}</p><p className="mt-2 font-display text-2xl">{value}</p></div>; }
