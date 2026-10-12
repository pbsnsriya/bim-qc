# Publication preparation checks

Prepared for `pbsnsriya/bim-qc` on 2026-10-11. Application runtime remains v0.7.16; repository documentation does not add application features.

| Check | Result |
| --- | --- |
| Eight recovered release ZIPs | ZIP CRC passed; source SHA-256 retained in release manifest |
| Release-import trees | Every tracked file verified byte-for-byte against its corresponding extracted release snapshot |
| Local Git object integrity | `git fsck --full` passed |
| Latest runtime source | Verified against v0.7.16 ZIP before testing; only repository documentation/configuration changes added afterwards |
| Python unit/integration suite | 118 tests passed |
| Frontend suites | Review ledger, viewer selection, opening marker coordinates, render batches and frontend interactions passed |
| Stage 3 standalone reference export | 30/30 controls passed; original kernel baseline retained |
| Documentation links | Relative file links resolved |
| Credential-pattern scan | No GitHub token or private-key patterns found in prepared tracked files |
| Local author/committer | `pbsnsriya` with GitHub no-reply email; no assistant co-author trailers |
| Physical Edge/GPU run | Not performed as part of publication preparation |
| GitHub repository creation/push | Private repository created; eight recovered releases and documentation published; every imported remote tree matches its prepared local tree |

Local checks used Python 3.12, Node.js 24, IfcOpenShell 0.8.5 and Manifold3D 3.5.1. This workspace crashed while loading native extensions from its workspace virtual environment; rerunning with the same pinned geometry dependencies installed in the container's temporary filesystem passed. No application code was changed to mask that environment failure.

The added CI configuration targets Python 3.11 and Node.js 22 on Ubuntu. Its hosted result must be checked separately; local passing results do not establish hosted CI success.

A subsequent 2026-10-12 user upload recovered thirteen earlier source snapshots (v0.4.0–v0.7.8). Their ZIP integrity, source bytes, aliases, declared versions, remote trees and `pbsnsriya` attribution were verified. Supplied v0.7.9–v0.7.15 copies match existing source. Historical tests were not rerun. Main retains the v0.7.16 application tree and its existing history, with the archival branch merged as an additional parent. Release imports use current timestamps and explicitly identify their provenance.
