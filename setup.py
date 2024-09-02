from setuptools import setup, find_packages

setup(
    name="DiveDB",
    version="0.1.0",
    packages=find_packages(
        include=[
            "services",
            "services.*",
            "services.utils",
            "services.utils.*",
            "server",
            "server.*",
            "server.django_app",
            "server.django_app.*",
            "server.metadata",
            "server.metadata.*",
        ]
    ),
    include_package_data=True,
)
