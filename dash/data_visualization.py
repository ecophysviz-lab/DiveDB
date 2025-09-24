"""
⚠️⚠️⚠️ TIMEZONE HACK WARNING ⚠️⚠️⚠️

This file contains a temporary hardcoded timezone correction for video timestamps.
Videos from Immich are incorrectly stored as UTC when they should be +13:00 timezone.

TODO: Fix video timezone metadata at the source (Immich system) and remove the
correct_video_timezone() function and all related timezone corrections.

⚠️⚠️⚠️ TIMEZONE HACK WARNING ⚠️⚠️⚠️
"""

import dash
import os
import sys
import pandas as pd
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

# Initialize Immich service
immich_service = ImmichService()


def correct_video_timezone(utc_timestamp_str):
    """
    ⚠️⚠️⚠️ TEMPORARY TIMEZONE HACK - FIX AT SOURCE ⚠️⚠️⚠️

    Videos in Immich are incorrectly stored as UTC when they should be +13:00.
    This function treats the UTC timestamp as if it were actually in +13:00 timezone.

    TODO: Fix video timezone metadata in Immich source system!

    Args:
        utc_timestamp_str: String like "2019-11-08T15:50:50.000Z" (incorrectly marked as UTC)

    Returns:
        Corrected timestamp string in proper +13:00 timezone
    """
    if not utc_timestamp_str or not utc_timestamp_str.endswith("Z"):
        return utc_timestamp_str

    # Remove Z suffix and treat as local time in +13:00
    local_time_str = utc_timestamp_str.replace("Z", "+13:00")

    print(f"   🔧 Timezone correction: {utc_timestamp_str} → {local_time_str}")

    return local_time_str


app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "/assets/styles.css",  # Custom SASS-compiled CSS
    ],
)

# Hard-coded dataset and deployment IDs
DATASET_ID = "apfo-adult-penguin_hr-sr_penguin-ranch_JKB-PP"
DEPLOYMENT_ID = "DepID_2019-11-08_apfo-001"  # Deployment ID format: date + animal ID

channel_options = duck_pond.get_available_channels(
    dataset=DATASET_ID,
    include_metadata=True,
    pack_groups=True,
)

# Fetch available video assets from Immich for this deployment
print(f"🔍 Fetching video assets from Immich for deployment: {DEPLOYMENT_ID}")
media_result = immich_service.find_media_by_deployment_id(
    DEPLOYMENT_ID, media_type="VIDEO", shared=True
)

if media_result["success"]:
    video_assets = media_result["data"]
    album_info = media_result.get("album_info", {})
    print(f"🎬 Total video assets: {len(video_assets)}")

    # Prepare video options for React component
    video_options = []
    if video_assets:
        for i, asset in enumerate(video_assets):
            asset_id = asset.get("id")
            filename = asset.get("originalFileName", "Unknown")
            created = asset.get("fileCreatedAt", "Unknown")
            file_created = asset.get("fileCreatedAt", "Unknown")

            # ⚠️ APPLY TIMEZONE CORRECTION - Videos incorrectly stored as UTC in Immich
            corrected_created = correct_video_timezone(file_created)

            # Create individual share link for this asset
            share_result = immich_service.create_asset_share_link(asset_id)
            asset_share_key = None

            if share_result["success"]:
                asset_share_key = share_result["share_data"]["key"]
            else:
                print(
                    f"      ⚠️ Failed to create share key: {share_result.get('error', 'Unknown')}"
                )

            # Get detailed metadata for this asset
            details_result = immich_service.get_media_details(asset_id)

            if details_result["success"]:
                metadata = details_result["data"]["metadata"]
                urls = details_result["data"]["urls"]

                # Create share URLs using the individual asset share key
                share_video_url = (
                    f"{urls.get('video_playback')}?key={asset_share_key}"
                    if asset_share_key
                    else None
                )
                share_thumbnail_url = (
                    f"{urls.get('thumbnail')}?key={asset_share_key}"
                    if asset_share_key
                    else urls.get("thumbnail")
                )

                video_option = {
                    "id": asset_id,
                    "filename": filename,
                    "fileCreatedAt": corrected_created,  # ⚠️ Using timezone-corrected timestamp
                    "shareUrl": share_video_url,
                    "originalUrl": urls.get("original"),  # Fallback if share fails
                    "thumbnailUrl": share_thumbnail_url,
                    "metadata": {
                        "duration": metadata.get("duration"),
                        "originalFilename": metadata.get("original_filename"),
                        "type": metadata.get("type"),
                    },
                }

                video_options.append(video_option)
            else:
                print(
                    f"      ❌ Failed to load metadata: {details_result.get('error', 'Unknown')}"
                )
    else:
        print("⚠️ No video assets found in deployment album")
else:
    print(f"❌ Failed to fetch media: {media_result.get('error', 'Unknown error')}")
    video_options = []

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

# Define the restricted time range (biologging data bounds) for video synchronization
data_start_time = dff["datetime"].min()
data_end_time = dff["datetime"].max()
restricted_time_range = {
    "start": data_start_time.isoformat(),
    "end": data_end_time.isoformat(),
    "startTimestamp": dff["timestamp"].min(),
    "endTimestamp": dff["timestamp"].max(),
}

print("📊 Biologging data time range for video sync:")
print(f"   Start: {data_start_time}")
print(f"   End: {data_end_time}")
print(f"   Duration: {(data_end_time - data_start_time).total_seconds():.1f} seconds\n")

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
)

# Register callbacks
register_callbacks(app, dff, video_options)
register_clientside_callbacks(app)


if __name__ == "__main__":
    app.run(debug=True)
