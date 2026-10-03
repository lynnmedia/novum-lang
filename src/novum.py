# Supported Novum RC1 runtime. This module has no research-module dependency.
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

__version__ = "0.2.0rc1"
RUNTIME_VERSION = f"novum/{__version__}"


class ParseError(SyntaxError):
    def __init__(self, code: str, message: str, line: int = 1, col: int = 1,
                 filename: str = "<memory>", source_line: str = ""):
        self.code = code
        self.message = message
        self.line = line
        self.col = col
        self.filename = filename
        self.source_line = source_line
        super().__init__(f"{code} at {filename}:{line}:{col}: {message}")

    def format_diagnostic(self) -> str:
        lines = [f"{self.code}: {self.message}"]
        lines.append(f"  --> {self.filename}:{self.line}:{self.col}")
        if self.source_line:
            lines.append("   |")
            lines.append(f"{self.line:2d} | {self.source_line}")
            caret_col = max(1, self.col)
            lines.append(f"   | {' ' * (caret_col - 1)}^")
        return "\n".join(lines)


OBJECT_TYPES = {
    "need", "goal", "function", "constraint", "assumption",
    "unknown", "tension", "mechanism", "concept", "claim",
    "test", "evidence", "decision"
}

RELATIONS = {
    "satisfies", "requires", "depends_on",
    "uses", "supports", "contradicts", "derives_from",
    "tests", "evidences"
}

RELATION_SIGNATURES = {
    "satisfies": {
        ("mechanism", "function"),
        ("concept", "function"),
    },
    "requires": {
        ("mechanism", "function"),
        ("concept", "function"),
        ("concept", "constraint"),
        ("function", "function"),       # NLE-006: decomposition obligation
        ("need", "function"),           # NLE-016: problem-to-function trace
        ("goal", "function"),
    },
    "depends_on": {
        ("concept", "assumption"),
        ("concept", "claim"),
        ("concept", "unknown"),
        ("claim", "assumption"),
        ("function", "assumption"),
    },
    "uses": {
        ("concept", "mechanism"),
    },
    "supports": {("claim","claim"), ("evidence","claim"), ("evidence","assumption"), ("evidence","concept")},
    "contradicts": {("claim","claim"), ("evidence","claim"), ("evidence","assumption"), ("evidence","concept")},
    "derives_from": {
        ("concept", "function"),
        ("concept", "tension"),
        ("concept", "concept"),
    },

    "tests": {("test","claim"), ("test","assumption"), ("test","concept")},
    "evidences": {("evidence","claim"), ("evidence","assumption"), ("evidence","concept")},
}

@dataclass
class Node:
    kind: str
    ident: str
    body: List[str] = field(default_factory=list)
    status: str = "active"

@dataclass
class Design:
    name: str = "UnnamedDesign"
    version: str = "0.3"
    nodes: Dict[str, Node] = field(default_factory=dict)
    edges: List[Tuple[str, str, str]] = field(default_factory=list)
    trace: List[dict] = field(default_factory=list)

    def add_node(self, node: Node, event: str = "declare"):
        if node.ident in self.nodes:
            raise ValueError(f"duplicate identifier: {node.ident}")
        self.nodes[node.ident] = node
        self.trace.append({"event": event, "kind": node.kind, "id": node.ident})

    def add_edge(self, src: str, rel: str, dst: str, event: str = "relate"):
        edge = (src, rel, dst)
        if edge not in self.edges:
            self.edges.append(edge)
            self.trace.append({"event": event, "source": src, "relation": rel, "target": dst})

    def remove_edge(self, edge: Tuple[str, str, str], reason: str):
        if edge in self.edges:
            self.edges.remove(edge)
            self.trace.append({
                "event": "unrelate", "source": edge[0], "relation": edge[1],
                "target": edge[2], "reason": reason
            })


def strip_comments(line: str) -> str:
    return line.split("#", 1)[0].rstrip()


def incoming(d: Design, ident: str, rel: str | None = None):
    return [(s, r, t) for s, r, t in d.edges if t == ident and (rel is None or r == rel)]


def outgoing(d: Design, ident: str, rel: str | None = None):
    return [(s, r, t) for s, r, t in d.edges if s == ident and (rel is None or r == rel)]


