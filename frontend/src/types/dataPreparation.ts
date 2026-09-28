export type PreparationColumn = {
  column_index: number;
  original_name: string;
  suggested_name: string;
  detected_type: string;
  suggested_type: string;
  type_confident: boolean;
  null_count: number;
  unique_count: number;
  examples: string[];
  warnings: string[];
};

export type PreparationIssue = {
  column: string | null;
  type: string;
  affected_count: number;
  examples: string[];
  recommendation: string;
  automatable: boolean;
};

export type PreparationOperation = {
  id: string;
  type: string;
  column_index: number | null;
  column: string | null;
  parameters: Record<string, string | number | boolean>;
  reason: string;
  affected_count: number;
  examples: string[];
  safe: boolean;
  selected: boolean;
  status: string;
};

export type PreparationOverview = {
  row_count: number;
  column_count: number;
  missing_values: number;
  missing_percentage: number;
  duplicate_rows: number;
  inconsistent_type_columns: number;
  inconsistent_format_columns: number;
  suggested_transformations: number;
  warnings: number;
};

export type PreparationPreview = {
  columns: string[];
  rows: Record<string, string | number | boolean | null>[];
  total_rows: number;
  returned_rows: number;
};

export type PreparationComparison = {
  original_row_count: number;
  final_row_count: number;
  original_column_count: number;
  final_column_count: number;
  missing_before: number;
  missing_after: number;
  duplicate_rows_before: number;
  duplicate_rows_after: number;
  successful_type_conversions: number;
  failed_type_conversions: { column_index: number; count: number; examples: string[] }[];
  columns_renamed: number;
  categories_standardized: number;
  rows_removed: number;
  warnings: string[];
};

export type PreparationSession = {
  id: string;
  status: "ANALYZED" | "APPLIED";
  filename: string;
  overview: PreparationOverview;
  columns: PreparationColumn[];
  issues: PreparationIssue[];
  plan: PreparationOperation[];
  comparison: PreparationComparison | null;
  history: Record<string, string | number>[];
  preview?: PreparationPreview;
};