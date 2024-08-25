import os

from keystoneauth1 import loading, session
from swiftclient import client as swiftclient

OPENSTACK_AUTH_URL = os.environ["OPENSTACK_AUTH_URL"]
OPENSTACK_APPLICATION_CREDENTIAL_ID = os.environ["OPENSTACK_APPLICATION_CREDENTIAL_ID"]
OPENSTACK_APPLICATION_CREDENTIAL_SECRET = os.environ[
    "OPENSTACK_APPLICATION_CREDENTIAL_SECRET"
]


class SwiftClient:
    loader = loading.get_plugin_loader("v3applicationcredential")
    auth = loader.load_from_options(
        auth_url=OPENSTACK_AUTH_URL,
        application_credential_id=OPENSTACK_APPLICATION_CREDENTIAL_ID,
        application_credential_secret=OPENSTACK_APPLICATION_CREDENTIAL_SECRET,
    )

    sess = session.Session(auth=auth)
    client = swiftclient.Connection(session=sess)

    def get_containers(self):
        return self.client.get_account()[1]

    def list_objects(self, container_name: str, regex=None):
        import re

        all_objects = self.client.get_container(container_name)[1]
        if not regex:
            return all_objects
        filtered_objects = [obj for obj in all_objects if re.match(regex, obj["name"])]
        return filtered_objects

    def get_object_binary(self, container_name: str, object_name: str):
        return self.client.get_object(container_name, object_name)[1]

    def write_object_to_local(self, output: str, **kwargs):
        obj = self.get_object_binary(**kwargs)
        with open(output, "wb") as f:
            f.write(obj)

    def put_object_to_swift(self, container_name: str, object_name: str, contents: str):
        # Untested while waiting on JKB to make a dev bucket
        with open(contents, "rb") as file_data:
            self.client.put_object(container_name, object_name, contents=file_data)
