#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path

from setuptools import find_packages, setup

from src.wireviz import APP_URL, CMD_NAME, __version__

# The description published with the package is the upstream README (docs/README.md is the docs index)
README_PATH = Path(__file__).parent / "docs" / "upstream" / "README.upstream.md"

setup(
    name=CMD_NAME,
    version=__version__,
    author="Daniel Rojas",
    # author_email='',
    description="Easily document cables and wiring harnesses",
    long_description=README_PATH.read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    python_requires=">=3.14",
    install_requires=[
        "click",
        "pyyaml",
        "pillow",
        "graphviz",
    ],
    license="GPLv3",
    keywords="cable connector hardware harness wiring wiring-diagram wiring-harness",
    url=APP_URL,
    package_dir={"": "src"},
    package_data={CMD_NAME: ["templates/*.html"]},
    packages=find_packages("src"),
    entry_points={
        "console_scripts": [
            "wireviz=wireviz.wv_cli:wireviz",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.14",
        "Topic :: Utilities",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
    ],
)
