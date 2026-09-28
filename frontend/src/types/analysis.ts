export type Chart = { type: "bar" | "line" | "pie" | "area" | "scatter" | "table"; x_axis?: string | null; y_axis?: string | null };
export type AnalysisResult = { question: string; sql: string; columns: string[]; rows: Record<string, string | number | null>[]; chart: Chart; insight: string; execution_time_ms: number };
export type ChatMessage = { id: number; role: "USER" | "ASSISTANT"; content: string; created_at: string };
export type AnalysisHistoryItem = { query_id: number; question: string; sql: string | null; columns: string[]; rows: Record<string, string | number | null>[]; insight: string | null; status: string; created_at: string };
