import dash
import os
import sys

import pandas as pd
from dotenv import load_dotenv
import dash_bootstrap_components as dbc
from pathlib import Path
import plotly.graph_objects as go

from DiveDB.services.duck_pond import DuckPond
from DiveDB.services.notion_orm import NotionORMManager
from layout import create_layout
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

# Load datasets on startup
print("🔍 Loading datasets from data lake...")
available_datasets = duck_pond.get_all_datasets()
print(f"📊 Found {len(available_datasets)} datasets: {available_datasets}")

# Load deployments for the first dataset if available
initial_deployments = []
if available_datasets:
    default_dataset = available_datasets[0]
    print(f"🔍 Loading deployments for default dataset: {default_dataset}")
    try:
        view_name = duck_pond.get_view_name(default_dataset, "data")
        query = f"""
            SELECT DISTINCT 
                deployment,
                animal,
                MIN(datetime) as min_date,
                MAX(datetime) as max_date,
                COUNT(*) as sample_count
            FROM {view_name}
            WHERE deployment IS NOT NULL AND animal IS NOT NULL
            GROUP BY deployment, animal
            ORDER BY min_date DESC
        """
        deployments_df = duck_pond.conn.sql(query).df()
        initial_deployments = deployments_df.to_dict("records")
        print(f"📊 Found {len(initial_deployments)} deployments")
    except Exception as e:
        print(f"❌ Error loading initial deployments: {e}")


def create_empty_figure():
    """Create an empty placeholder figure for initial load."""
    fig = go.Figure()
    fig.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=[
            dict(
                text="Select a dataset and deployment to begin",
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                xanchor="center",
                yanchor="middle",
                showarrow=False,
                font=dict(size=20, color="gray"),
            )
        ],
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(245,245,245,1)",
        margin=dict(l=0, r=0, t=0, b=0),
        height=600,
    )
    return fig


def create_empty_dataframe():
    """Create a minimal empty dataframe for initial stores."""
    now = pd.Timestamp.now()
    return pd.DataFrame(
        {
            "datetime": [now, now + pd.Timedelta(seconds=1)],
            "timestamp": [now.timestamp(), (now + pd.Timedelta(seconds=1)).timestamp()],
        }
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
    available_datasets=available_datasets,
    initial_deployments=initial_deployments,
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
