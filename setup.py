# All static metadata lives in pyproject.toml. This shim exists only to declare
# the C extension, because the declarative [[tool.setuptools.ext-modules]] table
# requires setuptools >=74.1 and Python 3.7 installs top out at setuptools 68.
from setuptools import Extension, setup

setup(
    ext_modules=[
        Extension(
            "octoprint_translatemodel._translate",
            sources=["src/translate.cpp"],
        )
    ]
)
