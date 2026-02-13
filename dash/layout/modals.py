"""
Modal dialog components for the dashboard.
"""
from dash import html, dcc
import dash_bootstrap_components as dbc


def create_event_modal():
    """Create the event creation modal dialog for B-key bookmark feature.

    This modal allows users to quickly create events (point or duration)
    at the current playhead position. It supports:
    - Selecting from existing event types
    - Creating new event types
    - Auto-fill of last used event type for rapid repeated annotations
    """
    # Note: modal content styling (background, border, border-radius) is handled
    # by the .event-modal-dark .modal-content rule in _components.scss.
    # Do NOT set backgroundColor here — it applies to the full-screen .modal
    # overlay wrapper, not the dialog box, and would hide the backdrop.
    header_style = {
        "backgroundColor": "#041827",  # blueExtraDark
        "borderBottom": "1px solid #0e3551",  # blueDark
        "color": "#ffffff",
    }
    body_style = {
        "backgroundColor": "#041827",  # blueExtraDark
        "color": "#ffffff",
    }
    footer_style = {
        "backgroundColor": "#041827",  # blueExtraDark
        "borderTop": "1px solid #0e3551",  # blueDark
    }
    label_style = {
        "color": "#ffffff",
        "fontWeight": "500",
        "fontSize": "14px",
    }
    input_style = {
        "backgroundColor": "#0e3551",  # blueDark
        "border": "1px solid #73a9c4",  # blueLight
        "color": "#ffffff",
        "borderRadius": "6px",
    }
    readonly_input_style = {
        "backgroundColor": "#092a42",  # blue
        "border": "1px solid #73a9c4",  # blueLight
        "color": "#73a9c4",  # blueLight text
        "borderRadius": "6px",
    }

    return dbc.Modal(
        [
            dbc.ModalHeader(
                dbc.ModalTitle("Create Event", style={"color": "#ffffff"}),
                style=header_style,
                close_button=True,
                class_name="event-modal-header",
            ),
            dbc.ModalBody(
                [
                    # Event Type Selection
                    html.Div(
                        [
                            dbc.Label(
                                "Event Type",
                                html_for="event-type-select",
                                style=label_style,
                            ),
                            dcc.Dropdown(
                                id="event-type-select",
                                options=[],  # Populated dynamically by callback
                                placeholder="Select event type...",
                                clearable=False,
                                className="event-modal-dropdown",
                            ),
                        ],
                        className="mb-3",
                    ),
                    # New Event Type Input (hidden by default)
                    html.Div(
                        [
                            dbc.Label(
                                "New Event Type Name",
                                html_for="new-event-type-input",
                                style=label_style,
                            ),
                            dbc.Input(
                                type="text",
                                id="new-event-type-input",
                                placeholder="Enter new event type name...",
                                style=input_style,
                            ),
                        ],
                        id="new-event-type-container",
                        className="mb-3",
                        style={"display": "none"},  # Hidden by default
                    ),
                    # Start Time (read-only, auto-filled from playhead)
                    html.Div(
                        [
                            dbc.Label(
                                "Start Time",
                                html_for="event-start-time",
                                style=label_style,
                            ),
                            dbc.Input(
                                type="text",
                                id="event-start-time",
                                readonly=True,
                                style=readonly_input_style,
                            ),
                        ],
                        className="mb-3",
                    ),
                    # End Time (optional, for duration events)
                    html.Div(
                        [
                            dbc.Label(
                                "End Time (optional)",
                                html_for="event-end-time",
                                style=label_style,
                            ),
                            dbc.Input(
                                type="text",
                                id="event-end-time",
                                placeholder="Leave blank for point event",
                                style=input_style,
                            ),
                            dbc.FormText(
                                "For point events, leave blank. For duration events, enter end time.",
                                style={"color": "#73a9c4"},  # blueLight
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label(
                                "Short Description (optional)",
                                html_for="event-short-description",
                                style=label_style,
                            ),
                            dbc.Input(
                                type="text",
                                id="event-short-description",
                                placeholder="Brief label or summary...",
                                maxLength=100,
                                style=input_style,
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Label(
                                "Long Description (optional)",
                                html_for="event-long-description",
                                style=label_style,
                            ),
                            dbc.Textarea(
                                id="event-long-description",
                                placeholder="Detailed notes about this event...",
                                style={**input_style, "height": "80px"},
                            ),
                        ],
                        className="mb-3",
                    ),
                ],
                style=body_style,
            ),
            dbc.ModalFooter(
                [
                    dbc.Button(
                        "CANCEL",
                        id="cancel-event-btn",
                        className="btn btn-sm",
                        n_clicks=0,
                        style={
                            "backgroundColor": "#0e3551",  # blueDark
                            "border": "none",
                            "color": "#ffffff",
                            "fontWeight": "600",
                            "letterSpacing": "0.05em",
                        },
                    ),
                    dbc.Button(
                        "SAVE",
                        id="save-event-btn",
                        className="btn btn-sm",
                        n_clicks=0,
                        style={
                            "backgroundColor": "transparent",
                            "border": "none",
                            "color": "#73a9c4",  # blueLight
                            "fontWeight": "600",
                            "letterSpacing": "0.05em",
                        },
                    ),
                ],
                style=footer_style,
            ),
        ],
        id="event-modal",
        is_open=False,
        centered=True,
        class_name="event-modal-dark",
    )


def create_event_toast():
    """Create a toast notification for event save feedback.

    Positioned in the bottom-right corner, auto-dismisses after 3 seconds.
    """
    return html.Div(
        dbc.Toast(
            id="event-toast",
            header="Event Saved",
            icon="success",
            is_open=False,
            dismissable=True,
            duration=3000,  # Auto-dismiss after 3 seconds
            style={
                "position": "fixed",
                "bottom": "20px",
                "right": "20px",
                "zIndex": 9999,
                "minWidth": "250px",
            },
        ),
        id="event-toast-container",
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
