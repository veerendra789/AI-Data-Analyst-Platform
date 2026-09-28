export type ProfileColumn = {
  name: string;
  data_type: string;
  nullable: boolean;
  unique_count: number;
  missing_count: number;
  missing_percentage: number;
};

export type DatasetProfile = {
  dataset_id: number;
  summary: {
    row_count: number;
    column_count: number;
    duplicate_rows: number;
    missing_values: number;
    missing_percentage: number;
    numeric_columns: string[];
    categorical_columns: string[];
    date_columns: string[];
  };
  columns: ProfileColumn[];
  numeric_statistics: Record<string, Record<string, number | null>>;
  categorical_summaries: Record<string, { unique_count: number; top_categories: { value: string; count: number }[] }>;
  correlations: Record<string, Record<string, number | null>>;
  distributions: Record<string, { start: number; end: number; count: number }[]>;
  outliers: Record<string, { lower_bound: number | null; upper_bound: number | null; count: number }>;
};

export type AnomalyResponse = {
  dataset_id: number;
  column: string;
  number_of_anomalies: number;
  anomaly_records: Record<string, string | number | null>[];
  relevant_columns: string[];
  model: string;
};
