"""
tools/image_extractor.py

Extracts text from image files using Azure Computer Vision OCR.

Supported: .jpg .jpeg .png .bmp .tiff .gif

Installation:
    pip install azure-cognitiveservices-vision-computervision msrest pillow

Environment variables required (.env file):
    AZURE_VISION_KEY      = your_azure_vision_key
    AZURE_VISION_ENDPOINT = https://your-resource.cognitiveservices.azure.com/
"""

import os
import io
import time
import logging
from typing import Optional

from PIL import Image
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from msrest.authentication import CognitiveServicesCredentials

logger = logging.getLogger("effectiveness_agent")

# Max retries waiting for Azure OCR operation to complete
MAX_POLL_ATTEMPTS = 15
POLL_INTERVAL_SEC = 1


def extract_text_from_image(file_path: str) -> Optional[str]:
    """
    Extract text from an image file using Azure Computer Vision OCR.

    Args:
        file_path : path to image file (.jpg, .jpeg, .png, .bmp, .tiff)

    Returns:
        Extracted text as string, or None if nothing detected

    Raises:
        FileNotFoundError : if file does not exist
        ValueError        : if Azure credentials are not set in environment
        Exception         : if OCR operation fails
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Image file not found: {file_path}")

    # ── Load Azure credentials from environment ───────────────────────────────
    subscription_key = os.getenv("AZURE_VISION_KEY")
    endpoint         = os.getenv("AZURE_VISION_ENDPOINT")

    if not subscription_key or not endpoint:
        raise ValueError(
            "Azure Computer Vision credentials not configured. "
            "Add these to your .env file:\n"
            "  AZURE_VISION_KEY      = your_key\n"
            "  AZURE_VISION_ENDPOINT = https://your-resource.cognitiveservices.azure.com/"
        )

    logger.info(f"[IMAGE EXTRACTOR] Starting Azure OCR | File: {file_path}")

    try:
        # ── Step 1: Init Azure client ─────────────────────────────────────────
        client = ComputerVisionClient(
            endpoint,
            CognitiveServicesCredentials(subscription_key)
        )

        # ── Step 2: Preprocess image ──────────────────────────────────────────
        image_bytes = _preprocess(file_path)

        # ── Step 3: Submit OCR job ────────────────────────────────────────────
        logger.info("[IMAGE EXTRACTOR] Submitting image to Azure OCR...")
        read_op      = client.read_in_stream(
            io.BytesIO(image_bytes),
            raw=True
        )
        operation_id = read_op.headers["Operation-Location"].split("/")[-1]
        logger.info(f"[IMAGE EXTRACTOR] Operation ID: {operation_id}")

        # ── Step 4: Poll for result ───────────────────────────────────────────
        result = None
        for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
            result = client.get_read_result(operation_id)
            logger.info(
                f"[IMAGE EXTRACTOR] Poll {attempt}/{MAX_POLL_ATTEMPTS} "
                f"— Status: {result.status}"
            )

            if result.status not in [
                OperationStatusCodes.running,
                OperationStatusCodes.not_started
            ]:
                break

            time.sleep(POLL_INTERVAL_SEC)

        # ── Step 5: Check final status ────────────────────────────────────────
        if result.status != OperationStatusCodes.succeeded:
            raise Exception(
                f"Azure OCR operation failed. "
                f"Final status: {result.status}"
            )

        # ── Step 6: Parse extracted text ──────────────────────────────────────
        text_lines = []

        if result.analyze_result and result.analyze_result.read_results:
            for read_result in result.analyze_result.read_results:
                for line in read_result.lines:
                    if line.text and line.text.strip():
                        text_lines.append(line.text.strip())

        extracted = "\n".join(text_lines)

        if not extracted.strip():
            logger.warning(
                "[IMAGE EXTRACTOR] Azure OCR returned no text. "
                "Check image quality."
            )
            return None

        logger.info(
            f"[IMAGE EXTRACTOR] Azure OCR complete | "
            f"Extracted {len(text_lines)} lines | {len(extracted)} chars"
        )
        return extracted

    except (FileNotFoundError, ValueError):
        raise

    except Exception as e:
        logger.error(f"[IMAGE EXTRACTOR] Azure OCR failed: {str(e)}")
        raise Exception(f"Failed to extract text from image: {str(e)}")


def _preprocess(file_path: str) -> bytes:
    """
    Preprocess image and return as bytes for Azure API submission.

    Steps:
      1. Open image with PIL
      2. Convert to RGB (Azure handles RGB best)
      3. Return as JPEG bytes

    Returns:
      Image as bytes ready for Azure API
    """
    image = Image.open(file_path)

    # Convert to RGB if needed
    if image.mode not in ("RGB",):
        image = image.convert("RGB")

    # Return as bytes
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=95)
    buffer.seek(0)
    return buffer.read()