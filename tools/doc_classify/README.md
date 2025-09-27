# Document Classification Tool

This tool uses OpenAI-compatible LLMs (including Gemma models) to classify PDF documents into predefined categories.

## Features

- Process single PDFs or entire folders of documents
- Convert PDFs to images for models that can only process images (like Gemma)
- Customizable categories defined in a JSON file
- Output results in JSON format with confidence scores and explanations

## Requirements

```bash
pip install openai pymupdf pillow
```

## Usage

### Classify a single document

```bash
python doc_classify.py --file path/to/document.pdf --categories categories.json
```

### Classify all documents in a folder

```bash
python doc_classify.py --folder path/to/documents/ --categories categories.json
```

### Save results to a file

```bash
python doc_classify.py --file path/to/document.pdf --categories categories.json --output results.json
```

### Using a different model

```bash
python doc_classify.py --file path/to/document.pdf --categories categories.json --model gemini-1.5-pro
```

### Using a different API endpoint

```bash
python doc_classify.py --file path/to/document.pdf --categories categories.json --proxy-url http://your-proxy:8000
```

## Categories JSON format

The categories JSON file should be a dictionary where keys are category names and values are descriptions:

```json
{
  "Invoice": "Financial document requesting payment...",
  "Contract": "Legal document outlining an agreement...",
  "Resume": "Professional document summarizing..."
}
```

## Output format

The tool outputs results in the following JSON format:

```json
[
  {
    "category": "Invoice",
    "confidence": 95,
    "explanation": "The document contains line items, pricing information...",
    "document": "path/to/document.pdf"
  }
]
```

## Using with Gemma

The tool is designed to work with models that can only process images (like Gemma) by converting PDFs to images before classification. Make sure your OpenAI-compatible proxy supports the model you want to use.