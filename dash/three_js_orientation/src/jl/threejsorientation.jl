# AUTO GENERATED FILE - DO NOT EDIT

export threejsorientation

"""
    threejsorientation(;kwargs...)

A ThreeJsOrientation component.

Keyword arguments:
- `id` (String; optional)
- `activeTime` (Real; required)
- `data` (String; required)
- `modelFile` (String; optional)
- `style` (Dict; optional)
- `textureFile` (String; optional)
"""
function threejsorientation(; kwargs...)
        available_props = Symbol[:id, :activeTime, :data, :modelFile, :style, :textureFile]
        wild_props = Symbol[]
        return Component("threejsorientation", "ThreeJsOrientation", "three_js_orientation", available_props, wild_props; kwargs...)
end

