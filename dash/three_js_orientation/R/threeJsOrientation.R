# AUTO GENERATED FILE - DO NOT EDIT

#' @export
threeJsOrientation <- function(id=NULL, activeTime=NULL, data=NULL, objFile=NULL, style=NULL, textureFile=NULL) {
    
    props <- list(id=id, activeTime=activeTime, data=data, objFile=objFile, style=style, textureFile=textureFile)
    if (length(props) > 0) {
        props <- props[!vapply(props, is.null, logical(1))]
    }
    component <- list(
        props = props,
        type = 'ThreeJsOrientation',
        namespace = 'three_js_orientation',
        propNames = c('id', 'activeTime', 'data', 'objFile', 'style', 'textureFile'),
        package = 'threeJsOrientation'
        )

    structure(component, class = c('dash_component', 'list'))
}
