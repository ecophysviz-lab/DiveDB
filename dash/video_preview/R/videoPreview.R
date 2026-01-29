# AUTO GENERATED FILE - DO NOT EDIT

#' @export
videoPreview <- function(id=NULL, datasetStartTime=NULL, isPlaying=NULL, playbackRate=NULL, playheadTime=NULL, showControls=NULL, style=NULL, timeOffset=NULL, videoMetadata=NULL, videoSrc=NULL) {
    
    props <- list(id=id, datasetStartTime=datasetStartTime, isPlaying=isPlaying, playbackRate=playbackRate, playheadTime=playheadTime, showControls=showControls, style=style, timeOffset=timeOffset, videoMetadata=videoMetadata, videoSrc=videoSrc)
    if (length(props) > 0) {
        props <- props[!vapply(props, is.null, logical(1))]
    }
    component <- list(
        props = props,
        type = 'VideoPreview',
        namespace = 'video_preview',
        propNames = c('id', 'datasetStartTime', 'isPlaying', 'playbackRate', 'playheadTime', 'showControls', 'style', 'timeOffset', 'videoMetadata', 'videoSrc'),
        package = 'videoPreview'
        )

    structure(component, class = c('dash_component', 'list'))
}
