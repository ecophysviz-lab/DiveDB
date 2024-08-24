from keystoneauth1 import loading, session
from swiftclient import client as swiftclient
import os

OPENSTACK_AUTH_URL = os.environ["OPENSTACK_AUTH_URL"]
OPANSTACK_APPLICATION_CREDENTIAL_ID = os.environ["OPANSTACK_APPLICATION_CREDENTIAL_ID"]
OPENSTACK_APPLICATION_CREDENTIAL_SECRET = os.environ[
    "OPENSTACK_APPLICATION_CREDENTIAL_SECRET"
]

class SwiftClient:
    loader = loading.get_plugin_loader("v3applicationcredential")
    auth = loader.load_from_options(
        auth_url=OPENSTACK_AUTH_URL,
        application_credential_id=OPANSTACK_APPLICATION_CREDENTIAL_ID,
        application_credential_secret=OPENSTACK_APPLICATION_CREDENTIAL_SECRET,
    )

    sess = session.Session(auth=auth)
    client = swiftclient.Connection(session=sess)

    def get_containers(self):
        return self.client.get_account[1]
    
    def list_objects(self, container_name: str):
        return self.client.get_container(container_name)[1]
    
    def get_object_binary(self, container_name: str, object_name: str):
        return self.client.get_object(container_name, object_name)[1]
    
    def write_object_to_local(self, output: str, **kwargs):
        obj = self.get_object_binary(**kwargs)
        with open(output, 'wb') as f:
            f.write(obj)
    
    
