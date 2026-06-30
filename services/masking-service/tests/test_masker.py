"""Unit tests for the Masker — no external dependencies."""

import pytest

from app.masker import Masker


def test_mask_returns_stable_token():
    m = Masker()
    t1 = m.mask("inc-1", "user", "john.doe")
    t2 = m.mask("inc-1", "user", "john.doe")
    assert t1 == t2


def test_different_incidents_produce_different_tokens():
    m = Masker()
    t1 = m.mask("inc-1", "user", "john.doe")
    t2 = m.mask("inc-2", "user", "john.doe")
    assert t1 != t2


def test_unmask_round_trip():
    m = Masker()
    plaintext = "192.168.1.100"
    token = m.mask("inc-3", "ip", plaintext)
    assert m.unmask("inc-3", token) == plaintext


def test_unmask_unknown_token_returns_none():
    m = Masker()
    assert m.unmask("inc-x", "nosuchtoken") is None


def test_delete_map_clears_reverse_map():
    m = Masker()
    token = m.mask("inc-4", "host", "dc01.corp")
    m.delete_map("inc-4")
    assert m.unmask("inc-4", token) is None


def test_token_prefix_by_kind():
    m = Masker()
    assert m.mask("inc-5", "user", "alice").startswith("user_")
    assert m.mask("inc-5", "host", "server1").startswith("host_")
    assert m.mask("inc-5", "ip", "10.0.0.1").startswith("ip_")


def test_empty_plaintext_passthrough():
    m = Masker()
    assert m.mask("inc-6", "user", "") == ""
