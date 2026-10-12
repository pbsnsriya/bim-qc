# Recovered release history

The repository imports actual ZIP source snapshots into Git. These commits were created for publication on the current date; they are not the original development commits and do not claim their timestamps. Each version tag points to the exact archived source tree, before the repository documentation commit.

The earliest complete recovered source is **v0.7.9**. The first MVP and v0.7.0–v0.7.8 source snapshots are unavailable. A surviving MVP-named local ZIP is truncated and contains later release documents, so it cannot be used as evidence of the first version. These gaps have not been filled with invented code or dates.

| Version/tag | Recovered release increment | Files | Source archive SHA-256 |
| --- | --- | --- | --- |
| v0.7.9 | Import earliest recovered release with independent geometry evidence | 89 | `66270fe4e4d4b2317f8a4a2b285916dcbe61a91f351bec671bfea02e619d9b7b` |
| v0.7.10 | Batch viewer geometry while preserving element picking and pair selection | 95 | `174faaab0122b2f362adec1fc502bcb47acf39ce91a3b1cf6a181b6215e8e237` |
| v0.7.11 | Compare duplicate pairs using physical fields and source properties | 99 | `3f32db0a6d954d9b9e12651c4f79479591b13cc2a4f91cdade1729efa667a741` |
| v0.7.12 | Show explicit opening hosts and context-aware comparison fields | 100 | `00ed03aaa5dcacc22651b523b8c480023225d96708cc8730b3f1f78adea16bad` |
| v0.7.13 | Add bounded translation-only near-duplicate detection | 105 | `81cfda34bb2df7f38446e00e72bc8e702c138f06c6b1732daedbe1b451ab55ea` |
| v0.7.14 | Measure opening-host bounds separation and visualize opening markers | 113 | `1b3f4dc91a274cbbae2dedfe38e62e4d1d0e7c323386398f22bd47cefea8cf9e` |
| v0.7.15 | Archive test review decisions and expose hard-clash reference failures | 128 | `cd691a706a75c4b55e68df1660e0604af2f5fd4feb301e1c7a71b36d2fa637e8` |
| v0.7.16 | Correct aligned overlap detection with solid Booleans and convex depth evidence | 137 | `c2451a93538f2d3039855742ebc1e50f2b535441029966d6a1880a3b80dcb189` |

Published import commit IDs, prepared local commit IDs and source hashes are in [release-snapshots.json](release-snapshots.json). SHA-256 values identify the validated release ZIPs; Git commits/tags identify their extracted trees. Each snapshot's archived README and licence files are preserved at its tag. The latest original release usage guide is also available as [LOCAL_USAGE.md](LOCAL_USAGE.md).

## Attribution

Published release-import and documentation commits were verified to resolve to the GitHub account `pbsnsriya` for both author and committer. The prepared local Git bundle uses the GitHub no-reply address `137526270+pbsnsriya@users.noreply.github.com`. Published and local commit IDs differ because publication follows GitHub repository initialization; their source trees were verified identical. Project commits contain no assistant co-author trailers. Existing vendor copyright and licence attribution remains intact.

## What the history proves

The archived source bytes and their ordered version differences are recoverable. This import cannot recreate missing intermediate edits, historic branch decisions, original commit messages, or the first release. If earlier authentic snapshots become available, recover them separately and retain their provenance rather than disguising them as original Git development history.
