from DiveDB.services.utils.openstack import SwiftClient
import logging
import xarray

import pytest

@pytest.mark.skip(reason="Skipping this test")
def test_swift_client():
    client = SwiftClient()
    logging.info(client.get_containers())
    
    obj = client.list_objects('dev_data')
    logging.info([o for o in obj if '.nc' in o['name']])
    # client.get_object_binary("dev_data", "deployment_data.nc")
    f = client.get_aws_handle("dev_data", "deployment_data.nc")
    logging.info(f)


def test_s3():
    client = SwiftClient()
    logging.info(client.get_containers())
    logging.info(client.get_aws_handle("data", ""))
    