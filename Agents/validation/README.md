# Validation Agent

## Purpose
Validates generated causes using grounded evidence from complaint and investigation datasets.

## Agent Type
LLM-driven, evidence-grounding agent (Bedrock) with strict JSON output schema.

## Responsibilities
- Accept generated causes from upstream cause generation.
- Build evidence corpus from complaint description, investigation records, logs, test reports, process data, historical CAPA records, and supporting system information.
- Parse evidence files (PDF, Word, Excel, images, txt/log/json/csv/md) using `tools/` extractors.
- Validate each cause with evidence match status:
	- `matched`
	- `partially_matched`
	- `no_evidence`
- Return only evidence-supported causes in `validated_causes`.
- Return per-cause support references and confidence.

## Flow
1. **Initialize**: Prepare default state.
2. **Prepare Evidence**: Normalize evidence into searchable records.
3. **Validate Causes**: Use LLM reasoning with strict prompt constraints to classify each cause.
4. **Filter Validated**: Keep only grounded causes.
5. **Finalize**: Return structured response.

## Input
- `generated_causes`: List of causes from previous agent (`cause_id`, `cause_text`, `process_step`, `failure_mode`, `potential_effects`, `severity`, `occurrence`, `detection`, `current_controls`, `source`).
- `question`: Original why question from cause generation output.
- `complaint_description`: Complaint statement.
- Mapped evidence fields:
	- `logs`
	- `reports`
	- `process_data`
	- `historical_capa`
	- `policies`
	- `sop`
	- `investigation_records`
	- `supporting_system_information`
- For `logs`, `reports`, `process_data`, `historical_capa`, `policies`, `sop`, and `investigation_records`, each field can be:
	- Inline content (string/object/list), or
	- File path string, or
	- List of file path strings.
- Supported file extensions: `.pdf`, `.docx`, `.doc`, `.xlsx`, `.xls`, images, `.txt`, `.log`, `.json`, `.csv`, `.md`.
- `investigation_evidence`: legacy catch-all evidence payload (optional, backward compatible).
- `supporting_system_information`: Additional context from systems.

## Output
- `validated_causes`: Evidence-grounded cause list only.
- `cause_validation_results`: Status for each input cause.
- `evidence_match_status`: `matched` / `partially_matched` / `no_evidence`.
- `supporting_evidence_references`: Evidence IDs used as support.
- `overall_confidence`: Aggregate confidence over validated causes.

## API
- `POST /validation/`
- `GET /validation/health`

## Notes
- This agent uses structured prompts in `prompt.py` and expects strict JSON output.
- `partially_matched` causes are retained for downstream SME review.
- `no_evidence` causes are excluded from `validated_causes`.
