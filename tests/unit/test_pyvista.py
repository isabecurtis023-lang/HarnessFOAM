import sys
import pyvista as pv

print("Starting pyvista test...")
try:
    with open("case.foam", "w") as f: pass
    reader = pv.OpenFOAMReader("case.foam")
    print("Reader created.")
    # Assuming no data exists in this dir, this might fail or be empty
    reader.set_active_time_value(0.0) 
    mesh = reader.read()
    print("Mesh read:", mesh)
    plotter = pv.Plotter(off_screen=True)
    plotter.add_mesh(mesh)
    plotter.screenshot('visualization.png')
    print("Screenshot saved.")
except Exception as e:
    print("Error:", e)
