from unittest.mock import patch


def pytest_load_initial_conftests(early_config, parser, args):
    print("Mocking SwiftClient")
    patcher = patch("DiveDB.services.utils.storage.SwiftClient")
    MockSwiftClient = patcher.start()
    instance = MockSwiftClient.return_value
    instance.get_containers.return_value = []
    instance.list_objects.return_value = []
    instance.get_object_binary.return_value = b""
    instance.write_object_to_local.return_value = None
    instance.create_container.return_value = None
    instance.put_object.return_value = "mocked_url"
    early_config.add_cleanup(patcher.stop)
