#!/usr/bin/env python3
import subprocess
import sys

from synthflow_mcp import credentials


def main():
    print("Synthflow MCP Setup")
    print("Get your API key at: https://app.synthflow.ai → Settings → API")
    print()
    api_key = input("Paste your Synthflow API key: ").strip()
    if not api_key:
        print("Error: API key cannot be empty.")
        sys.exit(1)
    # Persist through the pluggable store (OS keyring by default).
    backend = credentials.set_secret("SYNTHFLOW_API_KEY", api_key)
    if backend == "keyring":
        print(f"\nSaved to the OS keyring ({credentials.storage_backend()}).")
    else:
        print(f"\nSaved to {credentials.ENV_FILE} (0600).")
    print("Running verification...")
    result = subprocess.run(["synthflow-mcp-verify"])
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
