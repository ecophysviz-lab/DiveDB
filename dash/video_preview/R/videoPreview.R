# AUTO GENERATED FILE - DO NOT EDIT

#' @export
videoPreview <- function(id=NULL, datasetStartTime=NULL, isPlaying=NULL, playheadTime=NULL, style=NULL, videoMetadata=NULL, videoSrc=NULL) {
    
    props <- list(id=id, datasetStartTime=datasetStartTime, isPlaying=isPlaying, playheadTime=playheadTime, style=style, videoMetadata=videoMetadata, videoSrc=videoSrc)
    if (length(props) > 0) {
        props <- props[!vapply(props, is.null, logical(1))]
    }
    component <- list(
        props = props,
        type = 'VideoPreview',
        namespace = 'video_preview',
        propNames = c('id', 'datasetStartTime', 'isPlaying', 'playheadTime', 'style', 'videoMetadata', 'videoSrc'),
        package = 'videoPreview'
        )

    structure(component, class = c('dash_component', 'list'))
}
