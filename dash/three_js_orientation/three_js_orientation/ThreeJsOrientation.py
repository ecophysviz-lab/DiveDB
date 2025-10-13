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


class ThreeJsOrientation(Component):
    """A ThreeJsOrientation component.


    Keyword arguments:

    - id (string; optional)

    - activeTime (number; required)

    - data (string; required)

    - objFile (string; required)

    - textureFile (string; optional)"""

    _children_props = []
    _base_nodes = ["children"]
    _namespace = "three_js_orientation"
    _type = "ThreeJsOrientation"

    def __init__(
        self,
        id: typing.Optional[typing.Union[str, dict]] = None,
        data: typing.Optional[str] = None,
        activeTime: typing.Optional[NumberType] = None,
        objFile: typing.Optional[str] = None,
        textureFile: typing.Optional[str] = None,
        style: typing.Optional[typing.Any] = None,
        **kwargs,
    ):
        self._prop_names = [
            "id",
            "activeTime",
            "data",
            "objFile",
            "style",
            "textureFile",
        ]
        self._valid_wildcard_attributes = []
        self.available_properties = [
            "id",
            "activeTime",
            "data",
            "objFile",
            "style",
            "textureFile",
        ]
        self.available_wildcard_properties = []
        _explicit_args = kwargs.pop("_explicit_args")
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args}

        for k in ["activeTime", "data", "objFile"]:
            if k not in args:
                raise TypeError("Required argument `" + k + "` was not specified.")

        super(ThreeJsOrientation, self).__init__(**args)


setattr(ThreeJsOrientation, "__init__", _explicitize_args(ThreeJsOrientation.__init__))
