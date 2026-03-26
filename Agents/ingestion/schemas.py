"""
Document Ingestion Agent Schemas
Input/Output data models
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum


class DocumentType(str, Enum):
    """Supported document types"""
    PDF = "pdf"
    WORD = "word"
    EXCEL = "excel"
    CSV = "csv"
    IMAGE = "image"
    UNKNOWN = "unknown"


class ExtractionMode(str, Enum):
    """Extraction modes"""
    TEXT_ONLY = "text_only"
    STRUCTURED = "structured"
    BOTH = "both"


class DocumentInput(BaseModel):
    """Input for document ingestion"""
    document_id: str = Field(..., description="Unique document identifier")
    file_path: str = Field(..., description="Path to document file")
    extraction_mode: ExtractionMode = Field(default=ExtractionMode.BOTH, description="Type of extraction to perform")
    include_metadata: bool = Field(default=True, description="Whether to include file metadata")
    use_llm_structuring: bool = Field(default=True, description="Whether to use LLM for intelligent structuring")


class FileMetadata(BaseModel):
    """File metadata information"""
    file_name: str = Field(..., description="Name of the file")
    file_size: int = Field(..., description="File size in bytes")
    file_extension: str = Field(..., description="File extension")
    document_type: DocumentType = Field(..., description="Detected document type")
    created_time: Optional[float] = Field(None, description="File creation timestamp")
    modified_time: Optional[float] = Field(None, description="File modification timestamp")
    absolute_path: str = Field(..., description="Absolute file path")


class ExtractionResult(BaseModel):
    """Result of document extraction"""
    document_id: str = Field(..., description="Document identifier")
    file_metadata: FileMetadata = Field(..., description="File metadata")
    extracted_text: Optional[str] = Field(None, description="Extracted text content")
    structured_data: Optional[Dict[str, Any]] = Field(None, description="Structured data extraction")
    llm_structured_data: Optional[Dict[str, Any]] = Field(None, description="LLM-enhanced structured data")
    ocr_data: Optional[Dict[str, Any]] = Field(None, description="OCR results from embedded images")
    extraction_mode: ExtractionMode = Field(..., description="Extraction mode used")
    success: bool = Field(..., description="Whether extraction was successful")
    error_message: Optional[str] = Field(None, description="Error message if extraction failed")
    processing_time: float = Field(..., description="Processing time in seconds")


class BatchDocumentInput(BaseModel):
    """Input for batch document processing"""
    batch_id: str = Field(..., description="Unique batch identifier")
    file_paths: List[str] = Field(..., description="List of file paths to process")
    extraction_mode: ExtractionMode = Field(default=ExtractionMode.BOTH, description="Type of extraction to perform")
    include_metadata: bool = Field(default=True, description="Whether to include file metadata")
    use_llm_structuring: bool = Field(default=True, description="Whether to use LLM for intelligent structuring")


class BatchExtractionResult(BaseModel):
    """Result of batch document extraction"""
    batch_id: str = Field(..., description="Batch identifier")
    results: List[ExtractionResult] = Field(..., description="List of extraction results")
    total_documents: int = Field(..., description="Total number of documents processed")
    successful_extractions: int = Field(..., description="Number of successful extractions")
    failed_extractions: int = Field(..., description="Number of failed extractions")
    total_processing_time: float = Field(..., description="Total processing time in seconds")


class MessyIngestInput(BaseModel):
    """Input for messy/varied JSON ingestion"""
    source_system: str = Field(default="unknown", description="System of origin (ERP, CRM, etc.)")
    payload: Dict[str, Any] = Field(..., description="The raw, unformatted JSON data")
    priority_hint: Optional[str] = Field(None, description="Optional manual priority level")