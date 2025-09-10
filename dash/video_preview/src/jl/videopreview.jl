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
- `restrictedTimeRange` (optional): Time range restrictions for video playback synchronization.. restrictedTimeRange has the following type: lists containing elements 'start', 'end', 'startTimestamp', 'endTimestamp'.
Those elements have the following types:
  - `start` (String; optional)
  - `end` (String; optional)
  - `startTimestamp` (Real; optional)
  - `endTimestamp` (Real; optional)
- `selectedVideoId` (String; optional): The ID of the currently selected video.
- `startTime` (Real; optional)
- `style` (Dict; optional)
- `videoOptions` (optional): Array of available video options with metadata.. videoOptions has the following type: Array of lists containing elements 'id', 'filename', 'fileCreatedAt', 'shareUrl', 'originalUrl', 'thumbnailUrl', 'metadata'.
Those elements have the following types:
  - `id` (String; required)
  - `filename` (String; required)
  - `fileCreatedAt` (String; required)
  - `shareUrl` (String; optional)
  - `originalUrl` (String; optional)
  - `thumbnailUrl` (String; optional)
  - `metadata` (optional): . metadata has the following type: lists containing elements 'duration', 'originalFilename', 'type'.
Those elements have the following types:
  - `duration` (String; optional)
  - `originalFilename` (String; optional)
  - `type` (String; optional)s
- `videoSrc` (String; required)
"""
function videopreview(; kwargs...)
        available_props = Symbol[:id, :currentTime, :endTime, :isPlaying, :playheadTime, :restrictedTimeRange, :selectedVideoId, :startTime, :style, :videoOptions, :videoSrc]
        wild_props = Symbol[]
        return Component("videopreview", "VideoPreview", "video_preview", available_props, wild_props; kwargs...)
end

