"""
Layout components for the DiveDB data visualization dashboard.
"""

from dash import dcc, html
import dash_bootstrap_components as dbc
import pandas as pd
import three_js_orientation
import video_preview
from datetime import datetime, timedelta


def truncate_middle(text, max_length=30):
    """Truncate text in the middle, keeping start and end visible."""
    if len(text) <= max_length:
        return text

    # Keep roughly 1/3 at start, 1/3 at end
    start_len = max_length // 3
    end_len = max_length - start_len - 3  # -3 for "..."

    return f"{text[:start_len]}...{text[-end_len:]}"


def parse_video_duration(duration_str):
    """Parse video duration from HH:MM:SS.mmm format to total seconds."""
    if not duration_str:
        return 0

    try:
        # Handle HH:MM:SS.mmm format
        time_parts = duration_str.split(":")
        if len(time_parts) == 3:
            hours = int(time_parts[0])
            minutes = int(time_parts[1])
            # Handle seconds and milliseconds
            seconds_part = float(time_parts[2])
            total_seconds = hours * 3600 + minutes * 60 + seconds_part
            return total_seconds
    except (ValueError, IndexError):
        pass

    return 0


def calculate_video_timeline_position(video, timeline_start_ts, timeline_end_ts):
    """Calculate video start/end ratios for timeline positioning."""
    try:
        # Parse video creation timestamp
        video_start_dt = datetime.fromisoformat(video["fileCreatedAt"])
        video_start_ts = video_start_dt.timestamp()

        # Parse video duration
        duration_seconds = parse_video_duration(
            video.get("metadata", {}).get("duration", "0")
        )
        video_end_ts = video_start_ts + duration_seconds

        # Calculate timeline ratios (0.0 to 1.0)
        timeline_duration = timeline_end_ts - timeline_start_ts

        if timeline_duration <= 0:
            return {"start": 0, "end": 0, "status": "error"}

        start_ratio = (video_start_ts - timeline_start_ts) / timeline_duration
        end_ratio = (video_end_ts - timeline_start_ts) / timeline_duration

        # Handle videos that are completely outside the timeline
        if start_ratio > 1.0 or end_ratio < 0.0:
            if start_ratio > 1.0:
                # Video after timeline - show at far right
                return {"start": 0.95, "end": 1.0, "status": "after"}
            else:
                # Video before timeline - show at far left
                return {"start": 0.0, "end": 0.05, "status": "before"}

        # Handle videos that extend beyond the timeline bounds
        # Clamp ratios to 0.0-1.0 range but preserve relative positioning
        clamped_start = max(0.0, min(1.0, start_ratio))
        clamped_end = max(0.0, min(1.0, end_ratio))

        # Determine video status based on timeline relationship
        if start_ratio >= 0 and end_ratio <= 1:
            # Video is completely within timeline bounds
            status = "within"
        else:
            # Video spans across timeline boundaries
            status = "overlapping"

        # Ensure we have a valid range with minimum width
        if clamped_end <= clamped_start:
            # Video has been clamped to invalid range - ensure minimal visibility
            if start_ratio < 0:
                clamped_start = 0.0
                clamped_end = 0.05
            else:
                clamped_start = 0.95
                clamped_end = 1.0

        return {"start": clamped_start, "end": clamped_end, "status": status}
    except (ValueError, KeyError, TypeError) as e:
        print(f"   ❌ Error calculating video position: {e}")
        return {"start": 0, "end": 0, "status": "error"}


def create_header():
    """Create the main header/navbar component."""
    return html.Header(
        [
            dbc.Navbar(
                dbc.Container(
                    [
                        html.A(
                            dbc.Row(
                                [
                                    dbc.Col(
                                        html.Img(
                                            src="/assets/images/divedb_logo.png",
                                        ),
                                        className="logo",
                                    ),
                                    dbc.Col(
                                        dbc.NavbarBrand(
                                            "Data Visualization",
                                            className="ms-3",
                                        )
                                    ),
                                ],
                                align="center",
                                className="g-0",
                            ),
                            href="/",
                            style={"textDecoration": "none"},
                        ),
                        dbc.DropdownMenu(
                            children=[
                                dbc.DropdownMenuItem(
                                    "View Profile",
                                    href="#",
                                    id="view-profile",
                                ),
                                dbc.DropdownMenuItem(
                                    "Settings", href="#", id="settings"
                                ),
                                dbc.DropdownMenuItem(divider=True),
                                dbc.DropdownMenuItem(
                                    "Sign Out", href="#", id="sign-out"
                                ),
                            ],
                            toggle_class_name="btn btn-icon-only btn-icon-profile btn-lg",
                            id="profile-dropdown",
                            direction="down",
                            align_end=True,
                        ),
                        dbc.NavbarToggler(id="navbar-toggler", n_clicks=0),
                    ]
                ),
                color="dark",
                dark=True,
            )
        ],
        className="main_header",
    )


