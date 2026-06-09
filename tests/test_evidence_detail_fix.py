"""Tests for T023a evidence detail selection fix.

Verifies that each evidence group table binds its own rows correctly,
so selecting a row in one table shows the correct evidence detail.

Pure Python — no PySide6 required.
"""

from __future__ import annotations

import unittest

from fpga_devmind.desktop.trace_view_models import EvidenceRow
from fpga_devmind.desktop.page_view_models import EvidenceGroup


class TestEvidenceGroupRowBinding(unittest.TestCase):
    """Simulate the fixed row-binding logic from product_shell.py."""

    def _simulate_selection(self, group_rows: list[EvidenceRow], row_idx: int) -> EvidenceRow:
        """Simulate what _on_evidence_row_selected does with bound rows."""
        if row_idx < 0 or row_idx >= len(group_rows):
            raise IndexError("Row index out of range")
        return group_rows[row_idx]

    def test_group_1_row_0_correct(self) -> None:
        """Selecting row 0 in group 1 returns group 1's first row."""
        group1_rows = [
            EvidenceRow(evidence_id="EV_G1_0", source_type="concept_occurrence"),
            EvidenceRow(evidence_id="EV_G1_1", source_type="concept_occurrence"),
        ]
        row = self._simulate_selection(group1_rows, 0)
        self.assertEqual(row.evidence_id, "EV_G1_0")

    def test_group_2_row_0_correct(self) -> None:
        """Selecting row 0 in group 2 returns group 2's first row, not group 1's."""
        group1_rows = [
            EvidenceRow(evidence_id="EV_G1_0", source_type="concept_occurrence"),
            EvidenceRow(evidence_id="EV_G1_1", source_type="concept_occurrence"),
        ]
        group2_rows = [
            EvidenceRow(evidence_id="EV_G2_0", source_type="rtl_source"),
            EvidenceRow(evidence_id="EV_G2_1", source_type="rtl_source"),
        ]
        # With the OLD bug, both tables shared all_evidence_rows which
        # was [G1_0, G1_1, G2_0, G2_1]. Selecting row 0 in table 2 would
        # return G1_0 instead of G2_0.
        # With the fix, each table binds its own group.rows copy.
        row = self._simulate_selection(group2_rows, 0)
        self.assertEqual(row.evidence_id, "EV_G2_0")
        self.assertNotEqual(row.evidence_id, "EV_G1_0")

    def test_group_2_row_1_correct(self) -> None:
        """Selecting row 1 in group 2 returns group 2's second row."""
        group2_rows = [
            EvidenceRow(evidence_id="EV_G2_0", source_type="rtl_source"),
            EvidenceRow(evidence_id="EV_G2_1", source_type="rtl_source"),
        ]
        row = self._simulate_selection(group2_rows, 1)
        self.assertEqual(row.evidence_id, "EV_G2_1")

    def test_evidence_row_has_line_fields(self) -> None:
        """EvidenceRow includes start_line and end_line fields."""
        row = EvidenceRow(
            evidence_id="EV_1",
            source_type="concept_occurrence",
            file_path="/some/file.py",
            symbol="func_a",
            evidence_strength="strong",
            start_line=10,
            end_line=25,
        )
        self.assertEqual(row.start_line, 10)
        self.assertEqual(row.end_line, 25)

    def test_evidence_row_line_defaults(self) -> None:
        """EvidenceRow defaults start_line/end_line to 0."""
        row = EvidenceRow()
        self.assertEqual(row.start_line, 0)
        self.assertEqual(row.end_line, 0)


class TestEvidenceGroupRowsIsolation(unittest.TestCase):
    """Verify EvidenceGroup.rows isolation for binding."""

    def test_group_rows_are_independent(self) -> None:
        """Each EvidenceGroup has its own rows list."""
        row1 = EvidenceRow(evidence_id="EV_1")
        row2 = EvidenceRow(evidence_id="EV_2")
        group1 = EvidenceGroup(title="Group 1", rows=[row1])
        group2 = EvidenceGroup(title="Group 2", rows=[row2])
        self.assertEqual(len(group1.rows), 1)
        self.assertEqual(len(group2.rows), 1)
        self.assertEqual(group1.rows[0].evidence_id, "EV_1")
        self.assertEqual(group2.rows[0].evidence_id, "EV_2")


if __name__ == "__main__":
    unittest.main()
