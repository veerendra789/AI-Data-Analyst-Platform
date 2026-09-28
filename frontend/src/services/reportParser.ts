export type ReportDocument = {
  executive_summary?: string;
  dataset_overview?: { name?: string; filename?: string; rows?: number; columns?: number };
  data_quality?: { missing_values?: number; missing_percentage?: number; duplicate_rows?: number };
  important_metrics?: Record<string, Record<string, number | null>>;
  trends?: Record<string, unknown>;
  anomalies?: Record<string, unknown>;
  forecast?: { target_column?: string; forecast?: { date: string; value: number }[] } | null;
  major_findings?: { finding?: string }[];
  ai_insights?: { question?: string; insight?: string }[];
};

export function parseReport(content: string): ReportDocument | null {
  try {
    return JSON.parse(content) as ReportDocument;
  } catch {
    return null;
  }
}
