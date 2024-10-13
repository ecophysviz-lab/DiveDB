# AUTO GENERATED FILE - DO NOT EDIT

export threejsorientation

"""
    threejsorientation(;kwargs...)

A ThreeJsOrientation component.

Keyword arguments:
- `id` (String; optional)
- `activeTime` (String; required)
- `data` (String; required)
- `fbxFile` (String; required)
- `style` (Dict; optional)
"""
function threejsorientation(; kwargs...)
        available_props = Symbol[:id, :activeTime, :data, :fbxFile, :style]
        wild_props = Symbol[]
        return Component("threejsorientation", "ThreeJsOrientation", "three_js_orientation", available_props, wild_props; kwargs...)
end