def remove_object(d: Design, ident: str):
    if ident not in d.nodes:
        raise ValueError(f"remove target does not exist: {ident}")
    node = d.nodes[ident]
    affected = []
    for edge in list(d.edges):
        if ident in (edge[0], edge[2]):
            affected.append({"source": edge[0], "relation": edge[1], "target": edge[2]})
            d.remove_edge(edge, f"remove {ident}")
    del d.nodes[ident]
    d.trace.append({
        "event": "transform", "operator": "remove", "target": ident,
        "kind": node.kind, "removed_relations": affected
    })


def substitute_object(d: Design, old: str, new: str):
    if old not in d.nodes:
        raise ValueError(f"substitute source does not exist: {old}")
    if new not in d.nodes:
        raise ValueError(f"substitute replacement does not exist: {new}")
    if d.nodes[old].kind != d.nodes[new].kind:
        raise ValueError(
            f"substitute type mismatch: {old} is {d.nodes[old].kind}, "
            f"{new} is {d.nodes[new].kind}"
        )

    rewired = []
    for edge in list(d.edges):
        src, rel, dst = edge
        if src != old and dst != old:
            continue
        ns = new if src == old else src
        nd = new if dst == old else dst
        d.remove_edge(edge, f"substitute {old} with {new}")
        d.add_edge(ns, rel, nd, event="rewire")
        rewired.append({
            "from": {"source": src, "relation": rel, "target": dst},
            "to": {"source": ns, "relation": rel, "target": nd}
        })

    old_kind = d.nodes[old].kind
    del d.nodes[old]
    d.trace.append({
        "event": "transform", "operator": "substitute", "target": old,
        "replacement": new, "kind": old_kind, "rewired": rewired
    })


def decompose_function(d: Design, parent: str, children: List[str]):
    if parent not in d.nodes:
        raise ValueError(f"decompose target does not exist: {parent}")
    if d.nodes[parent].kind != "function":
        raise ValueError(f"decompose requires function target: {parent}")
    if not children:
        raise ValueError("decompose requires at least one child function")

    created = []
    for child in children:
        if child not in d.nodes:
            d.add_node(Node("function", child, [f"derived_by decompose {parent}"]), event="derive")
            created.append(child)
        elif d.nodes[child].kind != "function":
            raise ValueError(f"decompose child must be function: {child}")
        d.add_edge(parent, "requires", child, event="derive_relation")

    d.trace.append({
        "event": "transform", "operator": "decompose", "target": parent,
        "children": children, "created": created
    })


def dependent_nodes(d: Design, ident: str) -> List[str]:
    """Return transitive dependents through depends_on edges."""
    seen = set()
    queue = [ident]
    while queue:
        current = queue.pop(0)
        for src, rel, dst in d.edges:
            if rel == "depends_on" and dst == current and src not in seen:
                seen.add(src)
                queue.append(src)
    return sorted(seen)


def reopen_object(d: Design, ident: str):
    if ident not in d.nodes:
        raise ValueError(f"reopen target does not exist: {ident}")
    d.nodes[ident].status = "reopened"
    affected = dependent_nodes(d, ident)
    for dep in affected:
        d.nodes[dep].status = "stale"
    d.trace.append({
        "event": "transform", "operator": "reopen", "target": ident,
        "target_status": "reopened", "affected": affected,
        "affected_status": "stale"
    })




def mechanism_activated_tensions(d: Design, mechanism_id: str) -> List[str]:
    node = d.nodes.get(mechanism_id)
    if not node:
        return []
    out = []
    for line in node.body:
        m = re.fullmatch(r"activates\s+([A-Za-z_][A-Za-z0-9_.-]*)", line.strip())
        if m and m.group(1) in d.nodes and d.nodes[m.group(1)].kind == "tension":
            out.append(m.group(1))
    return sorted(dict.fromkeys(out))


