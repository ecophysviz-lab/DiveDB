import os, s3fs

from keystoneauth1 import loading, session
from swiftclient import client as swiftclient

import logging

OPENSTACK_AUTH_URL = os.getenv("OPENSTACK_AUTH_URL", "")
OPENSTACK_APPLICATION_CREDENTIAL_ID = os.getenv(
    "OPENSTACK_APPLICATION_CREDENTIAL_ID", ""
)
OPENSTACK_APPLICATION_CREDENTIAL_SECRET = os.getenv(
    "OPENSTACK_APPLICATION_CREDENTIAL_SECRET", ""
)


class SwiftClient:
    def __init__(self):
        loader = loading.get_plugin_loader("v3applicationcredential")
        auth = loader.load_from_options(
            auth_url=OPENSTACK_AUTH_URL,
            application_credential_id=OPENSTACK_APPLICATION_CREDENTIAL_ID,
            application_credential_secret=OPENSTACK_APPLICATION_CREDENTIAL_SECRET,
        )
        self.sess = session.Session(auth=auth)
        self.client = swiftclient.Connection(session=self.sess)
        self.storage_url, _ = self.client.get_auth()

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

    def get_aws_handle(self, container: str, path: str):
        # Access credentials for the Swift S3 store
        import boto3
        OTHER_AUTH_URL = "https://identity.cloud.sdsc.edu:5000/v3/users/107aa118a3c040d9a52db5f39c5ebdf0/credentials/OS-EC2/de051482a66f43188c420138e59c9f78"
        
        OTHER_AUTH_URL = "https://object.cloud.sdsc.edu/v1/AUTH_413c350724914abbbb2ece619b2b69d4"
        s3_fs = boto3.client(
            's3',
            aws_access_key_id='de051482a66f43188c420138e59c9f78',
            aws_secret_access_key='d1683e9710684a84be73bcd02e353d8b',
            endpoint_url=OTHER_AUTH_URL,
            use_ssl=False
        )

        # Define the S3 path to the netCDF file (in bucket/key format)
        # s3_path = f"{container}/{path}"
        logging.info("Files in container:")
        logging.info(s3_fs.list_objects_v2(Bucket=container))
        return s3_fs.list_objects_v2(Bucket=container)
        
        # logging.info(s3_path)
        # return s3_fs.open(s3_path)

        # Open the netCDF file directly from the Swift S3-compatible store
        # ds = xr.open_dataset(s3_fs.open(s3_path))

# Now you can work with your xarray Dataset
# print(ds)
