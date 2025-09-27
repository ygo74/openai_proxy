#!/usr/bin/env python3
"""Document Classification Tool using LLM.

This script processes PDF documents, converts them to images, and uses
OpenAI's LLM (compatible with Gemma) to classify them according to
predefined categories from a JSON configuration file.

Usage:
    python doc_classify.py --file path/to/document.pdf --categories categories.json
    python doc_classify.py --folder path/to/documents/ --categories categories.json

Features:
    - Process single PDF file or batch process entire folder
    - Convert PDFs to images (Gemma can only process images)
    - Dynamic category system defined in JSON
    - Customizable system prompt
    - Classification results output in JSON format
"""

import argparse
import base64
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

import openai
from openai import OpenAI, AzureOpenAI

# For PDF to image conversion
import fitz  # PyMuPDF
from PIL import Image
import io
import tempfile
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("doc_classify")

class DocumentClassification(BaseModel):
    category: str
    confidence: int
    explanation: str


class DocumentClassifier:
    """Document classifier using LLM through OpenAI API."""

    def __init__(
        self,
        client: OpenAI,
        categories_path: str,
        model: str = "gpt-4o",
        max_tokens: int = 1000,
        temperature: float = 0.0
    ):
        """Initialize the document classifier.

        Args:
            client: OpenAI client instance
            categories_path: Path to JSON file containing category definitions
            model: Model name to use for classification
            max_tokens: Maximum tokens for the response
            temperature: Temperature for response generation
        """
        self.client = client
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.categories = self._load_categories(categories_path)
        self.system_prompt = self._build_system_prompt()

    def _load_categories(self, categories_path: str) -> Dict[str, str]:
        """Load category definitions from JSON file.

        Args:
            categories_path: Path to JSON file with categories

        Returns:
            Dict[str, str]: Dictionary of category name to description

        Raises:
            FileNotFoundError: If categories file doesn't exist
            json.JSONDecodeError: If categories file has invalid JSON
        """
        try:
            with open(categories_path, 'r', encoding='utf-8') as f:
                categories = json.load(f)

            # Validate categories format
            if not isinstance(categories, dict):
                raise ValueError("Categories JSON must be a dictionary")

            return categories

        except FileNotFoundError:
            logger.error(f"Categories file not found: {categories_path}")
            raise
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in categories file: {categories_path}")
            raise

    def _build_system_prompt(self) -> str:
        """Build system prompt with category definitions.

        Returns:
            str: System prompt with category descriptions
        """
        prompt = (
            "You are an expert document classifier. Examine the provided document image carefully "
            "and classify it into EXACTLY ONE of the following categories. "
            "For each classification, provide a confidence score (0-100) and a brief explanation of your decision.\n\n"
            "Available categories:\n"
        )

        for category, description in self.categories.items():
            prompt += f"- {category}: {description}\n"

        prompt += "\nProvide your response in this format only:\n"
        prompt += "{\n  \"category\": \"<category_name>\",\n  \"confidence\": <score>,\n  \"explanation\": \"<explanation>\"\n}"

        return prompt

    def convert_pdf_to_images(self, pdf_path: str) -> List[str]:
        """Convert PDF document to a list of image paths.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            List[str]: List of paths to temporary image files

        Raises:
            FileNotFoundError: If PDF file doesn't exist
            ValueError: If PDF conversion fails
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        try:
            # Open the PDF
            pdf = fitz.open(pdf_path)
            image_paths = []

            # Create temporary directory for images
            temp_dir = tempfile.mkdtemp(prefix="doc_classify_")

            # Convert each page to an image
            for page_num in range(len(pdf)):
                page = pdf.load_page(page_num)
                pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))

                # Save the image
                image_path = os.path.join(temp_dir, f"page_{page_num}.png")
                pix.save(image_path)
                image_paths.append(image_path)

            return image_paths

        except Exception as e:
            logger.error(f"Error converting PDF to images: {e}")
            raise ValueError(f"PDF conversion failed: {e}")

    def image_to_base64(self, image_path: str) -> str:
        """Convert image to base64 string for API request.

        Args:
            image_path: Path to the image file

        Returns:
            str: Base64-encoded image with data URL prefix
        """
        with open(image_path, "rb") as f:
            image_data = f.read()

        b64_encoded = base64.b64encode(image_data).decode("utf-8")
        mime_type = "image/png"  # Assuming PNG format

        return f"data:{mime_type};base64,{b64_encoded}"

    def classify_document(self, document_path: str) -> Dict[str, Any]:
        """Classify a single document.

        Args:
            document_path: Path to the document (PDF)

        Returns:
            Dict[str, Any]: Classification result with category, confidence, and explanation
        """
        logger.info(f"Classifying document: {document_path}")

        # Convert PDF to images
        image_paths = self.convert_pdf_to_images(document_path)
        logger.info(f"Converted PDF to {len(image_paths)} images")

        # Use only the first page for classification to save on API costs
        # This can be modified to process more pages if needed
        image_path = image_paths[0]
        image_b64 = self.image_to_base64(image_path)

        # Create input content for the LLM
        input_content = [
            {
                "role": "system",
                "content": self.system_prompt
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "Classify this document into one of the predefined categories."
                    },
                    {
                        "type": "input_image",
                        "image_url": image_b64,
                        "detail": "high"
                    }
                ]
            }
        ]

        # Make API request
        try:
            response = self.client.responses.parse(
                model=self.model,
                input=input_content,
                max_output_tokens=self.max_tokens,
                temperature=self.temperature,
                text_format=DocumentClassification
            )

            # Parse the response
            response_text = response.output_text
            print(f"Response from API: {response_text}")
            print(response)
            classification_result = json.loads(response.output_text)

            # Clean up temporary image files
            for path in image_paths:
                try:
                    os.remove(path)
                except Exception as e:
                    logger.warning(f"Failed to remove temporary file {path}: {e}")

            # Add document path to result
            classification_result["document"] = document_path

            return classification_result

        except Exception as e:
            logger.error(f"Classification error: {e}")
            return {
                "document": document_path,
                "error": str(e),
                "category": "ERROR",
                "confidence": 0,
                "explanation": f"Failed to classify: {e}"
            }

    def classify_folder(self, folder_path: str) -> List[Dict[str, Any]]:
        """Classify all PDF documents in a folder.

        Args:
            folder_path: Path to folder containing PDF documents

        Returns:
            List[Dict[str, Any]]: List of classification results
        """
        if not os.path.exists(folder_path):
            raise FileNotFoundError(f"Folder not found: {folder_path}")

        logger.info(f"Processing folder: {folder_path}")
        results = []

        # Find all PDF files in the folder
        pdf_files = [
            os.path.join(folder_path, f)
            for f in os.listdir(folder_path)
            if f.lower().endswith(".pdf") and os.path.isfile(os.path.join(folder_path, f))
        ]

        if not pdf_files:
            logger.warning(f"No PDF files found in {folder_path}")
            return results

        logger.info(f"Found {len(pdf_files)} PDF files to process")

        # Process each PDF
        for pdf_file in pdf_files:
            result = self.classify_document(pdf_file)
            results.append(result)

        return results


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Document classification using LLM")

    # Document source (file or folder)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to a PDF document to classify")
    group.add_argument("--folder", help="Path to a folder containing PDF documents to classify")

    # Categories and output
    parser.add_argument("--categories", required=True, help="Path to JSON file with category definitions")
    parser.add_argument("--output", help="Path to save classification results (JSON)")

    # API and model configuration
    parser.add_argument("--model", default="gpt-4o", help="Model name for classification")
    parser.add_argument("--proxy-url", default="http://localhost:8000", help="OpenAI API proxy URL")
    parser.add_argument("--api-key", default="sk-16AwYoZqNoVKjfMz-Mr8TeuaXk3O6JeLwPdQSAQiF0s", help="API key")
    parser.add_argument("--max-tokens", type=int, default=1000, help="Maximum tokens for response")
    parser.add_argument("--temperature", type=float, default=0.0, help="Temperature for response generation")

    # Debug options
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    return parser.parse_args()


def main() -> int:
    """Main entry point.

    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    args = parse_args()

    # Set log level
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    try:
        # Initialize OpenAI client
        base_url = f"{args.proxy_url.rstrip('/')}/v1"
        client = OpenAI(
            api_key=args.api_key,
            base_url=base_url,
            max_retries=1
        )

        # client = AzureOpenAI(
        #     azure_endpoint="XXX",
        #     api_key="XXXX",
        #     api_version="2024-08-01-preview"
        # )

        # Initialize document classifier
        classifier = DocumentClassifier(
            client=client,
            categories_path=args.categories,
            model=args.model,
            max_tokens=args.max_tokens,
            temperature=args.temperature
        )

        # Process documents
        if args.file:
            results = [classifier.classify_document(args.file)]
        else:  # args.folder
            results = classifier.classify_folder(args.folder)

        # Display results
        for result in results:
            doc_name = os.path.basename(result["document"])
            if "error" in result:
                logger.error(f"{doc_name}: ERROR - {result['error']}")
            else:
                logger.info(f"{doc_name}: {result['category']} (confidence: {result['confidence']}%)")
                logger.debug(f"Explanation: {result['explanation']}")

        # Save results if output path provided
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2)
            logger.info(f"Results saved to {args.output}")

        return 0

    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())