"""
Footer timeline and playhead components.
"""
from dash import dcc, html
import dash_bootstrap_components as dbc
import pandas as pd
from datetime import datetime, timedelta

from .indicators import (
    generate_event_indicators_row,
    calculate_video_timeline_position,
    create_video_indicator,
    truncate_middle,
    parse_video_duration,
)


def create_timeline_section(dff, video_options=None, events_df=None):
    """
    Generate the timeline section HTML (slider + indicators).

    This is the content that goes inside timeline-container div.
    Returns the timeline section that can be updated via callback.
    """
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
                    {"type": "video-indicator", "id": video.get("id", i)},
                    tooltip_content,
                    position_data,
                    timestamp_min,
                    timestamp_max,
                )
            )

    # Generate event indicators
    event_indicator_rows = generate_event_indicators_row(
        events_df, timestamp_min, timestamp_max
    )

    # Wrap event indicator rows in a container with view bounds CSS variables
    # This enables client-side repositioning when timeline is zoomed
    # Always render the container (even empty) so callbacks can update it after event creation
    event_indicators_container = html.Div(
        event_indicator_rows,
        id="event-indicators-container",
        style={
            "--view-min": timestamp_min,
            "--view-max": timestamp_max,
        },
    )

    # Return the timeline section HTML
    return dbc.Container(
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
                                        delay={"show": 100, "hide": 0},
                                        autohide=True,
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
                                step=0.001,  # Millisecond resolution for sub-second playback
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
                                                                "%m/%d %H:%M:%S"
                                                            ),
                                                        ],
                                                        id="timeline-start-label",
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
                                                                "%m/%d %H:%M:%S"
                                                            ),
                                                        ],
                                                        id="timeline-end-label",
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
        ]
        + ([event_indicators_container] if event_indicators_container else [])
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
                                            delay={"show": 100, "hide": 0},
                                            autohide=True,
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
                                    id="video-indicators-container",
                                    className="video_available",
                                    style={
                                        "--view-min": timestamp_min,
                                        "--view-max": timestamp_max,
                                    },
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
    )


def create_deployment_info_display(animal_id, deployment_date, icon_url=None):
    """Create the animal/deployment info display at bottom of footer."""
    # Parse deployment date
    date_dt = pd.to_datetime(deployment_date)
    date_str = date_dt.strftime("%B %d, %Y")

    # Use provided icon_url or fallback to default
    if not icon_url:
        icon_url = "/assets/images/seal.svg"

    return dbc.Row(
        [
            dbc.Col(
                html.Div(
                    [
                        html.Div(
                            [
                                html.Img(
                                    src=icon_url,
                                ),
                            ],
                            className="animal_border ratio ratio-1x1",
                        ),
                    ],
                    className="animal_art",
                    style={"--bs-border-color": "var(--turquoise)"},
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
                    html.P(
                        [
                            date_str,
                        ],
                        className="sm m-0",
                    ),
                ],
            ),
        ],
        align="center",
        justify="center",
        className="h-100 gx-4",
    )


