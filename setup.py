import os
from setuptools import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "serialcommander",
    version = "0.0.1",
    author = "Ben Newhouse",
    author_email = "newhouseb@gmail.com",
    description = ("A toolkit for building minimal serial/UART CLIs in nmigen"),
    license = "Apache 2.0",
    keywords = "nmigen uart serial",
    packages=['serialcommander'],
    long_description=read('README.md'),
)