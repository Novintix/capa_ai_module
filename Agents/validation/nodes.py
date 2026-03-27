"""
Validation Agent Nodes
All node functions for the Validation Agent
"""

import json
import os
import re
from typing import Any, Dict, List

from config.aws_bedrock_config import get_llm

from .logger import (
	log_error,
	log_node_entry,
	log_node_exit,
	log_routing_decision,
	log_validation_summary,
)
from .prompt import VALIDATION_SYSTEM_PROMPT, VALIDATION_USER_PROMPT_TEMPLATE
from .state import AgentState
from .tools.excel_extractor import extract_text_from_excel
from .tools.ocr_extractor import extract_text_from_image
from .tools.pdf_extractor import extract_text_from_pdf
from .tools.txt_extractor import extract_text_from_txt
from .tools.word_extractor import extract_text_from_word


SUPPORTED_EVIDENCE_EXTENSIONS = {
	".pdf",
	".docx",
	".doc",
	".xlsx",
	".xls",
	".jpg",
	".jpeg",
	".png",
	".bmp",
	".tif",
	".tiff",
	".txt",
	".log",
	".json",
	".csv",
	".md",
}


def _normalize_text(value: Any) -> str:
	if value is None:
		return ""
	return re.sub(r"\s+", " ", str(value).strip().lower())


def clean_llm_response(response_text: str) -> str:
	"""Clean LLM response by removing reasoning tags and markdown wrappers."""
	if "<reasoning>" in response_text and "</reasoning>" in response_text:
		response_text = re.sub(r"<reasoning>.*?</reasoning>\s*", "", response_text, flags=re.DOTALL).strip()

	response_text = response_text.replace("```json", "").replace("```", "").strip()

	start_idx = response_text.find("{")
	end_idx = response_text.rfind("}")

	if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
		return response_text[start_idx:end_idx + 1]

	raise ValueError("No valid JSON object found in response")


def _flatten_evidence(payload: Any, source: str, prefix: str) -> List[Dict[str, str]]:
	"""Flatten mixed evidence payload (str/list/dict) into records with IDs."""
	records: List[Dict[str, str]] = []

	if payload is None:
		return records

	if isinstance(payload, str):
		if payload.strip():
			records.append({
				"reference_id": prefix,
				"source": source,
				"content": payload.strip(),
			})
		return records

	if isinstance(payload, list):
		for idx, item in enumerate(payload, start=1):
			records.extend(_flatten_evidence(item, source, f"{prefix}.{idx}"))
		return records

	if isinstance(payload, dict):
		record_id = payload.get("reference_id") or payload.get("id")
		text_bits: List[str] = []
		for key, value in payload.items():
			if key in {"reference_id", "id"}:
				continue
			if isinstance(value, (str, int, float)):
				text_bits.append(f"{key}: {value}")
		content = " | ".join(text_bits).strip()
		if content:
			records.append({
				"reference_id": str(record_id or prefix),
				"source": source,
				"content": content,
			})
		return records

	# Fallback for unknown types
	text = str(payload).strip()
	if text:
		records.append({
			"reference_id": prefix,
			"source": source,
			"content": text,
		})
	return records


def _extract_text_from_file(file_path: str) -> str:
	"""Extract text from supported evidence file types."""
	ext = os.path.splitext(file_path)[1].lower()

	if ext == ".pdf":
		return extract_text_from_pdf(file_path) or ""
	if ext in {".docx", ".doc"}:
		return extract_text_from_word(file_path) or ""
	if ext in {".xlsx", ".xls"}:
		return extract_text_from_excel(file_path) or ""
	if ext in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}:
		return extract_text_from_image(file_path) or ""
	if ext in {".txt", ".log", ".json", ".csv", ".md"}:
		if ext == ".txt":
			return extract_text_from_txt(file_path) or ""
		with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
			return file.read()

	raise ValueError(f"Unsupported evidence file type: {ext}")


def _default_evidence_dir() -> str:
	"""Return the built-in evidence directory for validation agent."""
	return os.path.join(os.path.dirname(__file__), "evidence_files")


