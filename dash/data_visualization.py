import dash
import pandas as pd
from dotenv import load_dotenv
import dash_bootstrap_components as dbc
import os

from DiveDB.services.duck_pond import DuckPond
from DiveDB.services.notion_orm import NotionORMManager
from graph_utils import plot_tag_data_interactive5
from layout import create_layout
from callbacks import register_callbacks
from clientside_callbacks import register_clientside_callbacks

load_dotenv()

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
duck_pond = DuckPond.from_environment(notion_manager=notion_manager)

app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "/assets/styles.css",  # Custom SASS-compiled CSS
    ],
)

channel_dff = duck_pond.get_available_channels(
    dataset="apfo-adult-penguin_hr-sr_penguin-ranch_JKB-PP",
    include_metadata=True,
    pack_groups=True,
)

dff = duck_pond.get_data(
    dataset="apfo-adult-penguin_hr-sr_penguin-ranch_JKB-PP",
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
    date_range=("2019-11-08T09:33:11+13:00", "2019-11-08T09:39:30+13:00"),
)

# Ensure datetimes are timezone-aware in UTC first
dff["datetime"] = pd.to_datetime(dff["datetime"], errors="coerce")
if dff["datetime"].dt.tz is None:
    dff["datetime"] = dff["datetime"].dt.tz_localize("UTC")
else:
    dff["datetime"] = dff["datetime"].dt.tz_convert("UTC")

# Convert datetime to timestamp (seconds since epoch) for slider control
dff["timestamp"] = dff["datetime"].apply(lambda x: x.timestamp())
dff["depth"] = dff["depth"].apply(lambda x: x * -1)

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
app.layout = create_layout(fig, data_json, dff)

# Register callbacks
register_callbacks(app, dff)
register_clientside_callbacks(app)


if __name__ == "__main__":
    app.run(debug=True)
