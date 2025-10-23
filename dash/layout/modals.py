"""
Modal dialog components for the dashboard.
"""
from dash import html
import dash_bootstrap_components as dbc


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