def _list_default_evidence_files() -> List[str]:
	"""List supported files from validation/evidence_files folder."""
	dir_path = _default_evidence_dir()
	if not os.path.isdir(dir_path):
		return []

	file_paths: List[str] = []
	for name in sorted(os.listdir(dir_path)):
		path = os.path.join(dir_path, name)
		if not os.path.isfile(path):
			continue
		ext = os.path.splitext(path)[1].lower()
		if ext in SUPPORTED_EVIDENCE_EXTENSIONS:
			file_paths.append(path)

	return file_paths


def _to_file_reference_name(path: str) -> str:
	"""Convert a file path to the filename used in output references."""
	return os.path.basename(path.strip())


def _looks_like_file_path(value: str) -> bool:
	"""Heuristic to distinguish likely file paths from plain text evidence."""
	text = value.strip()
	if not text:
		return False

	# Drive-letter path, UNC path, or clear path separators.
	if re.match(r"^[A-Za-z]:[\\/]", text):
		return True
	if text.startswith("\\\\"):
		return True
	if "\\" in text or "/" in text:
		return True

	# File-like token with a supported extension.
	_, ext = os.path.splitext(text)
	return ext.lower() in SUPPORTED_EVIDENCE_EXTENSIONS


def _normalize_reference_to_filename(reference: Any, reference_to_filename: Dict[str, str]) -> str:
	"""Normalize a support reference so file-based references are returned as filenames."""
	ref = str(reference).strip()
	if not ref:
		return ref

	if ref in reference_to_filename:
		return reference_to_filename[ref]

	if _is_file_path(ref):
		return _to_file_reference_name(ref)

	return ref


def _is_file_path(value: Any) -> bool:
	"""Check if a string value points to an existing local file."""
	if not isinstance(value, str):
		return False
	path = value.strip()
	if not path:
		return False
	try:
		return os.path.isfile(path)
	except OSError:
		return False


def _flatten_or_load_file_evidence(payload: Any, source: str, prefix: str) -> List[Dict[str, str]]:
	"""Normalize evidence payloads; load text when payload values are file paths."""
	records: List[Dict[str, str]] = []

	if payload is None:
		return records

	if isinstance(payload, str):
		value = payload.strip()
		if not value:
			return records

		if _is_file_path(value):
			try:
				text = _extract_text_from_file(value)
				if text and text.strip():
					records.append(
						{
							"reference_id": _to_file_reference_name(value),
							"source": source,
							"content": text.strip(),
							"file_path": value,
						}
					)
			except Exception as exc:
				log_error("prepare_evidence", f"Failed to parse evidence file {value}: {exc}")
			return records

		if _looks_like_file_path(value):
			log_error("prepare_evidence", f"Evidence file not found: {value}")
			return records

		records.append(
			{
				"reference_id": prefix,
				"source": source,
				"content": value,
			}
		)
		return records

	if isinstance(payload, list):
		for idx, item in enumerate(payload, start=1):
			records.extend(_flatten_or_load_file_evidence(item, source, f"{prefix}.{idx}"))
		return records

	if isinstance(payload, dict):
		file_path = payload.get("file_path") or payload.get("path")
		if isinstance(file_path, str) and file_path.strip():
			file_path_str = file_path.strip()
			if _is_file_path(file_path_str):
				try:
					text = _extract_text_from_file(file_path_str)
					if text and text.strip():
						records.append(
							{
								"reference_id": _to_file_reference_name(file_path_str),
								"source": source,
								"content": text.strip(),
								"file_path": file_path_str,
							}
						)
				except Exception as exc:
					log_error("prepare_evidence", f"Failed to parse evidence file {file_path_str}: {exc}")
				return records

			if _looks_like_file_path(file_path_str):
				log_error("prepare_evidence", f"Evidence file not found: {file_path_str}")

		# Remove path carrier keys and still keep any inline evidence content in this object.
		filtered_payload = {
			key: value
			for key, value in payload.items()
			if key not in {"file_path", "path"}
		}
		if filtered_payload:
			records.extend(_flatten_evidence(filtered_payload, source, prefix))
		return records

		records.extend(_flatten_evidence(payload, source, prefix))
		return records

	text = str(payload).strip()
	if text:
		records.append(
			{
				"reference_id": prefix,
				"source": source,
				"content": text,
			}
		)

	return records


