import { useState } from "react";
import { ArrowDownToLine, Check, ChevronDown, FileUp, Home, LoaderCircle, RefreshCw, Save, Sparkles, Trash2, X } from "lucide-react";
import { Link } from "react-router-dom";
import api from "../services/api";
import type { Dataset } from "../types/datasets";
import type { PreparationComparison, PreparationOperation, PreparationPreview, PreparationSession } from "../types/dataPreparation";

const LOGICAL_TYPES = ["string", "integer", "float", "boolean", "date", "datetime", "categorical"];

export default function DataPreparationPage() {
  const [file, setFile] = useState<File | null>(null);
  const [session, setSession] = useState<PreparationSession | null>(null);
  const [selectedOperations, setSelectedOperations] = useState<string[]>([]);
  const [columnNames, setColumnNames] = useState<Record<number, string>>({});
  const [columnTypes, setColumnTypes] = useState<Record<number, string>>({});
  const [missingStrategies, setMissingStrategies] = useState<Record<number, string>>({});
  const [missingConstants, setMissingConstants] = useState<Record<number, string>>({});
  const [categoryMappings, setCategoryMappings] = useState<Record<number, { from: string; to: string }>>({});
  const [removeDuplicates, setRemoveDuplicates] = useState(false);
  const [dropColumns, setDropColumns] = useState<number[]>([]);
  const [preview, setPreview] = useState<PreparationPreview | null>(null);
  const [previewVersion, setPreviewVersion] = useState<"original" | "proposed" | "cleaned">("original");
  const [progress, setProgress] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const analyze = async () => {
    if (!file) return;
    setBusy(true);
    setProgress(0);
    setError("");
    setNotice("");
    const form = new FormData();
    form.append("file", file);
    try {
      const { data } = await api.post<PreparationSession>("/api/data-preparation/analyze", form, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (event) => { if (event.total) setProgress(Math.round((event.loaded / event.total) * 100)); },
      });
      setSession(data);
      setPreview(data.preview ?? null);
      setSelectedOperations(data.plan.filter((operation) => operation.selected).map((operation) => operation.id));
      setColumnNames(Object.fromEntries(data.columns.map((column) => [column.column_index, column.suggested_name])));
      setColumnTypes(Object.fromEntries(data.columns.map((column) => [column.column_index, column.suggested_type])));
      setRemoveDuplicates(false);
    } catch (requestError: unknown) {
      setError(getError(requestError));
    } finally {
      setBusy(false);
    }
  };

  const buildRequest = () => {
    if (!session) return {};
    const overrides = session.columns.map((column) => ({
      column_index: column.column_index,
      ...(columnNames[column.column_index] !== column.suggested_name ? { name: columnNames[column.column_index] } : {}),
      ...(columnTypes[column.column_index] !== column.suggested_type ? { data_type: columnTypes[column.column_index] } : {}),
    })).filter((item) => item.name || item.data_type);
    const missing = Object.entries(missingStrategies).filter(([, strategy]) => strategy !== "keep").map(([index, strategy]) => ({
      column_index: Number(index), strategy,
      ...(strategy === "constant" ? { value: missingConstants[Number(index)] ?? "" } : {}),
    }));
    const mappings = Object.fromEntries(Object.entries(categoryMappings).filter(([, mapping]) => mapping.from.trim() && mapping.to.trim()).map(([index, mapping]) => [index, { [mapping.from]: mapping.to }]));
    return { selected_operation_ids: selectedOperations, column_overrides: overrides, missing_strategies: missing, category_mappings: mappings, remove_duplicates: removeDuplicates, drop_column_indexes: dropColumns };
  };

  const previewChanges = async () => {
    if (!session) return;
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post<{ preview: PreparationPreview; comparison: PreparationComparison }>(`/api/data-preparation/${session.id}/preview`, buildRequest());
      setPreview(data.preview);
      setPreviewVersion("proposed");
    } catch (requestError: unknown) {
      setError(getError(requestError));
    } finally {
      setBusy(false);
    }
  };

  const apply = async () => {
    if (!session) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const { data } = await api.post<PreparationSession>(`/api/data-preparation/${session.id}/apply`, buildRequest());
      setSession(data);
      setPreview(data.preview ?? null);
      setPreviewVersion("cleaned");
      setNotice("Selected changes have been applied to a separate prepared CSV. The original upload is unchanged.");
    } catch (requestError: unknown) {
      setError(getError(requestError));
    } finally {
      setBusy(false);
    }
  };

  const loadPreview = async (version: "original" | "cleaned") => {
    if (!session) return;
    setPreviewVersion(version);
    if (version === "original" && session.preview) {
      setPreview(session.preview);
      return;
    }
    try {
      const { data } = await api.get<PreparationPreview>(`/api/data-preparation/${session.id}/preview`, { params: { version } });
      setPreview(data);
    } catch (requestError: unknown) {
      setError(getError(requestError));
    }
  };

  const download = async () => {
    if (!session) return;
    try {
      const { data } = await api.get<Blob>(`/api/data-preparation/${session.id}/download`, { responseType: "blob" });
      const url = URL.createObjectURL(data);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${session.filename.replace(/\.csv$/i, "")}_cleaned.csv`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (requestError: unknown) {
      setError(getError(requestError));
    }
  };

  const save = async () => {
    if (!session) return;
    setBusy(true);
    try {
      const { data } = await api.post<Dataset>(`/api/data-preparation/${session.id}/save`, { name: `${session.filename.replace(/\.csv$/i, "")} cleaned` });
      setNotice(`Saved as “${data.name}” in Datasets. It is ready for profiling and analysis.`);
    } catch (requestError: unknown) {
      setError(getError(requestError));
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setSession(null);
    setPreview(null);
    setFile(null);
    setSelectedOperations([]);
    setColumnNames({});
    setColumnTypes({});
    setMissingStrategies({});
    setCategoryMappings({});
    setRemoveDuplicates(false);
    setDropColumns([]);
    setError("");
    setNotice("");
  };

  return <main className="min-h-screen bg-paper px-5 py-8 text-ink sm:px-8 lg:px-10">
    <div className="mx-auto max-w-7xl">
      <div className="flex items-center justify-between gap-4 border-b border-ink/10 pb-7">
        <div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-moss">Prepare for analysis</p><h1 className="mt-2 font-display text-4xl sm:text-5xl">AI Data Structurer</h1><p className="mt-3 max-w-2xl text-ink/60">Inspect a raw CSV, review every proposed change, then create a separate analysis-ready dataset.</p></div>
        <Link className="inline-flex shrink-0 items-center gap-2 text-sm font-semibold text-moss" to="/dashboard"><Home size={17} />Home</Link>
      </div>

      {error && <div role="alert" className="mt-6 flex items-start justify-between gap-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800"><span>{error}</span><button aria-label="Dismiss error" onClick={() => setError("")}><X size={17} /></button></div>}
      {notice && <p role="status" className="mt-6 rounded-lg border border-moss/20 bg-moss/5 p-4 text-sm text-moss">{notice}</p>}

      {!session && <section className="mt-8 border-l-4 border-coral bg-white p-6 shadow-sm sm:p-8">
        <div className="flex items-start gap-4"><div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-lime text-ink"><Sparkles size={21} /></div><div><h2 className="font-display text-2xl">Upload a CSV dataset</h2><p className="mt-1 text-sm text-ink/55">CSV only · maximum size follows the server upload limit · original file is kept unchanged.</p></div></div>
        <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-center">
          <label className="flex min-h-14 flex-1 cursor-pointer items-center gap-3 rounded-lg border border-dashed border-ink/25 px-4 py-3 transition hover:border-moss hover:bg-paper"><FileUp className="shrink-0 text-moss" size={19} /><span className="min-w-0 flex-1 truncate text-sm font-semibold">{file ? file.name : "Choose a CSV file"}</span>{file && <span className="text-xs text-ink/50">{formatBytes(file.size)}</span>}<input className="sr-only" type="file" accept=".csv,text/csv" onChange={(event) => { setFile(event.target.files?.[0] ?? null); setSession(null); }} /></label>
          {file && <button aria-label="Remove selected file" className="rounded-lg border border-ink/15 p-3 text-ink/60 hover:text-red-700" onClick={() => setFile(null)} type="button"><Trash2 size={18} /></button>}
          <button className="inline-flex items-center justify-center gap-2 rounded-lg bg-ink px-5 py-3 text-sm font-semibold text-paper transition hover:bg-moss disabled:cursor-not-allowed disabled:opacity-50" disabled={!file || busy} onClick={() => void analyze()} type="button">{busy ? <LoaderCircle className="animate-spin" size={17} /> : <Sparkles size={17} />}{busy ? `Analyzing ${progress}%` : "Analyze dataset"}</button>
        </div>
        {busy && <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-ink/10"><div className="h-full bg-coral transition-all" style={{ width: `${Math.max(progress, 8)}%` }} /></div>}
      </section>}

      {session && <>
        <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-b border-ink/10 pb-5"><div><p className="text-xs font-semibold uppercase tracking-[0.15em] text-moss">{session.status === "APPLIED" ? "Changes applied to output copy" : "Analysis complete"}</p><h2 className="mt-1 truncate font-display text-2xl">{session.filename}</h2></div><button className="inline-flex items-center gap-2 rounded-lg border border-ink/15 px-4 py-2.5 text-sm font-semibold hover:bg-white" onClick={reset} type="button"><RefreshCw size={16} />Start over</button></div>
        <section aria-label="Dataset overview" className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">{[
          ["Rows", session.overview.row_count.toLocaleString()], ["Columns", String(session.overview.column_count)], ["Missing", `${session.overview.missing_values.toLocaleString()} (${session.overview.missing_percentage}%)`], ["Duplicates", String(session.overview.duplicate_rows)], ["Type review", String(session.overview.inconsistent_type_columns)], ["Format review", String(session.overview.inconsistent_format_columns)], ["Suggestions", String(session.overview.suggested_transformations)], ["Warnings", String(session.overview.warnings)],
        ].map(([label, value]) => <div className="border-t-2 border-moss/50 bg-white/70 px-3 py-3" key={label}><p className="text-[11px] font-semibold uppercase tracking-wide text-ink/50">{label}</p><p className="mt-1 font-display text-2xl">{value}</p></div>)}</section>

        <section className="mt-10"><SectionTitle kicker="Detected schema" title="Columns and suggested structure" /><div className="mt-4 overflow-x-auto rounded-lg border border-ink/10 bg-white"><table className="min-w-[920px] w-full text-left text-sm"><thead className="bg-ink text-paper"><tr>{["Original column", "Suggested name", "Detected type", "Proposed type", "Missing", "Unique", "Examples / warnings"].map((heading) => <th className="px-4 py-3 font-semibold" key={heading}>{heading}</th>)}</tr></thead><tbody className="divide-y divide-ink/10">{session.columns.map((column) => <tr key={column.column_index} className="align-top"><td className="max-w-48 px-4 py-3 font-semibold">{column.original_name}</td><td className="min-w-48 px-3 py-2"><input aria-label={`Standardized name for ${column.original_name}`} className="w-full rounded border border-ink/15 px-2 py-2" value={columnNames[column.column_index] ?? ""} onChange={(event) => setColumnNames({ ...columnNames, [column.column_index]: event.target.value })} /></td><td className="px-4 py-3"><TypePill value={column.detected_type} /></td><td className="px-3 py-2"><select aria-label={`Suggested type for ${column.original_name}`} className="rounded border border-ink/15 bg-white px-2 py-2" value={columnTypes[column.column_index] ?? "string"} onChange={(event) => setColumnTypes({ ...columnTypes, [column.column_index]: event.target.value })}>{LOGICAL_TYPES.map((type) => <option key={type}>{type}</option>)}</select>{!column.type_confident && <p className="mt-1 max-w-36 text-[11px] text-coral">Ambiguous; retained unless confirmed.</p>}</td><td className="px-4 py-3">{column.null_count}</td><td className="px-4 py-3">{column.unique_count}</td><td className="max-w-64 px-4 py-3 text-xs text-ink/60"><p className="break-words">{column.examples.join(" · ") || "No values"}</p>{column.warnings.length > 0 && <p className="mt-1 text-coral">{column.warnings.join(", ")}</p>}</td></tr>)}</tbody></table></div></section>

        <section className="mt-10"><SectionTitle kicker="Quality review" title="Issues found" /><div className="mt-4 overflow-hidden rounded-lg border border-ink/10 bg-white"><div className="grid grid-cols-[1.1fr_1fr_0.6fr_2fr] gap-3 bg-ink px-4 py-3 text-xs font-semibold uppercase tracking-wide text-paper"><span>Issue</span><span>Column</span><span>Affected</span><span>Recommendation</span></div>{session.issues.length === 0 ? <p className="p-5 text-sm text-ink/55">No supported quality issues were detected. Review the inferred schema before applying changes.</p> : session.issues.map((issue, index) => <div className="grid grid-cols-[1.1fr_1fr_0.6fr_2fr] gap-3 border-t border-ink/10 px-4 py-3 text-sm" key={`${issue.type}-${issue.column}-${index}`}><span className="font-semibold">{humanize(issue.type)}{!issue.automatable && <span className="ml-2 text-[10px] uppercase text-coral">Review</span>}</span><span className="truncate text-ink/65">{issue.column ?? "All columns"}</span><span>{issue.affected_count}</span><span className="text-ink/65">{issue.recommendation}{issue.examples.length > 0 && <span className="mt-1 block text-xs text-ink/45">Examples: {issue.examples.join(" · ")}</span>}</span></div>)}</div></section>

        <section className="mt-10"><SectionTitle kicker="Review before applying" title="Transformation plan" /><p className="mt-2 text-sm text-ink/55">Suggestions are not applied unless selected. Rename and type edits in the schema table are user overrides.</p><div className="mt-4 divide-y divide-ink/10 overflow-hidden rounded-lg border border-ink/10 bg-white">{session.plan.length === 0 ? <p className="p-5 text-sm text-ink/55">No automatic operations were proposed. You can still review names and types below.</p> : session.plan.map((operation) => <OperationRow key={operation.id} operation={operation} selected={selectedOperations.includes(operation.id)} onToggle={() => setSelectedOperations((current) => current.includes(operation.id) ? current.filter((id) => id !== operation.id) : [...current, operation.id])} />)}</div>
          <div className="mt-5 grid gap-4 lg:grid-cols-2">
            <div className="rounded-lg border border-ink/10 bg-white p-5"><h3 className="font-display text-xl">Missing-value strategy</h3><p className="mt-1 text-xs text-ink/50">No imputation is performed by default.</p><div className="mt-4 space-y-3">{session.columns.filter((column) => column.null_count > 0).map((column) => <div className="grid gap-2 sm:grid-cols-[1fr_1fr_1fr] sm:items-center" key={column.column_index}><span className="truncate text-sm font-medium">{column.original_name} · {column.null_count} missing</span><select className="rounded border border-ink/15 bg-white px-2 py-2 text-sm" value={missingStrategies[column.column_index] ?? "keep"} onChange={(event) => setMissingStrategies({ ...missingStrategies, [column.column_index]: event.target.value })}><option value="keep">Keep as-is</option><option value="drop_rows">Remove rows</option>{["integer", "float"].includes(column.detected_type) && !/id|zip|postal|phone|code|sku/i.test(column.original_name) && <><option value="mean">Fill with mean</option><option value="median">Fill with median</option></>}<option value="mode">Fill with mode</option><option value="constant">Fill with value</option></select>{missingStrategies[column.column_index] === "constant" && <input aria-label={`Fill value for ${column.original_name}`} className="rounded border border-ink/15 px-2 py-2 text-sm" placeholder="Value" value={missingConstants[column.column_index] ?? ""} onChange={(event) => setMissingConstants({ ...missingConstants, [column.column_index]: event.target.value })} />}</div>)}</div>{!session.columns.some((column) => column.null_count > 0) && <p className="mt-4 text-sm text-ink/50">No missing cells to handle.</p>}</div>
            <div className="rounded-lg border border-ink/10 bg-white p-5"><h3 className="font-display text-xl">Explicit category mapping</h3><p className="mt-1 text-xs text-ink/50">Enter exact values. Similar-looking categories are never merged automatically.</p><div className="mt-4 space-y-3">{session.columns.filter((column) => column.detected_type === "categorical").map((column) => <div className="grid gap-2 sm:grid-cols-[1fr_1fr_1fr] sm:items-center" key={column.column_index}><span className="truncate text-sm font-medium">{column.original_name}</span><input aria-label={`Category to replace in ${column.original_name}`} className="min-w-0 rounded border border-ink/15 px-2 py-2 text-sm" placeholder="Exact source" value={categoryMappings[column.column_index]?.from ?? ""} onChange={(event) => setCategoryMappings({ ...categoryMappings, [column.column_index]: { ...categoryMappings[column.column_index], from: event.target.value, to: categoryMappings[column.column_index]?.to ?? "" } })} /><input aria-label={`Replacement category for ${column.original_name}`} className="min-w-0 rounded border border-ink/15 px-2 py-2 text-sm" placeholder="Replace with" value={categoryMappings[column.column_index]?.to ?? ""} onChange={(event) => setCategoryMappings({ ...categoryMappings, [column.column_index]: { ...categoryMappings[column.column_index], to: event.target.value, from: categoryMappings[column.column_index]?.from ?? "" } })} /></div>)}</div>{!session.columns.some((column) => column.detected_type === "categorical") && <p className="mt-4 text-sm text-ink/50">No categorical columns were inferred.</p>}</div>
          </div>
          <div className="mt-4 flex flex-wrap gap-5 rounded-lg border border-ink/10 bg-white p-4 text-sm"><label className="inline-flex items-center gap-2"><input type="checkbox" checked={removeDuplicates} onChange={(event) => setRemoveDuplicates(event.target.checked)} />Remove {session.overview.duplicate_rows} full duplicate rows, keep first</label>{session.columns.map((column) => <label className="inline-flex items-center gap-2" key={column.column_index}><input type="checkbox" checked={dropColumns.includes(column.column_index)} onChange={(event) => setDropColumns(event.target.checked ? [...dropColumns, column.column_index] : dropColumns.filter((index) => index !== column.column_index))} />Drop {column.original_name}</label>)}</div>
        </section>

        <div className="mt-8 flex flex-wrap items-center gap-3 border-y border-ink/10 py-5"><button className="inline-flex items-center gap-2 rounded-lg border border-ink/20 px-4 py-3 text-sm font-semibold hover:bg-white disabled:opacity-50" disabled={busy} onClick={() => void previewChanges()} type="button"><ChevronDown size={17} />Preview selected changes</button><button className="inline-flex items-center gap-2 rounded-lg bg-ink px-5 py-3 text-sm font-semibold text-paper hover:bg-moss disabled:opacity-50" disabled={busy} onClick={() => void apply()} type="button">{busy ? <LoaderCircle className="animate-spin" size={17} /> : <Check size={17} />}{session.status === "APPLIED" ? "Reapply selected changes" : "Apply selected changes"}</button>{session.status === "APPLIED" && <><button className="inline-flex items-center gap-2 rounded-lg border border-ink/20 px-4 py-3 text-sm font-semibold hover:bg-white" onClick={() => void download()} type="button"><ArrowDownToLine size={17} />Download CSV</button><button className="inline-flex items-center gap-2 rounded-lg bg-coral px-4 py-3 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50" disabled={busy} onClick={() => void save()} type="button"><Save size={17} />Save to Datasets</button></>}</div>

        {session.comparison && <Comparison comparison={session.comparison} />}
        <section className="mt-10"><div className="flex flex-wrap items-end justify-between gap-4"><div><SectionTitle kicker={previewVersion === "proposed" ? "Not applied" : "Inspect actual rows"} title={previewVersion === "proposed" ? "Proposed preview" : "Data preview"} /><p className="mt-1 text-sm text-ink/55">Showing up to 100 records. Original data is never overwritten.</p></div><div className="inline-flex rounded-lg border border-ink/15 bg-white p-1"><button className={`rounded px-3 py-2 text-sm ${previewVersion === "original" ? "bg-ink text-white" : ""}`} onClick={() => void loadPreview("original")} type="button">Original</button>{previewVersion === "proposed" && <button aria-current="page" className="rounded bg-lime px-3 py-2 text-sm" type="button">Proposed</button>}<button className={`rounded px-3 py-2 text-sm ${previewVersion === "cleaned" ? "bg-ink text-white" : ""}`} disabled={session.status !== "APPLIED"} onClick={() => void loadPreview("cleaned")} type="button">Prepared</button></div></div>{preview && <DataTable preview={preview} />}</section>
      </>}
    </div>
  </main>;
}

function OperationRow({ operation, selected, onToggle }: { operation: PreparationOperation; selected: boolean; onToggle: () => void }) {
  return <label className="grid cursor-pointer grid-cols-[auto_1fr_auto] items-center gap-3 px-4 py-3 transition hover:bg-paper/70"><input aria-label={`Select ${humanize(operation.type)} for ${operation.column ?? "all rows"}`} type="checkbox" checked={selected} onChange={onToggle} /><span><span className="block font-semibold">{humanize(operation.type)}{operation.column ? ` · ${operation.column}` : ""}</span><span className="mt-0.5 block text-xs text-ink/55">{operation.reason}{operation.affected_count > 0 ? ` · ${operation.affected_count} affected` : ""}</span></span><span className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase ${operation.safe ? "bg-moss/10 text-moss" : "bg-lime/50 text-ink"}`}>{operation.safe ? "Safe suggestion" : "Review"}</span></label>;
}

