import pytest
from unittest.mock import patch


@pytest.fixture(scope="session", autouse=True)
def mock_swiftclient():
    print("Mocking SwiftClient")
    patcher = patch("DiveDB.services.utils.openstack.SwiftClient")
    MockSwiftClient = patcher.start()
    instance = MockSwiftClient.return_value
    instance.get_containers.return_value = []
    instance.list_objects.return_value = []
    instance.get_object_binary.return_value = b""
    instance.write_object_to_local.return_value = None
    instance.create_container.return_value = None
    instance.put_object.return_value = "mocked_url"
    yield instance
    patcher.stop()