def _parse(path: Path, statement_extension=None) -> Design:
    lines = path.read_text(encoding="utf-8").splitlines()
    d = Design()
    i = 0

    while i < len(lines):
        raw = strip_comments(lines[i]).strip()
        i += 1
        if not raw:
            continue

        m = re.fullmatch(r"novum\s+([0-9.]+)", raw)
        if m:
            d.version = m.group(1)
            continue

        m = re.fullmatch(r"design\s+([A-Za-z_][A-Za-z0-9_.-]*)", raw)
        if m:
            d.name = m.group(1)
            continue

        m = re.fullmatch(
            r"(need|goal|function|constraint|assumption|unknown|tension|mechanism|concept|claim|test|evidence|decision)\s+"
            r"([A-Za-z_][A-Za-z0-9_.-]*)\s*\{",
            raw
        )
        if m:
            kind, ident = m.groups()
            body = []
            depth = 1
            while i < len(lines) and depth > 0:
                line = strip_comments(lines[i])
                i += 1
                depth += line.count("{")
                depth -= line.count("}")
                if depth > 0:
                    body.append(line.strip())
            if depth != 0:
                raise SyntaxError(f"unterminated block for {ident}")
            d.add_node(Node(kind, ident, body))
            continue

        # NLE-006 executable transforms
        m = re.fullmatch(r"remove\s+([A-Za-z_][A-Za-z0-9_.-]*)", raw)
        if m:
            remove_object(d, m.group(1))
            continue

        m = re.fullmatch(
            r"substitute\s+([A-Za-z_][A-Za-z0-9_.-]*)\s+with\s+([A-Za-z_][A-Za-z0-9_.-]*)",
            raw
        )
        if m:
            substitute_object(d, m.group(1), m.group(2))
            continue

        m = re.fullmatch(r"decompose\s+([A-Za-z_][A-Za-z0-9_.-]*)\s+into\s*\{", raw)
        if m:
            parent = m.group(1)
            children = []
            while i < len(lines):
                line = strip_comments(lines[i]).strip()
                i += 1
                if not line:
                    continue
                if line == "}":
                    break
                # permit optional commas and optional 'function' keyword
                line = line.rstrip(",").strip()
                cm = re.fullmatch(r"(?:function\s+)?([A-Za-z_][A-Za-z0-9_.-]*)", line)
                if not cm:
                    raise SyntaxError(f"invalid decompose child: {line}")
                children.append(cm.group(1))
            else:
                raise SyntaxError(f"unterminated decompose block for {parent}")
            decompose_function(d, parent, children)
            continue

        m = re.fullmatch(r"reopen\s+([A-Za-z_][A-Za-z0-9_.-]*)", raw)
        if m:
            reopen_object(d, m.group(1))
            continue

        m = re.fullmatch(
            r"([A-Za-z_][A-Za-z0-9_.-]*)\s+"
            r"(satisfies|requires|depends_on|uses|supports|contradicts|derives_from|tests|evidences)\s+"
            r"([A-Za-z_][A-Za-z0-9_.-]*)",
            raw
        )
        if m:
            d.add_edge(*m.groups())
            continue

        if statement_extension is not None:
            next_i = statement_extension(d, raw, lines, i)
            if next_i is not None:
                i = next_i
                continue

        raise ParseError("NOVUM-SYNTAX-001", f"cannot parse statement: {raw}",
                         line=i, col=1, filename=str(path), source_line=lines[i - 1] if i - 1 < len(lines) else raw)

    return d


def parse(path: Path) -> Design:
    """Parse only the frozen supported source subset."""
    return _parse(path)

def validate(d: Design) -> List[dict]:
    issues = []

    for src, rel, dst in d.edges:
        if src not in d.nodes:
            issues.append({"severity": "ERROR", "code": "NV001", "message": f"unknown source '{src}'"})
            continue
        if dst not in d.nodes:
            issues.append({"severity": "ERROR", "code": "NV002", "message": f"unknown target '{dst}'"})
            continue

        sig = (d.nodes[src].kind, d.nodes[dst].kind)
        allowed = RELATION_SIGNATURES.get(rel, set())
        if sig not in allowed:
            issues.append({
                "severity": "ERROR",
                "code": "NV003",
                "message": f"invalid relation signature: {sig[0]} {rel} {sig[1]}"
            })

    solution_words = {
        "fan", "compressor", "pump", "speaker", "motor",
        "wristband", "app", "device", "refrigerator"
    }
    for n in d.nodes.values():
        if n.kind == "need":
            text = " ".join(n.body).lower()
            hits = sorted(w for w in solution_words if re.search(rf"\b{re.escape(w)}\b", text))
            if hits:
                issues.append({
                    "severity": "WARNING",
                    "code": "NV101",
                    "message": f"need '{n.ident}' may encode solution mechanisms: {', '.join(hits)}"
                })

    return issues


