export type ForecastResponse = {
  dataset_id: number;
  date_column: string;
  target_column: string;
  historical: { date: string; value: number }[];
  forecast: { date: string; value: number }[];
  model: string;
  frequency: string;
  observations: number;
};

export type RootCauseResponse = {
  dataset_id: number;
  question: string;
  observed_result: string;
  associations: { dimension: string; value: string; mean_metric: number; difference_from_overall: number; observations: number; relationship: string }[];
  caveat: string;
  sql: string | null;
};
