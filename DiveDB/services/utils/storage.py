from .openstack import SwiftClient


class OpenStackStorage:
    def __init__(self):
        self.client = SwiftClient()

    def _open(self, name, mode="rb"):
        container_name, object_name = name.split("/", 1)
        return self.client.get_object_binary(container_name, object_name)

    def _save(self, name, content):
        container_name, object_name = name.split("/", 1)
        self.client.put_object(container_name, object_name, content)
        return name

    def exists(self, name):
        container_name, object_name = name.split("/", 1)
        objects = self.client.list_objects(container_name)
        return any(obj["name"] == object_name for obj in objects)

    def url(self, name):
        container_name, object_name = name.split("/", 1)
        return f"{self.client.storage_url}/{container_name}/{object_name}"
