
module ThreejsModel
using Dash

const resources_path = realpath(joinpath( @__DIR__, "..", "deps"))
const version = "0.0.1"

include("jl/threejsmodel.jl")

function __init__()
    DashBase.register_package(
        DashBase.ResourcePkg(
            "threejs_model",
            resources_path,
            version = version,
            [
                DashBase.Resource(
    relative_package_path = "threejs_model.min.js",
    external_url = nothing,
    dynamic = nothing,
    async = nothing,
    type = :js
),
DashBase.Resource(
    relative_package_path = "threejs_model.min.js.map",
    external_url = nothing,
    dynamic = true,
    async = nothing,
    type = :js
)
            ]
        )

    )
end
end
