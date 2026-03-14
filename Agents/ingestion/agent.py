"""
Document Ingestion Agent
Main agent class for extracting content from various document types
"""

import time
from typing import Dict, Any, List

from .graph import create_ingestion_graph
from .schemas import DocumentInput, ExtractionResult, FileMetadata, DocumentType, BatchDocumentInput, BatchExtractionResult
from .logger import log_error

class DocumentIngestionAgent:
    """
    Document Ingestion Agent using LangGraph
    
    Responsibilities:
    - Detect document type (PDF, Word, Excel, Image)
    - Extract text content from documents
    - Extract structured data from documents
    - Handle batch processing
    - Provide file metadata
    
    Supported formats:
    - PDF: .pdf
    - Word: .docx, .doc
    - Excel: .xlsx, .xls
    - Images: .jpg, .jpeg, .png, .bmp, .tiff, .tif
    """

    def __init__(self):
        """Initialize the document ingestion agent"""
        self.graph = create_ingestion_graph()
    
    def process_document(self, document_input: DocumentInput) -> Dict[str, Any]:
        """
        Process single document and extract content
        
        Args:
            document_input: Document input data
            
        Returns:
            Dictionary with extraction results
        """
        
        try:
            # Prepare initial state
            initial_state = {
                "document_id": document_input.document_id,
                "file_path": document_input.file_path,
                "extraction_mode": document_input.extraction_mode.value,
                "include_metadata": document_input.include_metadata,
                "use_llm_structuring": document_input.use_llm_structuring
            }
            
            # Run graph
            final_state = self.graph.invoke(initial_state)
            
            # Build file metadata
            file_metadata = final_state.get("file_metadata", {})
            if file_metadata:
                file_metadata_obj = FileMetadata(
                    file_name=file_metadata.get("file_name", ""),
                    file_size=file_metadata.get("file_size", 0),
                    file_extension=file_metadata.get("file_extension", ""),
                    document_type=DocumentType(file_metadata.get("document_type", "unknown")),
                    created_time=file_metadata.get("created_time"),
                    modified_time=file_metadata.get("modified_time"),
                    absolute_path=file_metadata.get("absolute_path", "")
                )
            else:
                # Minimal metadata if extraction failed
                file_metadata_obj = FileMetadata(
                    file_name=document_input.file_path.split("/")[-1],
                    file_size=0,
                    file_extension="",
                    document_type=DocumentType.UNKNOWN,
                    absolute_path=document_input.file_path
                )
            
            # Build result
            result = {
                "document_id": final_state.get("document_id"),
                "file_metadata": file_metadata_obj.dict(),
                "extracted_text": final_state.get("extracted_text"),
                "structured_data": final_state.get("structured_data"),
                "llm_structured_data": final_state.get("llm_structured_data"),
                "ocr_data": final_state.get("ocr_data"),
                "extraction_mode": document_input.extraction_mode.value,
                "success": final_state.get("success", False),
                "error_message": final_state.get("error_message"),
                "processing_time": final_state.get("processing_time", 0.0)
            }
            
            return result
            
        except Exception as e:
            log_error("process_document", str(e))
            return {
                "document_id": document_input.document_id,
                "file_metadata": FileMetadata(
                    file_name=document_input.file_path.split("/")[-1],
                    file_size=0,
                    file_extension="",
                    document_type=DocumentType.UNKNOWN,
                    absolute_path=document_input.file_path
                ).dict(),
                "extracted_text": None,
                "structured_data": None,
                "llm_structured_data": None,
                "ocr_data": None,
                "extraction_mode": document_input.extraction_mode.value,
                "success": False,
                "error_message": f"Agent error: {str(e)}",
                "processing_time": 0.0
            }
    
    def process_batch(self, batch_input: BatchDocumentInput) -> Dict[str, Any]:
        """
        Process multiple documents in batch
        
        Args:
            batch_input: Batch input data
            
        Returns:
            Dictionary with batch extraction results
        """
        
        start_time = time.time()
        results = []
        successful_count = 0
        failed_count = 0
        
        for i, file_path in enumerate(batch_input.file_paths):
            # Create individual document input
            doc_input = DocumentInput(
                document_id=f"{batch_input.batch_id}_doc_{i+1:03d}",
                file_path=file_path,
                extraction_mode=batch_input.extraction_mode,
                include_metadata=batch_input.include_metadata,
                use_llm_structuring=batch_input.use_llm_structuring
            )
            
            # Process document
            result = self.process_document(doc_input)
            results.append(result)
            
            # Count success/failure
            if result["success"]:
                successful_count += 1
            else:
                failed_count += 1
        
        total_processing_time = time.time() - start_time
        
        return {
            "batch_id": batch_input.batch_id,
            "results": results,
            "total_documents": len(batch_input.file_paths),
            "successful_extractions": successful_count,
            "failed_extractions": failed_count,
            "total_processing_time": total_processing_time
        }