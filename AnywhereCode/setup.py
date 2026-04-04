from setuptools import setup, find_packages

setup(
    name="anyplace",
    version="0.1.0",
    description="Code anywhere - AI-powered project generation for mobile and desktop",
    author="AnywhereCode Team",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "litellm>=1.0.0",
        "click>=8.0.0",
        "pyyaml>=6.0",
        "rich>=13.0.0",
        "requests>=2.28.0",
    ],
    entry_points={
        "console_scripts": [
            "anyplace=anyplace.cli.main:cli",
        ],
    },
    include_package_data=True,
    package_data={
        "anyplace": ["templates/**/*"],
    },
)
