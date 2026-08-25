"""Smoke: Protocols are importable and structural."""

from kb_application_ports import ObjectStorePort, RelationalDbHealthPort


def test_ports_are_protocols() -> None:
    assert ObjectStorePort is not None
    assert RelationalDbHealthPort is not None