def initialize_node(state: AgentState) -> AgentState:
	"""Node: Initialize state."""
	log_node_entry("initialize", state)

	updates: AgentState = {
		"iteration": 0,
		"max_iterations": 5,
		"evidence_records": [],
		"file_evidence_records": [],
		"cause_validation_results": [],
		"validated_causes": [],
		"total_input_causes": len(state.get("generated_causes", [])),
		"total_validated_causes": 0,
		"overall_confidence": 0.0,
		"error": None,
		"next_step": "prepare_evidence",
	}

	log_node_exit("initialize", updates)
	return updates


def prepare_evidence_node(state: AgentState) -> AgentState:
	"""Node: Build normalized evidence corpus from all data sources."""
	log_node_entry("prepare_evidence", state)

	try:
		evidence_records: List[Dict[str, str]] = []

		complaint = state.get("complaint_description", "")
		if complaint.strip():
			evidence_records.append(
				{
					"reference_id": "complaint.description",
					"source": "complaint_description",
					"content": complaint.strip(),
				}
			)

		if state.get("question"):
			evidence_records.append(
				{
					"reference_id": "question.original",
					"source": "question",
					"content": str(state.get("question", "")).strip(),
				}
			)

		evidence_records.extend(_flatten_or_load_file_evidence(state.get("logs"), "logs", "logs"))
		evidence_records.extend(_flatten_or_load_file_evidence(state.get("reports"), "reports", "reports"))
		evidence_records.extend(_flatten_or_load_file_evidence(state.get("process_data"), "process_data", "process_data"))
		evidence_records.extend(
			_flatten_or_load_file_evidence(state.get("historical_capa"), "historical_capa", "historical_capa")
		)
		evidence_records.extend(_flatten_or_load_file_evidence(state.get("policies"), "policies", "policies"))
		evidence_records.extend(_flatten_or_load_file_evidence(state.get("sop"), "sop", "sop"))
		evidence_records.extend(
			_flatten_or_load_file_evidence(
				state.get("investigation_records"), "investigation_records", "investigation_records"
			)
		)

		evidence_records.extend(
			_flatten_or_load_file_evidence(
				state.get("investigation_evidence"),
				source="investigation_evidence",
				prefix="investigation",
			)
		)
		evidence_records.extend(
			_flatten_or_load_file_evidence(
				state.get("supporting_system_information"),
				source="supporting_system_information",
				prefix="supporting",
			)
		)

		file_evidence_records = [record for record in evidence_records if record.get("file_path")]

		loaded_file_paths = {
			os.path.normcase(os.path.abspath(str(record.get("file_path"))))
			for record in file_evidence_records
			if record.get("file_path")
		}

		# Always include all files from the agent-level evidence_files folder.
		# This guarantees every cause is validated against the same full file corpus.
		for file_path in _list_default_evidence_files():
			normalized_path = os.path.normcase(os.path.abspath(file_path))
			if normalized_path in loaded_file_paths:
				continue

			try:
				text = _extract_text_from_file(file_path)
				if text and text.strip():
					record = {
						"reference_id": _to_file_reference_name(file_path),
						"source": "evidence_file",
						"content": text.strip(),
						"file_path": file_path,
					}
					evidence_records.append(record)
					file_evidence_records.append(record)
					loaded_file_paths.add(normalized_path)
			except Exception as exc:
				log_error("prepare_evidence", f"Failed to parse evidence file {file_path}: {exc}")

		if not evidence_records:
			updates: AgentState = {
				"error": "No evidence records were provided for validation.",
				"notes": "Provide complaint description or investigation evidence.",
				"next_step": "finalize",
			}
			log_routing_decision("prepare_evidence", "finalize", "No evidence corpus")
			log_node_exit("prepare_evidence", updates)
			return updates

		updates = {
			"evidence_records": evidence_records,
			"file_evidence_records": file_evidence_records,
			"notes": (
				f"Prepared {len(evidence_records)} evidence records "
				f"(including {len(file_evidence_records)} from files) for grounding."
			),
			"next_step": "validate_causes",
		}
		log_routing_decision("prepare_evidence", "validate_causes", "Evidence corpus prepared")
		log_node_exit(
			"prepare_evidence",
			{
				"evidence_count": len(evidence_records),
				"file_evidence_count": len(file_evidence_records),
				"next_step": "validate_causes",
			},
		)
		return updates

	except Exception as exc:
		error_msg = f"Evidence preparation failed: {exc}"
		log_error("prepare_evidence", error_msg)
		updates = {"error": error_msg, "next_step": "finalize"}
		log_routing_decision("prepare_evidence", "finalize", "Exception occurred")
		log_node_exit("prepare_evidence", updates)
		return updates