function Comparison({ comparison }: { comparison: PreparationComparison }) {
  const values: [string, string][] = [["Rows", `${comparison.original_row_count.toLocaleString()} → ${comparison.final_row_count.toLocaleString()}`], ["Columns", `${comparison.original_column_count} → ${comparison.final_column_count}`], ["Missing values", `${comparison.missing_before} → ${comparison.missing_after}`], ["Duplicate rows", `${comparison.duplicate_rows_before} → ${comparison.duplicate_rows_after}`], ["Rows removed", String(comparison.rows_removed)], ["Renamed columns", String(comparison.columns_renamed)], ["Type conversions", String(comparison.successful_type_conversions)], ["Category mappings", String(comparison.categories_standardized)]];
  return <section className="mt-8"><SectionTitle kicker="Applied output" title="Before and after" /><div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">{values.map(([label, value]) => <div className="border-l-2 border-coral bg-white px-4 py-3" key={label}><p className="text-xs uppercase tracking-wide text-ink/50">{label}</p><p className="mt-1 font-display text-xl">{value}</p></div>)}</div><div className="mt-3 space-y-1 text-sm">{comparison.failed_type_conversions.map((failure) => <p className="text-coral" key={failure.column_index}>Column {failure.column_index + 1}: {failure.count} values could not be converted; examples: {failure.examples.join(", ")}</p>)}{comparison.warnings.map((warning) => <p className="text-coral" key={warning}>{warning}</p>)}{comparison.warnings.length === 0 && comparison.failed_type_conversions.length === 0 && <p className="text-ink/50">No unresolved conversion failures were reported. Review the issue list for remaining data concerns.</p>}</div></section>;
}

