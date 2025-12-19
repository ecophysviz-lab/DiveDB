import os
import sys

from dotenv import load_dotenv
import dash_bootstrap_components as dbc
from pathlib import Path
from dash import dcc, html
import pandas as pd
from dash_extensions.enrich import DashProxy, ServersideOutputTransform

from DiveDB.services.duck_pond import DuckPond
from DiveDB.services.notion_orm import NotionORMManager
from layout import (
    create_header,
    create_main_content,
    create_left_sidebar,
    create_right_sidebar,
    create_footer,
    create_footer_empty,
    create_bookmark_modal,
    create_event_modal,
    create_event_toast,
    create_empty_figure,
    create_empty_dataframe,
    create_loading_overlay,
)
from callbacks import register_callbacks
from clientside_callbacks import register_clientside_callbacks
from selection_callbacks import register_selection_callbacks
from logging_config import get_logger

# Add DiveDB root to path for Immich integration
sys.path.append(str(Path(__file__).parent.parent))

from DiveDB.services import ImmichService  # noqa: E402

load_dotenv()

# Cache toggle - set via DASH_USE_CACHE environment variable
USE_CACHE = os.getenv("DASH_USE_CACHE", "false").lower() in ("true", "1", "yes")

# Initialize Notion manager
notion_manager = NotionORMManager(
    token=os.getenv("NOTION_TOKEN"),
    db_map={
        "Deployment DB": os.getenv("NOTION_DEPLOYMENT_DB"),
        "Recording DB": os.getenv("NOTION_RECORDING_DB"),
        "Logger DB": os.getenv("NOTION_LOGGER_DB"),
        "Animal DB": os.getenv("NOTION_ANIMAL_DB"),
        "Species DB": os.getenv("NOTION_SPECIES_DB"),
        "Asset DB": os.getenv("NOTION_ASSETS_DB"),
        "Dataset DB": os.getenv("NOTION_DATASET_DB"),
        "Signal DB": os.getenv("NOTION_SIGNAL_DB"),
        "Standardized Channel DB": os.getenv("NOTION_STANDARDIZEDCHANNEL_DB"),
    },
)

app = DashProxy(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "/assets/styles.css",  # Custom SASS-compiled CSS
    ],
    transforms=[ServersideOutputTransform()],
)

# Initialize services (will be passed to callbacks)
duck_pond = DuckPond.from_environment(notion_manager=notion_manager)
immich_service = ImmichService()

# Datasets will be loaded on page load via callback, not at server startup


def create_app_stores(dff):
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
        # Store the actual timestamp data for playback
        dcc.Store(id="playback-timestamps", data=dff["timestamp"].tolist()),
        # Store for selected video data
        dcc.Store(id="selected-video", data=None),
        # Store for sticky manual selection
        dcc.Store(id="manual-video-override", data=None),
        # Store for video timeline offset in seconds
        dcc.Store(id="video-time-offset", data=0),
        # Store for current video options (loaded dynamically with deployments)
        dcc.Store(id="current-video-options", data=[]),
        # Stores for dataset/deployment selection
        dcc.Store(id="selected-dataset", data=None),
        dcc.Store(id="selected-deployment", data=None),
        dcc.Store(
            id="all-datasets-deployments", data={}
        ),  # All datasets with deployments
        dcc.Store(id="selected-timezone", data=0),
        dcc.Store(id="is-loading-data", data=False),  # Track data loading state
        dcc.Store(id="channel-order", data=[]),  # Track channel order
        # Stores for channel management
        dcc.Store(id="available-channels", data=[]),  # Channel options from DuckPond
        dcc.Store(id="selected-channels", data=[]),  # User-selected channels to display
        # Store for FigureResampler object (server-side cached)
        dcc.Store(id="figure-store", data=None),
        # Stores for event management
        dcc.Store(
            id="available-events", data=[]
        ),  # List of unique event types for deployment
        dcc.Store(
            id="selected-events", data=[]
        ),  # List of dicts: [{event_key, signal, enabled}, ...]
        # Store for channel order from DOM (updated by clientside callback on Update Graph click)
        dcc.Store(id="channel-order-from-dom", data=[]),
        # Store for playback rate (1x, 5x, 10x, or 100x)
        dcc.Store(id="playback-rate", data=1),
        # Hidden input for arrow key navigation (updated by JS, triggers callback)
        dcc.Input(
            id="arrow-key-input",
            type="hidden",
            value="",
            style={"display": "none"},
        ),
        # Store for timeline bounds (updated on graph zoom)
        dcc.Store(id="timeline-bounds", data=None),  # {min: timestamp, max: timestamp}
        # Store for original bounds (persists initial range for reset zoom)
        dcc.Store(id="original-bounds", data=None),  # {min: timestamp, max: timestamp}
        # Stores for B-key event bookmark feature
        dcc.Input(
            id="bookmark-trigger",
            type="hidden",
            value="",
            style={"display": "none"},
        ),  # Captures B keypress
        dcc.Store(id="last-event-type", data=None),  # Persists last used event type
        dcc.Store(
            id="pending-event-time", data=None
        ),  # Captures playhead time when modal opens
        dcc.Store(
            id="event-refresh-trigger", data=0
        ),  # Counter to trigger graph refresh after event creation
    ]


