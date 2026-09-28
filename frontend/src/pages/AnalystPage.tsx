import { useEffect, useState } from "react";
import { ArrowLeft, BarChart3, LoaderCircle, Send, Table2 } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import api from "../services/api";
import type { AnalysisHistoryItem, AnalysisResult, ChatMessage } from "../types/analysis";
import type { Dataset } from "../types/datasets";

export default function AnalystPage() {
  const { datasetId } = useParams();
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!datasetId) return;
    Promise.all([api.get<Dataset>(`/api/datasets/${datasetId}`), api.get<AnalysisHistoryItem[]>(`/api/analysis/history/${datasetId}`)]).then(([datasetResponse, historyResponse]) => {
      setDataset(datasetResponse.data);
      const messages = historyResponse.data.flatMap((item) => [
        { id: item.query_id * 2, role: "USER" as const, content: item.question, created_at: item.created_at },
        ...(item.insight ? [{ id: item.query_id * 2 + 1, role: "ASSISTANT" as const, content: item.insight, created_at: item.created_at }] : []),
      ]);
      setHistory(messages);
      const latest = historyResponse.data.at(-1);
      if (latest?.sql && latest.insight) setResult({ question: latest.question, sql: latest.sql, columns: latest.columns, rows: latest.rows, chart: { type: "table" }, insight: latest.insight, execution_time_ms: 0 });
    }).catch(() => setError("The analyst workspace could not be loaded."));
  }, [datasetId]);

  const ask = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!datasetId || !question.trim()) return;
    const asked = question.trim();
    setQuestion(""); setError(""); setLoading(true);
    try {
      const { data } = await api.post<AnalysisResult>("/api/analysis/query", { dataset_id: Number(datasetId), question: asked });
      setResult(data);
      setHistory((current) => [...current, { id: Date.now(), role: "USER", content: asked, created_at: new Date().toISOString() }, { id: Date.now() + 1, role: "ASSISTANT", content: data.insight, created_at: new Date().toISOString() }]);
    } catch (requestError: any) { setError(requestError.response?.data?.detail ?? "The analysis could not be completed."); } finally { setLoading(false); }
  };

  return <main className="min-h-screen bg-paper px-6 py-8 text-ink sm:px-10"><div className="mx-auto max-w-7xl"><Link className="inline-flex items-center gap-2 text-sm font-semibold text-moss" to={datasetId ? `/datasets/${datasetId}` : "/datasets"}><ArrowLeft size={16} />Back to dataset</Link><div className="mt-7 border-b border-ink/10 pb-6"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-moss">AI analyst</p><h1 className="mt-2 font-display text-4xl">Ask {dataset?.name ?? "your dataset"}</h1><p className="mt-2 text-ink/55">Questions are answered from the selected dataset and returned with the generated SQL.</p></div><div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.35fr)]"><section className="flex min-h-[560px] flex-col rounded-xl border border-ink/10 bg-white p-5"><div className="flex-1 space-y-4 overflow-y-auto">{history.length === 0 ? <div className="flex h-full min-h-[380px] flex-col items-center justify-center text-center text-ink/45"><BarChart3 size={32} /><p className="mt-4 font-display text-2xl text-ink/70">What would you like to know?</p><p className="mt-2 max-w-xs text-sm">Try asking which products generated the most revenue.</p></div> : history.map((message) => <div className={`flex ${message.role === "USER" ? "justify-end" : "justify-start"}`} key={message.id}><div className={`max-w-[88%] rounded-xl px-4 py-3 text-sm leading-6 ${message.role === "USER" ? "bg-ink text-paper" : "bg-paper text-ink/75"}`}>{message.content}</div></div>)}</div>{error && <p className="mb-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}<form className="mt-5 flex gap-2 border-t border-ink/10 pt-5" onSubmit={ask}><input className="min-w-0 flex-1 rounded-lg border border-ink/15 px-3 py-3 text-sm outline-none focus:border-moss" disabled={loading} placeholder="Ask a question about this data..." value={question} onChange={(event) => setQuestion(event.target.value)} /><button aria-label="Send question" className="rounded-lg bg-ink p-3 text-paper disabled:opacity-50" disabled={loading || !question.trim()} title="Send question" type="submit">{loading ? <LoaderCircle className="animate-spin" size={18} /> : <Send size={18} />}</button></form></section><ResultPanel result={result} /></div></div></main>;
}

