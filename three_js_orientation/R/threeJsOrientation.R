# AUTO GENERATED FILE - DO NOT EDIT

#' @export
threeJsOrientation <- function(id=NULL, activeTime=NULL, data=NULL, fbxFile=NULL, style=NULL) {
    
    props <- list(id=id, activeTime=activeTime, data=data, fbxFile=fbxFile, style=style)
    if (length(props) > 0) {
        props <- props[!vapply(props, is.null, logical(1))]
    }
    component <- list(
        props = props,
        type = 'ThreeJsOrientation',
        namespace = 'three_js_orientation',
        propNames = c('id', 'activeTime', 'data', 'fbxFile', 'style'),
        package = 'threeJsOrientation'
        )

    structure(component, class = c('dash_component', 'list'))
}
