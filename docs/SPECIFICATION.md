# Novum supported subset RC1

This is the versioned supported-subset specification for this preview, derived from the qualified Novum semantic baseline `6a150e1ae4ddf15faa3765ea172b7fd0e17ce7ca`. A `novum <number>` header is recorded as source metadata; it is not a compatibility promise. The candidate package version is `0.2.0rc1` and the exchange marker remains `novum-dsc/0.1`.

One-line declaration openings `<kind> <id> {`, body lines, and `}` define `need`, `goal`, `function`, `constraint`, `assumption`, `unknown`, `tension`, `mechanism`, `concept`, `claim`, `test`, `evidence`, and `decision`. Identifiers match `[A-Za-z_][A-Za-z0-9_.-]*`. Comments begin with `#`. Omitted header and design name default to `0.3` and `UnnamedDesign`. Duplicate object identifiers fail; duplicate relation triples are retained once in first-seen order. `check` verifies endpoints and the implemented signatures below, whereas `parse` alone does not.

| Relation | Permitted source → target kinds |
| --- | --- |
| `satisfies` | mechanism → function; concept → function |
| `requires` | mechanism → function; concept → function or constraint; function → function; need → function; goal → function |
| `depends_on` | concept → assumption, claim, or unknown; claim → assumption; function → assumption |
| `uses` | concept → mechanism |
| `supports` | claim → claim; evidence → claim, assumption, or concept |
| `contradicts` | claim → claim; evidence → claim, assumption, or concept |
| `derives_from` | concept → function, tension, or concept |
| `tests` | test → claim, assumption, or concept |
| `evidences` | evidence → claim, assumption, or concept |

Direct transformations are `remove ID`, `substitute OLD with NEW`, `decompose FUNCTION into { CHILD ... }`, and `reopen ID`. They execute in source order on an insertion-ordered graph. `reopen` marks the target reopened and its transitive `depends_on` dependents stale. `derives_from` encodes candidate lineage; it does not calculate merit. Reparse under the same runtime and path is the replay method. No persistent graph serialization, independent feasibility proof, or cross-runtime byte stability is claimed.

The candidate does not include research commands such as `reject`, `explore`, `experiment`, or `autonomous_trial`. A research statement fails with the controlled `NOVUM-SYNTAX-001` diagnostic.
