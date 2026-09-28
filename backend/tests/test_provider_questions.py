from app.services.llm_provider import DevelopmentProvider


SCHEMA = [
    {"column_name": "order_id", "data_type": "integer", "nullable": False},
    {"column_name": "date", "data_type": "string", "nullable": False},
    {"column_name": "product", "data_type": "string", "nullable": False},
    {"column_name": "category", "data_type": "string", "nullable": False},
    {"column_name": "region", "data_type": "string", "nullable": False},
    {"column_name": "quantity", "data_type": "integer", "nullable": False},
    {"column_name": "price", "data_type": "float", "nullable": False},
    {"column_name": "revenue", "data_type": "float", "nullable": False},
]


def test_supported_questions_generate_read_only_dataset_queries():
    provider = DevelopmentProvider()
    questions = [
        "What is the total revenue?",
        "What are the top 5 products by revenue?",
        "Which region generated the highest revenue?",
        "Show monthly revenue.",
        "What is the average order value by category?",
        "Compare revenue between regions.",
        "Which products have unusually high sales?",
    ]

    for question in questions:
        result = provider.generate_sql(question, SCHEMA)
        assert result.sql.lower().startswith("select")
        assert "dataset_data" in result.sql
        assert all(keyword not in result.sql.lower() for keyword in ["drop", "delete", "update", "insert"])