def validate_causes_node(state: AgentState) -> AgentState:
	"""Node: Validate generated causes against evidence using LLM reasoning."""
	log_node_entry("validate_causes", state)

	try:
		causes = state.get("generated_causes", [])
		if not causes:
			updates = {
				"error": "No generated causes received for validation.",
				"notes": "Input field 'generated_causes' is empty.",
				"next_step": "finalize",
			}
			log_routing_decision("validate_causes", "finalize", "No causes")
			log_node_exit("validate_causes", updates)
			return updates

		evidence_records = state.get("evidence_records", [])
		if not evidence_records:
			updates = {
				"error": "Evidence corpus missing during cause validation.",
				"next_step": "finalize",
			}
			log_routing_decision("validate_causes", "finalize", "No evidence records")
			log_node_exit("validate_causes", updates)
			return updates

		llm = get_llm()

		normalized_results: List[Dict[str, Any]] = []
		allowed_status = {"matched", "partially_matched", "no_evidence"}
		reference_to_filename = {
			str(record.get("reference_id", "")).strip(): _to_file_reference_name(str(record.get("file_path", "")))
			for record in evidence_records
			if record.get("file_path") and str(record.get("reference_id", "")).strip()
		}

		for cause in causes:
			cause_id = str(cause.get("cause_id", "")).strip()
			cause_text = str(cause.get("cause_text", "")).strip()

			single_cause = [{"cause_id": cause_id, "cause_text": cause_text}]
			user_prompt = VALIDATION_USER_PROMPT_TEMPLATE.format(
				complaint_id=state.get("complaint_id") or "N/A",
				question=state.get("question") or "N/A",
				complaint_description=state.get("complaint_description", ""),
				generated_causes_json=json.dumps(single_cause, ensure_ascii=True, indent=2),
				logs_json=json.dumps(state.get("logs"), ensure_ascii=True, indent=2),
				reports_json=json.dumps(state.get("reports"), ensure_ascii=True, indent=2),
				process_data_json=json.dumps(state.get("process_data"), ensure_ascii=True, indent=2),
				historical_capa_json=json.dumps(state.get("historical_capa"), ensure_ascii=True, indent=2),
				policies_json=json.dumps(state.get("policies"), ensure_ascii=True, indent=2),
				sop_json=json.dumps(state.get("sop"), ensure_ascii=True, indent=2),
				investigation_records_json=json.dumps(state.get("investigation_records"), ensure_ascii=True, indent=2),
				supporting_system_information_json=json.dumps(
					state.get("supporting_system_information"), ensure_ascii=True, indent=2
				),
				file_evidence_records_json=json.dumps(state.get("file_evidence_records", []), ensure_ascii=True, indent=2),
				evidence_records_json=json.dumps(evidence_records, ensure_ascii=True, indent=2),
			)

			full_prompt = f"{VALIDATION_SYSTEM_PROMPT}\n\n---\n\n{user_prompt}"

			try:
				response = llm.invoke(full_prompt)
				response_text = clean_llm_response(response.content)
				parsed = json.loads(response_text)

				validation_results = parsed.get("cause_validation_results", [])
				if not isinstance(validation_results, list) or not validation_results:
					raise ValueError("LLM output missing valid 'cause_validation_results' for single-cause validation")

				item = validation_results[0]
				status = str(item.get("evidence_match_status", "no_evidence")).strip().lower().replace(" ", "_")
				if status not in allowed_status:
					status = "no_evidence"

				references = item.get("supporting_evidence_references", [])
				if not isinstance(references, list):
					references = []

				try:
					confidence = float(item.get("confidence", 0.0))
				except (TypeError, ValueError):
					confidence = 0.0
				confidence = max(0.0, min(1.0, confidence))

				if status == "no_evidence":
					references = []
				else:
					references = [
						_normalize_reference_to_filename(ref, reference_to_filename)
						for ref in references
					]
					references = [ref for ref in references if ref]
					references = list(dict.fromkeys(references))

				normalized_results.append(
					{
						"cause_id": cause_id,
						"cause_text": cause_text,
						"evidence_match_status": status,
						"supporting_evidence_references": [str(ref) for ref in references],
						"confidence": round(confidence, 3),
						"rationale": str(item.get("rationale", "Evidence assessment completed.")).strip(),
					}
				)

			except Exception as cause_exc:
				normalized_results.append(
					{
						"cause_id": cause_id,
						"cause_text": cause_text,
						"evidence_match_status": "no_evidence",
						"supporting_evidence_references": [],
						"confidence": 0.0,
						"rationale": f"Validation failed for this cause: {cause_exc}",
					}
				)

		validated_confidences = [
			float(item.get("confidence", 0.0))
			for item in normalized_results
			if item.get("evidence_match_status") in {"matched", "partially_matched"}
		]
		overall_confidence = round(sum(validated_confidences) / len(validated_confidences), 3) if validated_confidences else 0.0

		updates = {
			"cause_validation_results": normalized_results,
			"overall_confidence": overall_confidence,
			"notes": (
				"Validated each cause iteratively against the complete merged evidence corpus."
			),
			"next_step": "filter_validated",
		}
		log_routing_decision("validate_causes", "filter_validated", f"Validated {len(normalized_results)} causes")
		log_node_exit("validate_causes", {"validated_count": len(normalized_results), "next_step": "filter_validated"})
		return updates

	except json.JSONDecodeError as exc:
		error_msg = f"Failed to parse LLM validation response: {exc}"
		log_error("validate_causes", error_msg)
		updates = {"error": error_msg, "next_step": "finalize"}
		log_routing_decision("validate_causes", "finalize", "Invalid LLM JSON")
		log_node_exit("validate_causes", updates)
		return updates

	except Exception as exc:
		error_msg = f"Cause validation failed: {exc}"
		log_error("validate_causes", error_msg)
		updates = {"error": error_msg, "next_step": "finalize"}
		log_routing_decision("validate_causes", "finalize", "Exception occurred")
		log_node_exit("validate_causes", updates)
		return updates


