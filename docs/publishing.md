# Publishing source or artifacts

Local generation is not permission to publish. Confirm the destination, audience, files and visibility before creating a remote, pushing source, publishing a release or uploading user models. The portable CLI creates local evidence; it does not depend on an assistant account or cloud artifact service.

Before a source release:

- Run source checks and the supported runtime acceptance tests. Keep blocked and skipped gates visible in docs/acceptance.md.
- Review tracked files for secrets, credentials, private paths, usernames, chat identifiers, proprietary references and private designs.
- Keep build outputs, BLEND/STL exports, renders, logs, runtime binaries and generated benchmark runs out of source history unless explicitly reviewed for inclusion.
- Verify upstream pin notices, asset rights and dependency inventory. Do not imply a runtime is redistributed when it is not.
- Review the exact diff and destination. No automated telemetry or public benchmark upload is part of the default workflow.

Before sharing a run bundle, inspect its request, metadata, logs, source files and provenance for private information. Hash verification is necessary for internal consistency but does not sanitize a bundle or establish authorship. Keep the original private evidence if a separate sanitized public report is made.

A durable delivery includes a verified downloadable bundle and a recipient-accessible location. A temporary local path or an expired private URL is not a completed handoff. Verify the downloaded bundle again when possible.
