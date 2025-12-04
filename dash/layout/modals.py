"""
Modal and popover dialog components for the dashboard.
"""
from dash import html
import dash_bootstrap_components as dbc


def create_event_popover():
    """Create the event creation popover dialog anchored to the save button."""
    return dbc.Popover(
        [
            dbc.PopoverHeader("Create Event"),
            dbc.PopoverBody(
                [
                    # Event Type Selection
                    html.Div(
                        [
                            dbc.Label(
                                "Event Type",
                                html_for="event-type-select",
                                className="form-label-sm",
                            ),
                            dbc.Select(
                                id="event-type-select",
                                options=[
                                    # Will be populated dynamically by callback
                                    {"label": "Select event type...", "value": ""},
                                ],
                                value="",
                                className="form-select-sm",
                            ),
                        ],
                        className="mb-2",
                    ),
                    # New Event Type Input (hidden by default)
                    html.Div(
                        [
                            dbc.Input(
                                id="new-event-type-input",
                                type="text",
                                placeholder="Enter new event type name...",
                                className="form-control-sm",
                            ),
                        ],
                        id="new-event-type-container",
                        className="mb-2",
                        style={"display": "none"},
                    ),
                    # Duration Type Selection
                    html.Div(
                        [
                            dbc.Label(
                                "Event Duration",
                                className="form-label-sm",
                            ),
                            dbc.RadioItems(
                                id="event-duration-type",
                                options=[
                                    {"label": "Point Event", "value": "point"},
                                    {"label": "State Event", "value": "state"},
                                ],
                                value="point",
                                inline=True,
                                className="form-check-sm",
                            ),
                        ],
                        className="mb-2",
                    ),
                    # Timestamp Display (read-only)
                    html.Div(
                        [
                            dbc.Label(
                                "Time",
                                className="form-label-sm",
                            ),
                            html.Div(
                                id="event-timestamp-display",
                                className="form-control-plaintext form-control-sm text-muted",
                                children="--",
                            ),
                        ],
                        className="mb-2",
                    ),
                    # Description Input
                    html.Div(
                        [
                            dbc.Label(
                                "Description",
                                html_for="event-description",
                                className="form-label-sm",
                            ),
                            dbc.Textarea(
                                id="event-description",
                                placeholder="Enter description (optional)...",
                                className="form-control-sm",
                                style={"minHeight": "60px"},
                            ),
                        ],
                        className="mb-3",
                    ),
                    # Action Buttons
                    html.Div(
                        [
                            dbc.Button(
                                "Cancel",
                                id="cancel-event-button",
                                className="btn btn-secondary btn-sm me-2",
                                n_clicks=0,
                            ),
                            dbc.Button(
                                "Save",
                                id="save-event-button",
                                className="btn btn-primary btn-sm",
                                n_clicks=0,
                                disabled=True,  # Disabled until Phase 3 implements write logic
                            ),
                        ],
                        className="d-flex justify-content-end",
                    ),
                ],
                className="p-2",
                style={"minWidth": "280px"},
            ),
        ],
        id="event-popover",
        target="save-button",
        placement="top",
        is_open=False,
        trigger="legacy",  # Click to open, click outside to close
    )


# Keep the old function name as an alias for backward compatibility during transition
def create_bookmark_modal():
    """Deprecated: Use create_event_popover() instead."""
    return create_event_popover()
