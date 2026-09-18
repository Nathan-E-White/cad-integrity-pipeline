from STLReader import STLReader, PointCloudGeometryEstimator
from NURBSCoreEngine import RANSACPrimitiveClassifier, CADGeometryCardEngine, STEPGeometryExportEngine

# 1. Parse external STL geometry asset or raw point array
points, face_normals, faces = STLReader.load_stl("noisy_scan_input.stl")

# 2. Extract analytical curvature metrics from unorganized points
estimator = PointCloudGeometryEstimator(k_neighbors=15)
normals, curvatures = estimator.estimate_features(points)

# 3. Stream smooth geometry variables directly into downstream RANSAC/STEP engines
segmenter = RANSACPrimitiveClassifier(spatial_tol=0.01, normal_tol_deg=3.0)
primitives = segmenter.segment_primitives(points, normals, curvatures)

card_engine = CADGeometryCardEngine(precision=4)
geometry_card = card_engine.compute_cards(primitives, points)

step_engine = STEPGeometryExportEngine(start_id=100)
step_file_content = step_engine.export(geometry_card)
