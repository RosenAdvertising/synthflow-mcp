#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

CONFIG_DIR = Path.home() / ".synthflow-mcp"


def main():
    print("Synthflow MCP Setup")
    print("Get your API key at: https://app.synthflow.ai → Settings → API")
    print()
    api_key = input("Paste your Synthflow API key: ").strip()
    if not api_key:
        print("Error: API key cannot be empty.")
        sys.exit(1)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.chmod(0o700)
    env_file = CONFIG_DIR / ".env"
    # Credentials are stored in a chmod-0600 file. A pluggable OS-keyring backend
    # (macOS Keychain / Windows Credential Manager / Linux Secret Service) is being
    # evaluated as optional hardening; see the "pluggable OS-keyring" MCP task.
    with open(env_file, "w") as f:
        f.write(f"SYNTHFLOW_API_KEY={api_key}\n")
    os.chmod(env_file, 0o600)
    print(f"\nSaved to {env_file}")
    print("Running verification...")
    result = subprocess.run(["synthflow-mcp-verify"])
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
