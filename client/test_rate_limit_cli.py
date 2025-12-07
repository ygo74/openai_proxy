"""Test rate limit CLI commands."""
import subprocess
import sys


def run_command(cmd: list[str]) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        shell=False
    )
    return result.returncode, result.stdout, result.stderr


def test_rate_limit_help():
    """Test rate-limit help command."""
    print("\n=== Testing rate-limit help ===")
    exit_code, stdout, stderr = run_command([
        sys.executable,
        "rag-client.py",
        "rate-limit",
        "--help"
    ])

    if exit_code != 0:
        print(f"❌ FAILED: Exit code {exit_code}")
        print(f"STDERR: {stderr}")
        return False

    # Check that expected commands are in the help output
    expected_commands = [
        "list",
        "show",
        "create-global",
        "create-model",
        "create-group-model",
        "update",
        "delete"
    ]

    for cmd in expected_commands:
        if cmd not in stdout:
            print(f"❌ FAILED: Command '{cmd}' not found in help")
            return False

    print("✅ PASSED: All expected commands found")
    print(stdout)
    return True


def test_rate_limit_list_help():
    """Test rate-limit list help command."""
    print("\n=== Testing rate-limit list help ===")
    exit_code, stdout, stderr = run_command([
        sys.executable,
        "rag-client.py",
        "rate-limit",
        "list",
        "--help"
    ])

    if exit_code != 0:
        print(f"❌ FAILED: Exit code {exit_code}")
        print(f"STDERR: {stderr}")
        return False

    # Check for expected arguments
    if "--skip" not in stdout or "--limit" not in stdout:
        print(f"❌ FAILED: Expected arguments not found")
        return False

    print("✅ PASSED: List command help is correct")
    print(stdout)
    return True


def test_rate_limit_create_global_help():
    """Test rate-limit create-global help command."""
    print("\n=== Testing rate-limit create-global help ===")
    exit_code, stdout, stderr = run_command([
        sys.executable,
        "rag-client.py",
        "rate-limit",
        "create-global",
        "--help"
    ])

    if exit_code != 0:
        print(f"❌ FAILED: Exit code {exit_code}")
        print(f"STDERR: {stderr}")
        return False

    # Check for expected arguments
    if "--windows" not in stdout:
        print(f"❌ FAILED: --windows argument not found")
        return False

    print("✅ PASSED: Create-global command help is correct")
    print(stdout)
    return True


if __name__ == "__main__":
    print("Testing Rate Limit CLI Commands")
    print("=" * 50)

    tests = [
        test_rate_limit_help,
        test_rate_limit_list_help,
        test_rate_limit_create_global_help
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ EXCEPTION: {e}")
            failed += 1

    print("\n" + "=" * 50)
    print(f"Results: {passed} passed, {failed} failed")

    sys.exit(0 if failed == 0 else 1)
