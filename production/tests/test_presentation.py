from sql_analytics.main import csv_bytes


def test_csv_neutralizes_spreadsheet_formulas():
    data = csv_bytes(
        {
            "columns": ["name", "amount"],
            "rows": [
                {"name": '=HYPERLINK("evil")', "amount": "+1"},
                {"name": " @SUM(1)", "amount": "100"},
            ],
        }
    )
    text = data.decode("utf-8-sig")
    assert "'=HYPERLINK" in text
    assert "'+1" in text
    assert "' @SUM" in text
    assert "100" in text
