# HarnessFOAM 🌊

<div align="center">

**An End‑to‑End Composable Multi‑Agent Framework for Automating CFD Simulation in OpenFOAM**

![Architecture Diagram](assets/harnessfoam_architecture.jpg)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org) 
[![OpenFOAM](https://img.shields.io/badge/OpenFOAM-Compatible-darkgreen)](https://openfoam.org/) 
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

---

## 🚀 Overview

Computational Fluid Dynamics (CFD) is critical to modern engineering, but the steep learning curve, complex mesh generation, and intricate text-based solver setup in OpenFOAM make it highly labor-intensive. 

**HarnessFOAM** solves this by introducing a modular, composable multi-agent framework built on **LangGraph**. It completely automates the entire end-to-end CFD lifecycle from a single natural-language request (e.g., *"Simulate incompressible flow over a circular cylinder at 2 m/s"*). 

The platform offers a premium real-time Web User Interface, automatic environment provisioning (WSL/Docker/Native), a multi-agent orchestration pipeline, and automated visualization post-processing.

---

## 🖥️ Web User Interface

HarnessFOAM includes a state-of-the-art, zero-dependency HTML/CSS/JS frontend served by a FastAPI backend:

![HarnessFOAM Web UI](assets/web_ui_screenshot.png)

* **Interactive File Explorer** – Instant visualization of the generated folder hierarchy (`0/`, `constant/`, `system/`) and live configuration previews.
* **Console Width Auto-Resize** – Seamless layout adjustment when toggling sidebars or console views using smooth CSS transitions.
* **Real-time API Settings** – Live synchronization of provider parameters (`OPENAI_API_BASE`, `OPENAI_API_KEY`) and dynamic model list fetching.
* **Real-Time Agent Feed** – Interactive logs streaming every step taken by the 6 reasoning agents as the workflow progresses.

---

## 🔄 Composable Multi-Agent Workflow

The system is coordinated via a LangGraph state graph that passes a shared `SimulationState` context dictionary among specialized agents:

```mermaid
graph TD
    A[User Requirement] --> B[Architect Agent]
    B --> C[Meshing Agent]
    C --> D[Input Writer Agent]
    D --> E[Runner Agent]
    E --> F{Success/Failure?}
    F -- Failure & Attempts < Max --> G[Reviewer Agent]
    G --> D
    F -- Failure & Max Reached --> H[End Node]
    F -- Success --> I[Visualizer Agent]
    I --> H
```

1. **State Propagation** – A unified `llm_kwargs` dict is sent across all agents, ensuring runtime model overrides (e.g. `gpt-4o`, `claude-3-5-sonnet`, `gemini-2.5-pro`, `deepseek-v4-flash`, `minimax-m27`, `qwen3.5`) are consistently respected.
2. **Error Feedback Loops** – If a simulation run crashes, the environment logs are routed to the **Reviewer**, which writes suggestions, updates files, and commands the **Input Writer** to recompile config files.

---

## 🤖 Deep-Dive: The 6 AI Agents

Every agent inside HarnessFOAM operates with distinct inputs, toolboxes, and pydantic structured formats:

### 1. Architect Agent (`architect.py`)
* **Role**: Translates user requirements into a file generation plan.
* **Output**: A structured list of target files and directories (e.g. `system/blockMeshDict`, `constant/transportProperties`, `0/U`).
* **Fallback**: Generates a standard set of incompressible Navier-Stokes solver configurations if the LLM fails.

### 2. Meshing Agent (`meshing.py`)
* **Role**: Analyzes spatial layout requirements to choose the most suitable mesh strategy.
* **Logic**: Detects if native `blockMeshDict` is sufficient or if complex geometries (e.g., airfoils, cylinders) require custom `gmsh` scripts.
* **Execution**: Dynamically compiles a Python `gmsh` script, executes it, and converts the mesh output into OpenFOAM format.

### 3. Input Writer Agent (`input_writer.py`)
* **Role**: Generates raw, valid OpenFOAM dictionaries without formatting fences.
* **Technology**: Uses a custom **streaming API connection** to handle long generation windows without timing out, combined with aggressive regex filters to clean output and strip `<think>` tags.
* **Robustness**: Implements connection/read retries with exponential backoffs to deal with unstable API endpoints.

### 4. Runner Agent (`runner.py`)
* **Role**: Formulates execution command pipelines.
* **Output**: Writes the standard `./Allrun` executable. For cloud/HPC environments, it automatically outputs optimized Slurm allocation scripts specifying node bounds and parallel processing commands.
* **Execution**: Manages shell process execution inside native Windows, WSL, or Docker environments.

### 5. Reviewer Agent (`reviewer.py`)
* **Role**: Analyzes build and runtime logs to repair failing simulations.
* **Mechanism**: Leverages Large Vision-Language Models (VLMs) to visually review rendered post-processing plots. If flow physics show anomalies (e.g., flow divergence, incorrect boundary reflection), it overrides boundary conditions or decreases step intervals.

### 6. Visualizer Agent (`visualizer.py`)
* **Role**: Automated post-processing plotting.
* **Execution**: Compiles python scripts using `PyVista` to load OpenFOAM VTK results, applies contour filters, renders velocity/pressure fields, saves the output to a `.png` file, and streams it back to the client interface.

---

## 🔧 Installation & Quick Start

### Prerequisites
* **Python**: `3.10` or above.
* **OpenFOAM**: Installed locally or inside WSL. Alternatively, a running Docker daemon. (If missing, the UI installer can automatically provision OpenFOAM inside WSL).

### Setup
```bash
# 1. Clone the project repository
git clone https://github.com/isabecurtis023-lang/HarnessFOAM.git
cd HarnessFOAM

# 2. Install package in editable mode along with dev options
pip install -e .[dev]

# 3. Create and configure your environment variables
cp .env.example .env
```

Ensure your `.env` contains valid OpenAI or compatible (such as CSTCloud) credentials:
```env
OPENAI_API_KEY=your_api_key
OPENAI_API_BASE=your_base_url
LLM_MODEL=your_model_name
```

### Launching serves
```bash
# Serves the Web Interface on localhost:8000
harnessfoam serve --host 127.0.0.1 --port 8000
```
Open your browser and navigate to `http://127.0.0.1:8000`.

---

## 🧪 Benchmarks & Validations

HarnessFOAM includes tests and preconfigured scenarios validating model outputs across 15 diverse CFD use cases:

* **Heat Transfer** – Natural convection in cavities & heated flat plates using `buoyantBoussinesqPimpleFoam`.
* **Multiphase Flows** – Classical dam break dynamic surface tracking using `interFoam`.
* **Combustion** – Counter-flow diffusion flames with thermal kinetics using `reactingFoam`.
* **Shock Dynamics** – Sod shock tubes & forward-facing steps using `rhoCentralFoam`.
* **Aerodynamics** – 3D automobile drag coefficient calculations using `simpleFoam`.

Run the automated validation test suite:
```bash
pytest tests/
```

---

## 🌟 Future Roadmap

We are continuously advancing HarnessFOAM to make CFD engineering fully autonomous. Here are our core milestones:

* **Decentralized Peer-to-Peer Scientific Computing (De-Sci)** – Establish a blockchain-backed distributed compute framework, allowing scientific researchers to scale Runner agent workloads across a global peer-to-peer network of idle GPU/HPC nodes.
* **Generative Physical Diffusion (4D Flow-Diffusion)** – Move beyond traditional numerical discretization by integrating latent physical diffusion models (Flow-Diffusion/Flow-Sora) capable of synthesizing physically consistent 4D flow fields (3D space + time) in milliseconds under arbitrary boundary conditions.
* **Closed-Loop Vision-Language-Action (VLA) Aero-Design** – Create a unified VLA aerodynamic design agent capable of orchestrating the entire lifecycle from natural language to 3D CAD modeling, gmsh meshing, local simulation, and automated physical verification via robotic 3D-printing and wind-tunnel testing.
* **Quantum-Accelerated CFD (Q-CFD)** – Develop hybrid quantum-classical solvers for the Runner agent, leveraging variational quantum algorithms (VQE) and the HHL algorithm to solve dense sparse-linear Navier-Stokes matrices on QPUs.
* **Self-Evolutionary Physics Autopilot** – Implement self-play reinforcement learning loops where agents monitor solver residuals, autonomously write and compile custom local numerical schemes, generate novel turbulence closures, and discover empirical transport laws without human heuristics.
* **HPC SSH Integration & Remote Dispatch** – Enable full compatibility with remote supercomputing clusters, allowing HarnessFOAM to establish secure SSH connections to HPC systems, automatically dispatch and transfer simulation cases, generate and submit Slurm job scripts, and stream real-time solver logs back to the local Web UI.

---

## 📚 Related Papers

If you are interested in LLM-driven CFD automation, check out these related publications:

* **MetaOpenFOAM** – *MetaOpenFOAM: an LLM-based multi-agent framework for CFD* (Chen et al., [arXiv:2407.21320](https://arxiv.org/abs/2407.21320), Jul 2024)
* **MetaOpenFOAM 2.0** – *MetaOpenFOAM 2.0: Large Language Model Driven Chain of Thought for Automating CFD Simulation and Post-Processing* (Chen et al., [arXiv:2502.00498](https://arxiv.org/abs/2502.00498), Feb 2025)
* **OptMetaOpenFOAM** – *OptMetaOpenFOAM: Large Language Model Driven Chain of Thought for Sensitivity Analysis and Parameter Optimization based on CFD* (Chen et al., [arXiv:2503.01273](https://arxiv.org/abs/2503.01273), Mar 2025)
* **IteraSim RAG** – *IteraSim RAG: A Multi-Stage Retrieval-Augmented Agentic Back-End for OpenFOAM-Based Computational Fluid Dynamics* (Kumar, [arXiv:2607.20346](https://arxiv.org/abs/2607.20346), Jul 2026)
* **AutoFOAM** – *AutoFOAM: The Self-Refining Autonomous OpenFOAM Agent* (Neelan et al., [arXiv:2608.00003](https://arxiv.org/abs/2608.00003), May 2026)
* **PhyNiKCE** – *PhyNiKCE: A Neurosymbolic Agentic Framework for Autonomous Computational Fluid Dynamics* (Fan et al., [arXiv:2602.11666](https://arxiv.org/abs/2602.11666), Feb 2026)
* **TurboAgent** – *TurboAgent: An LLM-Driven Autonomous Multi-Agent Framework for Turbomachinery Aerodynamic Design* (Du et al., [arXiv:2604.06747](https://arxiv.org/abs/2604.06747), Apr 2026)
* **FlamePilot** – *Towards LLM-enabled autonomous combustion research: A literature-aware agent for self-corrective modeling workflows* (Xiao et al., [arXiv:2601.01357](https://arxiv.org/abs/2601.01357), Jan 2026)
* **ChatCFD** – *ChatCFD: An LLM-Driven Agent for End-to-End CFD Automation with Structured Knowledge and Reasoning* (Fan et al., [arXiv:2506.02019](https://arxiv.org/abs/2506.02019), May 2025)
* **Foam-Agent** – *Foam-Agent: A Large Language Model-Based Multi-Agent Framework for Automating Computational Fluid Dynamics Workflows* (Yue et al., [arXiv:2505.04997](https://arxiv.org/abs/2505.04997), May 2025)
* **AutoCFD / NL2FOAM** – *Fine-tuning a Large Language Model for Automating Computational Fluid Dynamics Simulations* (Dong et al., [arXiv:2504.09602](https://arxiv.org/abs/2504.09602), Apr 2025)
* **CFDLLMBench** – *CFDLLMBench: A Benchmark Suite for Evaluating Large Language Models in Computational Fluid Dynamics* (Somasekharan et al., [arXiv:2509.20374](https://arxiv.org/abs/2509.20374), Sep 2025)
* **CFD-copilot** – *CFD-copilot: leveraging domain-adapted large language model and model context protocol to enhance simulation automation* (Dong et al., [arXiv:2512.07917](https://arxiv.org/abs/2512.07917), Dec 2025)

*Note: If the above literature has omitted your important work, please do not hesitate to contact me.*

---

<div align="center">
<i>Built with ❤️ by Isabel Curtis and the Open‑Source AI4Science Community.</i><br>
<i>Empowering the next generation of automated engineering.</i>
</div>
