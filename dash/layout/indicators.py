"""
Event and video indicator components for the timeline.
"""
from dash import html
import dash_bootstrap_components as dbc
import pandas as pd
from datetime import datetime
from logging_config import get_logger

logger = get_logger("layout")


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
        logger.error(f"Error calculating video position: {e}")
        return {"start": 0, "end": 0, "status": "error"}


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
                delay={"show": 100, "hide": 0},
                autohide=True,
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
    button_style = {}

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
                delay={"show": 100, "hide": 0},
                autohide=True,
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


def create_event_indicator(
    event_id,
    tooltip_content,
    start_ratio,
    end_ratio,
    timestamp_min,
    timestamp_max,
    color=None,
):
    """Create an event indicator for the timeline."""
    timestamp_range = timestamp_max - timestamp_min

    # Ensure minimum width for very short events
    min_width_ratio = 0.005  # 0.5% of timeline
    if end_ratio - start_ratio < min_width_ratio:
        # Expand event to minimum width, centered on original position
        center = (start_ratio + end_ratio) / 2
        start_ratio = max(0, center - min_width_ratio / 2)
        end_ratio = min(1, center + min_width_ratio / 2)

    # Build style dict with color if provided
    style = {
        "--start": int(timestamp_range * start_ratio),
        "--end": int(timestamp_range * end_ratio),
        "--length": int(timestamp_range),
    }
    if color:
        style["--event-color"] = color

    return html.Div(
        [
            html.Button(
                [],
                className="",
                id=event_id,
                style={"backgroundColor": color} if color else {},
            ),
            dbc.Tooltip(
                tooltip_content,
                target=event_id,
                className="tooltip-saved",
                placement="top",
                delay={"show": 100, "hide": 0},
                autohide=True,
            ),
        ],
        className="saved_indicator",
        style=style,
    )


def get_event_color_palette():
    """Return a predefined color palette for the first 4 event types."""
    return [
        "#3498db",  # Blue
        "#2ecc71",  # Green
        "#e74c3c",  # Red
        "#f39c12",  # Orange
    ]


def generate_random_color(seed_text):
    """Generate a deterministic but visually distinct color based on seed text."""
    import hashlib

    # Use hash of the text to generate consistent colors for same event types
    hash_obj = hashlib.md5(seed_text.encode())
    hash_hex = hash_obj.hexdigest()

    # Extract RGB values from hash (use first 6 chars)
    r = int(hash_hex[0:2], 16)
    g = int(hash_hex[2:4], 16)
    b = int(hash_hex[4:6], 16)

    # Ensure colors are not too dark or too light
    # Adjust to be in the range 60-200 for better visibility
    r = 60 + (r % 140)
    g = 60 + (g % 140)
    b = 60 + (b % 140)

    return f"#{r:02x}{g:02x}{b:02x}"


def assign_event_colors(events_df):
    """Assign colors to events based on their event_key."""
    if events_df is None or len(events_df) == 0:
        return {}

    # Get unique event types
    unique_event_keys = events_df["event_key"].unique()

    # Get predefined palette
    palette = get_event_color_palette()

    # Create color mapping
    color_map = {}
    for idx, event_key in enumerate(unique_event_keys):
        if idx < len(palette):
            # Use predefined color for first 4 types
            color_map[event_key] = palette[idx]
        else:
            # Generate random color for additional types
            color_map[event_key] = generate_random_color(event_key)

    return color_map


