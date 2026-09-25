# Layer 2 dashboard visual prototype

Throwaway inspiration only. The question is: **what information hierarchy should
the inspection workspace use as it grows beyond topology into fields, metrics, UV,
and traces?**

Six structurally different variants live on one static route and switch with
`?variant=A` through `?variant=F`. None is a proposed contract.

Run from the repository root:

```sh
python3 -m http.server 8765 --directory components/inspection_workspace/frontend/prototypes/layer2-dashboard
```

Then open `http://127.0.0.1:8765/?variant=A`. Delete the prototype after its useful
ideas have been recorded in a durable design note.

`report-guided.html` is a separate, desktop-proportioned translation of the dense
dashboard composition in the integrated architecture report.