def create_dataset_accordion_item(
    title_text, animal_image, border_color, animal_id, item_id, status=None
):
    """Create a single accordion item for the dataset sidebar."""
    status_indicator = None
    if status:
        status_indicator = dbc.Col(
            html.Div(
                [
                    html.Span(
                        "●",
                        className=f"text-{status['color']} me-1",
                    ),
                    html.Small(
                        status["text"],
                        className="text-muted",
                    ),
                ],
                className="ms-auto d-flex align-items-center",
            ),
            width={"size": "auto"},
        )

    return dbc.AccordionItem(
        [
            html.Div(
                [
                    html.Button(
                        [
                            html.P(
                                [
                                    html.Strong(
                                        [
                                            "April 22, 2018",
                                        ],
                                    ),
                                ],
                                className="strong m-0",
                            ),
                        ],
                        className="list-group-item list-group-item-action animal_link",
                    ),
                    html.Button(
                        [
                            html.P(
                                [
                                    html.Strong(
                                        [
                                            "April 22, 2018",
                                        ],
                                    ),
                                ],
                                className="strong m-0",
                            ),
                        ],
                        className="list-group-item list-group-item-action animal_link",
                    ),
                    html.Button(
                        [
                            html.P(
                                [
                                    html.Strong(
                                        [
                                            "April 22, 2018",
                                        ],
                                    ),
                                ],
                                className="strong m-0",
                            ),
                        ],
                        className="list-group-item list-group-item-action",
                    ),
                ],
                className="list-group",
            ),
        ],
        title=[
            html.Div(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                html.Div(
                                    [
                                        html.Div(
                                            [
                                                html.Img(
                                                    src=f"/assets/images/{animal_image}",
                                                ),
                                            ],
                                            className="animal_border ratio ratio-1x1",
                                        ),
                                    ],
                                    className="animal_art sm",
                                    style={"--bs-border-color": f"var({border_color})"},
                                ),
                                width={"size": "auto"},
                            ),
                            dbc.Col(
                                [
                                    html.P(
                                        [
                                            html.Strong(
                                                [
                                                    animal_id,
                                                ],
                                            ),
                                        ],
                                        className="strong m-0",
                                    ),
                                ],
                            ),
                            dbc.Col(),
                            status_indicator if status else dbc.Col(),
                        ],
                        align="center",
                        className="gx-3",
                    ),
                ],
                className="w-100",
            )
        ],
        item_id=item_id,
    )


def create_left_sidebar():
    """Create the left sidebar with datasets."""
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        html.Button(
                                            id="left-toggle",
                                            className="btn btn-icon-only btn-sm btn-icon-expand toggle_left",
                                            n_clicks=0,
                                        ),
                                        dbc.Tooltip(
                                            "Toggle Left Sidebar",
                                            target="left-toggle",
                                            placement="right",
                                        ),
                                    ],
                                    width={"size": "auto"},
                                ),
                                dbc.Col(
                                    [
                                        html.P(
                                            [
                                                html.Strong(
                                                    [
                                                        "Datasets",
                                                    ],
                                                ),
                                            ],
                                            className="m-0",
                                        ),
                                    ],
                                    className="sidebar_title",
                                ),
                            ],
                            align="center",
                            className="gx-2",
                        ),
                        className="sidebar_header",
                    ),
                    html.Div(
                        dbc.Accordion(
                            [
                                create_dataset_accordion_item(
                                    "DOLP_001",
                                    "dolphin.svg",
                                    "--pink",
                                    "DOLP_001",
                                    "date-accordion-1",
                                ),
                                create_dataset_accordion_item(
                                    "APFO_001",
                                    "penguin.svg",
                                    "--orange",
                                    "APFO_001",
                                    "date-accordion-2",
                                    status={"color": "success", "text": "Active"},
                                ),
                                create_dataset_accordion_item(
                                    "NESC_001",
                                    "seal.svg",
                                    "--turquoise",
                                    "NESC_001",
                                    "date-accordion-3",
                                ),
                                create_dataset_accordion_item(
                                    "NESC_002",
                                    "seal.svg",
                                    "--green",
                                    "NESC_002",
                                    "date-accordion-4",
                                ),
                                create_dataset_accordion_item(
                                    "NESC_003",
                                    "seal.svg",
                                    "--purple",
                                    "NESC_003",
                                    "date-accordion-5",
                                ),
                                create_dataset_accordion_item(
                                    "TURL_001",
                                    "turtle.svg",
                                    "--red",
                                    "TURL_001",
                                    "date-accordion-6",
                                ),
                                create_dataset_accordion_item(
                                    "TURL_002",
                                    "turtle.svg",
                                    "--green",
                                    "TURL_002",
                                    "date-accordion-7",
                                ),
                                create_dataset_accordion_item(
                                    "TURL_003",
                                    "turtle.svg",
                                    "--pink",
                                    "TURL_003",
                                    "date-accordion-8",
                                ),
                            ],
                            id="sidebar-accordion",
                            start_collapsed=True,
                            always_open=False,
                            flush=True,
                        ),
                        className="sidebar_content",
                    ),
                ],
                className="sidebar",
            )
        ],
        className="left_sidebar",
    )


