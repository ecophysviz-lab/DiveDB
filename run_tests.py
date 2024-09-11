import pytest
from unittest.mock import patch

# Apply the patch at the very beginning
patcher = patch("DiveDB.services.utils.openstack.SwiftClient")
MockSwiftClient = patcher.start()
instance = MockSwiftClient.return_value
instance.get_containers.return_value = []
instance.list_objects.return_value = []
instance.get_object_binary.return_value = b""
instance.write_object_to_local.return_value = None
instance.create_container.return_value = None
instance.put_object.return_value = "mocked_url"

# Run pytest
exit_code = pytest.main()

# Stop the patcher
patcher.stop()

# Exit with the appropriate exit code
exit(exit_code)
