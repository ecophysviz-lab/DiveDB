import dash
from dash import html, dcc
import pytz
import three_js_orientation
from dash.dependencies import Input, Output
from DiveDB.services.duck_pond import DuckPond

app = dash.Dash(__name__)

# Create sample data
duckpond = DuckPond("/data/delta-2")
dff = duckpond.get_delta_data(
    animal_ids="oror-002",
    frequency=1,
    labels=[
        "derived_data_depth",
        "sensor_data_ecg",
        "sensor_data_temperature",
        "sensor_data_light",
        "pitch",
        "roll",
        "heading",
    ],
)

# Convert DataFrame to JSON
data_json = dff[["datetime", "pitch", "roll", "heading"]].to_json(orient="split")

app.layout = html.Div(
    [
        three_js_orientation.ThreeJsOrientation(
            id="three-d-model",
            data=data_json,
            activeTime="2021-01-01T00:01:00Z",
            fbxFile="/assets/6_KillerWhaleOrca_v020_HR_fast.fbx",
            style={"width": "800px", "height": "600px"},
        ),
        dcc.Interval(
            id="interval-component", interval=1 * 1000, n_intervals=0  # in milliseconds
        ),
    ]
)


@app.callback(
    Output("three-d-model", "activeTime"), [Input("interval-component", "n_intervals")]
)
def update_active_time(n_intervals):
    next_time_index = n_intervals % len(dff.index)
    next_time = dff.index[next_time_index]
    return next_time.tz_localize(pytz.UTC).isoformat()


if __name__ == "__main__":
    app.run_server(debug=True)
