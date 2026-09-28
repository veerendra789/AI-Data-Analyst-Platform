import { describe, expect, it } from "vitest";
import { parseReport } from "../services/reportParser";

describe("report parsing", () => {
  it("reads structured report content", () => {
    const report = parseReport(JSON.stringify({ executive_summary: "Grounded summary", data_quality: { missing_values: 2 } }));

    expect(report?.executive_summary).toBe("Grounded summary");
    expect(report?.data_quality?.missing_values).toBe(2);
  });

  it("rejects malformed report content", () => {
    expect(parseReport("not json")).toBeNull();
  });
});
