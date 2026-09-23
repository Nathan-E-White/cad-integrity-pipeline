#pragma once
// Private shared storage; constructors remain behind admitted operations.
#include "surface_preparation.hpp"
namespace cad::surface {
struct SurfaceStorage {
  std::vector<Point> vertices;
  std::vector<Triangle> triangles, triangle_edges;
  std::vector<Id> source_vertices, selected_faces, triangle_faces,
      boundary_vertices;
  Id source_face_count = 0;
  bool native_faces = false;
  simplicial::LengthUnit unit;
  Usage usage;
};
} // namespace cad::surface
