"""
Azure OCR Extractor Tool
Extracts text from images using Azure Computer Vision OCR.
"""

import os
from typing import Optional
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from msrest.authentication import CognitiveServicesCredentials
import time


def extract_text_from_image(file_path: str) -> Optional[str]:
    """
    Extract text from image using Azure Computer Vision OCR.
    
    Args:
        file_path: Path to image file (jpg, png, bmp, etc.)
        
    Returns:
        Extracted text as string, or None if extraction fails
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If Azure credentials not configured
        Exception: If OCR fails
        
    Environment Variables Required:
        AZURE_VISION_KEY: Azure Computer Vision API key
        AZURE_VISION_ENDPOINT: Azure Computer Vision endpoint URL
    """
    
    # Get Azure credentials from environment
    subscription_key = os.getenv("AZURE_VISION_KEY")
    endpoint = os.getenv("AZURE_VISION_ENDPOINT")
    
    if not subscription_key or not endpoint:
        raise ValueError(
            "Azure Computer Vision credentials not configured. "
            "Set AZURE_VISION_KEY and AZURE_VISION_ENDPOINT environment variables."
        )
    
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Image file not found: {file_path}")
        
        # Create Computer Vision client
        credentials = CognitiveServicesCredentials(subscription_key)
        client = ComputerVisionClient(endpoint, credentials)
        
        # Open image file
        with open(file_path, "rb") as image_stream:
            # Call Azure OCR API (Read API)
            read_operation = client.read_in_stream(image_stream, raw=True)
        
        # Get operation location (URL with operation ID)
        operation_location = read_operation.headers["Operation-Location"]
        operation_id = operation_location.split("/")[-1]
        
        # Wait for the operation to complete
        max_retries = 10
        retry_count = 0
        
        while retry_count < max_retries:
            result = client.get_read_result(operation_id)
            
            if result.status not in [OperationStatusCodes.running, OperationStatusCodes.not_started]:
                break
            
            time.sleep(1)
            retry_count += 1
        
        # Check if operation succeeded
        if result.status != OperationStatusCodes.succeeded:
            raise Exception(f"OCR operation failed with status: {result.status}")
        
        # Extract text from results
        text_parts = []
        
        if result.analyze_result and result.analyze_result.read_results:
            for read_result in result.analyze_result.read_results:
                for line in read_result.lines:
                    text_parts.append(line.text)
        
        full_text = "\n".join(text_parts)
        
        if not full_text.strip():
            return None
        
        return full_text
        
    except FileNotFoundError:
        raise
    except ValueError:
        raise
    except Exception as e:
        raise Exception(f"Failed to extract text from image using Azure OCR: {str(e)}")


def extract_text_from_image_batch(file_paths: list) -> dict:
    """
    Extract text from multiple images using Azure OCR.
    
    Args:
        file_paths: List of image file paths
        
    Returns:
        Dict mapping file paths to extracted text
    """
    
    results = {}
    
    for file_path in file_paths:
        try:
            text = extract_text_from_image(file_path)
            results[file_path] = text
        except Exception as e:
            results[file_path] = None
            print(f"Error processing {file_path}: {str(e)}")
    
    return results