def create_main_content(fig, channel_options=None):
    """Create the main content area with the graph."""
    # Convert channel_options to dropdown format
    dropdown_options = []
    if channel_options:
        for option in channel_options:
            if isinstance(option, dict):
                # Handle dictionary format
                label = option.get('label', option.get('name', 'Unknown'))
                value = option.get('value', option.get('id', label.lower()))
                dropdown_options.append({"label": label, "value": value})
            else:
                # Handle string format
                dropdown_options.append({"label": str(option), "value": str(option).lower()})
    else:
        # Fallback options if channel_options is None
        dropdown_options = [
            {"label": "Depth", "value": "depth"},
            {"label": "Pitch, roll, heading", "value": "prh"},
            {"label": "Temperature", "value": "temperature"},
            {"label": "Light", "value": "light"},
        ]

    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        html.P(
                                            [
                                                html.Strong(
                                                    [
                                                        "Data Channels",
                                                    ],
                                                ),
                                            ],
                                            className="m-0",
                                        ),
                                    ],
                                    className="sidebar_title",
                                ),
                                dbc.Col(
                                    [
                                        dbc.DropdownMenu(
                                            [
                                                html.Div(
                                                    [
                                                        dbc.ListGroup(
                                                            [
                                                                dbc.ListGroupItem(
                                                                    dbc.Row(
                                                                        [
                                                                            dbc.Col(
                                                                                html.Button(
                                                                                    html.Img(
                                                                                        src="/assets/images/drag.svg",
                                                                                        className="drag-icon",
                                                                                    ),
                                                                                    className="btn btn-icon-only btn-sm",
                                                                                    id={"type": "channel-drag", "index": 1},
                                                                                ),
                                                                                width="auto",
                                                                                className="drag-handle",
                                                                            ),
                                                                            dbc.Col(
                                                                                dbc.Select(
                                                                                    options=dropdown_options,
                                                                                    value=dropdown_options[0]["value"] if dropdown_options else "depth",
                                                                                    id={"type": "channel-select", "index": 1},
                                                                                ),
                                                                            ),
                                                                            dbc.Col(
                                                                                html.Button(
                                                                                    html.Img(
                                                                                        src="/assets/images/remove.svg",
                                                                                        className="remove-icon",
                                                                                    ),
                                                                                    className="btn btn-icon-only btn-sm",
                                                                                    id={"type": "channel-remove", "index": 1},
                                                                                ),
                                                                                width="auto",
                                                                            ),
                                                                        ],
                                                                        align="center",
                                                                        className="g-2",
                                                                    ),
                                                                ),
                                                                dbc.ListGroupItem(
                                                                    dbc.Row(
                                                                        [
                                                                            dbc.Col(
                                                                                dbc.Button(
                                                                                    "Add Graph",
                                                                                    color="primary",
                                                                                    className="btn-xs btn-stroke my-1",
                                                                                    id="add-graph-btn",
                                                                                ),
                                                                            ),
                                                                        ],
                                                                        align="center",
                                                                        className="g-2",
                                                                    ),
                                                                ),
                                                            ],
                                                            id="graph-channel-list",
                                                        ),
                                                        
                                                    ],
                                                    className="",
                                                )
                                            ],
                                            toggle_class_name="btn btn-sm btn-icon-only m-0",
                                            id="graph-channels",
                                            direction="down",
                                            align_end=False,
                                            label=[
                                                html.Img(
                                                    src="/assets/images/filter.svg",
                                                    className="",
                                                ),
                                                "Manage Channels"
                                            ]
                                        ),
                                        dbc.Tooltip(
                                            "Manage Channels",
                                            target="graph-channels",
                                            placement="right",
                                        ),
                                    ],
                                    width={"size": "auto"},
                                ),
                            ],
                            align="center",
                            className="gx-2",
                        ),
                        className="sidebar_header",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    dcc.Graph(
                                        id="graph-content",
                                        figure=fig,
                                        responsive=True,
                                    ),
                                ],
                                className="graph-content-container",
                            ),
                        ],
                        className="sidebar_content",
                    )
                ],
                className="sidebar",
            ),
            html.Div([], className="resize-bar", id="resizeHandle"),
        ],
        className="main_content",
    )


