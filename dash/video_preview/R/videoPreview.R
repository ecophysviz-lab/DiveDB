# AUTO GENERATED FILE - DO NOT EDIT

#' @export
videoPreview <- function(id=NULL, currentTime=NULL, endTime=NULL, isPlaying=NULL, playheadTime=NULL, restrictedTimeRange=NULL, selectedVideoId=NULL, startTime=NULL, style=NULL, videoOptions=NULL, videoSrc=NULL) {
    
    props <- list(id=id, currentTime=currentTime, endTime=endTime, isPlaying=isPlaying, playheadTime=playheadTime, restrictedTimeRange=restrictedTimeRange, selectedVideoId=selectedVideoId, startTime=startTime, style=style, videoOptions=videoOptions, videoSrc=videoSrc)
    if (length(props) > 0) {
        props <- props[!vapply(props, is.null, logical(1))]
    }
    component <- list(
        props = props,
        type = 'VideoPreview',
        namespace = 'video_preview',
        propNames = c('id', 'currentTime', 'endTime', 'isPlaying', 'playheadTime', 'restrictedTimeRange', 'selectedVideoId', 'startTime', 'style', 'videoOptions', 'videoSrc'),
        package = 'videoPreview'
        )

    structure(component, class = c('dash_component', 'list'))
}