def filter_validated_node(state: AgentState) -> AgentState:
	"""Node: Keep only evidence-grounded causes and compute summary confidence."""
	log_node_entry("filter_validated", state)

	try:
		all_results = state.get("cause_validation_results", [])
		validated = [
			result
			for result in all_results
			if result.get("evidence_match_status") in {"matched", "partially_matched"}
		]

		if validated:
			overall_confidence = state.get("overall_confidence")
			if not isinstance(overall_confidence, (int, float)) or overall_confidence <= 0:
				overall_confidence = round(
					sum(float(item.get("confidence", 0.0)) for item in validated) / len(validated),
					3,
				)
			notes = "Returning causes with grounded supporting evidence."
		else:
			overall_confidence = 0.0
			notes = state.get("notes") or "No generated causes were sufficiently grounded in supplied evidence."

		updates = {
			"validated_causes": validated,
			"total_validated_causes": len(validated),
			"overall_confidence": overall_confidence,
			"notes": notes,
			"next_step": "finalize",
		}

		log_validation_summary(len(all_results), len(validated), overall_confidence)
		log_routing_decision("filter_validated", "finalize", "Validation summary prepared")
		log_node_exit(
			"filter_validated",
			{
				"total_input_causes": len(all_results),
				"total_validated_causes": len(validated),
				"overall_confidence": overall_confidence,
				"next_step": "finalize",
			},
		)
		return updates

	except Exception as exc:
		error_msg = f"Filtering validated causes failed: {exc}"
		log_error("filter_validated", error_msg)
		updates = {"error": error_msg, "next_step": "finalize"}
		log_routing_decision("filter_validated", "finalize", "Exception occurred")
		log_node_exit("filter_validated", updates)
		return updates


def finalize_node(state: AgentState) -> AgentState:
	"""Node: Finalize output."""
	log_node_entry("finalize", state)

	updates = {
		"next_step": "end",
		"iteration": state.get("iteration", 0) + 1,
	}

	log_routing_decision("finalize", "END", "Process complete")
	log_node_exit("finalize", updates)
	return updates
