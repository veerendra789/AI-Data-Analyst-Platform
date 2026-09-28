import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Database, FileUp, Home, LoaderCircle, Trash2 } from "lucide-react";
import api from "../services/api";
import type { Dataset, DatasetListResponse } from "../types/datasets";

function formatBytes(bytes: number) { return `${(bytes / 1024).toFixed(1)} KB`; }

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const loadDatasets = async () => {
    const { data } = await api.get<DatasetListResponse>("/api/datasets");
    setDatasets(data.items);
  };
  useEffect(() => { void loadDatasets(); }, []);

  const upload = async (file: File) => {
    setError("");
    setUploadProgress(0);
    const formData = new FormData();
    formData.append("file", file);
    try {
      await api.post("/api/datasets/upload", formData, { headers: { "Content-Type": "multipart/form-data" }, onUploadProgress: (event) => { if (event.total) setUploadProgress(Math.round((event.loaded / event.total) * 100)); } });
      await loadDatasets();
    } catch (uploadError: any) {
      setError(uploadError.response?.data?.detail ?? "The dataset could not be uploaded.");
    } finally { setUploadProgress(null); if (inputRef.current) inputRef.current.value = ""; }
  };

  const remove = async (dataset: Dataset) => {
    if (!window.confirm(`Delete ${dataset.original_filename}? This cannot be undone.`)) return;
    await api.delete(`/api/datasets/${dataset.id}`);
    setDatasets((current) => current.filter((item) => item.id !== dataset.id));
  };

  return <main className="min-h-screen bg-paper px-6 py-10 text-ink sm:px-10"><div className="mx-auto max-w-6xl"><div className="mb-6 flex justify-end"><Link className="inline-flex items-center gap-2 text-sm font-semibold text-moss" to="/dashboard"><Home size={16} />Home</Link></div><div className="flex flex-col justify-between gap-5 border-b border-ink/10 pb-7 sm:flex-row sm:items-end"><div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-moss">Workspace</p><h1 className="mt-2 font-display text-4xl">Datasets</h1><p className="mt-2 text-ink/60">Upload and inspect the data that powers your analysis.</p></div><label className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg bg-ink px-5 py-3 text-sm font-semibold text-paper hover:bg-moss"><FileUp size={17} />Upload CSV<input ref={inputRef} accept=".csv,text/csv" className="hidden" disabled={uploadProgress !== null} type="file" onChange={(event) => { const file = event.target.files?.[0]; if (file) void upload(file); }} /></label></div>{uploadProgress !== null && <div className="mt-6 rounded-lg border border-moss/20 bg-moss/5 p-4"><div className="flex items-center justify-between text-sm"><span className="flex items-center gap-2"><LoaderCircle className="animate-spin" size={16} />Uploading dataset</span><span>{uploadProgress}%</span></div><div className="mt-3 h-2 overflow-hidden rounded-full bg-moss/15"><div className="h-full bg-moss transition-all" style={{ width: `${uploadProgress}%` }} /></div></div>}{error && <p className="mt-6 rounded-lg bg-red-50 p-4 text-sm text-red-700">{error}</p>}<div className="mt-10 overflow-hidden rounded-xl border border-ink/10 bg-white">{datasets.length === 0 ? <div className="px-6 py-20 text-center"><Database className="mx-auto text-ink/30" size={34} /><h2 className="mt-4 font-display text-2xl">No datasets yet</h2><p className="mt-2 text-sm text-ink/55">Upload a CSV to begin exploring your data.</p></div> : <div className="divide-y divide-ink/10">{datasets.map((dataset) => <div className="flex flex-col gap-4 px-6 py-5 sm:flex-row sm:items-center sm:justify-between" key={dataset.id}><Link className="min-w-0" to={`/datasets/${dataset.id}`}><p className="truncate font-semibold hover:text-moss">{dataset.name}</p><p className="mt-1 text-sm text-ink/55">{dataset.row_count.toLocaleString()} rows · {dataset.column_count} columns · {formatBytes(dataset.file_size)}</p></Link><div className="flex items-center gap-4"><span className="text-xs font-semibold uppercase tracking-[0.12em] text-moss">{dataset.status}</span><button aria-label={`Delete ${dataset.name}`} className="rounded-md p-2 text-ink/40 hover:bg-red-50 hover:text-red-700" onClick={() => void remove(dataset)} title="Delete dataset" type="button"><Trash2 size={17} /></button></div></div>)}</div>}</div></div></main>;
}
