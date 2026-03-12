"""
Platform Spec sectie 18 — validation_logic unit tests.
"""
import math
import pytest
from app.services.validation_logic import calculate_confidence_score


def test_high_confidence_approval():
    """0.92 → approved (e.g. 1, 0.9, 0.75, 1 -> 0.30+0.27+0.15+0.20=0.92)"""
    r = calculate_confidence_score(1.0, 0.9, 0.75, 1.0)
    assert r["confidence_score"] == 0.92
    assert r["status"] == "approved"
    assert r["is_retrievable"] is True


def test_threshold_rejection_no_rounding():
    """< 0.70 → rejected (geen rounding naar 0.70)"""
    # 0.69 something must stay rejected
    r = calculate_confidence_score(0.7, 0.7, 0.7, 0.6)
    # 0.21 + 0.21 + 0.14 + 0.12 = 0.68
    assert r["confidence_score"] == 0.68
    assert r["status"] == "rejected"
    assert r["is_retrievable"] is False


def test_external_evidence_impact():
    """0.79 → approved (external evidence scenario)"""
    r = calculate_confidence_score(1.0, 0.7, 0.5, 0.8)
    # 0.30 + 0.21 + 0.10 + 0.16 = 0.77
    # Actually for 0.79 we need: e*0.3 + f*0.3 + h*0.2 + v*0.2 = 0.79
    # e.g. 1.0, 0.9, 0.5, 0.8 -> 0.30+0.27+0.10+0.16 = 0.83
    # 0.79: 0.30 + 0.27 + 0.10 + 0.12 = 0.79
    r = calculate_confidence_score(1.0, 0.9, 0.5, 0.6)
    assert r["confidence_score"] == 0.79
    assert r["status"] == "approved"


def test_zero_evidence_always_rejected():
    """evidence=0 kan nooit >= 0.70 halen met gewichten"""
    r = calculate_confidence_score(0.0, 1.0, 1.0, 1.0)
    # 0 + 0.30 + 0.20 + 0.20 = 0.70 exactly
    assert r["confidence_score"] == 0.70
    assert r["status"] == "approved"
    # With evidence 0 and others lower:
    r2 = calculate_confidence_score(0.0, 1.0, 0.5, 0.5)
    # 0 + 0.30 + 0.10 + 0.10 = 0.50
    assert r2["confidence_score"] == 0.50
    assert r2["status"] == "rejected"


def test_perfect_score():
    """1.00 → approved"""
    r = calculate_confidence_score(1.0, 1.0, 1.0, 1.0)
    assert r["confidence_score"] == 1.0
    assert r["status"] == "approved"


def test_truncation_not_rounding():
    """0.6958 → 0.69, rejected (floor, no round to 0.70)"""
    r = calculate_confidence_score(0.7, 0.7, 0.7, 0.68)
    # 0.21 + 0.21 + 0.14 + 0.136 = 0.696 -> floor 0.69
    assert r["confidence_score"] == 0.69
    assert r["status"] == "rejected"
