#! /usr/bin/env python
from setuptools import setup, find_packages
from io import open
import versioneer

setup(
    name='python-caltrain',
    packages=find_packages(exclude=["tests"]),
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description='A library for working with raw Caltrain scheduling'
                'data in Python',
    author='Dillon Dixon',
    author_email='dillondixon@gmail.com',
    url='https://github.com/ownaginatious/python-caltrain',
    download_url='https://github.com/ownaginatious/python-caltrain'
                 '/tarball/2016.4.5',
    license='MIT',
    keywords=['caltrain', 'python'],
    zip_safe=True,
    include_package_data=True,
    exclude_package_data={'': ['README.rst', 'LICENSE']},
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5'
    ],
    install_requires=[line.strip()
                      for line in open("requirements.txt", "r",
                                       encoding="utf-8").readlines()],
)
