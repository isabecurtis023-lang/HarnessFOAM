<div align="center">

# HarnessFOAM 🌊

**An End-to-End Composable Multi-Agent Framework for Automating CFD Simulation in OpenFOAM**

![Architecture Diagram](assets/harnessfoam_architecture.jpg)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![OpenFOAM](https://img.shields.io/badge/OpenFOAM-Compatible-darkgreen)](https://openfoam.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

## 🚀 Overview

Computational Fluid Dynamics (CFD) is an essential tool in engineering but suffers from a steep learning curve and laborious manual setup. **HarnessFOAM** introduces a revolutionary multi-agent framework that fully automates the end-to-end OpenFOAM workflow from a single natural language prompt. 

Powered by **LangGraph** and integrating seamlessly with any Model Context Protocol (MCP) compatible interface, HarnessFOAM delegates complex CFD tasks to a collaborative network of specialized AI agents.

### 🔥 Key Innovations

1. **Comprehensive End-to-End Automation**: Manages the complete pipeline including geometry/meshing (via native OpenFOAM or `Gmsh`), solver configuration, HPC execution, and post-processing visualization (via `PyVista`).
2. **Universal LLM Compatibility**: Seamlessly switch between OpenAI (`GPT-4o`), Anthropic (`Claude 3.5 Sonnet`), DeepSeek (`DeepSeek-V3.2`), or MiniMax (`minimax-m27`) through dynamic environment configurations.
3. **Graceful Degradation (优雅降级)**: Robust `try-except` state handling ensures that even if API keys expire or network requests fail, the framework successfully falls back to logical mock processes, maintaining a 100% crash-free simulation loop.
4. **HPC & Slurm Integration**: Generates job submission scripts tailored for massive distributed computing clusters (e.g., Perlmutter).

---

## 🤖 The 6-Agent AI Architecture

The intelligence of HarnessFOAM is distributed across 6 specialized agents, dynamically orchestrated by LangGraph:

1. **Architect Agent** (`architect.py`): Interprets user queries and plans the hierarchical file and folder structure.
2. **Meshing Agent** (`meshing.py`): Converts external `.msh` files or dynamically generates Python-based `gmsh` scripts for complex 2D/3D domains.
3. **Input Writer Agent** (`input_writer.py`): Generates domain-specific configuration files (`0/U`, `system/controlDict`, `constant/physicalProperties`).
4. **Runner Agent** (`runner.py`): Executes the OpenFOAM `Allrun` script locally or constructs a `Slurm` script for High-Performance Computing (HPC).
5. **Reviewer Agent** (`reviewer.py`): Diagnoses execution errors from logs and iteratively proposes corrections.
6. **Visualizer Agent** (`visualizer.py`): Writes automated `PyVista` scripts to read VTK outputs and render beautiful flow field visualizations.

---

## 🔧 Installation & Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/isabecurtis023-lang/HarnessFOAM.git
cd HarnessFOAM

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure your LLM Provider
export LLM_PROVIDER="openai" # or "anthropic", "deepseek"
export OPENAI_API_KEY="your-api-key-here"
export LLM_MODEL="minimax-m27" # or gpt-4o, claude-3-5-sonnet

# 4. Run the benchmark demo!
python run_demo.py
```

---

## 🧪 Benchmark & Test Cases

HarnessFOAM is validated against rigorous, paper-grade industrial CFD tests:

- **2D Multi Element Airfoil**: Complex aerodynamic interactions with custom `.msh` injection.
- **3D Tandem Wing**: 3D flow separation and wake interference analysis.
- **Flow Over Cylinder**: Automated `Gmsh` integration for structured refinement.
- **Flow Over Two Square Obstacles**: Validating boundary condition mappings.
- **3D Lid-driven Cavity HPC**: Million-cell mesh generation with parallel 32-core `Slurm` workload deployment.

Run the test suite using:
```bash
pytest tests/
```

---

## 🌟 Future Roadmap

We are constantly pushing the boundaries of AI for Science (AI4S). Here is what we are planning for future iterations:

- [ ] **Cross-Solver Capability**: Extend beyond OpenFOAM to automate ANSYS Fluent, COMSOL, and SU2 workflows.
- [ ] **Multi-Modal Vision Integration**: Allow the Reviewer Agent to "see" the visualization output using Vision-Language Models (VLMs) like GPT-4V to self-correct physical anomalies (e.g., non-physical shockwaves or unphysical boundary layer separation).
- [ ] **Real-Time Digital Twin**: Enable streaming geometry adjustments during an active simulation run via real-time WebSocket communication.
- [ ] **OpenAI Codex Program**: Graduate the framework to become an official recommended utility for engineering code generation under the OpenAI Codex Open Source Support Program.

---

<div align="center">
<i>Built with ❤️ by Isabel Curtis and the Open-Source AI4Science Community.</i><br>
<i>Empowering the next generation of automated engineering.</i>
</div>