def create_right_sidebar(
    data_json, video_min_timestamp, video_options=None, restricted_time_range=None
):
    """Create the right sidebar with 3D model and video."""
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        html.P(
                                            [
                                                html.Strong(
                                                    [
                                                        "Visuals",
                                                    ],
                                                ),
                                            ],
                                            className="m-0",
                                        ),
                                    ],
                                    className="sidebar_title",
                                ),
                                dbc.Col(
                                    [
                                        html.Button(
                                            id="right-toggle",
                                            className="btn btn-icon-only btn-sm btn-icon-expand toggle_right",
                                            n_clicks=0,
                                        ),
                                        dbc.Tooltip(
                                            "Toggle Right Sidebar",
                                            target="right-toggle",
                                            placement="left",
                                        ),
                                    ],
                                    width={"size": "auto"},
                                ),
                            ],
                            align="center",
                            className="gx-2",
                        ),
                        className="sidebar_header xd-none",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            three_js_orientation.ThreeJsOrientation(
                                                id="three-d-model",
                                                data=data_json,
                                                activeTime=0,
                                                objFile="/assets/PenguinSwim.obj",
                                                textureFile="/assets/PenguinSwim.png",
                                                style={
                                                    "width": "100%",
                                                    "height": "100%",
                                                },
                                            ),
                                            html.Button(
                                                [
                                                    "Expand",
                                                ],
                                                id="right-top-toggle",
                                                className="btn btn-icon toggle_right_top",
                                                n_clicks=0,
                                            ),
                                            dbc.Tooltip(
                                                "Expand 3D Model",
                                                target="right-top-toggle",
                                                placement="left",
                                            ),
                                        ],
                                        className="three-d-model-container",
                                    )
                                ],
                                className="right_sidebar_top",
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            video_preview.VideoPreview(
                                                id="video-trimmer",
                                                videoSrc="",  # Empty string as placeholder until proper rebuild
                                                videoMetadata=None,  # Will be populated when video is selected
                                                datasetStartTime=video_min_timestamp,
                                                playheadTime=video_min_timestamp,
                                                isPlaying=False,
                                                showControls=False,
                                            ),
                                            html.Button(
                                                [
                                                    "Expand",
                                                ],
                                                id="right-bottom-toggle",
                                                className="btn btn-icon toggle_right_bottom",
                                                n_clicks=0,
                                            ),
                                            dbc.Tooltip(
                                                "Expand Video",
                                                target="right-bottom-toggle",
                                                placement="left",
                                            ),
                                        ],
                                        className="video-container",
                                    )
                                ],
                                className="right_sidebar_bottom",
                            ),
                        ],
                        className="sidebar_content",
                    ),
                ],
                className="sidebar",
            ),
        ],
        className="right_sidebar",
    )


def create_saved_indicator(
    saved_id,
    timestamp_display,
    notes,
    start_ratio,
    end_ratio,
    timestamp_min,
    timestamp_max,
):
    """Create a saved timestamp indicator."""
    timestamp_range = timestamp_max - timestamp_min
    return html.Div(
        [
            html.Button(
                [],
                className="",
                id=saved_id,
            ),
            dbc.Tooltip(
                [
                    html.Div(
                        timestamp_display,
                        className="timestamp",
                    ),
                    html.Div(notes),
                ],
                target=saved_id,
                className="tooltip-saved",
                placement="top",
            ),
        ],
        className="saved_indicator",
        style={
            "--start": int(timestamp_range * start_ratio),
            "--end": int(timestamp_range * end_ratio),
            "--length": int(timestamp_range),
        },
    )


