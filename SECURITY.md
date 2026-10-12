# Security and data handling

This is a local development application, not a hardened multi-user server. Run it on `127.0.0.1`; the API has no account authentication or tenant isolation. Public/shared deployment requires access control, upload isolation, quotas, durable storage policy and service hardening.

Uploaded IFCs are kept in bounded temporary local sessions. Review notes live in browser localStorage and may be included in exported reports. Treat model names, property values and diagnostic exports as project data. Do not upload confidential source models or credentials to this repository.

For a suspected vulnerability, contact the repository owner through GitHub before posting confidential reproduction data. For ordinary failures, open an issue using a synthetic IFC or a minimal description that avoids private model information.
