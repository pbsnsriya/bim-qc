# Contributing

Create a focused branch and describe the trigger, expected behavior, actual behavior and validation in a pull request. Application work lives in `ifcqc/`, `server.py` and `web/`; synthetic models and known-answer generators live in `samples/` and `scripts/`.

Install with `python -m pip install -e .`, then run:

```bash
python -m unittest discover -s tests -v
npm ci --prefix web
npm test --prefix web
```

For geometry changes, run the affected analytic reference matrix and inspect the exported measurements, units, coordinates, thresholds and incompleteness states. Preserve failed/unknown evidence. Do not relax tolerances or move test geometry merely to make an engine pass.

Keep full-model scans bounded. Do not enable later-stage geometry prototypes until their individual acceptance cases have passed. Viewer stubs and headless WASM tests do not prove physical GPU performance or visual pair highlighting.

Use synthetic or redistribution-authorized test data. Do not commit uploaded private IFCs, access tokens, passwords, environment files, dependency installations or local temporary sessions. Preserve third-party licence notices.

Recovered releases v0.7.9–v0.7.16 retain their version tags; thirteen earlier snapshots are recorded on `archive/recovered-releases` and in the merged main history. Future changes use ordinary feature/fix/documentation commits; do not backdate development history or relabel unavailable snapshots as verified releases.
