import threejs_model
from dash import Dash, callback, html, Input, Output
from DiveDB.services.duck_pond import DuckPond


duckpond = DuckPond()

labels = duckpond.conn.sql(
    f"""
    SELECT DISTINCT label
    FROM DataLake
    WHERE animal = 'oror-002'
    """
).df()
print(labels)

app = Dash(__name__)

app.layout = html.Div(
    [
        threejs_model.ThreejsModel(id="input", value="my-value", label="my-label"),
        html.Div(id="output"),
    ]
)


@callback(Output("output", "children"), Input("input", "value"))
def display_output(value):
    return "You have entered {}".format(value)


if __name__ == "__main__":
    app.run_server(debug=True, host="0.0.0.0", port=8050)
