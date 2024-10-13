import dash
from dash import html, dcc
import pytz
import pandas as pd
import three_js_orientation
from dash.dependencies import Input, Output

app = dash.Dash(__name__)

# Create sample data
dates = pd.date_range(start="2021-01-01", periods=10, freq="T")
data = {
    "pitch": [i * 5 for i in range(10)],
    "roll": [i * 3 for i in range(10)],
    "heading": [i * 10 for i in range(10)],
}
df = pd.DataFrame(data, index=dates)

print(df)

# Convert DataFrame to JSON
data_json = df.to_json(orient="split")

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
    # Calculate the next active time based on the number of intervals
    next_time_index = n_intervals % len(df.index)
    print(df.index[next_time_index])
    # Localize the timestamp to UTC
    next_time = df.index[next_time_index].tz_localize(pytz.UTC).isoformat()
    # Print the next time and its pitch, roll, and heading
    next_pitch = df.loc[next_time_index, "pitch"]
    next_roll = df.loc[next_time_index, "roll"]
    next_heading = df.loc[next_time_index, "heading"]
    print(
        f"Next time: {next_time}, Pitch: {next_pitch}, Roll: {next_roll}, Heading: {next_heading}"
    )
    return next_time


if __name__ == "__main__":
    app.run_server(debug=True)