function ResultPanel({ result }: { result: AnalysisResult | null }) { const [showSql, setShowSql] = useState(false); if (!result) return <section className="flex min-h-[560px] items-center justify-center rounded-xl border border-dashed border-ink/15 text-center text-ink/45"><div><Table2 className="mx-auto" size={30} /><p className="mt-3 text-sm">Your analysis result will appear here.</p></div></section>; return <section className="space-y-5"><div className="rounded-xl border border-ink/10 bg-white p-5"><div className="flex items-start justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-[0.15em] text-moss">Insight</p><p className="mt-3 leading-7 text-ink/75">{result.insight}</p></div><button className="shrink-0 text-xs font-semibold text-moss" onClick={() => setShowSql(!showSql)} type="button">{showSql ? "Hide SQL" : "View SQL"}</button></div>{showSql && <pre className="mt-4 overflow-x-auto rounded-lg bg-ink p-4 text-xs leading-5 text-lime">{result.sql}</pre>}</div><div className="rounded-xl border border-ink/10 bg-white p-5"><h2 className="font-display text-2xl">Results</h2><div className="mt-4 overflow-x-auto"><table className="min-w-full text-left text-sm"><thead className="border-b border-ink/10"><tr>{result.columns.map((column) => <th className="whitespace-nowrap px-3 py-3 font-semibold" key={column}>{column}</th>)}</tr></thead><tbody className="divide-y divide-ink/10">{result.rows.map((row, index) => <tr key={index}>{result.columns.map((column) => <td className="whitespace-nowrap px-3 py-3 text-ink/70" key={column}>{String(row[column] ?? "")}</td>)}</tr>)}</tbody></table></div></div><ChartPanel result={result} /></section>; }

function ChartPanel({ result }: { result: AnalysisResult }) { const { chart, rows } = result; if (chart.type === "table" || !chart.x_axis || !chart.y_axis || rows.length === 0) return null; const data = rows.map((row) => ({ x: row[chart.x_axis!], y: Number(row[chart.y_axis!]) || 0 })); return <div className="rounded-xl border border-ink/10 bg-white p-5"><h2 className="font-display text-2xl">Visualization</h2><div className="mt-4 h-72"><ResponsiveContainer height="100%" width="100%">{chart.type === "line" ? <LineChart data={data}><CartesianGrid stroke="#10211b18" /><XAxis dataKey="x" /><YAxis /><Tooltip /><Line dataKey="y" stroke="#2f6f52" strokeWidth={3} /></LineChart> : chart.type === "area" ? <AreaChart data={data}><CartesianGrid stroke="#10211b18" /><XAxis dataKey="x" /><YAxis /><Tooltip /><Area dataKey="y" fill="#d7f36b" stroke="#2f6f52" /></AreaChart> : chart.type === "scatter" ? <ScatterChart><CartesianGrid stroke="#10211b18" /><XAxis dataKey="x" /><YAxis dataKey="y" /><Tooltip /><Scatter data={data} fill="#2f6f52" /></ScatterChart> : chart.type === "pie" ? <PieChart><Tooltip /><Pie data={data} dataKey="y" nameKey="x" outerRadius={100}>{data.map((_, index) => <Cell fill={["#2f6f52", "#d7f36b", "#10211b", "#9cc9b1"][index % 4]} key={index} />)}</Pie></PieChart> : <BarChart data={data}><CartesianGrid stroke="#10211b18" /><XAxis dataKey="x" /><YAxis /><Tooltip /><Bar dataKey="y" fill="#2f6f52" /></BarChart>}</ResponsiveContainer></div></div>; }
