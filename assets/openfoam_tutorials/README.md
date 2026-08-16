# Vendored OpenFOAM tutorials

This directory contains a curated set of official OpenFOAM tutorial cases used as local retrieval-augmented generation (RAG) context:

- `OpenFOAM-13/legacy/incompressible/icoFoam/cavity`
- `OpenFOAM-13/incompressibleFluid/{cavity,pitzDaily,motorBike}`
- `OpenFOAM-13/incompressibleVoF/damBreak`
- `OpenFOAM-13/fluid/{hotRoom,shockTube}`
- `OpenFOAM-13/mesh/snappyHexMesh/motorBike`

Source: [OpenFOAM/OpenFOAM-13 tutorials](https://github.com/OpenFOAM/OpenFOAM-13/tree/master/tutorials). The upstream `COPYING` file is included. HarnessFOAM indexes dictionary files such as `controlDict`, `blockMeshDict`, `fvSchemes`, `fvSolution`, boundary fields and `Allrun`; it does not execute tutorial scripts automatically.

The bundled corpus and the WSL verification environment are both OpenFOAM 13. Solver names, dictionary syntax and physical models still pass HarnessFOAM preflight, `checkMesh` and the installed solver's runtime checks.
