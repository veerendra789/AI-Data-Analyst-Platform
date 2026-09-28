import { BarChart3, Database, Home, LogOut, Plus, Sparkles, WandSparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import { useAuth } from "./context/useAuth";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import DatasetDetailsPage from "./pages/DatasetDetailsPage";
import DatasetsPage from "./pages/DatasetsPage";
import AnalystPage from "./pages/AnalystPage";
import AnalystLandingPage from "./pages/AnalystLandingPage";
import ReportsPage from "./pages/ReportsPage";
import ProfilePage from "./pages/ProfilePage";
import DataPreparationPage from "./pages/DataPreparationPage";
import api from "./services/api";
import type { Dataset, DatasetListResponse } from "./types/datasets";
import type { Report } from "./types/reports";

function Dashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.get<DatasetListResponse>("/api/datasets?limit=5"), api.get<Report[]>("/api/reports?limit=5")])
      .then(([datasetResponse, reportResponse]) => { setDatasets(datasetResponse.data.items); setReports(reportResponse.data); })
      .catch(() => setError("Your workspace summary could not be loaded."))
      .finally(() => setLoading(false));
  }, []);

  const initials = user?.name.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase();

  return (
    <div className="min-h-screen bg-paper text-ink">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-ink/10 bg-ink px-6 py-7 text-paper lg:block">
        <div className="flex items-center gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-xl bg-lime text-ink"><BarChart3 size={21} strokeWidth={2.5} /></div><div><p className="font-display text-lg leading-none">Signal</p><p className="mt-1 text-[10px] uppercase tracking-[0.22em] text-paper/50">Data analyst</p></div></div>
        <nav className="mt-16 space-y-2" aria-label="Primary navigation"><Link className="flex w-full items-center gap-3 rounded-lg bg-lime px-3 py-3 text-left text-sm font-semibold text-ink shadow-[4px_4px_0_#e76f51]" to="/dashboard"><Home size={18} />Home</Link><Link className="flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left text-sm text-paper/60 transition hover:bg-paper/5 hover:text-paper" to="/datasets"><Database size={18} />Datasets</Link><Link className="flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left text-sm text-paper/60 transition hover:bg-paper/5 hover:text-paper" to="/data-preparation"><WandSparkles size={18} />Data Structurer</Link><Link className="flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left text-sm text-paper/60 transition hover:bg-paper/5 hover:text-paper" to="/analyst"><Sparkles size={18} />Analyst</Link><Link className="flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left text-sm text-paper/60 transition hover:bg-paper/5 hover:text-paper" to="/reports"><BarChart3 size={18} />Reports</Link></nav>
        <Link className="absolute bottom-7 left-6 right-6 flex items-center gap-3 border-t border-paper/10 pt-4 text-left" to="/profile"><div className="flex h-9 w-9 items-center justify-center rounded-full bg-lime text-xs font-bold text-ink">{initials}</div><div className="min-w-0"><p className="truncate text-xs text-paper/70">{user?.name}</p><p className="truncate text-[11px] text-paper/40">View profile</p></div></Link>
      </aside>
      <main className="lg:ml-64">
        <header className="flex items-center justify-between border-b border-ink/10 px-6 py-5 sm:px-10"><div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-moss">Workspace</p><h1 className="mt-1 font-display text-3xl sm:text-4xl">Good analysis starts here.</h1></div><div className="flex items-center gap-3"><Link aria-label="Open profile" className="flex h-10 w-10 items-center justify-center rounded-full bg-moss text-sm font-semibold text-white" to="/profile">{initials}</Link><button aria-label="Log out" className="rounded-lg border border-ink/15 p-2 text-ink/60 hover:border-ink/40 hover:text-ink" onClick={() => { logout(); navigate("/login"); }} title="Log out" type="button"><LogOut size={17} /></button></div></header>
        <div className="border-b border-ink/10 px-6 py-3 lg:hidden"><nav className="flex gap-2 overflow-x-auto" aria-label="Mobile navigation"><Link className="whitespace-nowrap rounded-lg bg-lime px-3 py-2 text-xs font-semibold text-ink" to="/dashboard">Home</Link><Link className="whitespace-nowrap rounded-lg border border-ink/10 px-3 py-2 text-xs font-semibold" to="/datasets">Datasets</Link><Link className="whitespace-nowrap rounded-lg border border-ink/10 px-3 py-2 text-xs font-semibold" to="/data-preparation">Data Structurer</Link><Link className="whitespace-nowrap rounded-lg border border-ink/10 px-3 py-2 text-xs font-semibold" to="/analyst">Analyst</Link><Link className="whitespace-nowrap rounded-lg border border-ink/10 px-3 py-2 text-xs font-semibold" to="/reports">Reports</Link><Link className="whitespace-nowrap rounded-lg border border-ink/10 px-3 py-2 text-xs font-semibold" to="/profile">Profile</Link></nav></div>
        <section className="px-6 py-10 sm:px-10 sm:py-12"><div className="flex flex-col justify-between gap-6 md:flex-row md:items-end"><div className="max-w-2xl"><p className="max-w-xl text-lg leading-8 text-ink/65">A focused home for exploring datasets, asking sharper questions, and turning raw numbers into decisions.</p></div><Link className="inline-flex items-center justify-center gap-2 rounded-lg bg-ink px-5 py-3 text-sm font-semibold text-paper transition hover:bg-moss" to="/datasets"><Plus size={17} />Add dataset</Link></div>{error && <p className="mt-6 rounded-lg bg-red-50 p-4 text-sm text-red-700">{error}</p>}<div className="mt-10 grid gap-4 sm:grid-cols-3"><Metric label="Datasets" value={loading ? "..." : String(datasets.length)} detail="In your workspace" /><Metric label="Rows analyzed" value={loading ? "..." : datasets.reduce((total, dataset) => total + dataset.row_count, 0).toLocaleString()} detail="Across available data" /><Metric label="Reports" value={loading ? "..." : String(reports.length)} detail="Saved insights" /></div><div className="mt-12 grid gap-8 xl:grid-cols-[1.2fr_0.8fr]"><section><div className="flex items-center justify-between"><div><p className="text-xs font-semibold uppercase tracking-[0.15em] text-moss">Recent data</p><h2 className="mt-2 font-display text-2xl">Datasets</h2></div><Link className="text-sm font-semibold text-moss" to="/datasets">View all</Link></div><div className="mt-4 overflow-hidden rounded-xl border border-ink/10 bg-white">{loading ? <LoadingRows /> : datasets.length === 0 ? <EmptyPanel text="Upload a CSV to start exploring." /> : <div className="divide-y divide-ink/10">{datasets.slice(0, 4).map((dataset) => <Link className="flex items-center justify-between gap-4 px-5 py-4 transition hover:bg-paper" key={dataset.id} to={`/datasets/${dataset.id}`}><div className="min-w-0"><p className="truncate font-semibold">{dataset.name}</p><p className="mt-1 text-xs text-ink/50">{dataset.row_count.toLocaleString()} rows · {dataset.column_count} columns</p></div><span className="rounded-full bg-moss/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-moss">{dataset.status}</span></Link>)}</div>}</div></section><section><p className="text-xs font-semibold uppercase tracking-[0.15em] text-moss">Saved work</p><h2 className="mt-2 font-display text-2xl">Recent reports</h2><div className="mt-4 overflow-hidden rounded-xl border border-ink/10 bg-white">{loading ? <LoadingRows /> : reports.length === 0 ? <EmptyPanel text="Generate a report after your first analysis." /> : <div className="divide-y divide-ink/10">{reports.slice(0, 4).map((report) => <Link className="block px-5 py-4 transition hover:bg-paper" key={report.id} to="/reports"><p className="truncate font-semibold">{report.title}</p><p className="mt-1 text-xs text-ink/50">{new Date(report.created_at).toLocaleDateString()}</p></Link>)}</div>}</div></section></div></section>
      </main>
    </div>
  );
}

