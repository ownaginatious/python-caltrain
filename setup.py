#! /usr/bin/env python
from setuptools import setup, find_packages
from io import open

setup(
    name='python-caltrain',
    packages=find_packages(exclude=["tests"]),
    version='2016.4.2',
    description='A library for working with raw Caltrain scheduling'
                'data in Python',
    author='Dillon Dixon',
    author_email='dillondixon@gmail.com',
    url='https://github.com/ownaginatious/python-caltrain',
    download_url='https://github.com/ownaginatious/python-caltrain'
                 '/tarball/2016.4.2',
    license='MIT',
    keywords=['caltrain', 'python'],
    zip_safe=True,
    include_package_data=True,
    exclude_package_data={'': ['README.rst', 'LICENSE']},
    classifiers=[
        'Environment :: Console',
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
