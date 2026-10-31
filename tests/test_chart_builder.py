import pytest

import pandas as pd

from backend.app.viz.chart_builder import ChartError, ChartSpec, build_figure, to_table_payload


def test_unknown_column_raises():
    pytest.importorskip("plotly")
    with pytest.raises(ChartError, match="not in result"):
        build_figure(pd.DataFrame({"x": [1]}), ChartSpec(result_id="D1", chart_type="bar", x="x", y="nope", title="t"))


def test_chart_data_consistency():
    pytest.importorskip("plotly")
    df = pd.DataFrame({"month": ["Jan", "Feb"], "ticket_count": [12, 20]})
    fig = build_figure(df, ChartSpec(result_id="D1", chart_type="bar", x="month", y="ticket_count", title="t"))
    y_values = list(fig.data[0].y)
    table = to_table_payload(df)
    table_y = [row[1] for row in table["rows"]]
    assert y_values == table_y == [12, 20]

