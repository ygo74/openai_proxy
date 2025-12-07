#!/usr/bin/env python
"""Test script for rate limit CLI commands."""
import subprocess
import sys
import json

def run_command(cmd):
    """Run a command and return output."""
    print(f"\n{'='*60}")
    print(f"Running: {cmd}")
    print('='*60)
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(f"STDERR: {result.stderr}", file=sys.stderr)
    print(f"Exit code: {result.returncode}")
    return result.returncode, result.stdout, result.stderr

def main():
    """Test rate limit CLI commands."""
    print("Testing Rate Limit CLI Commands")
    print("="*60)

    # Test 1: List rate limits
    print("\n### Test 1: List all rate limits")
    run_command("rag-client rate-limit list")

    # Test 2: Create model rate limit
    print("\n### Test 2: Create model rate limit for model 5")
    windows = json.dumps([{
        "from_time": "00:00:00",
        "to_time": "23:59:59",
        "max_requests": 500,
        "max_tokens": 50000
    }])
    run_command(f"rag-client rate-limit create-model --model-id 5 --windows '{windows}'")

    # Test 3: Show specific rate limit
    print("\n### Test 3: Show rate limit for model 5")
    run_command("rag-client rate-limit show --scope-type model --scope-id 5")

    # Test 4: Update rate limit (disable)
    print("\n### Test 4: Update rate limit - disable")
    run_command("rag-client rate-limit update --scope-type model --scope-id 5 --enabled false")

    # Test 5: Show after update
    print("\n### Test 5: Show rate limit after update")
    run_command("rag-client rate-limit show --scope-type model --scope-id 5")

    # Test 6: Update rate limit (enable)
    print("\n### Test 6: Update rate limit - enable")
    run_command("rag-client rate-limit update --scope-type model --scope-id 5 --enabled true")

    # Test 7: Delete rate limit
    print("\n### Test 7: Delete rate limit")
    run_command("rag-client rate-limit delete --scope-type model --scope-id 5")

    # Test 8: List after delete
    print("\n### Test 8: List rate limits after delete")
    run_command("rag-client rate-limit list")

    print("\n" + "="*60)
    print("All tests completed!")
    print("="*60)

if __name__ == "__main__":
    main()
