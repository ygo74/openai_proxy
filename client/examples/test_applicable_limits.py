"""Example script demonstrating the get_applicable_limits() method.

This script shows how to use the management client to query hierarchical
rate limits for debugging and testing purposes.
"""
import sys
import os

# Add client to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ygo74.fastapi_openai_rag_client.core.client import ApiClient
from ygo74.fastapi_openai_rag_client.core.auth import AuthContext


def print_separator():
    """Print a visual separator."""
    print("\n" + "="*80 + "\n")


def print_limits(title: str, result: dict):
    """Pretty print rate limit query results.

    Args:
        title: Title to display
        result: Result dictionary from get_applicable_limits()
    """
    print(f"🔍 {title}")
    print(f"   Group ID: {result.get('group_id', 'None')}")
    print(f"   Model ID: {result.get('model_id', 'None')}")
    print()

    # Group+Model limit
    if result.get('group_model_limit'):
        limit = result['group_model_limit']
        print(f"   ✓ Group+Model Limit (team-a:gpt-4)")
        print(f"     Enabled: {limit['enabled']}")
        for w in limit['windows']:
            print(f"     Window: {w['from_time']} - {w['to_time']}")
            print(f"       Max Requests: {w['max_requests']}")
            print(f"       Max Tokens: {w['max_tokens']}")
    else:
        print(f"   ✗ Group+Model Limit: Not configured")
    print()

    # Model limit
    if result.get('model_limit'):
        limit = result['model_limit']
        print(f"   ✓ Model Limit (gpt-4)")
        print(f"     Enabled: {limit['enabled']}")
        for w in limit['windows']:
            print(f"     Window: {w['from_time']} - {w['to_time']}")
            print(f"       Max Requests: {w['max_requests']}")
            print(f"       Max Tokens: {w['max_tokens']}")
    else:
        print(f"   ✗ Model Limit: Not configured")
    print()

    # Global limit
    if result.get('global_limit'):
        limit = result['global_limit']
        print(f"   ✓ Global Limit")
        print(f"     Enabled: {limit['enabled']}")
        for w in limit['windows']:
            print(f"     Window: {w['from_time']} - {w['to_time']}")
            print(f"       Max Requests: {w['max_requests']}")
            print(f"       Max Tokens: {w['max_tokens']}")
    else:
        print(f"   ✗ Global Limit: Not configured")
    print()

    # Effective limit
    if result.get('effective_limit'):
        limit = result['effective_limit']
        print(f"   🎯 EFFECTIVE LIMIT: {limit['scope_type']}")
        print(f"      This is the limit that will be enforced!")
        for w in limit['windows']:
            print(f"      Max Requests: {w['max_requests']}")
            print(f"      Max Tokens: {w['max_tokens']}")
    else:
        print(f"   ⚠️  No effective limit: All requests allowed")


def main():
    """Demonstrate get_applicable_limits() usage."""

    print_separator()
    print("📊 Rate Limit Hierarchy Query Demo")
    print_separator()

    # Initialize API client
    auth = AuthContext(
        api_url=os.getenv("RAG_API_URL", "http://localhost:8000"),
        api_key=os.getenv("RAG_API_KEY")
    )

    client = ApiClient(auth)

    try:
        # Example 1: Query with both group and model
        print("Example 1: Full Hierarchy Query")
        print("Command: client.get_applicable_limits(group_id='team-a', model_id='gpt-4')")
        result = client.get_applicable_limits(group_id="team-a", model_id="gpt-4")
        print_limits("Query for team-a using gpt-4", result)

        print_separator()

        # Example 2: Query with only model (no group)
        print("Example 2: Model + Global Query (skip group+model)")
        print("Command: client.get_applicable_limits(model_id='gpt-4')")
        result = client.get_applicable_limits(model_id="gpt-4")
        print_limits("Query for any group using gpt-4", result)

        print_separator()

        # Example 3: Query global only
        print("Example 3: Global Only Query")
        print("Command: client.get_applicable_limits()")
        result = client.get_applicable_limits()
        print_limits("Query for global limits only", result)

        print_separator()

        print("✅ Demo completed successfully!")
        print("\nUse cases for this API:")
        print("  • Debug rate limit configuration")
        print("  • Test hierarchical priority before production")
        print("  • Understand which limit applies to specific requests")
        print("  • Validate changes after updating limits")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nMake sure:")
        print("  • API server is running (http://localhost:8000)")
        print("  • You have admin credentials configured")
        print("  • Rate limits are configured in the database")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
