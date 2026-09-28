from pathlib import Path

import pandas as pd
import pytest

from app.services.data_preparation_service import (
    PreparationError,
    analyze_csv,
    apply_plan,
    normalize_column_names,
    preview_frame,
    write_clean_csv,
)


def write_source(tmp_path: Path, text: str) -> Path:
    source = tmp_path / "raw.csv"
    source.write_text(text, encoding="utf-8")
    return source


def test_normalize_column_names_is_safe_and_resolves_collisions():
    assert normalize_column_names(["Customer Name", "Annual Salary ($)", "Order-Date", "customer_name", "SELECT", ""]) == [
        "customer_name", "annual_salary", "order_date", "customer_name_2", "select_value", "column_6"
    ]


def test_analysis_preserves_identifier_and_flags_ambiguous_date(tmp_path):
    source = write_source(tmp_path, "Customer ID,Order Date,Amount\n00124,03/04/2025,₹50,000\n00125,04/05/2025,45000\n")
    # Quoted currency fields keep the source CSV structurally valid.
    source.write_text('Customer ID,Order Date,Amount\n00124,03/04/2025,"₹50,000"\n00125,04/05/2025,45000\n', encoding="utf-8")

    metadata, plan = analyze_csv(source, "raw.csv")

    assert metadata["columns"][0]["suggested_type"] == "string"
    assert metadata["columns"][0]["examples"][0] == "00124"
    assert metadata["columns"][1]["type_confident"] is False
    assert any(issue["type"] == "ambiguous_date" for issue in metadata["issues"])
    assert any(operation["type"] == "parse_numeric" for operation in plan)


def test_apply_selected_rename_currency_parse_categories_and_duplicates(tmp_path):
    source = write_source(tmp_path, 'Customer ID,Revenue,Gender\n0012,"₹50,000",Male\n0012,"₹50,000",Male\n0003,1000,male\n')
    metadata, plan = analyze_csv(source, "raw.csv")
    numeric_id = next(item["id"] for item in plan if item["type"] == "rename_column" and item["column_index"] == 0)
    numeric_revenue = next(item["id"] for item in plan if item["type"] == "parse_numeric")
    duplicate_id = next(item["id"] for item in plan if item["type"] == "remove_duplicate_rows")
    frame, comparison, history = apply_plan(source, metadata, plan, {
        "selected_operation_ids": [numeric_id, numeric_revenue, duplicate_id],
        "column_overrides": [], "missing_strategies": [],
        "category_mappings": {"2": {"male": "Male"}}, "remove_duplicates": True,
        "drop_column_indexes": [],
    })

    assert frame["customer_id"].tolist() == ["0012", "0003"]
    assert frame["revenue"].tolist() == [50000.0, 1000.0]
    assert frame["gender"].tolist() == ["Male", "Male"]
    assert comparison["rows_removed"] == 1
    assert comparison["duplicate_rows_after"] == 0
    assert any(item["type"] == "replace_categories" for item in history)


def test_missing_imputation_rejects_identifier_and_empty_column(tmp_path):
    source = write_source(tmp_path, "customer_id,value\n001,\n002,\n")
    metadata, plan = analyze_csv(source, "raw.csv")

    with pytest.raises(PreparationError, match="entirely missing"):
        apply_plan(source, metadata, plan, {
            "selected_operation_ids": [], "column_overrides": [],
            "missing_strategies": [{"column_index": 1, "strategy": "mean"}],
            "category_mappings": {}, "remove_duplicates": False, "drop_column_indexes": [],
        })


def test_invalid_numeric_conversion_is_reported_and_csv_is_written(tmp_path):
    source = write_source(tmp_path, "amount\n10\ninvalid\n")
    frame = pd.DataFrame({"amount": [10, 11]})
    output = tmp_path / "prepared" / "clean.csv"

    assert write_clean_csv(frame, output) > 0
    assert pd.read_csv(output)["amount"].tolist() == [10, 11]
    assert preview_frame(frame)["total_rows"] == 2

    metadata, _ = analyze_csv(source, "raw.csv")
    _, comparison, _ = apply_plan(source, metadata, [], {
        "selected_operation_ids": [], "column_overrides": [{"column_index": 0, "data_type": "integer"}],
        "missing_strategies": [], "category_mappings": {}, "remove_duplicates": False,
        "drop_column_indexes": [],
    })
    assert comparison["failed_type_conversions"][0]["count"] == 1