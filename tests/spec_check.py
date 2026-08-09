#!/usr/bin/env python3
"""Offline guard for the MCP protocol revision used by synthflow-mcp."""

from __future__ import annotations

import argparse

from mcp.types import LATEST_PROTOCOL_VERSION


EXPECTED_MCP_PROTOCOL_VERSION = "2026-07-28"


def check_mcp_revision() -> tuple[bool, str]:
    """Return whether the installed SDK still targets the migrated revision."""
    actual = LATEST_PROTOCOL_VERSION
    if actual == EXPECTED_MCP_PROTOCOL_VERSION:
        return True, f"MCP protocol: {actual}"
    return (
        False,
        f"expected {EXPECTED_MCP_PROTOCOL_VERSION!r}, got {actual!r}",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mcp-only",
        action="store_true",
        help="Check only the installed MCP protocol revision.",
    )
    parser.parse_args()

    passed, detail = check_mcp_revision()
    print(f"Spec check: {'PASS' if passed else 'FAIL'}")
    print(detail)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
