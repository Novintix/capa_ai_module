# Document Ingestion Agent

## Purpose
Universal document processing agent that extracts text and structured data from various document types with advanced LLM-powered structuring and embedded image OCR capabilities.

## Agent Type
Hybrid agent combining deterministic document processing with LLM-enhanced intelligent structuring.

## Supported Formats
- **PDF**: .pdf (text extraction + metadata + embedded image OCR)
- **Word**: .docx, .doc (text + tables + structure + embedded image OCR)
- **Excel**: .xlsx, .xls (text + structured data per sheet)
- **Images**: .jpg, .jpeg, .png, .bmp, .tiff, .tif (OCR via Azure Vision)

## Advanced Features
- **LLM Structuring**: Uses AWS Bedrock to intelligently convert extracted text into structured JSON
- **Embedded Image OCR**: Extracts and processes images within PDF/Word documents using Azure Vision
- **Document Type Detection**: Automatically detects FMEA, Policy, SOP, Report formats for optimal structuring
- **Semantic Analysis**: Identifies document sections, tables, key data relationships

## Extraction Modes
- **text_only**: Extract only text content
- **structured**: Extract structured data (tables, metadata, formatting)
- **both**: Extract both text and structured data (default)

## Flow
1. **Initialize**: Set up state
2. **Detect Type**: Validate file and detect document type
3. **Extract Content**: Extract based on type and mode
4. **Process Images**: Extract and OCR embedded images (PDF/Word only)
5. **Structure with LLM**: Convert text to intelligent JSON structure (optional)
6. **Finalize**: Return comprehensive result

## Input
```json
{
  "document_id": "DOC001",
  "file_path": "path/to/document.pdf",
  "extraction_mode": "both",
  "include_metadata": true,
  "use_llm_structuring": true
}
```

## Output
```json
{
  "document_id": "DOC001",
  "file_metadata": {
    "file_name": "document.pdf",
    "file_size": 1024000,
    "document_type": "pdf",
    "created_time": 1640995200.0
  },
  "extracted_text": "Document content...",
  "structured_data": {...},
  "llm_structured_data": {
    "document_type": "fmea",
    "title": "Process FMEA",
    "sections": [...],
    "tables": [...],
    "processing_metadata": {...}
  },
  "ocr_data": {
    "total_images": 3,
    "images_with_text": 2,
    "ocr_results": [...]
  },
  "success": true,
  "processing_time": 8.5
}
```

## LLM Structuring Capabilities
- **FMEA Documents**: Structures into standard FMEA format with process steps, failure modes, causes, effects
- **Policy Documents**: Organizes into sections, requirements, procedures, definitions
- **SOP Documents**: Structures into step-by-step procedures with responsibilities
- **General Documents**: Creates semantic sections, tables, key data extraction
- **Fallback Structure**: Basic structure when LLM processing fails

## Configuration
- **Azure Vision API** (for OCR): Set `AZURE_VISION_KEY` and `AZURE_VISION_ENDPOINT`
- **AWS Bedrock** (for LLM structuring): Configured via `config/aws_bedrock_config.py`
- **PyMuPDF**: Required for PDF embedded image extraction

## Dependencies
```
PyMuPDF  # PDF image extraction
azure-cognitiveservices-vision-computervision  # OCR
boto3  # AWS Bedrock
sentence-transformers  # Document type detection
```

## Logging
Logs to: `Agents/logs/ingestion.log`

## Error Handling
- Graceful fallbacks when LLM structuring fails
- Continues processing even if embedded image OCR fails
- Comprehensive error reporting with processing metadata
- Maintains document processing pipeline integrity