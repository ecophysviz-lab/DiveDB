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


def create_footer(dff, video_options=None, events_df=None):
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
                    ]
                    + generate_event_indicators_row(
                        events_df, timestamp_min, timestamp_max
                    )
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
