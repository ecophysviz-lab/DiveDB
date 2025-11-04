import dash
import os
import sys

from dotenv import load_dotenv
import dash_bootstrap_components as dbc
from pathlib import Path
from dash import dcc, html

from DiveDB.services.duck_pond import DuckPond
from DiveDB.services.notion_orm import NotionORMManager
from layout import (
    create_header,
    create_main_content,
    create_left_sidebar,
    create_right_sidebar,
    create_footer,
    create_bookmark_modal,
    create_empty_figure,
    create_empty_dataframe,
)
from callbacks import register_callbacks
from clientside_callbacks import register_clientside_callbacks
from selection_callbacks import register_selection_callbacks

# Add DiveDB root to path for Immich integration
sys.path.append(str(Path(__file__).parent.parent))

from immich_integration import ImmichService  # noqa: E402

load_dotenv()

# Initialize Notion manager
notion_manager = NotionORMManager(
    token=os.getenv("NOTION_TOKEN"),
    db_map={
        "Deployment DB": os.getenv("NOTION_DEPLOYMENT_DB"),
        "Recording DB": os.getenv("NOTION_RECORDING_DB"),
        "Logger DB": os.getenv("NOTION_LOGGER_DB"),
        "Animal DB": os.getenv("NOTION_ANIMAL_DB"),
        "Dataset DB": os.getenv("NOTION_DATASET_DB"),
        "Signal DB": os.getenv("NOTION_SIGNAL_DB"),
        "Standardized Channel DB": os.getenv("NOTION_STANDARDIZEDCHANNEL_DB"),
    },
)

app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "/assets/styles.css",  # Custom SASS-compiled CSS
    ],
)

# Initialize services (will be passed to callbacks)
duck_pond = DuckPond.from_environment(notion_manager=notion_manager)
immich_service = ImmichService()

# Datasets will be loaded on page load via callback, not at server startup


def create_app_stores(dff, initial_deployments=None):
    """Create the dcc.Store and dcc.Interval components."""
    return [
        # Location for triggering callbacks on page load
        dcc.Location(id="url", refresh=False),
        # Existing stores for playback
        dcc.Interval(
            id="interval-component",
            interval=1 * 1000,  # Base interval of 1 second
            n_intervals=0,
            disabled=True,  # Start with the interval disabled
        ),
        dcc.Store(id="playhead-time", data=dff["timestamp"].min()),
        dcc.Store(id="is-playing", data=False),
        # Store for selected video data
        dcc.Store(id="selected-video", data=None),
        # Store for sticky manual selection
        dcc.Store(id="manual-video-override", data=None),
        # Store for video timeline offset in seconds
        dcc.Store(id="video-time-offset", data=0),
        # New stores for dataset/deployment selection
        dcc.Store(id="selected-dataset", data=None),
        dcc.Store(id="selected-deployment", data=None),
        # Trigger callbacks on page load
        dcc.Store(id="trigger-initial-load", data=True),
        dcc.Store(id="selected-date-range", data=None),
        dcc.Store(id="selected-timezone", data=0),
        dcc.Store(id="available-datasets", data=[]),  # Store for loaded datasets
        dcc.Store(id="available-deployments", data=initial_deployments or []),
        dcc.Store(id="deployment-date-ranges", data={}),
        dcc.Store(id="visualization-loaded", data=False),
        dcc.Store(id="loading-state", data={"stage": "idle", "message": ""}),
        # Store for passing duck_pond reference (will be populated by app)
        dcc.Store(id="duck-pond-config", data=None),
    ]


def create_layout(
    fig,
    data_json,
    dff,
    video_options=None,
    restricted_time_range=None,
    events_df=None,
    available_datasets=None,
    initial_deployments=None,
):
    """Create the complete app layout."""
    return html.Div(
        [
            html.Div(
                [
                    html.Div([], className="announcement_bar"),
                    create_header(),
                    create_left_sidebar(
                        available_datasets=available_datasets,
                        initial_deployments=initial_deployments,
                    ),
                    create_main_content(fig),
                    create_right_sidebar(
                        data_json,
                        dff["timestamp"].min(),
                        video_options=video_options,
                        restricted_time_range=restricted_time_range,
                    ),
                    create_footer(
                        dff, video_options=video_options, events_df=events_df
                    ),
                ],
                className="grid",
            ),
            create_bookmark_modal(),
            *create_app_stores(dff, initial_deployments=initial_deployments),
        ],
        id="main-layout",
        className="default-layout",
    )


# Create initial empty layout
initial_dff = create_empty_dataframe()
initial_fig = create_empty_figure()
initial_data_json = initial_dff[["datetime"]].to_json(orient="split")  # Minimal data

# Create the app layout with empty initial state
app.layout = create_layout(
    fig=initial_fig,
    data_json=initial_data_json,
    dff=initial_dff,
    video_options=[],
    restricted_time_range=None,
    events_df=None,
    available_datasets=[],
    initial_deployments=[],
)

# Register all callbacks
print("🚀 Starting callback registration...")
register_callbacks(app, initial_dff, video_options=[])
print("✓ Standard callbacks registered")
# Register selection callbacks BEFORE clientside to establish primary outputs
register_selection_callbacks(app, duck_pond, immich_service)
print("✓ Selection callbacks registered")
# Register clientside callbacks last (these use allow_duplicate=True)
register_clientside_callbacks(app)
print("✓ Clientside callbacks registered")
print("🎉 All callbacks registered! App ready.")


if __name__ == "__main__":
    app.run(debug=True, port=8054)
