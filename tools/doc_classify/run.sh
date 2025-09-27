#!/bin/bash
# Simple script to run the document classifier with default settings

# Default values
MODEL="gpt-4o"
PROXY_URL="http://localhost:8000"
API_KEY="sk-16AwYoZqNoVKjfMz-Mr8TeuaXk3O6JeLwPdQSAQiF0s"
CATEGORIES="categories.json"

# Check if Python is available
if ! command -v python &> /dev/null; then
    echo "Error: Python is not installed or not in PATH"
    exit 1
fi

# Check if the doc_classify.py script exists
if [ ! -f "doc_classify.py" ]; then
    echo "Error: doc_classify.py not found in current directory"
    exit 1
fi

# Check if categories.json exists
if [ ! -f "$CATEGORIES" ]; then
    echo "Error: $CATEGORIES not found in current directory"
    exit 1
fi

# Display usage if no arguments provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 [--file document.pdf | --folder documents/]"
    echo "Optional arguments:"
    echo "  --output results.json    Save results to JSON file"
    echo "  --model model_name       Specify a different model (default: $MODEL)"
    echo "  --verbose                Enable verbose logging"
    exit 1
fi

# Run the script with provided arguments
python doc_classify.py --proxy-url "$PROXY_URL" --api-key "$API_KEY" --model "$MODEL" --categories "$CATEGORIES" "$@"