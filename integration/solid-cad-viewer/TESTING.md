# Validation report

Validation performed in the authoring environment on 2026-09-19:

- Node v22.16.0 and TypeScript 5.8.3.
- `node scripts/test-core.mjs`: **47 passed, 0 failed**. This first performs strict TypeScript compilation of the dependency-free model, math, selection, NPZ/wire/source modules, server handler and synthetic fixture.
- TypeScript syntax parsing of **23 `.ts`/`.tsx` files: 0 syntax diagnostics**. This includes renderer/UI code and Nitro examples, but does not resolve or check third-party APIs.
- **59 local import references** resolved to existing source files.
- A real `numpy.savez_compressed` file was generated and decoded successfully, including NumPy's local ZIP64 headers.

Tests cover numeric buffers and indexing; units/UV preservation; affine composition; deep hierarchies; revision-scoped selection; JSON interchange; NPY versions, byte order and Fortran layout; archive CRC/size constraints and cancellation; HTTP limits; injected STEP adapter validation; and server authorization/revision handling.

The test using a `StepTessellator` uses a mock. It does not parse a STEP file, and is not evidence of a working CAD-kernel binding.

## Not validated here

Dependency downloads were blocked by DNS/network access in this environment. As a result the following were **not run**:

- Full dependency-aware application typecheck or Vite build.
- Biome lint/format checks.
- Solid hydration, bundling and Web Worker execution in a browser.
- WebGL rendering/picking/camera/context-loss acceptance tests.
- Running the Nitro wrapper in a Nitro application.
- Any native STEP import/tessellation, exact geometry or engineering validation.

The implementation should undergo those checks in the target project before release. No lockfile is supplied because dependencies could not be installed and resolved here.

## Reproduce and extend

```sh
bun install
bun run test
node scripts/check-syntax.mjs
bun run typecheck
bun run format
bun run check
bun run build
bun run dev
```

Browser acceptance should exercise both projections and narrow viewports; Y/Z-up presets; repeated-asset instances; face/triangle/edge picks; selection after revision replacement; hierarchy visibility; clipping; large-coordinate fixtures; worker load/cancel/unmount; repeated mount/dispose; initially hidden containers; WebGL context loss; and server-rendered routes without browser globals.

Inspect GPU memory over repeated load/unload cycles. Benchmark real target meshes and retain original topology/index mappings when introducing acceleration or LOD.
