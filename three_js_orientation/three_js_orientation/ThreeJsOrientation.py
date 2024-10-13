# AUTO GENERATED FILE - DO NOT EDIT

from dash.development.base_component import Component, _explicitize_args


class ThreeJsOrientation(Component):
    """A ThreeJsOrientation component.


    Keyword arguments:

    - id (string; optional)

    - activeTime (string; required)

    - data (string; required)

    - fbxFile (string; required)

    - style (dict; optional)"""

    _children_props = []
    _base_nodes = ["children"]
    _namespace = "three_js_orientation"
    _type = "ThreeJsOrientation"

    @_explicitize_args
    def __init__(
        self,
        id=Component.UNDEFINED,
        data=Component.REQUIRED,
        activeTime=Component.REQUIRED,
        fbxFile=Component.REQUIRED,
        style=Component.UNDEFINED,
        **kwargs,
    ):
        self._prop_names = ["id", "activeTime", "data", "fbxFile", "style"]
        self._valid_wildcard_attributes = []
        self.available_properties = ["id", "activeTime", "data", "fbxFile", "style"]
        self.available_wildcard_properties = []
        _explicit_args = kwargs.pop("_explicit_args")
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args}

        for k in ["activeTime", "data", "fbxFile"]:
            if k not in args:
                raise TypeError("Required argument `" + k + "` was not specified.")

        super(ThreeJsOrientation, self).__init__(**args)
