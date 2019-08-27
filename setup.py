from setuptools import setup, find_packages
from io import open
import os

here = os.path.abspath(os.path.dirname(__file__))
with open(
    os.path.join(here, "python_caltrain", "__version__.py"), "r", encoding="utf-8"
) as f:
    captured = {}
    exec(f.read(), captured)
    version = captured["__version__"]


def get_long_description():
    with open("README.rst") as f:
        return f.read()


setup(
    name="python-caltrain",
    packages=find_packages(exclude=["tests"]),
    version=version,
    description="A library for working with raw Caltrain scheduling data in Python",
    long_description=get_long_description(),
    author="Dillon Dixon",
    author_email="dillondixon@gmail.com",
    url="https://github.com/ownaginatious/python-caltrain",
    license="MIT",
    keywords=["caltrain", "python"],
    zip_safe=True,
    include_package_data=True,
    exclude_package_data={"": ["README.rst", "LICENSE"]},
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
    test_suite="tests",
)
