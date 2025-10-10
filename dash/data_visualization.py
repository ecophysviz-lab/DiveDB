import dash
import os
import sys
from dotenv import load_dotenv
import dash_bootstrap_components as dbc
from pathlib import Path

from DiveDB.services.duck_pond import DuckPond
from DiveDB.services.notion_orm import NotionORMManager
from graph_utils import plot_tag_data_interactive5
from layout import create_layout
from callbacks import register_callbacks
from clientside_callbacks import register_clientside_callbacks

# Add DiveDB root to path for Immich integration
sys.path.append(str(Path(__file__).parent.parent))

from immich_integration import ImmichService  # noqa: E402

load_dotenv()
# Hard-coded dataset and deployment IDs
DATASET_ID = "apfo-adult-penguin_hr-sr_penguin-ranch_JKB-PP"
DEPLOYMENT_ID = "DepID_2019-11-08_apfo-001"  # Deployment ID format: date + animal ID
START_DATE = "2019-11-08T09:33:11"
END_DATE = "2019-11-08T09:39:30"
TIMEZONE = 13
START_DATE_TZ = START_DATE + f"+{TIMEZONE}:00"
END_DATE_TZ = END_DATE + f"+{TIMEZONE}:00"

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

duck_pond = DuckPond.from_environment(notion_manager=notion_manager)

channel_options = duck_pond.get_available_channels(
    dataset=DATASET_ID,
    include_metadata=True,
    pack_groups=True,
)

# Fetch available video assets from Immich for this deployment
immich_service = ImmichService()
media_result = immich_service.find_media_by_deployment_id(
    DEPLOYMENT_ID, media_type="VIDEO", shared=True
)

# Prepare video options for React component using immich service method
video_result = immich_service.prepare_video_options_for_react(media_result)
video_options = video_result.get("video_options", [])

dff = duck_pond.get_data(
    dataset=DATASET_ID,
    animal_ids="apfo-001",
    frequency=1,
    labels=[
        "depth",
        "temp_ext",
        "light",
        "pitch",
        "roll",
        "heading",
    ],
    pivoted=True,
    date_range=(START_DATE_TZ, END_DATE_TZ),
    apply_timezone_offset=TIMEZONE,
    add_timestamp_column=True,
)

# Fetch events for this deployment
events_df = duck_pond.get_events(
    dataset=DATASET_ID,
    animal_ids="apfo-001",
    date_range=(START_DATE_TZ, END_DATE_TZ),
    apply_timezone_offset=TIMEZONE,
    add_timestamp_columns=True,
)
dff["depth"] = dff["depth"].apply(lambda x: x * -1)

# Define the restricted time range (biologging data bounds) for video synchronization
data_start_time = dff["datetime"].min()
data_end_time = dff["datetime"].max()
restricted_time_range = {
    "start": data_start_time.isoformat(),
    "end": data_end_time.isoformat(),
    "startTimestamp": dff["timestamp"].min(),
    "endTimestamp": dff["timestamp"].max(),
}

# Replace the existing figure creation with a call to the new function
fig = plot_tag_data_interactive5(
    data_pkl={
        "sensor_data": {
            "light": dff[["datetime", "light"]],
            "temperature": dff[["datetime", "temp_ext"]],
        },
        "derived_data": {
            "prh": dff[["datetime", "pitch", "roll", "heading"]],
            "depth": dff[["datetime", "depth"]],
        },
        "sensor_info": {
            "light": {
                "channels": ["light"],
                "metadata": {
                    "light": {
                        "original_name": "Light",
                        "unit": "lux",
                    }
                },
            },
            "temperature": {
                "channels": ["temp_ext"],
                "metadata": {
                    "temperature": {
                        "original_name": "Temperature (imu)",
                        "unit": "°C",
                    }
                },
            },
        },
        "derived_info": {
            "depth": {
                "channels": ["depth"],
                "metadata": {
                    "depth": {
                        "original_name": "Corrected Depth",
                        "unit": "m",
                    }
                },
            },
            "prh": {
                "channels": ["pitch", "roll", "heading"],
                "metadata": {
                    "pitch": {
                        "original_name": "Pitch",
                        "unit": "°",
                    },
                    "roll": {
                        "original_name": "Roll",
                        "unit": "°",
                    },
                    "heading": {
                        "original_name": "Heading",
                        "unit": "°",
                    },
                },
            },
        },
    },
    sensors=["light", "temperature"],
)

# Set x-axis range to data range and set uirevision
fig.update_layout(
    xaxis=dict(
        range=[dff["datetime"].min(), dff["datetime"].max()],
    ),
    uirevision="constant",  # Maintain UI state across updates
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=-0.15,
        xanchor="right",
        x=1,
    ),
    font_family="Figtree",
    title_font_family="Figtree",
    font=dict(
        family="Figtree",
        size=14,
        weight="bold",
    ),
    paper_bgcolor="rgba(0,0,0,0)",  # Transparent background
    plot_bgcolor="rgba(245,245,245,1)",  # Transparent plot
    margin=dict(l=0, r=0, t=0, b=0),
)

# Convert DataFrame to JSON
data_json = dff[["datetime", "pitch", "roll", "heading"]].to_json(orient="split")

# Create the app layout using the modular layout system
app.layout = create_layout(
    fig,
    data_json,
    dff,
    video_options=video_options,
    restricted_time_range=restricted_time_range,
    events_df=events_df,
)

# Register callbacks
register_callbacks(app, dff, video_options)
register_clientside_callbacks(app)


if __name__ == "__main__":
    app.run(debug=True, port=8054)
