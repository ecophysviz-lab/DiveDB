# AUTO GENERATED FILE - DO NOT EDIT

export videopreview

"""
    videopreview(;kwargs...)

A VideoPreview component.

Keyword arguments:
- `id` (String; optional)
- `datasetStartTime` (Real; optional)
- `isPlaying` (Bool; optional)
- `playheadTime` (Real; optional)
- `style` (Dict; optional)
- `videoMetadata` (Dict; optional)
- `videoSrc` (String; optional)
"""
function videopreview(; kwargs...)
        available_props = Symbol[:id, :datasetStartTime, :isPlaying, :playheadTime, :style, :videoMetadata, :videoSrc]
        wild_props = Symbol[]
        return Component("videopreview", "VideoPreview", "video_preview", available_props, wild_props; kwargs...)
end