def generate_event_indicators_row(
    events_df, timestamp_min, timestamp_max, max_events_per_type=100000
):
    """Generate the event indicators rows for the timeline (one row per event type)."""
    # If no events, return empty list
    if events_df is None or len(events_df) == 0:
        return []

    # Assign colors to event types
    color_map = assign_event_colors(events_df)

    # Group events by event_key
    event_types = events_df["event_key"].unique()

    # Create a row for each event type
    rows = []
    for event_type in event_types:
        # Filter events for this type
        type_events = events_df[events_df["event_key"] == event_type]

        # LIMIT THE NUMBER OF EVENTS RENDERED
        if len(type_events) > max_events_per_type:
            logger.warning(
                f"Event type '{event_type}' has {len(type_events)} events, limiting to {max_events_per_type}"
            )
            type_events = type_events.head(max_events_per_type)

        # Generate indicators for this event type
        event_indicators = []
        for i, event in type_events.iterrows():
            # Calculate position using pre-computed timestamp columns
            start_ts = event["timestamp_start"]
            end_ts = event["timestamp_end"]

            start_ratio = (start_ts - timestamp_min) / (timestamp_max - timestamp_min)
            end_ratio = (end_ts - timestamp_min) / (timestamp_max - timestamp_min)

            # Clamp ratios to [0, 1] range for events extending beyond timeline
            start_ratio = max(0.0, min(1.0, start_ratio))
            end_ratio = max(0.0, min(1.0, end_ratio))

            # Format times for tooltip with milliseconds
            start_dt = pd.to_datetime(event["datetime_start"])
            end_dt = pd.to_datetime(event["datetime_end"])

            # Format with milliseconds (strftime %f gives microseconds, so divide by 1000)
            start_time = start_dt.strftime("%H:%M:%S.%f")[
                :-3
            ]  # Remove last 3 digits to get milliseconds
            end_time = end_dt.strftime("%H:%M:%S.%f")[:-3]

            # Get color for this event type
            event_color = color_map.get(event["event_key"], "#95a5a6")  # Default gray

            # Create tooltip with event details
            tooltip_content = [
                html.Div(
                    event["event_key"],
                    className="event-key",
                    style={"fontWeight": "bold"},
                )
            ]

            # Show single time if start and end are the same, otherwise show range
            if start_dt == end_dt:
                start_time = start_dt.strftime("%H:%M:%S.%f")[
                    :-3
                ]  # Remove last 3 digits to get milliseconds
                tooltip_content.append(html.Div(start_time, className="event-time"))
            else:
                start_time = start_dt.strftime("%H:%M:%S")
                end_time = end_dt.strftime("%H:%M:%S")
                tooltip_content.append(
                    html.Div(f"{start_time} - {end_time}", className="event-time")
                )

            if pd.notna(event.get("short_description")):
                tooltip_content.append(html.Div(event["short_description"]))

            event_indicators.append(
                create_event_indicator(
                    f"event-{i}",
                    tooltip_content,
                    start_ratio,
                    end_ratio,
                    timestamp_min,
                    timestamp_max,
                    color=event_color,
                )
            )

        # Create a row for this event type
        rows.append(
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Span(
                                                "●",
                                                style={
                                                    "color": color_map.get(
                                                        event_type, "#95a5a6"
                                                    ),
                                                    "fontSize": "10px",
                                                    "marginRight": "4px",
                                                },
                                            ),
                                            html.Span(
                                                truncate_middle(
                                                    event_type, max_length=20
                                                ),
                                                style={
                                                    "fontSize": "12px",
                                                    "color": color_map.get(
                                                        event_type, "#95a5a6"
                                                    ),
                                                    "maxWidth": "24px",
                                                    "overflow": "hidden",
                                                    "textOverflow": "ellipsis",
                                                    "whiteSpace": "nowrap",
                                                },
                                            ),
                                        ],
                                        style={
                                            "display": "flex",
                                            "alignItems": "center",
                                        },
                                    ),
                                ],
                                className="sm",
                            ),
                        ],
                        width={"size": "auto"},
                    ),
                    dbc.Col(
                        [
                            html.Div(
                                event_indicators,
                                className="saved",
                                style={"backgroundColor": "transparent"},
                            ),
                        ],
                        className="",
                    ),
                ],
                align="center",
                className="g-4",
            )
        )

    return rows