def create_video_indicator(
    video_id, tooltip_content, position_data, timestamp_min, timestamp_max
):
    """Create a video available indicator."""
    timestamp_range = timestamp_max - timestamp_min
    start_ratio = position_data["start"]
    end_ratio = position_data["end"]
    status = position_data["status"]

    # Determine CSS classes based on video status
    base_class = "video_available_indicator"
    status_class = f"video_status_{status}"
    full_class = f"{base_class} {status_class}"

    # Add visual styling hints for out-of-view videos
    button_style = {
        "cursor": "pointer",
        "background": "transparent",
        "border": "none",
        "width": "100%",
        "height": "100%",
        "position": "absolute",
        "top": "0",
        "left": "0",
    }

    # Add visual indicators for out-of-view videos
    if status in ["before", "after"]:
        button_style["opacity"] = "0.5"  # Make out-of-view videos semi-transparent
        button_style["filter"] = "grayscale(0.5)"  # Add slight desaturation
    return html.Div(
        [
            html.Button(
                [],
                className="video-indicator-btn",
                id=video_id,
                style=button_style,
            ),
            dbc.Tooltip(
                tooltip_content,
                target=video_id,
                placement="top",
            ),
        ],
        className=full_class,
        style={
            "--start": int(timestamp_range * start_ratio),
            "--end": int(timestamp_range * end_ratio),
            "--length": int(timestamp_range),
            "position": "relative",  # Ensure button positioning works
        },
    )


