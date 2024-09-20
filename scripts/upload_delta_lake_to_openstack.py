import os
from datetime import datetime
from keystoneauth1 import loading, session
from swiftclient import client as swiftclient


def main():
    print("Warning: This script is meant to be run in Nautilus.")

    confirm = input(
        f"Are you sure you want to upload the contents of {os.getenv('STORAGE_DIR')} to OpenStack Swift? (yes/no): "
    )
    if confirm.lower() != "yes":
        print("Upload cancelled.")
        return

    storage_dir = os.getenv("CONTAINER_DELTA_LAKE_PATH")
    container_name = os.getenv("OPENSTACK_FILE_STORAGE_CONTAINER_NAME")

    # Load the OpenStack Swift environment variables for auth v3
    auth_url = os.getenv("OPENSTACK_AUTH_URL")
    application_credential_id = os.getenv("OPENSTACK_APPLICATION_CREDENTIAL_ID")
    application_credential_secret = os.getenv("OPENSTACK_APPLICATION_CREDENTIAL_SECRET")

    # Authenticate with OpenStack
    loader = loading.get_plugin_loader("v3applicationcredential")
    auth = loader.load_from_options(
        auth_url=auth_url,
        application_credential_id=application_credential_id,
        application_credential_secret=application_credential_secret,
    )
    sess = session.Session(auth=auth)
    swift = swiftclient.Connection(session=sess)

    def upload_to_swift(directory):
        print(f"Uploading contents of {directory} to container {container_name}...")

        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, storage_dir)
                print(f"Uploading {relative_path}...")
                today_date = datetime.now().strftime("%Y-%m-%d")
                with open(file_path, "rb") as f:
                    swift.put_object(
                        container_name, f"{today_date}/{relative_path}", contents=f
                    )

    # Check if the container exists, if not create it
    containers = [container["name"] for container in swift.get_account()[1]]
    if container_name not in containers:
        print(f"Creating container {container_name}...")
        swift.put_container(container_name)

    # Call the upload function
    upload_to_swift(storage_dir)

    print("Upload complete.")


if __name__ == "__main__":
    main()
