# Recovered early QC releases

The user supplied `openbim-qc version upto 0.78.zip` on 2026-10-12. Its ZIP CRC check passed. After checking actual version declarations and excluding installed dependencies/caches and nested duplicate projects, thirteen distinct older QC source snapshots were recovered.

The archive branch [archive/recovered-releases](https://github.com/pbsnsriya/bim-qc/tree/archive/recovered-releases) contains the source snapshots in numeric version order. Each table link opens the exact imported source tree. These commits use current import dates and `pbsnsriya` attribution; they are not reconstructed original development commits.

| Declared version | Source files | Imported source commit |
| --- | --- | --- |
| v0.4.0 | 38 | [0043fa7](https://github.com/pbsnsriya/bim-qc/tree/0043fa79378dd901d88f62baf8277f88c90d41e4) |
| v0.5.1 | 42 | [5bae4cb](https://github.com/pbsnsriya/bim-qc/tree/5bae4cb90c1c9cd7f63ec0725e59339f37396cc8) |
| v0.5.3 | 52 | [5f913fe](https://github.com/pbsnsriya/bim-qc/tree/5f913fe1a5b97cf14502eb638963db92d95540b1) |
| v0.6.1 | 56 | [6bfdec3](https://github.com/pbsnsriya/bim-qc/tree/6bfdec3b143596db5898b006867becb8413026f6) |
| v0.6.2 | 56 | [ed361e6](https://github.com/pbsnsriya/bim-qc/tree/ed361e6a729b20a4ee925c62e8e5b15fcaea613f) |
| v0.7.0 | 59 | [848d366](https://github.com/pbsnsriya/bim-qc/tree/848d3663fa80a61b74bb580c00a4d843c7d11b80) |
| v0.7.1 | 60 | [35b9855](https://github.com/pbsnsriya/bim-qc/tree/35b985545fb8c4e319628baf53f59a1b899073e6) |
| v0.7.2 | 60 | [df50b06](https://github.com/pbsnsriya/bim-qc/tree/df50b06c61fdfc10243c8ce0d6376e6558cbc148) |
| v0.7.3 | 60 | [ba8c691](https://github.com/pbsnsriya/bim-qc/tree/ba8c691f657d19923062bb5e77bd77c1d93cd5bf) |
| v0.7.4 | 60 | [2651963](https://github.com/pbsnsriya/bim-qc/tree/2651963f6afe989998f6c5c10c5d20fe5ebcba57) |
| v0.7.5 | 60 | [4f4fe7b](https://github.com/pbsnsriya/bim-qc/tree/4f4fe7bbdb61ae3984b7d39579e86888d289ac54) |
| v0.7.6 | 60 | [523ec8f](https://github.com/pbsnsriya/bim-qc/tree/523ec8f8dce32399cacec5f67193cdc40dbb9921) |
| v0.7.8 | 60 | [b1b2a42](https://github.com/pbsnsriya/bim-qc/tree/b1b2a42cfb8e7365d3ba586e8de600b1723c6534) |

## Version labels and duplicate aliases

- The folder labelled `openbim-qc-mvp0.2` contains **v0.6.2**, identical to the copy under `openbim-qc-mvp0.61`.
- The root of `openbim-qc-mvp0.6` declares **v0.6.1** and includes a nested **v0.5.3** project. The nested project matches the standalone `openbim-qc` copy; both identities are retained in provenance, with one source commit per distinct version/tree.
- Both supplied v0.7.9 folders are identical. Supplied v0.7.9–v0.7.15 source trees also match the already-published releases, so their existing commits and tags are retained.
- The earliest declared QC version in this upload is **v0.4.0**. There is no v0.7.7 snapshot or source before v0.4.0 in the upload. This index does not invent those versions.
- `OpenBIM-Milestone-3B-navigation-fix` is a separate CAD/DWG-to-3D project. It is recorded in the inventory and excluded from this IFC QC history import.

## What was verified

ZIP integrity, required source files, declared versions, canonical per-file SHA-256 inventories, identical-copy comparisons, and byte-identical remote Git trees were checked. Vendor runtime and licence notices are retained. Installed `node_modules`, Python caches and nested duplicate source trees are excluded.

These are archival checks, not a claim that every old release is correct or that its historical tests passed again. Older engine limitations and failed controls remain part of their source history.

## Main-branch behavior

The legacy branch is merged into `main` by retaining the current v0.7.16 application tree and adding the legacy branch as a second parent. This makes the older commits reachable from the main history without force-pushing, deleting existing commits or replacing the current application with an older release. Only current documentation/provenance changes are included in the main tree.

All twenty-one recovered version identities are indexed in [release-snapshots.json](release-snapshots.json). Existing v0.7.9–v0.7.16 tags remain unchanged; earlier source snapshots are addressed by their archive commits.
