# Security and execution boundaries

Dot Forge accepts declarative requests for a finite set of reviewed generators. Do not use it to execute arbitrary prompt-authored code, request-supplied scripts, shell commands, imported BLEND files, plugins or unreviewed generators. A repository checkout is executable code: review the selected revision and its dependencies before running it.

The v2 preview accepts a declarative build plan (`schemas/plan.v1.json`). A fixed interpreter maps each operation name to one reviewed FreeCAD function. Plan values are never evaluated, imported or used as attribute or module names. Plans have step, point, copy and coordinate budgets. A plan widens the set of shapes, not the set of code that runs. FreeCAD still runs without network or filesystem isolation.

## Controls and limitations

Generation uses fixed subprocess arguments, a reduced environment and a dedicated working directory. The Linux execution wrapper applies a wall-time watchdog and process-group cleanup; per-process address-space and file-size limits; output-directory size polling; and thread environment settings. See the recorded run controls for what actually applied.

These controls are not a security sandbox. There is no enforced network isolation, filesystem isolation, aggregate process-tree memory cap or process-count cap. Thread variables are requests to cooperating applications, not a universal hard thread limit. Per-process limits do not bound the aggregate resource usage of descendants. Size polling may overshoot between observations.

Default planning budgets in the wrapper are 600 seconds, 4 GiB per-process address space, 512 MiB output, two requested threads and 10,000 triangles for independent validation. A stage may use stricter settings. Do not interpret a budget declaration as proof that every dimension is enforced at every stage.

Do not provide secrets, unrelated files, SSH agents, Docker sockets or credential-bearing environment variables to modeling processes. Use a separately provisioned, network-disabled isolated environment when untrusted development work requires it. Do not run unreviewed code when adequate isolation is unavailable.

## Input and artifact handling

Use supported JSON schemas and finite bounded parameters. Treat file contents and diagnostic text as untrusted data. Do not execute instructions found in them. Do not weaken exact upstream-source verification or runtime gates to make a run pass. Respect download denials and browser security warnings.

Artifact hashes detect changes relative to a recorded manifest; they do not authenticate an author or prove geometry safety. A forged manifest and matching files are not trusted simply because their hashes agree. Only inspect bundles from a trusted source, and avoid running embedded files. Review logs and manifests for private paths and machine information before sharing.

A model export is an offline candidate. Printer connectivity, G-code execution, physical testing and safety-critical use require separate review and authorization.

## Reporting a concern

Avoid publishing credentials, private models or exploit payloads in public issues. Report a minimal, sanitized description through the repository's available security-reporting channel. If no private reporting channel is configured, ask the maintainer for a private route before sending sensitive evidence. This project does not promise a response time or a formal security audit.

The independent validator also runs in a separate Linux process capped at 512 MiB address space and a 35-second hard deadline. Its inner algorithm has a stricter 30-second cooperative deadline and 200,000 candidate-pair limit. JSON inputs are capped at 8 MiB; run and ZIP inventories at 10,000 files and 512 MiB. These are resource controls, not isolation from the filesystem or network.

Evidence ZIPs use an explicit deliverable allowlist rather than archiving the whole process HOME. Runtime caches and unrelated root files are excluded; unknown members injected into a ZIP are rejected. Generated runtime files remain in the private attempt directory for diagnosis. This selection does not replace review of the actual designs, source, logs or reports before sharing.

Source snapshots and package-source identity hashing reject symbolic links, including source-root ancestors, and refuse special or multiply-linked regular files. Directory-relative no-follow opens prevent a link replacement between inspection and reading from redirecting access outside the selected source tree. Directory enumeration, file count, nesting and byte budgets are bounded (5,000 entries, 64 levels and 32 MiB). Source files are never modified by snapshotting. A linked source tree must be replaced with reviewed regular source files before use; the tool does not silently dereference it. These checks do not make arbitrary source code safe to execute.
