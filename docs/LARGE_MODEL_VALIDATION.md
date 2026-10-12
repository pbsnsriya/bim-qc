# Large-model validation

Version 0.6.2 was exercised locally against three non-synthetic IFC4 models.
The source IFC files are not redistributed with this project.

| Model | IFC size | IFC entities | QC elements | Semantic analysis | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| Terrain/office permit model | 2.0 MiB | 14,447 | 137 | 0.6 s | 0 errors, 0 warnings |
| Timber office as-built model | 77.59 MiB | 809,333 | 10,562 | 19.49 s through multipart model-session API | 0 errors, 0 warnings |
| Concrete housing as-built model | 76.73 MiB | 412,192 | 1,433 | 17.5 s direct local analysis | 0 errors, 0 warnings |

The 77.59 MiB source was uploaded once as an 81,357,672-byte multipart request;
the stored IFC was 81,357,305 bytes and the analysis response was 7.32 MiB.
web-ifc independently streamed 10,446 visible
elements, 19,757 geometry fragments, and approximately 2.8 million triangles
from that model in 6.6 seconds in the Node test environment.

The same 77.59 MiB model was also started and cancelled successfully in an
initial job-control test. A subsequent uninterrupted exhaustive run produced
the result below.

## Exhaustive Stage 1 result

Uploading, semantic QC, property browsing, and web-ifc geometry streaming are
separate from exhaustive IfcOpenShell tessellation. The 77.59 MiB timber office
model completed the full single-worker IfcOpenShell run in 563.4 seconds:

- 11,129 of 11,137 represented products generated (99.9% coverage);
- 1,456,792 vertices and 2,803,050 triangles;
- finite world bounds, millimetre-to-metre units, and STEP-ID mapping passed;
- eight failed shapes, all `IfcGrid` curve-set records rather than building
  solids; and
- the configured backend core gate passed.

Independent web-ifc WASM processing completed in 7.0 seconds with 10,446
visible elements, 19,757 mesh groups, and 2,808,099 triangles. Element-ID sets
matched exactly, but seven element extents exceeded the strict 1 mm tolerance:
six walls differed by about 103.2 mm and one roof slab by about 2.5 mm.
Therefore the overall cross-engine Stage 1 conclusion remains
**needs attention**, not pass. See `OFFICE_STAGE1_EVIDENCE_2026-09-26.json`.

Large models force IfcOpenShell geometry iteration to one worker to avoid
multiplying OpenCASCADE memory. Version 0.6.2 runs this work in a separate
process, reports processed/total represented products, and provides true
cancellation. The local runtime permits one geometry job, terminates it after
15 minutes, applies a best-effort 4 GiB address-space ceiling, and retains at
most three model sessions within a 250 MiB budget.

A synthetically padded but schema-valid 99 MiB IFC (103,809,024 bytes) was
accepted through the multipart endpoint and parsed as IFC4 in 3.33 seconds.
This proves the upload boundary and parser path, not complex-model geometry
performance. A separate earlier 76.73 MiB housing-model run was stopped after
four minutes and remains incomplete; it must not be conflated with the completed
77.59 MiB timber-office test above.

The UI includes a two-second browser/GPU evidence probe. A local run on
2026-09-27 created a WebGL 2 context on an AMD Radeon 780M and rendered the
77.59 MiB model (19,757 mesh groups and 2,808,099 loaded triangles). The probe
measured 11 frames in 2,248 ms, or 4.9 average FPS. This passes rendering
capability but does not meet the 20 FPS interactive target. The browser reported
the integrated AMD GPU rather than the available discrete RTX 5060. Use the new
isolate-selection mode for review and configure the browser/Windows graphics
preference for the discrete GPU before repeating the performance check.
