from pathlib import Path

from setuptools import setup, find_packages

# The full docs live at the repo root (that is what GitHub renders); the
# copy inside this directory is a pointer. Prefer the root for PyPI.
_here = Path(__file__).parent
long_description = ""
for _candidate in (_here.parent / "README.md", _here / "README.md"):
    if _candidate.exists():
        long_description = _candidate.read_text(encoding="utf-8")
        break

setup(
    name="anyplace",
    version="0.2.0",
    description=(
        "Build and ship real apps from your phone — AI project generation "
        "with cloud APK builds, no laptop required"
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="AnywhereCode Contributors",
    url="https://github.com/RudraO2/AnywhereCode",
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.8",
    # Every runtime dependency is pure Python. Anything needing a Rust or C
    # toolchain fails to build on Termux/aarch64, which would lock out the
    # platform this tool exists for.
    install_requires=[
        "requests>=2.28.0",
        "click>=8.0.0",
        "pyyaml>=6.0",
        "rich>=13.0.0",
        "qrcode>=7.4",
    ],
    extras_require={
        "mcp": ["mcp>=1.0.0"],  # Only needed for `anyplace serve`
    },
    entry_points={
        "console_scripts": [
            "anyplace=anyplace.cli.main:cli",
        ],
    },
    include_package_data=True,
    package_data={
        "anyplace": ["templates/**/*"],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Android",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Code Generators",
    ],
    keywords="ai codegen termux android expo eas mobile cli scaffolding",
)
