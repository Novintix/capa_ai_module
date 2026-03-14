"""
Image Document Extractor
Extracts text from images using OCR
"""

from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from msrest.authentication import CognitiveServicesCredentials
import os
import time
from typing import Dict, Any


def extract_text_from_image(file_path: str) -> str:
    """
    Extract text from image using Azure OCR
    
    Args:
        file_path: Path to image file
        
    Returns:
        Extracted text as string
    """
    try:
        # Get Azure credentials
        subscription_key = os.getenv("AZURE_VISION_KEY")
        endpoint = os.getenv("AZURE_VISION_ENDPOINT")
        
        if not subscription_key or not endpoint:
            raise Exception("Azure Vision credentials not found in environment variables")
        
        # Initialize client
        computervision_client = ComputerVisionClient(
            endpoint, 
            CognitiveServicesCredentials(subscription_key)
        )
        
        # Read image
        with open(file_path, "rb") as image_stream:
            read_response = computervision_client.read_in_stream(image_stream, raw=True)
        
        # Get operation ID
        read_operation_location = read_response.headers["Operation-Location"]
        operation_id = read_operation_location.split("/")[-1]
        
        # Wait for result
        while True:
            read_result = computervision_client.get_read_result(operation_id)
            if read_result.status not in ['notStarted', 'running']:
                break
            time.sleep(1)
        
        # Extract text
        text_lines = []
        if read_result.status == OperationStatusCodes.succeeded:
            for text_result in read_result.analyze_result.read_results:
                for line in text_result.lines:
                    text_lines.append(line.text)
        
        return "\n".join(text_lines)
        
    except Exception as e:
        raise Exception(f"Failed to extract text from image: {str(e)}")


def extract_structured_from_image(file_path: str) -> Dict[str, Any]:
    """
    Extract structured content from image with bounding boxes
    
    Args:
        file_path: Path to image file
        
    Returns:
        Dictionary with structured OCR results
    """
    try:
        # Get Azure credentials
        subscription_key = os.getenv("AZURE_VISION_KEY")
        endpoint = os.getenv("AZURE_VISION_ENDPOINT")
        
        if not subscription_key or not endpoint:
            raise Exception("Azure Vision credentials not found in environment variables")
        
        # Initialize client
        computervision_client = ComputerVisionClient(
            endpoint, 
            CognitiveServicesCredentials(subscription_key)
        )
        
        # Read image
        with open(file_path, "rb") as image_stream:
            read_response = computervision_client.read_in_stream(image_stream, raw=True)
        
        # Get operation ID
        read_operation_location = read_response.headers["Operation-Location"]
        operation_id = read_operation_location.split("/")[-1]
        
        # Wait for result
        while True:
            read_result = computervision_client.get_read_result(operation_id)
            if read_result.status not in ['notStarted', 'running']:
                break
            time.sleep(1)
        
        # Extract structured data
        pages = []
        if read_result.status == OperationStatusCodes.succeeded:
            for page_result in read_result.analyze_result.read_results:
                lines = []
                for line in page_result.lines:
                    lines.append({
                        "text": line.text,
                        "bounding_box": line.bounding_box,
                        "words": [{"text": word.text, "confidence": word.confidence} for word in line.words]
                    })
                
                pages.append({
                    "page_number": page_result.page,
                    "width": page_result.width,
                    "height": page_result.height,
                    "unit": page_result.unit,
                    "lines": lines,
                    "num_lines": len(lines)
                })
        
        return {
            "pages": pages,
            "num_pages": len(pages),
            "total_lines": sum(page["num_lines"] for page in pages)
        }
        
    except Exception as e:
        raise Exception(f"Failed to extract structured content from image: {str(e)}")