function App() {
  return <Routes><Route path="/login" element={<LoginPage />} /><Route path="/register" element={<RegisterPage />} /><Route element={<ProtectedRoute />}><Route path="/dashboard" element={<Dashboard />} /><Route path="/datasets" element={<DatasetsPage />} /><Route path="/datasets/:datasetId" element={<DatasetDetailsPage />} /><Route path="/data-preparation" element={<DataPreparationPage />} /><Route path="/analyst" element={<AnalystLandingPage />} /><Route path="/datasets/:datasetId/analyst" element={<AnalystPage />} /><Route path="/reports" element={<ReportsPage />} /><Route path="/profile" element={<ProfilePage />} /><Route path="/" element={<Navigate to="/dashboard" replace />} /></Route><Route path="*" element={<Navigate to="/dashboard" replace />} /></Routes>;
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) { return <div className="border-t-2 border-ink/15 pt-3"><p className="text-sm text-ink/55">{label}</p><p className="mt-2 font-display text-4xl">{value}</p><p className="mt-1 text-xs uppercase tracking-[0.12em] text-ink/35">{detail}</p></div>; }
function LoadingRows() { return <div className="space-y-3 p-5"><div className="h-4 animate-pulse rounded bg-ink/10" /><div className="h-4 w-2/3 animate-pulse rounded bg-ink/10" /><div className="h-4 w-1/2 animate-pulse rounded bg-ink/10" /></div>; }
function EmptyPanel({ text }: { text: string }) { return <div className="px-5 py-12 text-center text-sm text-ink/50">{text}</div>; }

export default App;