def create_footer_empty():
    """Create empty footer with disabled controls for initial state."""
    return html.Footer(
        [
            html.Div(
                dbc.Container(
                    [
                        html.Div(
                            [
                                html.P(
                                    "Select a deployment to view timeline",
                                    className="text-muted text-center py-4",
                                    style={"fontSize": "1.1rem"},
                                ),
                            ],
                            id="timeline-container",
                        ),
                    ],
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
                                    html.Div(
                                        id="deployment-info-display",
                                        children=[
                                            html.P(
                                                "",
                                                className="text-muted",
                                            )
                                        ],
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
                                                            "Skip Back",
                                                            html.Img(
                                                                src="/assets/images/skip-backward-circular.svg",
                                                            ),
                                                        ],
                                                        className="btn btn-icon-only btn-icon-skip-back",
                                                        id="previous-button",
                                                        n_clicks=0,
                                                        disabled=True,
                                                    ),
                                                    dbc.Tooltip(
                                                        "Skip Back (10s)",
                                                        target="previous-button",
                                                        placement="top",
                                                        id="previous-button-tooltip",
                                                        delay={"show": 100, "hide": 0},
                                                        autohide=True,
                                                    ),
                                                ],
                                                width={"size": "auto"},
                                            ),
                                            dbc.Col(
                                                [
                                                    html.Button(
                                                        [
                                                            "Slower",
                                                            html.Img(
                                                                src="/assets/images/rewind-bold.svg",
                                                            ),
                                                        ],
                                                        className="btn btn-icon-only btn-icon-reverse",
                                                        id="rewind-button",
                                                        n_clicks=0,
                                                        disabled=True,
                                                    ),
                                                    dbc.Tooltip(
                                                        "Speed: 1×",
                                                        target="rewind-button",
                                                        placement="top",
                                                        id="rewind-button-tooltip",
                                                        delay={"show": 100, "hide": 0},
                                                        autohide=True,
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
                                                                disabled=True,
                                                            ),
                                                            dbc.Tooltip(
                                                                "Play/Pause",
                                                                target="play-button",
                                                                placement="top",
                                                                id="play-button-tooltip",
                                                                delay={
                                                                    "show": 100,
                                                                    "hide": 0,
                                                                },
                                                                autohide=True,
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
                                                            "Faster",
                                                            html.Img(
                                                                src="/assets/images/foward-bold.svg",
                                                            ),
                                                        ],
                                                        className="btn btn-icon-only btn-icon-forward",
                                                        id="forward-button",
                                                        n_clicks=0,
                                                        disabled=True,
                                                    ),
                                                    dbc.Tooltip(
                                                        "Speed: 1×",
                                                        target="forward-button",
                                                        placement="top",
                                                        id="forward-button-tooltip",
                                                        delay={"show": 100, "hide": 0},
                                                        autohide=True,
                                                    ),
                                                ],
                                                width={"size": "auto"},
                                            ),
                                            dbc.Col(
                                                [
                                                    html.Button(
                                                        [
                                                            "Skip Forward",
                                                            html.Img(
                                                                src="/assets/images/skip-forward-circular.svg",
                                                            ),
                                                        ],
                                                        className="btn btn-icon-only btn-icon-skip-forward",
                                                        id="next-button",
                                                        n_clicks=0,
                                                        disabled=True,
                                                    ),
                                                    dbc.Tooltip(
                                                        "Skip Forward (10s)",
                                                        target="next-button",
                                                        placement="top",
                                                        id="next-button-tooltip",
                                                        delay={"show": 100, "hide": 0},
                                                        autohide=True,
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
                                                                            "Event",
                                                                            html.Img(
                                                                                src="/assets/images/save.svg",
                                                                            ),
                                                                        ],
                                                                        className="btn btn-icon-only btn-icon-save",
                                                                        id="save-button",
                                                                        n_clicks=0,
                                                                        disabled=True,
                                                                    ),
                                                                    dbc.Tooltip(
                                                                        "Create Event (B)",
                                                                        target="save-button",
                                                                        placement="top",
                                                                        delay={
                                                                            "show": 100,
                                                                            "hide": 0,
                                                                        },
                                                                        autohide=True,
                                                                    ),
                                                                ],
                                                                width={"size": "auto"},
                                                            ),
                                                            dbc.Col(
                                                                [
                                                                    dbc.Button(
                                                                        [
                                                                            "1×",
                                                                            html.Img(
                                                                                src="/assets/images/speed.svg",
                                                                            ),
                                                                        ],
                                                                        id="playback-rate-display",
                                                                        className="btn btn-icon-only btn-icon-speed",
                                                                        disabled=True,
                                                                    ),
                                                                    dbc.Tooltip(
                                                                        "Current Speed: 1×",
                                                                        target="playback-rate-display",
                                                                        placement="top",
                                                                        id="playback-rate-tooltip",
                                                                        delay={
                                                                            "show": 100,
                                                                            "hide": 0,
                                                                        },
                                                                        autohide=True,
                                                                    ),
                                                                ],
                                                                width={"size": "auto"},
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
                                                                        disabled=True,
                                                                    ),
                                                                    dbc.Tooltip(
                                                                        id="fullscreen-tooltip",
                                                                        target="fullscreen-button",
                                                                        placement="top",
                                                                        delay={
                                                                            "show": 100,
                                                                            "hide": 0,
                                                                        },
                                                                        autohide=True,
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


def create_footer(dff, video_options=None, events_df=None):
    """Create the footer with playhead controls and timeline (with updatable containers)."""
    # Generate timeline section using helper
    timeline_section = create_timeline_section(dff, video_options, events_df)

    return html.Footer(
        [
            html.Div(
                html.Div(
                    timeline_section,
                    id="timeline-container",
                ),
                className="playhead-slider-container",
            ),
            html.Div(
                dbc.Container(
                    [
                        dbc.Row(
                            [
                                dbc.Col(
                                    html.Div(
                                        id="deployment-info-display",
                                        children=[
                                            html.P(
                                                "No deployment info",
                                                className="text-muted",
                                            )
                                        ],
                                    ),
                                    width={"size": "4"},
                                ),
                                dbc.Col(
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                [
                                                    html.Button(
                                                        [
                                                            "Skip Back",
                                                            html.Img(
                                                                src="/assets/images/skip-backward-circular.svg",
                                                            ),
                                                        ],
                                                        className="btn btn-icon-only btn-icon-skip-back",
                                                        id="previous-button",
                                                        n_clicks=0,
                                                    ),
                                                    dbc.Tooltip(
                                                        "Skip Back (10s)",
                                                        target="previous-button",
                                                        placement="top",
                                                        id="previous-button-tooltip",
                                                        delay={"show": 100, "hide": 0},
                                                        autohide=True,
                                                    ),
                                                ],
                                                width={"size": "auto"},
                                            ),
                                            dbc.Col(
                                                [
                                                    html.Button(
                                                        [
                                                            "Slower",
                                                            html.Img(
                                                                src="/assets/images/rewind-bold.svg",
                                                            ),
                                                        ],
                                                        className="btn btn-icon-only btn-icon-reverse",
                                                        id="rewind-button",
                                                        n_clicks=0,
                                                    ),
                                                    dbc.Tooltip(
                                                        "Speed: 1×",
                                                        target="rewind-button",
                                                        placement="top",
                                                        id="rewind-button-tooltip",
                                                        delay={"show": 100, "hide": 0},
                                                        autohide=True,
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
                                                                delay={
                                                                    "show": 100,
                                                                    "hide": 0,
                                                                },
                                                                autohide=True,
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
                                                            "Faster",
                                                            html.Img(
                                                                src="/assets/images/foward-bold.svg",
                                                            ),
                                                        ],
                                                        className="btn btn-icon-only btn-icon-forward",
                                                        id="forward-button",
                                                        n_clicks=0,
                                                    ),
                                                    dbc.Tooltip(
                                                        "Speed: 1×",
                                                        target="forward-button",
                                                        placement="top",
                                                        id="forward-button-tooltip",
                                                        delay={"show": 100, "hide": 0},
                                                        autohide=True,
                                                    ),
                                                ],
                                                width={"size": "auto"},
                                            ),
                                            dbc.Col(
                                                [
                                                    html.Button(
                                                        [
                                                            "Skip Forward",
                                                            html.Img(
                                                                src="/assets/images/skip-forward-circular.svg",
                                                            ),
                                                        ],
                                                        className="btn btn-icon-only btn-icon-skip-forward",
                                                        id="next-button",
                                                        n_clicks=0,
                                                    ),
                                                    dbc.Tooltip(
                                                        "Skip Forward (10s)",
                                                        target="next-button",
                                                        placement="top",
                                                        id="next-button-tooltip",
                                                        delay={"show": 100, "hide": 0},
                                                        autohide=True,
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
                                                                            "Event",
                                                                            html.Img(
                                                                                src="/assets/images/save.svg",
                                                                            ),
                                                                        ],
                                                                        className="btn btn-icon-only btn-icon-save",
                                                                        id="save-button",
                                                                        n_clicks=0,
                                                                    ),
                                                                    dbc.Tooltip(
                                                                        "Create Event (B)",
                                                                        target="save-button",
                                                                        placement="top",
                                                                        delay={
                                                                            "show": 100,
                                                                            "hide": 0,
                                                                        },
                                                                        autohide=True,
                                                                    ),
                                                                ],
                                                                width={"size": "auto"},
                                                            ),
                                                            dbc.Col(
                                                                [
                                                                    dbc.Button(
                                                                        [
                                                                            "1×",
                                                                            html.Img(
                                                                                src="/assets/images/speed.svg",
                                                                            ),
                                                                        ],
                                                                        id="playback-rate-display",
                                                                        className="btn btn-icon-only btn-icon-speed",
                                                                    ),
                                                                    dbc.Tooltip(
                                                                        "Current Speed: 1×",
                                                                        target="playback-rate-display",
                                                                        placement="top",
                                                                        id="playback-rate-tooltip",
                                                                        delay={
                                                                            "show": 100,
                                                                            "hide": 0,
                                                                        },
                                                                        autohide=True,
                                                                    ),
                                                                ],
                                                                width={"size": "auto"},
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
