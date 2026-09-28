import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "../services/api";
import DataPreparationPage from "./DataPreparationPage";
import type { PreparationSession } from "../types/dataPreparation";

vi.mock("../services/api", () => ({ default: { post: vi.fn(), get: vi.fn() } }));

const analyzedSession: PreparationSession = {
  id: "prep-1",
  status: "ANALYZED",
  filename: "raw.csv",
  overview: { row_count: 2, column_count: 2, missing_values: 1, missing_percentage: 25, duplicate_rows: 0, inconsistent_type_columns: 0, inconsistent_format_columns: 0, suggested_transformations: 1, warnings: 1 },
  columns: [{ column_index: 0, original_name: "Customer ID", suggested_name: "customer_id", detected_type: "string", suggested_type: "string", type_confident: true, null_count: 0, unique_count: 2, examples: ["0012", "0003"], warnings: [] }, { column_index: 1, original_name: "Revenue", suggested_name: "revenue", detected_type: "float", suggested_type: "float", type_confident: true, null_count: 1, unique_count: 1, examples: ["1200"], warnings: ["missing_values"] }],
  issues: [{ column: "Revenue", type: "missing_values", affected_count: 1, examples: [], recommendation: "Choose a missing strategy", automatable: false }],
  plan: [{ id: "trim:0", type: "trim_whitespace", column_index: 0, column: "Customer ID", parameters: {}, reason: "Trim whitespace", affected_count: 1, examples: [], safe: true, selected: false, status: "proposed" }],
  comparison: null,
  history: [],
  preview: { columns: ["Customer ID", "Revenue"], rows: [{ "Customer ID": "0012", Revenue: "1200" }, { "Customer ID": "0003", Revenue: null }], total_rows: 2, returned_rows: 2 },
};

const appliedSession: PreparationSession = {
  ...analyzedSession,
  status: "APPLIED",
  comparison: { original_row_count: 2, final_row_count: 2, original_column_count: 2, final_column_count: 2, missing_before: 1, missing_after: 0, duplicate_rows_before: 0, duplicate_rows_after: 0, successful_type_conversions: 0, failed_type_conversions: [], columns_renamed: 1, categories_standardized: 0, rows_removed: 0, warnings: [] },
  preview: { columns: ["customer_id", "revenue"], rows: [{ customer_id: "0012", revenue: 1200 }], total_rows: 2, returned_rows: 1 },
};

function renderPage() {
  return render(<MemoryRouter><DataPreparationPage /></MemoryRouter>);
}

describe("DataPreparationPage", () => {
  beforeEach(() => vi.resetAllMocks());

  it("uploads, reviews, applies, previews, downloads, and saves a prepared dataset", async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ data: analyzedSession }).mockResolvedValueOnce({ data: appliedSession }).mockResolvedValueOnce({ data: { id: 7, name: "raw cleaned" } });
    vi.mocked(api.get).mockResolvedValue({ data: new Blob(["customer_id,revenue\n0012,1200"]), headers: {} });
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:prepared") });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);

    renderPage();
    fireEvent.change(screen.getByLabelText("Choose a CSV file"), { target: { files: [new File(["Customer ID,Revenue"], "raw.csv", { type: "text/csv" })] } });
    expect(screen.getByText("raw.csv")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /analyze dataset/i }));
    await screen.findByText("Columns and suggested structure");
    expect(screen.getByText("Missing Values")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Select Trim Whitespace for Customer ID"));
    fireEvent.click(screen.getByRole("button", { name: /apply selected changes/i }));
    await screen.findByText("Before and after");
    expect(screen.getByRole("button", { name: "Prepared" })).toBeEnabled();
    expect(screen.getByText("0012")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /download csv/i }));
    await waitFor(() => expect(api.get).toHaveBeenCalledWith("/api/data-preparation/prep-1/download", { responseType: "blob" }));
    fireEvent.click(screen.getByRole("button", { name: /save to datasets/i }));
    await waitFor(() => expect(api.post).toHaveBeenLastCalledWith("/api/data-preparation/prep-1/save", { name: "raw cleaned" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Saved as");
    click.mockRestore();
  });

  it("shows understandable analysis errors", async () => {
    vi.mocked(api.post).mockRejectedValueOnce({ response: { data: { detail: "Only CSV files are supported." } } });
    renderPage();
    fireEvent.change(screen.getByLabelText("Choose a CSV file"), { target: { files: [new File(["x"], "raw.txt")] } });
    fireEvent.click(screen.getByRole("button", { name: /analyze dataset/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Only CSV files are supported.");
  });
});