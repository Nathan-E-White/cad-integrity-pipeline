// Standalone native-stage timing. Build command is in IMPLEMENTATION.md.
#include "surface_preparation.hpp"
#include <algorithm>
#include <chrono>
#include <iostream>
#include <map>
#include <numeric>

using namespace cad::surface;
template <class F> double timed(F &&f) {
  const auto start = std::chrono::steady_clock::now();
  f();
  return std::chrono::duration<double, std::milli>(
             std::chrono::steady_clock::now() - start)
      .count();
}
double median(std::vector<double> values) {
  std::sort(values.begin(), values.end());
  return values[values.size() / 2];
}
int main() {
  constexpr Id n = 25;
  cad::simplicial::PolygonalInput input;
  std::vector<Id> selection;
  std::vector<UV> uv;
  for (Id y = 0; y < n; ++y)
    for (Id x = 0; x < n; ++x) {
      input.vertices.push_back(
          {static_cast<double>(x), static_cast<double>(y), 0});
      uv.push_back({static_cast<double>(x), static_cast<double>(y)});
    }
  std::map<std::pair<Id, Id>, Id> edges;
  input.face_offsets = {0};
  for (Id y = 0; y < n - 1; ++y)
    for (Id x = 0; x < n - 1; ++x) {
      std::array<Id, 4> face{y * n + x, y * n + x + 1, (y + 1) * n + x + 1,
                             (y + 1) * n + x};
      selection.push_back(static_cast<Id>(selection.size()));
      for (int k = 0; k < 4; ++k) {
        auto a = face[k], b = face[(k + 1) % 4];
        const auto key = std::minmax(a, b);
        auto [it, inserted] = edges.emplace(key, static_cast<Id>(edges.size()));
        if (inserted)
          input.edges.push_back({key.first, key.second});
        input.face_coedges.push_back((a < b ? 1 : -1) * (it->second + 1));
      }
      input.face_offsets.push_back(static_cast<Id>(input.face_coedges.size()));
    }
  auto surface = prepare({input, selection, {}, {}});
  if (!surface)
    return 1;
  std::vector<double> copying, preparation, assembly, qualification, uvcopy;
  for (int i = 0; i < 7; ++i) {
    PreparationRequest request;
    copying.push_back(timed([&] { request = {input, selection, {}, {}}; }));
    preparation.push_back(
        timed([&] { surface = prepare(std::move(request)); }));
    if (!surface)
      return 2;
    assembly.push_back(timed([&] {
      if (!assemble(*surface))
        std::abort();
    }));
    std::vector<UV> coordinates;
    uvcopy.push_back(timed([&] { coordinates = uv; }));
    qualification.push_back(timed([&] {
      if (!qualify_chart(*surface, std::move(coordinates)))
        std::abort();
    }));
  }
  std::cout << "{\n  \"owned_polygonal_input_copy_ms\": " << median(copying)
            << ",\n  \"native_prepare_excluding_input_copy_ms\": "
            << median(preparation)
            << ",\n  \"native_assembly_ms\": " << median(assembly)
            << ",\n  \"owned_uv_copy_ms\": " << median(uvcopy)
            << ",\n  \"native_chart_qualification_excluding_uv_copy_ms\": "
            << median(qualification) << "\n}\n";
}
