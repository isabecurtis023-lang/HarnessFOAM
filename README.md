# HarnessFOAM 🌊

An End-to-End Composable Multi-Agent Framework for Automating CFD Simulation in OpenFOAM. This original project reimagines computational fluid dynamics through the lens of modern AI, acting as a highly capable co-pilot for engineers and researchers.

## Overview
HarnessFOAM completely automates the tedious, error-prone workflow of OpenFOAM. From a single natural language prompt, the framework autonomously handles:
- **Architecture Planning**: Decomposing physical requirements into directory structures.
- **Mesh Generation**: Calling native blockMesh/snappyHexMesh or `Gmsh` dynamically.
- **Input Writing**: Contextually generating interdependent files (`0/`, `constant/`, `system/`).
- **Execution & HPC**: Automatically generating Slurm scripts and running simulations on clusters (e.g. Perlmutter) or locally.
- **Iterative Review**: Self-healing loops that parse error logs and apply targeted fixes.
- **Visualization**: Automating PyVista/Paraview rendering.

## Architecture
This project is built using:
- **LangGraph**: For stateful, multi-agent orchestration.
- **MCP (Model Context Protocol)**: Decoupling CFD capabilities into standardized, modular tools, making it compatible with generic LLM assistants like Claude Desktop or Cursor.
- **FAISS**: Hierarchical RAG indices for high-fidelity configuration generation based on official OpenFOAM tutorials.

## Usage
Install the dependencies:
```bash
pip install -e .
```
Run tests (includes comprehensive benchmark simulations):
```bash
pytest -v
```

This project aims to democratize complex scientific computing and drastically lower the barrier to entry for CFD analysis.