function DataTable({ preview }: { preview: PreparationPreview }) {
  return <div className="mt-4 max-h-[520px] overflow-auto rounded-lg border border-ink/10 bg-white"><table className="min-w-full text-left text-sm"><thead className="sticky top-0 bg-ink text-paper"><tr>{preview.columns.map((column) => <th className="whitespace-nowrap px-4 py-3" key={column}>{column}</th>)}</tr></thead><tbody className="divide-y divide-ink/10">{preview.rows.map((row, rowIndex) => <tr key={rowIndex}>{preview.columns.map((column) => <td className="max-w-64 whitespace-nowrap px-4 py-3 text-ink/70" key={column}>{row[column] === null || row[column] === undefined ? <span className="text-ink/30">null</span> : String(row[column])}</td>)}</tr>)}</tbody></table><p className="border-t border-ink/10 px-4 py-2 text-xs text-ink/45">{preview.returned_rows} of {preview.total_rows.toLocaleString()} rows shown</p></div>;
}

function SectionTitle({ kicker, title }: { kicker: string; title: string }) { return <div><p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-moss">{kicker}</p><h2 className="mt-1 font-display text-2xl">{title}</h2></div>; }
function TypePill({ value }: { value: string }) { return <span className="rounded-full bg-lime/50 px-2 py-1 text-xs font-semibold capitalize">{value}</span>; }
function humanize(value: string) { return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()); }
function formatBytes(bytes: number) { return bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / (1024 * 1024)).toFixed(2)} MB`; }
function getError(error: unknown) { if (typeof error === "object" && error !== null && "response" in error) { const response = (error as { response?: { data?: { detail?: string; error?: { message?: string } } } }).response; return response?.data?.error?.message ?? response?.data?.detail ?? "The request could not be completed."; } return "The request could not be completed."; }