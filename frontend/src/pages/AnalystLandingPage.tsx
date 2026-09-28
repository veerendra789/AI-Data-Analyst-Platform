import { useEffect, useState } from "react";
import { ArrowRight, Database, LoaderCircle, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import api from "../services/api";
import type { Dataset, DatasetListResponse } from "../types/datasets";

export default function AnalystLandingPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<DatasetListResponse>("/api/datasets?limit=100")
      .then(({ data }) => setDatasets(data.items))
      .catch(() => setError("Your datasets could not be loaded."))
      .finally(() => setLoading(false));
  }, []);

  return <main className="min-h-screen bg-paper px-6 py-10 text-ink sm:px-10"><div className="mx-auto max-w-5xl"><header className="border-b border-ink/10 pb-8"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-moss">AI analyst</p><h1 className="mt-2 font-display text-4xl sm:text-5xl">Choose a dataset</h1><p className="mt-3 max-w-2xl text-lg leading-8 text-ink/60">Start with a question. Signal will generate safe SQL, return the underlying rows, and explain what the data supports.</p></header>{error && <p className="mt-6 rounded-lg bg-red-50 p-4 text-sm text-red-700">{error}</p>}{loading ? <div className="flex justify-center py-20"><LoaderCircle className="animate-spin text-moss" /></div> : datasets.length === 0 ? <div className="mt-10 rounded-xl border border-dashed border-ink/15 bg-white px-6 py-20 text-center"><Database className="mx-auto text-ink/30" size={36} /><h2 className="mt-4 font-display text-2xl">Upload data first</h2><p className="mt-2 text-sm text-ink/55">Add a CSV dataset before asking analytical questions.</p><Link className="mt-6 inline-flex items-center gap-2 rounded-lg bg-ink px-4 py-3 text-sm font-semibold text-paper" to="/datasets">Open datasets <ArrowRight size={16} /></Link></div> : <div className="mt-10 grid gap-4 md:grid-cols-2">{datasets.map((dataset) => <Link className="group rounded-xl border border-ink/10 bg-white p-5 transition hover:-translate-y-0.5 hover:border-moss hover:shadow-lg" key={dataset.id} to={`/datasets/${dataset.id}/analyst`}><div className="flex items-start justify-between gap-4"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-lime text-ink"><Sparkles size={20} /></div><ArrowRight className="text-ink/30 transition group-hover:text-moss" size={20} /></div><h2 className="mt-8 font-display text-2xl">{dataset.name}</h2><p className="mt-1 text-sm text-ink/55">{dataset.row_count.toLocaleString()} rows · {dataset.column_count} columns</p><p className="mt-5 text-xs font-semibold uppercase tracking-[0.12em] text-moss">Open analyst</p></Link>)}</div>}</div></main>;
}
