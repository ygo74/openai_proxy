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

    def _extract_page(self, image_path: str, page_index: int) -> Dict[str, Any]:
        """Extract OCR text for a single page image.

        Args:
            image_path: Path to page image
            page_index: Zero-based page index

        Returns:
            Dict[str, Any]: Extraction result for the page
        """
        image_b64: str = self.image_to_base64(image_path)
        input_content: List[Dict[str, Any]] = [
            {
                "role": "system",
                "content": self.system_prompt
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"Perform OCR for page {page_index + 1} and return raw markdown text only."
                    },
                    {
                        "type": "input_image",
                        "image_url": image_b64,
                        "detail": "high"
                    }
                ]
            }
        ]
        try:
            response = self.client.responses.parse(
                model=self.model,
                input=input_content,
                max_output_tokens=self.max_tokens,
                temperature=self.temperature
            )
            page_text: str = response.output_text
            return {
                "page_index": page_index,
                "text": page_text
            }
        except Exception as e:
            logger.error(f"OCR error on page {page_index}: {e}")
            return {
                "page_index": page_index,
                "error": str(e),
                "text": ""
            }

    def extract_content(
        self,
        document_path: str,
        start_page: int = 0,
        end_page: Optional[int] = None,
        max_pages: Optional[int] = None
    ) -> Dict[str, Any]:
        """Extract OCR content for all (or a slice of) pages of a PDF.

        Args:
            document_path: Path to PDF file
            start_page: First page index (0-based) to process
            end_page: Inclusive last page index (0-based). If None, process until last.
            max_pages: Hard cap on number of pages processed (applied after slicing)

        Returns:
            Dict[str, Any]: Aggregated extraction result
        """
        logger.info(f"Extracting document: {document_path}")
        image_paths: List[str] = self.convert_pdf_to_images(document_path)
        total_pages: int = len(image_paths)
        logger.info(f"Document has {total_pages} pages")

        if end_page is None or end_page >= total_pages:
            end_page = total_pages - 1
        if start_page < 0:
            start_page = 0
        if start_page > end_page:
            raise ValueError("start_page cannot be greater than end_page")

        selected_paths: List[str] = image_paths[start_page:end_page + 1]
        if max_pages is not None:
            selected_paths = selected_paths[:max_pages]

        results_per_page: List[Dict[str, Any]] = []
        aggregated_text_parts: List[str] = []

        for local_index, image_path in enumerate(selected_paths):
            page_index: int = start_page + local_index
            logger.debug(f"Processing page {page_index + 1}/{total_pages}: {image_path}")
            page_result: Dict[str, Any] = self._extract_page(image_path, page_index)
            results_per_page.append(page_result)
            if page_result.get("text"):
                aggregated_text_parts.append(f"# Page {page_index + 1}\n{page_result['text'].rstrip()}")

        aggregated_text: str = "\n\n".join(aggregated_text_parts)

        # Cleanup temporary images
        for path in image_paths:
            try:
                logger.debug(f"Removing temporary file: {path}")
                # os.remove(path)
            except Exception as e:
                logger.warning(f"Failed to remove temporary file {path}: {e}")

        return {
            "document": document_path,
            "page_count": total_pages,
            "processed_pages": len(results_per_page),
            "start_page": start_page,
            "end_page": start_page + len(results_per_page) - 1,
            "pages": results_per_page,
            "aggregated_text": aggregated_text
        }


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Document classification using LLM")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to a PDF document to classify")

    parser.add_argument("--model", default="gpt-4o", help="Model name for classification")
    parser.add_argument("--proxy-url", default="http://localhost:8000", help="OpenAI API proxy URL")
    parser.add_argument("--api-key", default="sk-your-key", help="API key")
    parser.add_argument("--max-tokens", type=int, default=2000, help="Maximum tokens per page response")
    parser.add_argument("--temperature", type=float, default=0.0, help="Temperature")

    # New page range options
    parser.add_argument("--start-page", type=int, default=0, help="Zero-based start page index")
    parser.add_argument("--end-page", type=int, help="Zero-based end page index (inclusive)")
    parser.add_argument("--max-pages", type=int, help="Maximum number of pages to process from the start slice")

    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    return parser.parse_args()

def main() -> int:
    """Main entry point.

    Returns:
        int: Exit code
    """
    args = parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    try:
        base_url: str = f"{args.proxy_url.rstrip('/')}/v1"
        client: OpenAI = OpenAI(
            api_key=args.api_key,
            base_url=base_url,
            max_retries=1
        )
        extractor: DocumentExtraction = DocumentExtraction(
            client=client,
            model=args.model,
            max_tokens=args.max_tokens,
            temperature=args.temperature
        )
        results: Dict[str, Any] = extractor.extract_content(
            document_path=args.file,
            start_page=args.start_page,
            end_page=args.end_page,
            max_pages=args.max_pages
        )
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())