"""CAD Integrity Lab: a research work sample, not an engineering certification service."""
from .algebra import HomologyEngine, IntegralHomologyEngine
from .models import PolyhedralBRep, TriangleMesh
from .pipeline import RepairPipeline, RepairPolicy
from .repair import WeldPolicy
from .simplicial import (
           FilteredSimplicialComplex,
           PersistentHomologyEngine,
           Simplex,
           SimplicialComplex,
)
from .topology import BRepHomologyStitchAnalyzer, analyze_mesh

__version__ = "0.1.0"
__all__ = ["BRepHomologyStitchAnalyzer", "FilteredSimplicialComplex", "HomologyEngine",
           "IntegralHomologyEngine", "PersistentHomologyEngine", "PolyhedralBRep",
           "RepairPipeline", "RepairPolicy", "Simplex", "SimplicialComplex", "TriangleMesh",
           "WeldPolicy", "analyze_mesh"]
