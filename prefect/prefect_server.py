from crl_datacube.test.test_datacube import BASE, main as ingest_nbs_adapts
from crl_datacube.conf import caribbean_config
from crl_datacube.datacube import DataCubeConfig
import rioxarray as rxr
from prefect import flow
import asyncio


@flow
def nbs_adapts(
        regions: list[str] = ["DOM_01", "DOM_02", "HTI_North", "HTI_South"], 
        output: str | None = None,
        basepath: str = BASE, 
        config: dict = caribbean_config,
        init: bool = True
    ):
    return ingest_nbs_adapts(
        DataCubeConfig(**config), 
        regions=regions, 
        basepath=basepath, 
        output=output, 
        initialize=init
    )
    
async def main():
    flows = [nbs_adapts]
    tasks = [flow.serve(name=f"deployment-{i+1}") for i, flow in enumerate(flows)]
    await asyncio.gather(*tasks)

    
if __name__ == "__main__":
    asyncio.run(main())