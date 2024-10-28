# AUTO GENERATED FILE - DO NOT EDIT

#' @export
videoPreview <- function(id=NULL, activeTime=NULL, endTime=NULL, isPlaying=NULL, playheadTime=NULL, startTime=NULL, style=NULL, videoSrc=NULL) {
    
    props <- list(id=id, activeTime=activeTime, endTime=endTime, isPlaying=isPlaying, playheadTime=playheadTime, startTime=startTime, style=style, videoSrc=videoSrc)
    if (length(props) > 0) {
        props <- props[!vapply(props, is.null, logical(1))]
    }
    component <- list(
        props = props,
        type = 'VideoPreview',
        namespace = 'video_preview',
        propNames = c('id', 'activeTime', 'endTime', 'isPlaying', 'playheadTime', 'startTime', 'style', 'videoSrc'),
        package = 'videoPreview'
        )

    structure(component, class = c('dash_component', 'list'))
}
