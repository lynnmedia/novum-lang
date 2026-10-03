"""Synthetic installed-candidate behavior checks; no private fixture dependency."""

import json
from pathlib import Path
import unittest

import novum


ROOT = Path(__file__).resolve().parents[1]


class CandidateTests(unittest.TestCase):
    def test_minimal_and_failure(self):
        valid = novum.parse(ROOT / "examples/minimal-valid.novum")
        self.assertEqual(novum.validate(valid), [])
        invalid = novum.parse(ROOT / "examples/invalid-target.novum")
        self.assertEqual([issue["code"] for issue in novum.validate(invalid)], ["NV002"])

    def test_lineage_reopen_and_replay(self):
        path = ROOT / "examples/branch-lineage-reopen.novum"
        left, right = novum.parse(path), novum.parse(path)
        self.assertEqual(novum.inspect_design(left), novum.inspect_design(right))
        self.assertEqual(left.trace, right.trace)
        self.assertIn(("CandidateB", "derives_from", "CandidateA"), left.edges)
        self.assertEqual(left.nodes["Alignment"].status, "reopened")
        self.assertEqual(left.nodes["CandidateB"].status, "stale")
        self.assertEqual(left.trace[-1]["operator"], "reopen")
        self.assertEqual([issue for issue in novum.validate(left) if issue["severity"] == "ERROR"], [])

    def test_export_snapshot(self):
        path = ROOT / "examples/branch-lineage-reopen.novum"
        contract = novum.export_dsc_contract(novum.parse(path), "examples/branch-lineage-reopen.novum")
        expected = json.loads((ROOT / "examples/branch-lineage-reopen.novum-dsc.json").read_text())
        self.assertEqual(contract, expected)
        self.assertEqual(contract["contract"], "novum-dsc/0.1")
        self.assertEqual(contract["provenance"]["exporter_version"], "novum/0.2.0rc1")


if __name__ == "__main__":
    unittest.main()
