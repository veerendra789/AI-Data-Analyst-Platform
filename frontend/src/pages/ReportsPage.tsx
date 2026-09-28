import { useEffect, useState } from "react";
import { FileText, LoaderCircle, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";
import api from "../services/api";
import type { Dataset, DatasetListResponse } from "../types/datasets";
import type { Report, ReportJob } from "../types/reports";
import { parseReport, type ReportDocument } from "../services/reportParser";

export default function ReportsPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [datasetId, setDatasetId] = useState("");
  const [title, setTitle] = useState("Analytical report");
  const [job, setJob] = useState<ReportJob | null>(null);
  const [selected, setSelected] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const [datasetResponse, reportResponse] = await Promise.all([
        api.get<DatasetListResponse>("/api/datasets?limit=100"),
        api.get<Report[]>("/api/reports?limit=100"),
      ]);
      setDatasets(datasetResponse.data.items);
      setReports(reportResponse.data);
      setDatasetId((current) => current || String(datasetResponse.data.items[0]?.id ?? ""));
    } catch {
      setError("Reports could not be loaded.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  useEffect(() => {
    if (!job || (job.status !== "PENDING" && job.status !== "PROCESSING")) return;
    const timer = window.setInterval(() => {
      void api.get<ReportJob>(`/api/reports/jobs/${job.job_id}`).then(({ data }) => {
        setJob(data);
        if (data.status === "COMPLETED" && data.result) {
          setSelected(data.result);
          setReports((current) => [data.result!, ...current.filter((report) => report.id !== data.result!.id)]);
          setGenerating(false);
        }
        if (data.status === "FAILED") setGenerating(false);
      }).catch(() => {
        setError("The report job status could not be checked.");
        setGenerating(false);
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [job]);

  const generate = async () => {
    if (!datasetId || !title.trim()) return;
    setError("");
    setGenerating(true);
    setSelected(null);
    try {
      const { data } = await api.post<ReportJob>("/api/reports/jobs", { dataset_id: Number(datasetId), title: title.trim() });
      setJob(data);
    } catch (requestError: any) {
      setError(requestError.response?.data?.error?.message ?? "The report could not be started.");
      setGenerating(false);
    }
  };

  const document = selected ? parseReport(selected.content) : null;

  return <main className="min-h-screen bg-paper px-6 py-10 text-ink sm:px-10"><div className="mx-auto max-w-6xl"><div className="flex flex-col justify-between gap-5 border-b border-ink/10 pb-7 sm:flex-row sm:items-end"><div><Link className="text-sm font-semibold text-moss" to="/datasets">Back to datasets</Link><p className="mt-7 text-xs font-semibold uppercase tracking-[0.18em] text-moss">Reporting</p><h1 className="mt-2 font-display text-4xl">Reports</h1><p className="mt-2 text-ink/60">Grounded summaries built from your dataset and saved analysis results.</p></div><FileText className="text-moss" size={38} /></div>{error && <p className="mt-6 rounded-lg bg-red-50 p-4 text-sm text-red-700">{error}</p>}<section className="mt-8 rounded-xl border border-ink/10 bg-white p-5"><h2 className="font-display text-2xl">Generate a report</h2><div className="mt-4 grid gap-3 sm:grid-cols-[1fr_1fr_auto]"><select className="rounded-lg border border-ink/15 bg-white px-3 py-3 text-sm" disabled={generating} value={datasetId} onChange={(event) => setDatasetId(event.target.value)}><option value="">Select a dataset</option>{datasets.map((dataset) => <option key={dataset.id} value={dataset.id}>{dataset.name}</option>)}</select><input className="rounded-lg border border-ink/15 px-3 py-3 text-sm" disabled={generating} value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Report title" /><button className="inline-flex items-center justify-center gap-2 rounded-lg bg-ink px-5 py-3 text-sm font-semibold text-paper disabled:opacity-50" disabled={!datasetId || !title.trim() || generating} onClick={() => void generate()} type="button">{generating && <LoaderCircle className="animate-spin" size={16} />}{generating ? "Generating..." : "Generate report"}</button></div>{job && <div className="mt-4 flex items-center justify-between rounded-lg bg-paper p-3 text-sm"><span>Job status: <strong>{job.status}</strong></span>{job.status === "FAILED" && <button className="inline-flex items-center gap-2 font-semibold text-moss" onClick={() => void generate()} type="button"><RefreshCw size={15} />Retry</button>}</div>}</section><div className="mt-10 grid gap-8 lg:grid-cols-[minmax(220px,0.7fr)_minmax(0,1.5fr)]"><section><h2 className="font-display text-2xl">Report history</h2>{loading ? <LoaderCircle className="mt-6 animate-spin text-moss" /> : reports.length === 0 ? <p className="mt-4 text-sm text-ink/55">No reports generated yet.</p> : <div className="mt-4 space-y-2">{reports.map((report) => <button className={`block w-full rounded-lg border p-4 text-left ${selected?.id === report.id ? "border-moss bg-moss/5" : "border-ink/10 bg-white"}`} key={report.id} onClick={() => { setSelected(report); setJob(null); }} type="button"><p className="font-semibold">{report.title}</p><p className="mt-1 text-xs text-ink/50">{new Date(report.created_at).toLocaleString()}</p></button>)}</div>}</section>{document && selected ? <ReportView document={document} report={selected} /> : <div className="flex min-h-80 items-center justify-center rounded-xl border border-dashed border-ink/15 text-center text-sm text-ink/50">Select a report to inspect its findings.</div>}</div></div></main>;
}

function ReportView({ document, report }: { document: ReportDocument; report: Report }) { return <article className="space-y-5"><div><p className="text-xs font-semibold uppercase tracking-[0.15em] text-moss">{report.title}</p><h2 className="mt-2 font-display text-3xl">{document.executive_summary ?? "Report summary"}</h2></div>{document.dataset_overview && <ReportSection title="Dataset overview"><p>{document.dataset_overview.name} · {document.dataset_overview.rows?.toLocaleString()} rows · {document.dataset_overview.columns} columns</p><p className="mt-1 text-sm text-ink/55">{document.dataset_overview.filename}</p></ReportSection>}{document.data_quality && <ReportSection title="Data quality"><p>{document.data_quality.missing_values ?? 0} missing values ({document.data_quality.missing_percentage ?? 0}%) · {document.data_quality.duplicate_rows ?? 0} duplicate rows</p></ReportSection>}{document.important_metrics && <ReportSection title="Important metrics"><div className="grid gap-3 sm:grid-cols-2">{Object.entries(document.important_metrics).map(([name, values]) => <div className="rounded-lg bg-paper p-3" key={name}><p className="font-semibold">{name}</p><p className="mt-1 text-sm text-ink/60">Mean: {values.mean ?? "n/a"} · Range: {values.minimum ?? "n/a"} to {values.maximum ?? "n/a"}</p></div>)}</div></ReportSection>}{document.forecast && <ReportSection title="Forecast"><p className="text-sm text-ink/60">{document.forecast.target_column} · {document.forecast.forecast?.length ?? 0} future periods</p></ReportSection>}{document.major_findings && document.major_findings.length > 0 && <ReportSection title="Major findings"><ul className="space-y-2">{document.major_findings.map((finding, index) => <li key={index}>{finding.finding}</li>)}</ul></ReportSection>}{document.ai_insights && document.ai_insights.length > 0 && <ReportSection title="AI-generated insights"><div className="space-y-3">{document.ai_insights.map((insight, index) => <div key={index}><p className="font-semibold">{insight.question}</p><p className="mt-1 text-ink/65">{insight.insight}</p></div>)}</div></ReportSection>}</article>; }
function ReportSection({ title, children }: { title: string; children: React.ReactNode }) { return <section className="rounded-xl border border-ink/10 bg-white p-5"><h3 className="font-display text-2xl">{title}</h3><div className="mt-3 text-sm leading-6 text-ink/75">{children}</div></section>; }
