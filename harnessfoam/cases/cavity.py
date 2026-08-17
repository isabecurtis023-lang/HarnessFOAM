"""Small valid 2-D icoFoam cavity fallback."""
from typing import Dict

HEADER = "FoamFile\n{{\n    version 2.0;\n    format ascii;\n    class {cls};\n    object {obj};\n}}\n"

def cavity_files() -> Dict[str, str]:
    def h(cls, obj):
        return HEADER.format(cls=cls, obj=obj)
    return {
        "system/blockMeshDict": h("dictionary", "blockMeshDict") + """convertToMeters 1;
vertices ((0 0 0) (0.1 0 0) (0.1 0.1 0) (0 0.1 0) (0 0 0.001) (0.1 0 0.001) (0.1 0.1 0.001) (0 0.1 0.001));
blocks ( hex (0 1 2 3 4 5 6 7) (20 20 1) simpleGrading (1 1 1) );
edges ();
boundary ( movingWall { type wall; faces ((3 7 6 2)); } fixedWalls { type wall; faces ((0 4 5 1) (1 5 6 2) (3 7 4 0)); } frontAndBack { type empty; faces ((0 3 2 1) (4 5 6 7)); } );
mergePatchPairs ();
""",
        "system/controlDict": h("dictionary", "controlDict") + """application icoFoam;
startFrom startTime;
startTime 0;
stopAt endTime;
endTime 0.5;
deltaT 0.001;
writeControl timeStep;
writeInterval 100;
purgeWrite 0;
writeFormat ascii;
writePrecision 6;
writeCompression off;
timeFormat general;
timePrecision 6;
runTimeModifiable yes;
""",
        "system/fvSchemes": h("dictionary", "fvSchemes") + """ddtSchemes { default Euler; }
gradSchemes { default Gauss linear; }
divSchemes { default none; div(phi,U) Gauss linear; div((nuEff*dev2(T(grad(U))))) Gauss linear; }
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes { default corrected; }
wallDist { method meshWave; }
""",
        "system/fvSolution": h("dictionary", "fvSolution") + """solvers { p { solver PCG; preconditioner DIC; tolerance 1e-06; relTol 0; } pFinal { $p; relTol 0; } U { solver PBiCG; preconditioner DILU; tolerance 1e-05; relTol 0; } UFinal { $U; relTol 0; } }
PISO { nCorrectors 2; nNonOrthogonalCorrectors 0; pRefCell 0; pRefValue 0; }
""",
        # OpenFOAM 13 uses physicalProperties for icoFoam transport data.
        "constant/physicalProperties": h("dictionary", "physicalProperties") + """viscosityModel constant;
nu 0.01 [m^2/s];
""",
        "0/p": h("volScalarField", "p") + """dimensions [0 2 -2 0 0 0 0];
internalField uniform 0;
boundaryField { movingWall { type zeroGradient; } fixedWalls { type zeroGradient; } frontAndBack { type empty; } }
""",
        "0/U": h("volVectorField", "U") + """dimensions [0 1 -1 0 0 0 0];
internalField uniform (0 0 0);
boundaryField { movingWall { type fixedValue; value uniform (1 0 0); } fixedWalls { type fixedValue; value uniform (0 0 0); } frontAndBack { type empty; } }
""",
    }

def is_cavity_prompt(prompt: str) -> bool:
    text = (prompt or "").lower()
    return any(x in text for x in ("cavity", "lid driven", "lid-driven", "square cavity"))