def create_footer(dff, video_options=None):
    """Create the footer with playhead controls and timeline."""
    timestamp_min = dff["timestamp"].min()
    timestamp_max = dff["timestamp"].max()

    # Generate video indicators from real video data
    video_indicators = []
    if video_options:
        for i, video in enumerate(video_options):
            position_data = calculate_video_timeline_position(
                video, timestamp_min, timestamp_max
            )

            # Skip videos with error status
            if position_data["status"] == "error":
                continue

            # Create tooltip text with video info
            filename = video.get("filename", "Unknown Video")
            duration = video.get("metadata", {}).get("duration", "Unknown")
            created = video.get("fileCreatedAt", "")

            # Create multi-line tooltip with structured HTML
            tooltip_content = [
                html.Div(truncate_middle(filename), className="video-filename")
            ]

            start_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            start_time = start_dt.strftime("%H:%M:%S")

            if duration != "Unknown":
                duration_seconds = parse_video_duration(duration)
                if duration_seconds > 0:
                    end_dt = start_dt + timedelta(seconds=duration_seconds)
                    end_time = end_dt.strftime("%H:%M:%S")
                    tooltip_content.append(
                        html.Div(f"Duration: {start_time} - {end_time}")
                    )

            # Add status indicator to tooltip
            status_messages = {
                "within": "📍 Fully within timeline",
                "overlapping": "📍 Spans timeline boundaries",
                "before": "⏮️ Before timeline (out of view)",
                "after": "⏭️ After timeline (out of view)",
                "error": "❌ Error processing video",
            }
            status_msg = status_messages.get(position_data["status"], "")
            if status_msg:
                tooltip_content.append(html.Div(status_msg, className="video-status"))

            video_indicators.append(
                create_video_indicator(
                    f"video-{video.get('id', i)}",
                    tooltip_content,
                    position_data,
                    timestamp_min,
                    timestamp_max,
                )
            )

    return html.Footer(
        [
            html.Div(
                dbc.Container(
                    [
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        html.Div(
                                            [
                                                html.Img(
                                                    src="/assets/images/scrubber.svg",
                                                    id="scrubber-icon",
                                                ),
                                                dbc.Tooltip(
                                                    "Timeline Scrubber",
                                                    target="scrubber-icon",
                                                    placement="top",
                                                ),
                                            ],
                                            className="icon sm",
                                        ),
                                    ],
                                    width={"size": "auto"},
                                ),
                                dbc.Col(
                                    [
                                        dcc.Slider(
                                            id="playhead-slider",
                                            className="playhead-slider",
                                            min=timestamp_min,
                                            max=timestamp_max,
                                            value=timestamp_min,
                                            step=1,
                                            marks=None,
                                            tooltip={
                                                "placement": "top",
                                                "always_visible": True,
                                                "transform": "formatTimestamp",
                                            },
                                        ),
                                        dbc.Row(
                                            [
                                                dbc.Col(
                                                    [
                                                        html.Div(
                                                            [
                                                                html.P(
                                                                    [
                                                                        pd.to_datetime(
                                                                            timestamp_min,
                                                                            unit="s",
                                                                        ).strftime(
                                                                            "%H:%M:%S"
                                                                        ),
                                                                    ],
                                                                    className="xs m-0",
                                                                ),
                                                            ],
                                                            className="time-start",
                                                        ),
                                                    ],
                                                    width={"size": "auto"},
                                                ),
                                                dbc.Col(
                                                    [
                                                        html.Div(
                                                            [
                                                                html.P(
                                                                    [
                                                                        pd.to_datetime(
                                                                            timestamp_max,
                                                                            unit="s",
                                                                        ).strftime(
                                                                            "%H:%M:%S"
                                                                        ),
                                                                    ],
                                                                    className="xs m-0",
                                                                ),
                                                            ],
                                                            className="time-end",
                                                        ),
                                                    ],
                                                    width={"size": "auto"},
                                                ),
                                            ],
                                            align="center",
                                            justify="between",
                                            className="gx-4",
                                        ),
                                    ],
                                    className="",
                                ),
                            ],
                            align="center",
                            className="g-4",
                        ),
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        html.Div(
                                            [
                                                html.Img(
                                                    src="/assets/images/saved.svg",
                                                    id="saved-icon",
                                                ),
                                                dbc.Tooltip(
                                                    "Saved Timestamps",
                                                    target="saved-icon",
                                                    placement="top",
                                                ),
                                            ],
                                            className="icon sm",
                                        ),
                                    ],
                                    width={"size": "auto"},
                                ),
                                dbc.Col(
                                    [
                                        html.Div(
                                            [
                                                create_saved_indicator(
                                                    "saved-1",
                                                    "09:33:42",
                                                    "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
                                                    0.075,
                                                    0.45,
                                                    timestamp_min,
                                                    timestamp_max,
                                                ),
                                                create_saved_indicator(
                                                    "saved-2",
                                                    "09:36:42",
                                                    "Donec nunc mi, faucibus sed vestibulum non, lacinia nec nisl. Integer volutpat odio a elit malesuada hendrerit. Maecenas nec massa urna.",
                                                    0.55,
                                                    0.45,
                                                    timestamp_min,
                                                    timestamp_max,
                                                ),
                                                create_saved_indicator(
                                                    "saved-3",
                                                    "09:37:31",
                                                    "Pellentesque cursus hendrerit justo, sit amet volutpat massa mattis id.",
                                                    0.675,
                                                    0.45,
                                                    timestamp_min,
                                                    timestamp_max,
                                                ),
                                            ],
                                            className="saved",
                                        ),
                                    ],
                                    className="",
                                ),
                            ],
                            align="center",
                            className="g-4",
                        ),
                    ]
                    + (
                        [
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            html.Div(
                                                [
                                                    html.Img(
                                                        src="/assets/images/video.svg",
                                                        id="video-icon",
                                                    ),
                                                    dbc.Tooltip(
                                                        "Video Available",
                                                        target="video-icon",
                                                        placement="top",
                                                    ),
                                                ],
                                                className="icon sm",
                                            ),
                                        ],
                                        width={"size": "auto"},
                                    ),
                                    dbc.Col(
                                        [
                                            html.Div(
                                                video_indicators,
                                                className="video_available",
                                            ),
                                        ],
                                        className="",
                                    ),
                                ],
                                align="center",
                                className="g-4",
                            ),
                        ]
                        if video_indicators
                        else []
                    ),
                    fluid=True,
                ),
                className="playhead-slider-container",
            ),
            html.Div(
                dbc.Container(
                    [
                        dbc.Row(
                            [
                                dbc.Col(
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                html.Div(
                                                    [
                                                        html.Div(
                                                            [
                                                                html.Img(
                                                                    src="/assets/images/penguin.svg",
                                                                ),
                                                            ],
                                                            className="animal_border ratio ratio-1x1",
                                                        ),
                                                    ],
                                                    className="animal_art",
                                                    style={
                                                        "--bs-border-color": "var(--orange)"
                                                    },
                                                ),
                                                width={"size": "auto"},
                                            ),
                                            dbc.Col(
                                                [
                                                    html.P(
                                                        [
                                                            html.Strong(
                                                                [
                                                                    "APFO_001",
                                                                ],
                                                            ),
                                                        ],
                                                        className="strong m-0",
                                                    ),
                                                    html.P(
                                                        [
                                                            "November 8, 2019",
                                                        ],
                                                        className="sm m-0",
                                                    ),
                                                ],
                                            ),
                                        ],
                                        align="center",
                                        justify="center",
                                        className="h-100 gx-4",
                                    ),
                                    width={"size": "3"},
                                ),
                                dbc.Col(
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                [
                                                    html.Button(
                                                        [
                                                            "Previous Deployment",
                                                            html.Img(
                                                                src="/assets/images/skip-prev-bold.svg",
                                                            ),
                                                        ],
                                                        className="btn btn-icon-only btn-icon-skip-back",
                                                        id="previous-button",
                                                        n_clicks=0,
                                                    ),
                                                    dbc.Tooltip(
                                                        "Previous Deployment",
                                                        target="previous-button",
                                                        placement="top",
                                                    ),
                                                ],
                                                width={"size": "auto"},
                                            ),
                                            dbc.Col(
                                                [
                                                    html.Button(
                                                        [
                                                            "Rewind",
                                                            html.Img(
                                                                src="/assets/images/rewind-bold.svg",
                                                            ),
                                                        ],
                                                        className="btn btn-icon-only btn-icon-reverse",
                                                        id="rewind-button",
                                                        n_clicks=0,
                                                    ),
                                                    dbc.Tooltip(
                                                        "Rewind",
                                                        target="rewind-button",
                                                        placement="top",
                                                    ),
                                                ],
                                                width={"size": "auto"},
                                            ),
                                            dbc.Col(
                                                [
                                                    html.Div(
                                                        [
                                                            html.Button(
                                                                "Play",
                                                                id="play-button",
                                                                n_clicks=0,
                                                                className="btn btn-primary btn-round btn-play btn-lg",
                                                            ),
                                                            dbc.Tooltip(
                                                                "Play/Pause",
                                                                target="play-button",
                                                                placement="top",
                                                                id="play-button-tooltip",
                                                            ),
                                                        ],
                                                        className="p-1",
                                                    ),
                                                ],
                                                width={"size": "auto"},
                                            ),
                                            dbc.Col(
                                                [
                                                    html.Button(
                                                        [
                                                            "Fast Foward",
                                                            html.Img(
                                                                src="/assets/images/foward-bold.svg",
                                                            ),
                                                        ],
                                                        className="btn btn-icon-only btn-icon-forward",
                                                        id="forward-button",
                                                        n_clicks=0,
                                                    ),
                                                    dbc.Tooltip(
                                                        "Fast Foward",
                                                        target="forward-button",
                                                        placement="top",
                                                    ),
                                                ],
                                                width={"size": "auto"},
                                            ),
                                            dbc.Col(
                                                [
                                                    html.Button(
                                                        [
                                                            "Next Deployment",
                                                            html.Img(
                                                                src="/assets/images/skip-next-bold.svg",
                                                            ),
                                                        ],
                                                        className="btn btn-icon-only btn-icon-skip-forward",
                                                        id="next-button",
                                                        n_clicks=0,
                                                    ),
                                                    dbc.Tooltip(
                                                        "Next Deployment",
                                                        target="next-button",
                                                        placement="top",
                                                    ),
                                                ],
                                                width={"size": "auto"},
                                            ),
                                        ],
                                        align="center",
                                        justify="center",
                                        className="h-100 gx-2",
                                    ),
                                    width={"size": "6"},
                                ),
                                dbc.Col(
                                    html.Div(
                                        [
                                            html.Div(
                                                [
                                                    dbc.Row(
                                                        [
                                                            dbc.Col(
                                                                [
                                                                    html.Button(
                                                                        [
                                                                            "Save",
                                                                            html.Img(
                                                                                src="/assets/images/save.svg",
                                                                            ),
                                                                        ],
                                                                        className="btn btn-icon-only btn-icon-save",
                                                                        id="save-button",
                                                                        n_clicks=0,
                                                                    ),
                                                                    dbc.Tooltip(
                                                                        "Bookmark Timestamp",
                                                                        target="save-button",
                                                                        placement="top",
                                                                    ),
                                                                ],
                                                                width={"size": "auto"},
                                                            ),
                                                            dbc.Col(
                                                                [
                                                                    dbc.Button(
                                                                        [
                                                                            "Speed",
                                                                            html.Img(
                                                                                src="/assets/images/speed.svg",
                                                                            ),
                                                                        ],
                                                                        id="playback-rate",
                                                                        className="btn btn-icon-only btn-icon-speed",
                                                                    ),
                                                                    dbc.Tooltip(
                                                                        "Playback Rate",
                                                                        target="playback-rate",
                                                                        placement="top",
                                                                    ),
                                                                    dbc.Popover(
                                                                        [
                                                                            dbc.PopoverBody(
                                                                                [
                                                                                    dcc.Slider(
                                                                                        id="playback-rate-slider",
                                                                                        min=0,
                                                                                        max=4,
                                                                                        step=None,
                                                                                        updatemode="drag",
                                                                                        marks={
                                                                                            0: "0.25x",
                                                                                            1: "0.5x",
                                                                                            2: "1x",
                                                                                            3: "1.5x",
                                                                                            4: "2x",
                                                                                        },
                                                                                        value=2,
                                                                                    ),
                                                                                ]
                                                                            ),
                                                                        ],
                                                                        target="playback-rate",
                                                                        trigger="click",
                                                                        placement="top",
                                                                    ),
                                                                ],
                                                                width={"size": "4"},
                                                            ),
                                                            dbc.Col(
                                                                [
                                                                    html.Button(
                                                                        [
                                                                            "Expand",
                                                                            html.Img(
                                                                                src="/assets/images/fullscreen.svg",
                                                                            ),
                                                                        ],
                                                                        className="btn btn-icon-only btn-icon-fullscreen",
                                                                        id="fullscreen-button",
                                                                    ),
                                                                    dbc.Tooltip(
                                                                        id="fullscreen-tooltip",
                                                                        target="fullscreen-button",
                                                                        placement="top",
                                                                    ),
                                                                ],
                                                            ),
                                                        ],
                                                        align="center",
                                                        className="g-3",
                                                    ),
                                                ],
                                                className="d-flex justify-content-end align-items-center h-100",
                                            ),
                                        ],
                                    ),
                                    width={"size": "3"},
                                ),
                            ],
                            className="",
                            align="center",
                        ),
                    ],
                    fluid=True,
                ),
                className="controls-container",
            ),
        ],
        className="main_footer",
    )


