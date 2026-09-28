export type DatasetColumn = {
  id: number;
  column_name: string;
  data_type: string;
  nullable: boolean;
  unique_count: number;
  missing_count: number;
};

export type Dataset = {
  id: number;
  name: string;
  original_filename: string;
  row_count: number;
  column_count: number;
  file_size: number;
  source_preparation_id?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  columns: DatasetColumn[];
};

export type DatasetListResponse = { items: Dataset[]; total: number };
export type DatasetPreview = { dataset_id: number; columns: string[]; rows: Record<string, string | null>[]; total_rows: number; returned_rows: number };
