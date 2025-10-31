"""
Layout module for DiveDB data visualization dashboard.

This module is organized into focused components:
- core: Main layout assembly, header, and stores
- sidebar: Left (selection) and right (visuals) sidebars
- timeline: Footer with playhead controls and timeline
- indicators: Event and video indicators for the timeline
- modals: Modal dialogs (bookmarks, etc.)
"""

from .core import (
    create_header,
    create_main_content,
    create_empty_figure,
    create_empty_dataframe,
)
from .sidebar import create_left_sidebar, create_right_sidebar
from .timeline import create_footer
from .indicators import (
    create_event_indicator,
    create_video_indicator,
    create_saved_indicator,
    generate_event_indicators_row,
    calculate_video_timeline_position,
)
from .modals import create_bookmark_modal

__all__ = [
    # Component creators
    "create_header",
    "create_main_content",
    "create_left_sidebar",
    "create_right_sidebar",
    "create_footer",
    "create_bookmark_modal",
    # Empty state helpers
    "create_empty_figure",
    "create_empty_dataframe",
    # Indicators
    "create_event_indicator",
    "create_video_indicator",
    "create_saved_indicator",
    "generate_event_indicators_row",
    "calculate_video_timeline_position",
]
