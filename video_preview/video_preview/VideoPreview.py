# AUTO GENERATED FILE - DO NOT EDIT

from dash.development.base_component import Component, _explicitize_args


class VideoPreview(Component):
    """A VideoPreview component.


Keyword arguments:

- id (string; optional)

- activeTime (number; default 0)

- endTime (number; optional)

- isPlaying (boolean; default False)

- playheadTime (number; optional)

- startTime (number; optional)

- style (dict; optional)

- videoSrc (string; required)"""
    _children_props = []
    _base_nodes = ['children']
    _namespace = 'video_preview'
    _type = 'VideoPreview'
    @_explicitize_args
    def __init__(self, id=Component.UNDEFINED, videoSrc=Component.REQUIRED, activeTime=Component.UNDEFINED, startTime=Component.UNDEFINED, endTime=Component.UNDEFINED, style=Component.UNDEFINED, playheadTime=Component.UNDEFINED, isPlaying=Component.UNDEFINED, **kwargs):
        self._prop_names = ['id', 'activeTime', 'endTime', 'isPlaying', 'playheadTime', 'startTime', 'style', 'videoSrc']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['id', 'activeTime', 'endTime', 'isPlaying', 'playheadTime', 'startTime', 'style', 'videoSrc']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args}

        for k in ['videoSrc']:
            if k not in args:
                raise TypeError(
                    'Required argument `' + k + '` was not specified.')

        super(VideoPreview, self).__init__(**args)
