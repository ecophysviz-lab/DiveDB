from setuptools import setup, find_packages

setup(
    name="DiveDB",
    version="0.1.0",
    packages=find_packages(include=["services", "server"]),
)
