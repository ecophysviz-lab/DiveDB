import dash
from dash import html
from dash.dependencies import Input, Output, State

import video_preview

app = dash.Dash(__name__)

app.layout = html.Div(
    [
        video_preview.VideoPreview(
            id="video-trimmer",
            videoSrc="/assets/2024-01-16_oror-002a_camera-96-20240116-091402-00008.mp4",
            activeTime=5,
            style={"width": "50vw", "height": "40vw"},
        ),
        html.Div(id="trim-output"),
    ]
)


@app.callback(
    Output("trim-output", "children"),
    [Input("video-trimmer", "startTime"), Input("video-trimmer", "endTime")],
    [State("video-trimmer", "id")],
)
def display_trim_times(start_time, end_time, component_id):
    if start_time is None or end_time is None:
        return "Loading..."
    return f"Trimmed video from {start_time:.2f}s to {end_time:.2f}s (Component ID: {component_id})"


if __name__ == "__main__":
    app.run_server(debug=True)