def frontier(d: Design, status_extension=None, include_unknown=None) -> List[dict]:
    items = []

    for node in d.nodes.values():
        if node.status == "reopened":
            items.append({"kind": "REOPENED", "id": node.ident})
        elif node.status == "stale":
            items.append({"kind": "STALE", "id": node.ident})
        elif status_extension is not None:
            items.extend(status_extension(node, "primary"))

        if node.kind == "unknown" and (include_unknown is None or include_unknown(node)):
            items.append({"kind": "UNKNOWN", "id": node.ident})

        elif node.kind == "tension":
            items.append({"kind": "TENSION", "id": node.ident})

        elif node.kind == "function":
            satisfiers = [s for s, r, t in d.edges if r == "satisfies" and t == node.ident]
            if not satisfiers:
                items.append({"kind": "UNSATISFIED_FUNCTION", "id": node.ident})

        elif node.kind == "claim":
            supporters = incoming(d, node.ident, "supports")
            if not supporters:
                items.append({"kind": "UNSUPPORTED_CLAIM", "id": node.ident})


    for node in d.nodes.values():
        if node.status == "reopened":
            items.append({"kind":"REOPENED","id":node.ident})
        elif status_extension is not None:
            items.extend(status_extension(node, "secondary"))
    deduped = []
    seen_frontier = set()
    for item in items:
        key = tuple(sorted(item.items()))
        if key not in seen_frontier:
            seen_frontier.add(key)
            deduped.append(item)
    items = deduped
    return items


def challenge(d: Design, target: str, finding_extension=None) -> List[dict]:
    if target not in d.nodes:
        return [{"severity": "ERROR", "code": "NV404", "message": f"unknown target '{target}'"}]

    n = d.nodes[target]
    findings = []

    if n.status == "stale":
        findings.append({"severity": "WARNING", "code": "NV405", "message": "object is stale after reopened dependency"})
    elif n.status == "reopened":
        findings.append({"severity": "INFO", "code": "NV406", "message": "object is explicitly reopened for reassessment"})
    elif finding_extension is not None:
        findings.extend(finding_extension(d, target, n, "status"))

    if n.kind not in {"concept", "claim", "mechanism"}:
        findings.append({
            "severity": "INFO",
            "code": "NV400",
            "message": f"challenge is shallow for object type '{n.kind}' in NLE-006"
        })

    if n.kind == "concept":
        if not outgoing(d, target, "uses"):
            findings.append({"severity": "WARNING", "code": "NV401", "message": "concept uses no declared mechanism"})

        if not outgoing(d, target, "depends_on"):
            findings.append({"severity": "WARNING", "code": "NV402", "message": "concept has no declared assumption/claim dependencies"})

        if not outgoing(d, target, "satisfies"):
            findings.append({"severity": "WARNING", "code": "NV403", "message": "concept satisfies no declared function"})

        for _, _, dep in outgoing(d, target, "depends_on"):
            dn = d.nodes.get(dep)
            if dn and dn.kind == "claim" and not incoming(d, dep, "supports"):
                findings.append({"severity": "WARNING", "code": "NV404", "message": f"concept depends on unsupported claim '{dep}'"})


    if n.kind == "concept" and finding_extension is not None:
        findings.extend(finding_extension(d, target, n, "dependencies"))
    if not findings:
        findings.append({"severity": "INFO", "code": "NV000", "message": "no minimal-kernel challenge findings"})
    return findings


def inspect_design(d: Design) -> dict:
    by_type = {}
    statuses = {}
    for node in d.nodes.values():
        by_type.setdefault(node.kind, []).append(node.ident)
        if node.status != "active":
            statuses[node.ident] = node.status
    for ids in by_type.values():
        ids.sort()

    return {
        "novum_version": d.version,
        "design": d.name,
        "objects": by_type,
        "statuses": statuses,
        "relations": [
            {"source": s, "relation": r, "target": t}
            for s, r, t in d.edges
        ],
    }


