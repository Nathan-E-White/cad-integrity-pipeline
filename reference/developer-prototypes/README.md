# Historical motorcycle-graph prototypes

These standalone translation units are preserved as unqualified development
history. They are not product contracts, are excluded from every active CMake
target and Python extension, and must not be linked or used as the canonical
implementation.

The supported pure-quad implementation is `native/quad_tracing.hpp` and
`native/quad_tracing.cpp`, exposed to Python by `cad_integrity.quad`. The
`integration/mesh_healing_extension` bundle is retained separately as delivered;
its `MotorcycleGraphTracer` is also not activated or imported by the product.
