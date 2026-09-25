# Desktop engineering inspection prototypes

Five throwaway desktop variants answer one question: how should the layer-2
inspection workspace organize geometry, selection, fields, traces, and validation
without consumer-dashboard styling?

Run from the frontend directory:

```sh
python3 -m http.server 8765
```

Open `http://127.0.0.1:8765/prototypes/desktop-engineering/?variant=A` and switch
with the fixed A–E bar. Delete or absorb the prototype after recording a verdict.

Do not open `index.html` directly with a `file://` URL. The prototype uses
root-relative Three.js module paths and must be served from the frontend root.
