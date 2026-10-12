# Large-model validation

Version 0.5.3 was exercised locally against three non-synthetic IFC4 models.
The source IFC files are not redistributed with this project.

| Model | IFC size | IFC entities | QC elements | Semantic analysis | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| Terrain/office permit model | 2.0 MiB | 14,447 | 137 | 0.6 s | 0 errors, 0 warnings |
| Timber office as-built model | 77.59 MiB | 809,333 | 10,562 | 17.5 s through HTTP API | 0 errors, 0 warnings |
| Concrete housing as-built model | 76.73 MiB | 412,192 | 1,433 | 17.5 s direct local analysis | 0 errors, 0 warnings |

The 77.59 MiB HTTP request was 77.60 MiB after JSON encoding and returned a
7.32 MiB analysis response. web-ifc independently streamed 10,446 visible
elements, 19,757 geometry fragments, and approximately 2.8 million triangles
from that model in 6.6 seconds in the Node test environment.

## Important performance boundary

Uploading, semantic QC, property browsing, and web-ifc geometry streaming are
separate from exhaustive IfcOpenShell tessellation. Full Stage 1 geometry
validation on a complex 76.73 MiB model exceeded four minutes during testing.
The run was manually stopped; it was not reported as a pass.

Large models now force IfcOpenShell geometry iteration to one worker to avoid
multiplying OpenCASCADE memory. The UI explicitly warns that exhaustive
geometry validation may take several minutes. A future background-job and
progress/cancellation milestone is recommended before treating exhaustive
checks on 100 MiB models as an interactive production workflow.
