import gmsh
import math
import sys

gmsh.initialize()
gmsh.model.add("flow_over_cylinder")

# Parameters
D = 1.0  # cylinder diameter
L = 20.0  # domain length
H = 10.0  # domain height
lc = 0.025  # mesh size near cylinder
lc_far = 0.5  # mesh size far field

# Create rectangle domain (x from -L/2 to L/2, y from -H/2 to H/2)
# Use points and lines for rectangle
p1 = gmsh.model.geo.addPoint(-L/2, -H/2, 0, lc_far)
p2 = gmsh.model.geo.addPoint(L/2, -H/2, 0, lc_far)
p3 = gmsh.model.geo.addPoint(L/2, H/2, 0, lc_far)
p4 = gmsh.model.geo.addPoint(-L/2, H/2, 0, lc_far)

l1 = gmsh.model.geo.addLine(p1, p2)
l2 = gmsh.model.geo.addLine(p2, p3)
l3 = gmsh.model.geo.addLine(p3, p4)
l4 = gmsh.model.geo.addLine(p4, p1)

# Create cylinder (circle) centered at origin
c = gmsh.model.geo.addPoint(0, 0, 0, lc)
# Use circle with center and two points on circle
# Points on circle at (D/2,0) and (0,D/2)
pc1 = gmsh.model.geo.addPoint(D/2, 0, 0, lc)
pc2 = gmsh.model.geo.addPoint(0, D/2, 0, lc)
circle = gmsh.model.geo.addCircle(c, pc1, pc2)

# Create surface for rectangle with hole
# First create curve loop for rectangle
cl_rect = gmsh.model.geo.addCurveLoop([l1, l2, l3, l4])
# Curve loop for circle (must be closed)
cl_circ = gmsh.model.geo.addCurveLoop([circle])
# Add surface with hole
s = gmsh.model.geo.addPlaneSurface([cl_rect, cl_circ])

gmsh.model.geo.synchronize()

# Add physical groups
# Inlet (left boundary)
gmsh.model.addPhysicalGroup(1, [l4], 1, "inlet")
# Outlet (right boundary)
gmsh.model.addPhysicalGroup(1, [l2], 2, "outlet")
# Top and bottom walls
# Note: l1 is bottom, l3 is top
gmsh.model.addPhysicalGroup(1, [l1], 3, "bottom")
gmsh.model.addPhysicalGroup(1, [l3], 4, "top")
# Cylinder wall
gmsh.model.addPhysicalGroup(1, [circle], 959, "cylinder")
# Fluid domain
gmsh.model.addPhysicalGroup(2, [s], 5, "fluid")

# Set mesh size field for refinement near cylinder
# Use distance field
field = gmsh.model.mesh.field.add("Distance")
gmsh.model.mesh.field.setNumbers(field, "CurvesList", [circle])
gmsh.model.mesh.field.setNumber(field, "Sampling", 100)

# Threshold field for mesh size
field2 = gmsh.model.mesh.field.add("Threshold")
gmsh.model.mesh.field.setNumber(field2, "InField", field)
gmsh.model.mesh.field.setNumber(field2, "SizeMin", lc)
gmsh.model.mesh.field.setNumber(field2, "SizeMax", lc_far)
gmsh.model.mesh.field.setNumber(field2, "DistMin", 0.5)
gmsh.model.mesh.field.setNumber(field2, "DistMax", 5.0)

gmsh.model.mesh.field.setAsBackgroundMesh(field2)

# Generate 2D mesh
gmsh.model.mesh.generate(2)

# Save mesh
gmsh.write("mesh.msh")

gmsh.finalize()
