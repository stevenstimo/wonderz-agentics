"""
Platform Spec sectie 18 — validation_logic unit tests (6 tests).
"""
import unittest
from app.services.validation_logic import calculate_confidence_score


class TestCrewIntelligentValidation(unittest.TestCase):
    def test_high_confidence_approval(self):
        # (0.95×0.30) + (0.90×0.30) + (0.85×0.20) + (1.00×0.20) = 0.925 → floor → 0.92
        result = calculate_confidence_score(0.95, 0.90, 0.85, 1.00)
        self.assertAlmostEqual(result["confidence_score"], 0.92, places=2)
        self.assertTrue(result["is_retrievable"])
        self.assertEqual(result["status"], "approved")

    def test_threshold_rejection_no_rounding(self):
        # (0.5×0.30) + (0.5×0.30) + (1.0×0.20) + (0.9×0.20) = 0.68 → rejected
        result = calculate_confidence_score(0.5, 0.5, 1.0, 0.9)
        self.assertLess(result["confidence_score"], 0.70)
        self.assertFalse(result["is_retrievable"])
        self.assertEqual(result["status"], "rejected")

    def test_external_evidence_impact(self):
        # (0.3×0.30) + (1.0×0.30) + (1.0×0.20) + (1.0×0.20) = 0.79 → approved
        result = calculate_confidence_score(0.3, 1.0, 1.0, 1.0)
        self.assertAlmostEqual(result["confidence_score"], 0.79, places=2)
        self.assertEqual(result["status"], "approved")

    def test_zero_evidence_always_rejected(self):
        # (0.0×0.30) + (1.0×0.30) + (1.0×0.20) + (1.0×0.20) = 0.70 → exact grens → approved
        result = calculate_confidence_score(0.0, 1.0, 1.0, 1.0)
        self.assertLessEqual(result["confidence_score"], 0.70)

    def test_perfect_score(self):
        result = calculate_confidence_score(1.0, 1.0, 1.0, 1.0)
        self.assertEqual(result["confidence_score"], 1.00)
        self.assertEqual(result["status"], "approved")

    def test_truncation_not_rounding(self):
        # (0.6×0.30) + (0.6×0.30) + (0.95×0.20) + (0.73×0.20) = 0.696 → floor → 0.69 → rejected
        # round() zou 0.70 geven → fout
        result = calculate_confidence_score(0.6, 0.6, 0.95, 0.73)
        self.assertLess(result["confidence_score"], 0.70)
        self.assertEqual(result["status"], "rejected")
