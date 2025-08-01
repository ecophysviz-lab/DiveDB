"""
OpenStack Swift Client - NOT CURRENTLY IN USE or actively maintained.
"""

import os

from keystoneauth1 import loading, session
from swiftclient import client as swiftclient

OPENSTACK_AUTH_URL = os.getenv("OPENSTACK_AUTH_URL", "")
OPENSTACK_APPLICATION_CREDENTIAL_ID = os.getenv(
    "OPENSTACK_APPLICATION_CREDENTIAL_ID", ""
)
OPENSTACK_APPLICATION_CREDENTIAL_SECRET = os.getenv(
    "OPENSTACK_APPLICATION_CREDENTIAL_SECRET", ""
)


class SwiftClient:
    def __init__(self):
        if (
            OPENSTACK_AUTH_URL
            and OPENSTACK_APPLICATION_CREDENTIAL_ID
            and OPENSTACK_APPLICATION_CREDENTIAL_SECRET
        ):
            loader = loading.get_plugin_loader("v3applicationcredential")
            auth = loader.load_from_options(
                auth_url=OPENSTACK_AUTH_URL,
                application_credential_id=OPENSTACK_APPLICATION_CREDENTIAL_ID,
                application_credential_secret=OPENSTACK_APPLICATION_CREDENTIAL_SECRET,
            )
            self.sess = session.Session(auth=auth)
            self.client = swiftclient.Connection(session=self.sess)
            self.storage_url, _ = self.client.get_auth()
        else:
            print(
                "No OpenStack credentials found. SwiftClient will not be initialized."
            )

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

    def create_container(self, container_name: str):
        self.client.put_container(container_name)

    def put_object(self, container_name: str, object_name: str, contents: str):
        if container_name not in [
            container["name"] for container in self.get_containers()
        ]:
            print(f"Container {container_name} does not exist. Creating...")
            self.create_container(container_name)
        self.client.put_object(container_name, object_name, contents=contents)
        return f"{self.storage_url}/{container_name}/{object_name}"
