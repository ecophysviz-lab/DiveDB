# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
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

- endTime (number; optional)

- isPlaying (boolean; default False)

- playheadTime (number; optional)

- startTime (number; optional)

- videoSrc (string; optional)"""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'video_preview'
    _type = 'VideoPreview'


    def __init__(
        self,
        id: typing.Optional[typing.Union[str, dict]] = None,
        videoSrc: typing.Optional[str] = None,
        startTime: typing.Optional[NumberType] = None,
        endTime: typing.Optional[NumberType] = None,
        style: typing.Optional[typing.Any] = None,
        playheadTime: typing.Optional[NumberType] = None,
        isPlaying: typing.Optional[bool] = None,
        **kwargs
    ):
        self._prop_names = ['id', 'endTime', 'isPlaying', 'playheadTime', 'startTime', 'style', 'videoSrc']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['id', 'endTime', 'isPlaying', 'playheadTime', 'startTime', 'style', 'videoSrc']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args}

        super(VideoPreview, self).__init__(**args)

setattr(VideoPreview, "__init__", _explicitize_args(VideoPreview.__init__))
