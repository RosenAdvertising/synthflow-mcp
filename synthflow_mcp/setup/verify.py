#!/usr/bin/env python3
import sys


def main():
    try:
        from synthflow_mcp.client import SynthflowClient

        client = SynthflowClient()
        info = client.who_am_i()
        print("Connected to Synthflow.")
        if isinstance(info, dict):
            name = info.get("name") or info.get("account_name") or info.get("email", "")
            if name:
                print(f"Account: {name}")
        print("synthflow-mcp is ready.")
    except Exception as e:
        print(f"Error: {e}")
        print("Run synthflow-mcp-setup to configure your API key.")
        sys.exit(1)


if __name__ == "__main__":
    main()
