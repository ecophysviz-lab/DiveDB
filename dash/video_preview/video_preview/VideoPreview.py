# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal  # noqa: F401
from dash.development.base_component import Component, _explicitize_args

ComponentType = typing.Union[
    str,
    int,
    float,
    Component,
    None,
    typing.Sequence[typing.Union[str, int, float, Component, None]],
]

NumberType = typing.Union[
    typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex
]


class VideoPreview(Component):
    """A VideoPreview component.


    Keyword arguments:

    - id (string; optional)

    - currentTime (number; default 0)

    - endTime (number; optional)

    - isPlaying (boolean; default False)

    - playheadTime (number; optional)

    - restrictedTimeRange (dict; optional):
        Time range restrictions for video playback synchronization.

        `restrictedTimeRange` is a dict with keys:

        - start (string; optional)

        - end (string; optional)

        - startTimestamp (number; optional)

        - endTimestamp (number; optional)

    - selectedVideoId (string; optional):
        The ID of the currently selected video.

    - startTime (number; optional)

    - videoOptions (list of dicts; optional):
        Array of available video options with metadata.

        `videoOptions` is a list of dicts with keys:

        - id (string; required)

        - filename (string; required)

        - fileCreatedAt (string; required)

        - shareUrl (string; optional)

        - originalUrl (string; optional)

        - thumbnailUrl (string; optional)

        - metadata (dict; optional)

            `metadata` is a dict with keys:

            - duration (string; optional)

            - originalFilename (string; optional)

            - type (string; optional)

    - videoSrc (string; required)"""

    _children_props = []
    _base_nodes = ["children"]
    _namespace = "video_preview"
    _type = "VideoPreview"
    VideoOptionsMetadata = TypedDict(
        "VideoOptionsMetadata",
        {
            "duration": NotRequired[str],
            "originalFilename": NotRequired[str],
            "type": NotRequired[str],
        },
    )

    VideoOptions = TypedDict(
        "VideoOptions",
        {
            "id": str,
            "filename": str,
            "fileCreatedAt": str,
            "shareUrl": NotRequired[str],
            "originalUrl": NotRequired[str],
            "thumbnailUrl": NotRequired[str],
            "metadata": NotRequired["VideoOptionsMetadata"],
        },
    )

    RestrictedTimeRange = TypedDict(
        "RestrictedTimeRange",
        {
            "start": NotRequired[str],
            "end": NotRequired[str],
            "startTimestamp": NotRequired[NumberType],
            "endTimestamp": NotRequired[NumberType],
        },
    )

    def __init__(
        self,
        id: typing.Optional[typing.Union[str, dict]] = None,
        videoSrc: typing.Optional[str] = None,
        startTime: typing.Optional[NumberType] = None,
        endTime: typing.Optional[NumberType] = None,
        style: typing.Optional[typing.Any] = None,
        playheadTime: typing.Optional[NumberType] = None,
        isPlaying: typing.Optional[bool] = None,
        currentTime: typing.Optional[NumberType] = None,
        videoOptions: typing.Optional[typing.Sequence["VideoOptions"]] = None,
        selectedVideoId: typing.Optional[str] = None,
        restrictedTimeRange: typing.Optional["RestrictedTimeRange"] = None,
        **kwargs,
    ):
        self._prop_names = [
            "id",
            "currentTime",
            "endTime",
            "isPlaying",
            "playheadTime",
            "restrictedTimeRange",
            "selectedVideoId",
            "startTime",
            "style",
            "videoOptions",
            "videoSrc",
        ]
        self._valid_wildcard_attributes = []
        self.available_properties = [
            "id",
            "currentTime",
            "endTime",
            "isPlaying",
            "playheadTime",
            "restrictedTimeRange",
            "selectedVideoId",
            "startTime",
            "style",
            "videoOptions",
            "videoSrc",
        ]
        self.available_wildcard_properties = []
        _explicit_args = kwargs.pop("_explicit_args")
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args}

        for k in ["videoSrc"]:
            if k not in args:
                raise TypeError("Required argument `" + k + "` was not specified.")

        super(VideoPreview, self).__init__(**args)


setattr(VideoPreview, "__init__", _explicitize_args(VideoPreview.__init__))
