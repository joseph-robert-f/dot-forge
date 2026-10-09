# Publishing source or artifacts

Local generation is not permission to publish. Confirm the destination, audience, files and visibility before creating a remote, pushing source, publishing a release or uploading user models. The portable CLI creates local evidence; it does not depend on an assistant account or cloud artifact service.

Before a source release:

- Run source checks and the supported runtime acceptance tests. Keep blocked and skipped gates visible in docs/acceptance.md.
- Review tracked files for secrets, credentials, private paths, usernames, chat identifiers, proprietary references and private designs.
- Keep build outputs, BLEND/STL exports, renders, logs, runtime binaries and generated benchmark runs out of source history unless explicitly reviewed for inclusion.
- Verify upstream pin notices, asset rights and dependency inventory. Do not imply a runtime is redistributed when it is not.
- Review the exact diff and destination. No automated telemetry or public benchmark upload is part of the default workflow.

Before sharing a run bundle, inspect its request, metadata, logs, source files and provenance for private information. Hash verification is necessary for internal consistency but does not sanitize a bundle or establish authorship. Keep the original private evidence if a separate sanitized public report is made.

## Characters and other people's designs

A model of a character, a logo or another design can belong to someone else. Printing it for personal use is a different decision from sharing or selling the file or the print. Before you publish, upload or sell such a model, confirm that you have the right to do so. A Dot must not publish or upload it for the user without that decision. The printability report says nothing about rights.

A durable delivery includes a verified downloadable bundle and a recipient-accessible location. A temporary local path or an expired private URL is not a completed handoff. Verify the downloaded bundle again when possible.