def create_layout(
    fig,
    data_json,
    dff,
    video_options=None,
    restricted_time_range=None,
    events_df=None,
    channel_options=None,
    use_empty_footer=False,
):
    """Create the complete app layout."""
    # Choose footer based on whether we have data
    if use_empty_footer:
        footer_component = create_footer_empty()
    else:
        footer_component = create_footer(
            dff, video_options=video_options, events_df=events_df
        )

    return html.Div(
        [
            html.Div(
                [
                    html.Div([], className="announcement_bar"),
                    create_header(),
                    create_left_sidebar(),  # No initial data - populated by callback
                    create_main_content(fig, channel_options=channel_options),
                    create_right_sidebar(
                        data_json,
                        dff["timestamp"].min(),
                        video_options=video_options,
                        restricted_time_range=restricted_time_range,
                    ),
                    footer_component,
                ],
                className="grid",
            ),
            create_bookmark_modal(),
            create_event_modal(),  # B-key event creation modal
            create_event_toast(),  # Toast notification for event save feedback
            create_loading_overlay(),  # Add loading overlay
            *create_app_stores(dff),
        ],
        id="main-layout",
        className="default-layout",
    )


# Create initial empty layout
initial_dff = create_empty_dataframe()
initial_fig = create_empty_figure()
# Create empty data JSON with proper structure for 3D model
# Use completely empty dataframe (no rows, no columns) to avoid errors
empty_model_df = pd.DataFrame({"datetime": []}).set_index("datetime")
initial_data_json = empty_model_df.to_json(orient="split")

# Create the app layout with empty initial state
app.layout = create_layout(
    fig=initial_fig,
    data_json=initial_data_json,
    dff=initial_dff,
    video_options=[],
    restricted_time_range=None,
    events_df=None,
    channel_options=None,  # Will use default fallback options
    use_empty_footer=True,  # Start with empty footer
)

# Register all callbacks
logger = get_logger(__name__)
logger.info("Starting callback registration...")
register_callbacks(app, initial_dff, video_options=[], channel_options=None)
logger.debug("Standard callbacks registered")
# Register selection callbacks BEFORE clientside to establish primary outputs
register_selection_callbacks(app, duck_pond, immich_service, use_cache=USE_CACHE)
logger.debug("Selection callbacks registered")
# Register clientside callbacks last (these use allow_duplicate=True)
register_clientside_callbacks(app)
logger.debug("Clientside callbacks registered")
logger.info("All callbacks registered! App ready.")


if __name__ == "__main__":
    app.run(debug=True, port=8054)
