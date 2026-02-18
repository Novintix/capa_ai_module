from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional
import json
from Agents.occurrence.state import ComplaintData, OccurrenceOutput
from Agents.occurrence.graph import occurrence_graph
from Agents.occurrence.utils import MetricsParser
from Agents.occurrence.prompts import load_metrics

router = APIRouter()


@router.post("/analyze", response_model=OccurrenceOutput)
async def analyze_occurrence(
    complaint_id: str = Form(...),
    description: str = Form(...),
    source: str = Form(...),
    date: str = Form(...),
    product: str = Form(...),
    additional_context: Optional[str] = Form(None),
    similar_cases_json: Optional[str] = Form(None),
    metrics_file: Optional[UploadFile] = File(None),
    data_file: Optional[UploadFile] = File(None)
):
    """
    Analyze the occurrence of a complaint/failure mode.

    Accepts:
    - Form Data: complaint details.
    - similar_cases_json: Optional JSON string of similar cases list.
    - metrics_file: Optional metrics definition file (JSON). Overrides default metrics.json.
    - data_file: Optional historical data file (Excel, CSV, PDF, Docx) appended as context.

    Returns:
    - Weighted Occurrence Score (1-10) with rating and parameter breakdown.
    """
    try:
        # 1. Parse similar cases from JSON string
        parsed_similar_cases = []
        if similar_cases_json:
            try:
                parsed_similar_cases = json.loads(similar_cases_json)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON format for similar_cases_json")

        # 2. Parse metrics file (JSON only — defines the scoring rubric)
        metrics_data_str = None
        if metrics_file:
            raw = await metrics_file.read()
            try:
                # Validate it's valid JSON and re-serialize
                parsed_metrics = json.loads(raw.decode("utf-8"))
                metrics_data_str = json.dumps(parsed_metrics)
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail=f"metrics_file must be a valid JSON file. Got: {metrics_file.filename}"
                )

        # 3. Parse data file (Excel, CSV, PDF, Docx) as additional context
        parsed_context_from_file = ""
        if data_file:
            file_content = await MetricsParser.parse_file(data_file)
            parsed_context_from_file = (
                f"\n\n--- HISTORICAL DATA FILE ({data_file.filename}) ---\n"
                f"{file_content}\n"
                f"--------------------------------------------------\n"
            )

        # 4. Combine context
        full_context = (additional_context or "") + parsed_context_from_file

        # 5. Build input state
        input_data = ComplaintData(
            complaint_id=complaint_id,
            description=description,
            source=source,
            date=date,
            product=product,
            similar_cases=parsed_similar_cases,
            additional_context=full_context,
            metrics_data=metrics_data_str  # None = use default metrics.json
        )

        initial_state = {"input": input_data}

        # 6. Invoke Graph
        result = occurrence_graph.invoke(initial_state)
        final_output = result.get("final_output")

        if not final_output:
            raise ValueError("Agent failed to produce a final output.")

        return final_output

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing occurrence analysis: {str(e)}")
