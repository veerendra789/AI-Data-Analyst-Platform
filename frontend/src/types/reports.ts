export type Report = {
  id: number;
  dataset_id: number;
  title: string;
  content: string;
  created_at: string;
};

export type ReportJob = {
  job_id: string;
  status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
  result: Report | null;
  error: string | null;
};
