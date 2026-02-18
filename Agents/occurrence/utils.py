import pandas as pd
import json
import io
from fastapi import UploadFile
import PyPDF2
from docx import Document

class MetricsParser:
    @staticmethod
    async def parse_file(file: UploadFile) -> str:
        """
        Parses text/data from an uploaded file (JSON, Excel, CSV, PDF, Docx).
        Returns a string representation of the data.
        """
        content = await file.read()
        filename = file.filename.lower()
        
        try:
            if filename.endswith(".json"):
                data = json.loads(content)
                return json.dumps(data, indent=2)
                
            elif filename.endswith(".csv"):
                df = pd.read_csv(io.BytesIO(content))
                return df.to_markdown(index=False)
                
            elif filename.endswith(".xlsx") or filename.endswith(".xls"):
                df = pd.read_excel(io.BytesIO(content))
                return df.to_markdown(index=False)
                
            elif filename.endswith(".pdf"):
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text
                
            elif filename.endswith(".docx"):
                doc = Document(io.BytesIO(content))
                text = "\n".join([para.text for para in doc.paragraphs])
                return text
                
            elif filename.endswith(".txt"):
                return content.decode("utf-8")
                
            # TODO: Add Image OCR support if needed (requires Azure or Vision Model)
            elif filename.endswith((".png", ".jpg", ".jpeg")):
                return f"[Image File Provided: {filename} - Content Extraction Not Implemented without OCR Service]"
                
            else:
                return f"[Unsupported file format: {filename}]"
                
        except Exception as e:
            return f"Error parsing file {filename}: {str(e)}"
