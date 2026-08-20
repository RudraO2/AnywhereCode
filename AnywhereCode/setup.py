"""Packaging for Anywhere Code."""

from pathlib import Path

from setuptools import find_packages, setup

HERE = Path(__file__).parent
# The README lives at the repository root (it is the GitHub landing page);
# fall back to a local copy so an sdist built from this directory still has one.
README = ""
for candidate in (HERE / "README.md", HERE.parent / "README.md"):
    if candidate.exists():
        README = candidate.read_text(encoding="utf-8")
        break

setup(
    name="anywhere-code",
    version="2.0.0",
    description="Build and ship real projects from your phone. An AI coding CLI for small screens.",
    long_description=README,
    long_description_content_type="text/markdown",
    author="Anywhere Code",
    url="https://github.com/RudraO2/Classic-Snake-Made-using-Qwen-",
    packages=find_packages(exclude=("tests", "tests.*")),
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.28.0",
        "click>=8.0.0",
        "pyyaml>=6.0",
        "rich>=13.0.0",
    ],
    extras_require={
        "mcp": ["mcp>=1.0.0"],
        "dev": ["pytest>=7.0.0"],
    },
    entry_points={
        "console_scripts": [
            # The name we want people to type…
            "anywhere=anyplace.cli.main:main",
            # …and the one from v1, so existing installs keep working.
            "anyplace=anyplace.cli.main:main",
        ],
    },
    include_package_data=True,
    package_data={"anyplace": ["templates/**/*", "templates/*/*.json"]},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Operating System :: Android",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Topic :: Software Development :: Code Generators",
    ],
    keywords="ai cli termux android mobile codegen scaffolding",
)
