import os

from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Sewing
from OCC.Core.BRepClass3d import BRepClass3d_SolidClassifier
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_SHELL
from OCC.Core.TopoDS import topods



def reconstruct_brep_topology(step_path, tolerance=1e-3):
    """
    Reads a malformed STEP file, isolates disconnected faces,
    and sews them into a valid manifold B-rep topology.
    """
    if not os.path.exists(step_path):
        raise FileNotFoundError(f"STEP file not found: {step_path}")

    # 1. Load the raw geometric shapes from STEP
    reader = STEPControl_Reader()
    status = reader.ReadFile(step_path)

    if status != 1:
        raise IOError("Error: Unable to read the STEP file format.")

    reader.TransferRoots()
    raw_shape = reader.OneShape()

    # Count input faces to track structural integrity
    face_explorer = TopExp_Explorer(raw_shape, TopAbs_FACE)
    initial_face_count = 0
    while face_explorer.More():
        initial_face_count += 1
        face_explorer.Next()

    print(f"--- Loaded geometry containing {initial_face_count} raw faces ---")

    # 2. Configure the topological sewing engine
    # This engine replaces duplicate geometric edges with single shared topological edges
    sewing_engine = BRepBuilderAPI_Sewing(tolerance)
    sewing_engine.SetMaxTolerance(tolerance * 10)
    sewing_engine.Add(raw_shape)
    sewing_engine.Perform()

    stitched_shape = sewing_engine.SewedShape()

    # 3. Structural Diagnostics Post-Sewing
    num_free_edges = sewing_engine.NbFreeEdges()
    num_cont_edges = sewing_engine.NbContendedEdges()  # Multiple manifold errors
    num_deg_edges = sewing_engine.NbDegeneratedEdges()

    print(f"Sewing Diagnostics:")
    print(f"  - Remaining Free Edges: {num_free_edges} (Should be 0 if fully closed)")
    print(f"  - Non-Manifold Contended Edges: {num_cont_edges}")
    print(f"  - Degenerated Edges: {num_deg_edges}")

    # 4. Extract shells and attempt solidification
    shell_explorer = TopExp_Explorer(stitched_shape, TopAbs_SHELL)
    valid_solids = []

    while shell_explorer.More():
        shell = topods.Shell(shell_explorer.Current())

        # Verify if the shell represents a closed volume using a 3D classifier
        classifier = BRepClass3d_SolidClassifier(shell)
        classifier.PerformInfinitePoint(tolerance)

        # If the infinite point is OUTSIDE, the shell completely encloses space
        if classifier.State() == 3:  # TopAbs_OUT
            from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeSolid
            solid_builder = BRepBuilderAPI_MakeSolid(shell)
            if solid_builder.IsDone():
                valid_solids.append(solid_builder.Solid())
        shell_explorer.Next()
    print(f"\nReconstruction completed. Successfully built {len(valid_solids)} solid(s).")
    return valid_solids

# Example Execution Context:
# solids = reconstruct_brep_topology("malformed_model.step", tolerance=1e-2)