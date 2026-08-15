from setuptools import setup, find_packages

setup(
    name="harnessfoam",
    version="0.1.0",
    description="An End-to-End Composable Multi-Agent Framework for Automating CFD Simulation in OpenFOAM",
    author="Isabel Curtis",
    packages=find_packages(),
    install_requires=[
        "langgraph",
        "langchain-openai",
        "pydantic",
        "rich",
        "fastapi",
        "uvicorn",
        "websockets"
    ],
    entry_points={
        "console_scripts": [
            "harnessfoam=harnessfoam.cli:main",
        ],
    },
)
