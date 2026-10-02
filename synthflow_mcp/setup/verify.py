#!/usr/bin/env python3
import logging
import sys


logger = logging.getLogger(__name__)


def main():
    try:
        from synthflow_mcp.client import SynthflowClient

        client = SynthflowClient()
        info = client.who_am_i()
        print("Connected to Synthflow.")
        if isinstance(info, dict):
            name = info.get("name") or info.get("account_name") or info.get("email", "")
            if name:
                print("Account identity verified.")
        print("synthflow-mcp is ready.")
    except Exception:
        logger.warning(
            "Synthflow verification rejected",
            extra={
                "event": "synthflow_verification_rejected",
                "reason": "connection_check_failed",
            },
        )
        print("Error: unable to verify the Synthflow connection.")
        print("Run synthflow-mcp-setup to configure your API key.")
        sys.exit(1)


if __name__ == "__main__":
    main()
