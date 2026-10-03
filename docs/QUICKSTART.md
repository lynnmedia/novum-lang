# Quickstart

Use Python 3.9–3.14. In a clean environment, install the supplied wheel with `python -m pip install --no-index --no-deps ./novum_lang-0.2.0rc1-py3-none-any.whl`. The same archive includes the examples under `share/novum-lang/examples` when installed; an authorized reviewer may also read them directly from the source archive.

Run these commands from the unpacked source archive root:

```sh
novum check examples/minimal-valid.novum
novum inspect examples/branch-lineage-reopen.novum
novum trace examples/branch-lineage-reopen.novum
novum frontier examples/branch-lineage-reopen.novum
novum challenge examples/branch-lineage-reopen.novum CandidateB
novum check examples/invalid-target.novum
novum export-dsc examples/branch-lineage-reopen.novum -o /tmp/novum-candidate-exchange.json
```

The invalid program exits 1 with `NV002`, without a traceback. `trace` shows the direct `reopen` event and ordered declarations/relations. Repeating the commands with identical source bytes and path under the same runtime reproduces the graph and trace; Novum has no durable run store. Compare the export with `examples/branch-lineage-reopen.novum-dsc.json` (the same relative source path) to verify byte identity. To import, install the separately released bounded DSC Core `0.2.0rc1` wheel in a Python 3.12 environment and run `dsc import-novum /tmp/novum-candidate-exchange.json --workspace /tmp/novum-candidate-workspace`. Read [Compatibility](COMPATIBILITY.md) before interpreting the result.