def export_dsc_contract(d: Design, source_file: str = "<memory>") -> dict:
    """
    Exports a canonical, versioned Novum-DSC exchange contract object (novum-dsc/0.1).
    """
    issues = validate(d)
    critical_errors = [x for x in issues if x["severity"] == "ERROR"]
    if critical_errors:
        raise ValueError(f"cannot export invalid design to DSC contract: {critical_errors}")

    entities = []
    for node in d.nodes.values():
        entities.append({
            "id": node.ident,
            "kind": node.kind,
            "body": list(node.body),
            "status": node.status
        })

    relations = []
    for s, r, t in d.edges:
        relations.append({
            "source": s,
            "relation": r,
            "target": t
        })

    # Tensions & Mechanisms specialized structures
    tensions = [
        {"id": n.ident, "description": " ".join(n.body) if n.body else n.ident}
        for n in d.nodes.values() if n.kind == "tension"
    ]
    mechanisms = [
        {
            "id": n.ident,
            "description": " ".join(n.body) if n.body else n.ident,
            "satisfies": [r["target"] for r in relations if r["source"] == n.ident and r["relation"] == "satisfies"],
            "activates_tensions": mechanism_activated_tensions(d, n.ident)
        }
        for n in d.nodes.values() if n.kind == "mechanism"
    ]

    # Obligations (downstream requirements & unresolved unknowns)
    obligations = [
        {
            "id": n.ident,
            "kind": n.kind,
            "status": n.status,
            "dependents": dependent_nodes(d, n.ident)
        }
        for n in d.nodes.values() if n.kind in ("unknown", "assumption")
    ]

    # Evidence records
    evidence = [
        {
            "id": n.ident,
            "body": list(n.body),
            "supports": [r["target"] for r in relations if r["source"] == n.ident and r["relation"] == "supports"],
            "contradicts": [r["target"] for r in relations if r["source"] == n.ident and r["relation"] == "contradicts"]
        }
        for n in d.nodes.values() if n.kind == "evidence"
    ]

    return {
        "contract": "novum-dsc/0.1",
        "problem": {
            "name": d.name,
            "novum_version": d.version,
            "needs": [n.ident for n in d.nodes.values() if n.kind == "need"],
            "goals": [n.ident for n in d.nodes.values() if n.kind == "goal"],
            "functions": [n.ident for n in d.nodes.values() if n.kind == "function"],
            "constraints": [n.ident for n in d.nodes.values() if n.kind == "constraint"]
        },
        "entities": entities,
        "relations": relations,
        "tensions": tensions,
        "mechanisms": mechanisms,
        "obligations": obligations,
        "evidence": evidence,
        "provenance": {
            "source_file": str(source_file),
            "exporter_version": RUNTIME_VERSION,
            "entity_count": len(entities),
            "relation_count": len(relations)
        }
    }


def emit(obj):
    print(json.dumps(obj, indent=2))


def main(argv=None, source_parser=None, frontier_view=None, challenge_view=None):
    parser = argparse.ArgumentParser(prog="novum", description="Novum Language Runtime v0.1")
    parser.add_argument("--version", action="version", version=RUNTIME_VERSION)
    sub = parser.add_subparsers(dest="cmd", required=True)

    for cmd in ["check", "inspect", "frontier", "trace"]:
        p = sub.add_parser(cmd)
        p.add_argument("file", type=Path)

    p = sub.add_parser("challenge")
    p.add_argument("file", type=Path)
    p.add_argument("target")

    p = sub.add_parser("export-dsc", help="export canonical novum-dsc/0.1 contract exchange JSON")
    p.add_argument("file", type=Path)
    p.add_argument("-o", "--output", type=Path, required=True)

    args = parser.parse_args(argv)
    if source_parser is None:
        source_parser = parse
    if frontier_view is None:
        frontier_view = frontier
    if challenge_view is None:
        challenge_view = challenge

    try:
        d = source_parser(args.file)
    except ParseError as e:
        print(e.format_diagnostic(), file=sys.stderr)
        emit({"ok": False, "error": str(e), "diagnostic": e.format_diagnostic()})
        sys.exit(2)
    except Exception as e:
        emit({"ok": False, "error": str(e)})
        sys.exit(2)

    if args.cmd == "check":
        issues = validate(d)
        ok = not any(x["severity"] == "ERROR" for x in issues)
        emit({"ok": ok, "design": d.name, "issues": issues})
        return 0 if ok else 1
    elif args.cmd == "inspect":
        emit(inspect_design(d))
    elif args.cmd == "frontier":
        emit({"design": d.name, "frontier": frontier_view(d)})
    elif args.cmd == "challenge":
        emit({"design": d.name, "target": args.target, "findings": challenge_view(d, args.target)})
    elif args.cmd == "trace":
        emit({"design": d.name, "trace": d.trace})
    elif args.cmd == "export-dsc":
        try:
            contract_obj = export_dsc_contract(d, source_file=str(args.file))
        except ValueError as e:
            emit({"ok": False, "error": str(e)})
            return 1
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(contract_obj, indent=2), encoding="utf-8")
        emit({
            "ok": True,
            "command": "export-dsc",
            "contract": "novum-dsc/0.1",
            "design": d.name,
            "output": str(args.output),
            "entity_count": len(contract_obj["entities"]),
            "relation_count": len(contract_obj["relations"])
        })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