def create_bookmark_modal():
    """Create the bookmark modal dialog."""
    return dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("Bookmark Timestamp")),
            dbc.ModalBody(
                [
                    html.Div(
                        [
                            html.P(
                                "Enter a name and notes for this bookmark.",
                            ),
                            dbc.Label("Timestamp Notes", html_for="bookmark-notes"),
                            dbc.Input(
                                type="textarea",
                                id="bookmark-notes",
                                placeholder="Enter notes...",
                            ),
                        ],
                        className="mb-3",
                    )
                ]
            ),
            dbc.ModalFooter(
                [
                    dbc.Button(
                        "Close",
                        id="close",
                        className="btn btn-secondary btn-sm",
                        n_clicks=0,
                    ),
                    dbc.Button(
                        "Save",
                        id="save-bookmark-button",
                        className="btn btn-primary btn-sm",
                    ),
                ]
            ),
        ],
        id="modal",
        is_open=False,
    )


def create_app_stores(dff):
    """Create the dcc.Store and dcc.Interval components."""
    return [
        dcc.Interval(
            id="interval-component",
            interval=1 * 1000,  # Base interval of 1 second
            n_intervals=0,
            disabled=True,  # Start with the interval disabled
        ),
        dcc.Store(id="playhead-time", data=dff["timestamp"].min()),
        dcc.Store(id="is-playing", data=False),
        dcc.Store(id="selected-video", data=None),  # Store for selected video data
        dcc.Store(
            id="manual-video-override", data=None
        ),  # Store for sticky manual selection
        dcc.Store(
            id="video-time-offset", data=0
        ),  # Store for video timeline offset in seconds
        dcc.Store(
            id="channel-order", data=[]
        ),  # Store for channel order after drag and drop
    ]


def create_layout(fig, data_json, dff, video_options=None, restricted_time_range=None, channel_options=None):
    """Create the complete app layout."""
    return html.Div(
        [
            html.Div(
                [
                    html.Div([], className="announcement_bar"),
                    create_header(),
                    create_left_sidebar(),
                    create_main_content(
                        fig,
                        channel_options=channel_options,
                    ),
                    create_right_sidebar(
                        data_json,
                        dff["timestamp"].min(),
                        video_options=video_options,
                        restricted_time_range=restricted_time_range,
                    ),
                    create_footer(dff, video_options=video_options),
                ],
                className="grid",
            ),
            create_bookmark_modal(),
            *create_app_stores(dff),
        ],
        id="main-layout",
        className="default-layout",
    )
