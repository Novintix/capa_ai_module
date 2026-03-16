"""
Image Processing for Embedded Images
Extracts and processes images embedded in documents
"""

import os
import io
import base64
from PIL import Image
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from msrest.authentication import CognitiveServicesCredentials
import time
from typing import List, Dict, Any


def extract_images_from_pdf(file_path: str) -> List[Dict[str, Any]]:
    """
    Extract embedded images from PDF
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        List of extracted images with metadata
    """
    try:
        import fitz  # PyMuPDF
        
        doc = fitz.open(file_path)
        images = []
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            image_list = page.get_images()
            
            for img_index, img in enumerate(image_list):
                # Extract image
                xref = img[0]
                pix = fitz.Pixmap(doc, xref)
                
                if pix.n - pix.alpha < 4:  # GRAY or RGB
                    img_data = pix.tobytes("png")
                    
                    images.append({
                        "page_number": page_num + 1,
                        "image_index": img_index,
                        "image_data": img_data,
                        "width": pix.width,
                        "height": pix.height,
                        "format": "png"
                    })
                
                pix = None
        
        doc.close()
        return images
        
    except ImportError:
        # Fallback if PyMuPDF not available
        return []
    except Exception as e:
        print(f"Error extracting images from PDF: {str(e)}")
        return []


def extract_images_from_word(file_path: str) -> List[Dict[str, Any]]:
    """
    Extract embedded images from Word document
    
    Args:
        file_path: Path to Word file
        
    Returns:
        List of extracted images with metadata
    """
    try:
        import docx
        from docx.document import Document
        from docx.oxml.table import CT_Tbl
        from docx.oxml.text.paragraph import CT_P
        from docx.table import _Cell, Table
        from docx.text.paragraph import Paragraph
        
        doc = docx.Document(file_path)
        images = []
        
        # Extract images from document relationships
        for rel in doc.part.rels.values():
            if "image" in rel.target_ref:
                img_data = rel.target_part.blob
                
                images.append({
                    "relationship_id": rel.rId,
                    "image_data": img_data,
                    "target_ref": rel.target_ref,
                    "format": rel.target_ref.split('.')[-1] if '.' in rel.target_ref else "unknown"
                })
        
        return images
        
    except Exception as e:
        print(f"Error extracting images from Word: {str(e)}")
        return []


def ocr_image_data(image_data: bytes) -> str:
    """
    Perform OCR on image data using Azure Vision
    
    Args:
        image_data: Raw image bytes
        
    Returns:
        Extracted text from image
    """
    try:
        # Get Azure credentials
        subscription_key = os.getenv("AZURE_VISION_KEY")
        endpoint = os.getenv("AZURE_VISION_ENDPOINT")
        
        if not subscription_key or not endpoint:
            return ""
        
        # Initialize client
        computervision_client = ComputerVisionClient(
            endpoint, 
            CognitiveServicesCredentials(subscription_key)
        )
        
        # Create image stream
        image_stream = io.BytesIO(image_data)
        
        # Read image
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
        print(f"Error performing OCR: {str(e)}")
        return ""


def process_embedded_images(file_path: str, document_type: str) -> Dict[str, Any]:
    """
    Extract and OCR all embedded images from document
    
    Args:
        file_path: Path to document
        document_type: Type of document (pdf, word)
        
    Returns:
        Dictionary with OCR results from all images
    """
    try:
        images = []
        
        if document_type == "pdf":
            images = extract_images_from_pdf(file_path)
        elif document_type == "word":
            images = extract_images_from_word(file_path)
        
        # Perform OCR on each image
        ocr_results = []
        for i, img in enumerate(images):
            ocr_text = ocr_image_data(img["image_data"])
            
            if ocr_text.strip():
                ocr_results.append({
                    "image_index": i,
                    "ocr_text": ocr_text,
                    "metadata": {k: v for k, v in img.items() if k != "image_data"}
                })
        
        return {
            "total_images": len(images),
            "images_with_text": len(ocr_results),
            "ocr_results": ocr_results
        }
        
    except Exception as e:
        return {
            "total_images": 0,
            "images_with_text": 0,
            "ocr_results": [],
            "error": str(e)
        }