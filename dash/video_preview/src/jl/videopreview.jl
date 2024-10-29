# AUTO GENERATED FILE - DO NOT EDIT

export videopreview

"""
    videopreview(;kwargs...)

A VideoPreview component.

Keyword arguments:
- `id` (String; optional)
- `currentTime` (Real; optional)
- `endTime` (Real; optional)
- `isPlaying` (Bool; optional)
- `playheadTime` (Real; optional)
- `startTime` (Real; optional)
- `style` (Dict; optional)
- `videoSrc` (String; required)
"""
function videopreview(; kwargs...)
        available_props = Symbol[:id, :currentTime, :endTime, :isPlaying, :playheadTime, :startTime, :style, :videoSrc]
        wild_props = Symbol[]
        return Component("videopreview", "VideoPreview", "video_preview", available_props, wild_props; kwargs...)
end

