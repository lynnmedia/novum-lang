# CLI and API reference

The installed `novum` command has `check`, `inspect`, `frontier`, `trace`, `challenge FILE ID`, and `export-dsc FILE -o OUTPUT`. `check` exits 0 for no errors, 1 for validation errors; parse or transform failure exits 2. `export-dsc` validates first and leaves its requested output unwritten on validation failure. Successful export may overwrite an existing target. `inspect`, `frontier`, `trace`, and `challenge` parse but do not automatically validate.

The installed Python module `novum` exposes `parse(Path)`, `validate(design)`, `inspect_design(design)`, `frontier(design)`, `challenge(design, id)`, and `export_dsc_contract(design, source_file=...)`. `parse` returns an in-memory graph, not a stable serialized Python object format. `inspect` sorts identifiers within kinds but retains relation order. `trace` is chronological, not a cryptographic event log.

Validation codes include `NV001` unknown source, `NV002` unknown target, `NV003` invalid relation signature, and heuristic warning `NV101`. `NOVUM-SYNTAX-001` reports an unmatched statement with a caret. `challenge` is shallow and may report `NV404` for an unknown target. Declaration bodies are not fully schema-checked, scientific contradictions are not adjudicated, and file-write I/O failures are not normalized into these diagnostic codes.
