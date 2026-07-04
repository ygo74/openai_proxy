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


class DocumentExtraction:
    """Document classifier using LLM through OpenAI API."""

    def __init__(
        self,
        client: OpenAI,
        model: str = "gpt-4o",
        max_tokens: int = 1000,
        temperature: float = 0.0
    ):
        """Initialize the document classifier.

        Args:
            client: OpenAI client instance
            model: Model name to use for classification
            max_tokens: Maximum tokens for the response
            temperature: Temperature for response generation
        """
        self.client = client
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.system_prompt = self._build_system_prompt()


    def _build_system_prompt(self) -> str:
        """Build system prompt with category definitions.

        Returns:
            str: System prompt with category descriptions
        """
        prompt = (
            "You are an OCR extraction assistant."
        )

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
            temp_dir = tempfile.mkdtemp(prefix="doc_extraction_")

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

    def extract_content(self, document_path: str) -> Dict[str, Any]:
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
        image_path = image_paths[2]
        print(f"Using image for classification: {image_path}")
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
                        "text": "Perform OCR and return markdown with bounding boxes annotations."
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
                temperature=self.temperature
            )

            # Parse the response
            response_text = response.output_text
            print(f"Response from API: {response_text}")
            print(response)

            # Clean up temporary image files
            for path in image_paths:
                try:
                    print(f"Removing temporary file: {path}")
                    # os.remove(path)
                except Exception as e:
                    logger.warning(f"Failed to remove temporary file {path}: {e}")

            return response.to_dict()

        except Exception as e:
            logger.error(f"Classification error: {e}")
            return {
                "document": document_path,
                "error": str(e),
                "category": "ERROR",
                "confidence": 0,
                "explanation": f"Failed to classify: {e}"
            }


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Document classification using LLM")

    # Document source (file or folder)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to a PDF document to classify")

    # API and model configuration
    parser.add_argument("--model", default="gpt-4o", help="Model name for classification")
    parser.add_argument("--proxy-url", default="http://localhost:8000", help="OpenAI API proxy URL")
    parser.add_argument("--api-key", default="", help="API key")
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

        # Initialize document classifier
        extractor = DocumentExtraction(
            client=client,
            model=args.model,
            max_tokens=args.max_tokens,
            temperature=args.temperature
        )

        # Process documents
        results = extractor.extract_content(args.file)
        print(results)

        return 0

    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())