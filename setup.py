from setuptools import setup, find_namespace_packages

setup(
    name="uwb-localization-mesh",
    version="0.1.0",
    packages=find_namespace_packages(include=["packages.*"]),
    package_dir={"": "."},
    install_requires=[
        "numpy>=1.24.0",
        "scipy>=1.10.0",
        "paho-mqtt>=1.6.0",
    ],
    python_requires=">=3.8",
)
