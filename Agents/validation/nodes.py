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
	logger,
)
from .tools.semantic_retriever import build_evidence_index, retrieve_relevant_chunks
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

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_AGENT_BASE_DIR = _THIS_DIR
_PROJECT_ROOT_DIR = os.path.dirname(os.path.dirname(_THIS_DIR))


def _normalize_text(value: Any) -> str:
	if value is None:
		return ""
	return re.sub(r"\s+", " ", str(value).strip().lower())


def _coerce_optional_int(value: Any) -> Any:
	"""Coerce optional numeric score fields to int when possible."""
	if value is None:
		return None
	if isinstance(value, str) and not value.strip():
		return None
	try:
		return int(value)
	except (TypeError, ValueError):
		return None


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


def _to_file_reference_name(path: str) -> str:
	"""Convert a file path to the filename used in output references."""
	return os.path.basename(path.strip())


def _looks_like_file_path(value: str) -> bool:
	"""Return True only for strings that are clearly filesystem paths (not plain text).

	Only matches drive-letter paths (C:\\...), UNC paths (\\\\server\\...), or
	strings whose file extension is a supported evidence type. Plain text that
	happens to contain '/' or '\\' (e.g. 'temp 50/100°C') is intentionally NOT
	matched so it is kept as text evidence.
	"""
	text = value.strip()
	if not text:
		return False

	# Drive-letter path (C:\ or C:/)
	if re.match(r"^[A-Za-z]:[/\\]", text):
		return True
	# UNC path
	if text.startswith("\\\\"):
		return True

	# Bare filename / relative path with a recognised evidence extension
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


def _resolve_existing_file_path(value: str) -> str | None:
	"""Resolve an input path to an existing file.

	Supports:
	- absolute paths
	- workspace-relative paths (e.g. Agents\\validation\\evidence_files\\file.txt)
	- validation-agent-relative paths (e.g. evidence_files\\file.txt)
	"""
	raw = value.strip().strip('"').strip("'")
	if not raw:
		return None

	normalized = os.path.normpath(raw)
	candidates: List[str] = [normalized]

	if not os.path.isabs(normalized):
		candidates.append(os.path.normpath(os.path.join(os.getcwd(), normalized)))
		candidates.append(os.path.normpath(os.path.join(_PROJECT_ROOT_DIR, normalized)))
		candidates.append(os.path.normpath(os.path.join(_AGENT_BASE_DIR, normalized)))

	seen: set[str] = set()
	for candidate in candidates:
		if candidate in seen:
			continue
		seen.add(candidate)
		try:
			if os.path.isfile(candidate):
				return candidate
		except OSError:
			continue

	return None


def _is_file_path(value: Any) -> bool:
	"""Check if a string value points to an existing local file."""
	if not isinstance(value, str):
		return False
	path = value.strip()
	if not path:
		return False
	return _resolve_existing_file_path(path) is not None


def _flatten_or_load_file_evidence(payload: Any, source: str, prefix: str) -> List[Dict[str, str]]:
	"""Normalize evidence payloads; load text when payload values are file paths."""
	records: List[Dict[str, str]] = []

	if payload is None:
		return records

	if isinstance(payload, str):
		value = payload.strip()
		if not value:
			return records

		resolved_file_path = _resolve_existing_file_path(value)
		if resolved_file_path:
			try:
				text = _extract_text_from_file(resolved_file_path)
				if text and text.strip():
					records.append(
						{
							"reference_id": _to_file_reference_name(value),
							"source": source,
							"content": text.strip(),
							"file_path": resolved_file_path,
						}
					)
			except Exception as exc:
				log_error("prepare_evidence", f"Failed to parse evidence file {value}: {exc}")
			return records

		if _looks_like_file_path(value):
			# Looks like an absolute/relative file path but file does not exist on disk.
			# Skip it — do NOT add the raw path string as evidence text.
			log_error("prepare_evidence", f"Evidence file not found or not accessible: {value}")
			return records

		# Plain text evidence — keep as-is.
		# Strings that contain '/' or '\\' but are NOT path-like (e.g. 'ratio 50/100°C')
		# correctly fall through here because _looks_like_file_path returned False.
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
			resolved_file_path = _resolve_existing_file_path(file_path_str)
			if resolved_file_path:
				try:
					text = _extract_text_from_file(resolved_file_path)
					if text and text.strip():
						records.append(
							{
								"reference_id": _to_file_reference_name(file_path_str),
								"source": source,
								"content": text.strip(),
								"file_path": resolved_file_path,
							}
						)
				except Exception as exc:
					log_error("prepare_evidence", f"Failed to parse evidence file {file_path_str}: {exc}")
				return records

		# Remove path carrier keys and recursively process remaining values so that
		# nested file-path lists (e.g. evidence_files: [...]) are properly loaded.
		for idx, (key, value) in enumerate(
			{k: v for k, v in payload.items() if k not in {"file_path", "path"}}.items(), start=1
		):
			records.extend(_flatten_or_load_file_evidence(value, source, f"{prefix}.{key}"))
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

		# Deduplicate: drop records whose (source, content) pair has already been seen.
		# This prevents the same text appearing twice when evidence is supplied via
		# multiple fields (e.g. investigation_records AND investigation_evidence).
		seen: set = set()
		deduped: List[Dict[str, str]] = []
		for record in evidence_records:
			key = (record.get("source", ""), record.get("content", "")[:300])
			if key not in seen:
				seen.add(key)
				deduped.append(record)
		evidence_records = deduped

		if not evidence_records:
			updates: AgentState = {
				"error": "No evidence records were provided for validation.",
				"notes": "Provide complaint description or investigation evidence.",
				"next_step": "finalize",
			}
			log_routing_decision("prepare_evidence", "finalize", "No evidence corpus")
			log_node_exit("prepare_evidence", updates)
			return updates

		# Build in-memory semantic index: chunk all records and embed them once.
		# Use complaint_id as request_id so concurrent requests never share an index.
		request_id = str(state.get("complaint_id") or "default")
		try:
			chunk_count = build_evidence_index(evidence_records, request_id=request_id)
			logger.info(
				f"[prepare_evidence] Semantic index built: {chunk_count} chunks "
				f"from {len(evidence_records)} records ({len(file_evidence_records)} files)"
			)
		except Exception as idx_exc:
			chunk_count = 0
			log_error("prepare_evidence", f"Semantic indexing failed (non-fatal): {idx_exc}")

		updates = {
			"evidence_records": evidence_records,
			"file_evidence_records": file_evidence_records,
			"evidence_chunk_count": chunk_count,
			"request_id": request_id,
			"notes": (
				f"Prepared {len(evidence_records)} evidence records "
				f"({len(file_evidence_records)} from files, {chunk_count} chunks indexed)."
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
		max_retries = state.get("max_iterations", 5)
		request_id = str(state.get("request_id") or state.get("complaint_id") or "default")

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
			cause_payload = {
				"cause_id": cause_id,
				"cause_text": cause_text,
				"process_step": cause.get("process_step"),
				"failure_mode": cause.get("failure_mode"),
				"potential_effects": cause.get("potential_effects"),
				"severity": _coerce_optional_int(cause.get("severity")),
				"occurrence": _coerce_optional_int(cause.get("occurrence")),
				"detection": _coerce_optional_int(cause.get("detection")),
				"current_controls": cause.get("current_controls"),
				"source": cause.get("source"),
			}

			# Build semantic query: cause text + process step + failure mode
			semantic_query = " ".join(filter(None, [
				cause_text,
				str(cause.get("process_step") or ""),
				str(cause.get("failure_mode") or ""),
			]))

			# Retrieve top-6 semantically relevant evidence chunks for this request
			retrieved_chunks = retrieve_relevant_chunks(semantic_query, request_id=request_id, top_k=6)

			# Fallback: if semantic index empty, surface short non-file records
			if not retrieved_chunks:
				retrieved_chunks = [
					{"reference_id": r["reference_id"], "source": r["source"], "content": r["content"], "similarity_score": 0.0}
					for r in evidence_records
					if not r.get("file_path") and len(r.get("content", "")) < 2000
				][:8]

			logger.info(
				f"[validate_causes] cause={cause_id} query_len={len(semantic_query)} "
				f"retrieved={len(retrieved_chunks)} chunks"
			)

			single_cause = [cause_payload]
			user_prompt = VALIDATION_USER_PROMPT_TEMPLATE.format(
				complaint_id=state.get("complaint_id") or "N/A",
				question=state.get("question") or "N/A",
				complaint_description=state.get("complaint_description", ""),
				generated_causes_json=json.dumps(single_cause, ensure_ascii=True, indent=2),
				retrieved_evidence_json=json.dumps(retrieved_chunks, ensure_ascii=True, indent=2),
			)

			full_prompt = f"{VALIDATION_SYSTEM_PROMPT}\n\n---\n\n{user_prompt}"

			# Retry up to max_retries times on LLM / parse failures.
			last_exc: Exception | None = None
			succeeded = False
			for attempt in range(max_retries):
				try:
					response = llm.invoke(full_prompt)
					response_text = clean_llm_response(response.content)
					parsed = json.loads(response_text)

					validation_results = parsed.get("cause_validation_results", [])
					if not isinstance(validation_results, list) or not validation_results:
						raise ValueError("LLM output missing valid 'cause_validation_results'")

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
						confidence = 0.0
					else:
						references = [
							_normalize_reference_to_filename(ref, reference_to_filename)
							for ref in references
						]
						references = [ref for ref in references if ref]
						references = list(dict.fromkeys(references))

					normalized_results.append(
						{
							**cause_payload,
							"evidence_match_status": status,
							"supporting_evidence_references": [str(ref) for ref in references],
							"confidence": round(confidence, 3),
							"rationale": str(item.get("rationale", "Evidence assessment completed.")).strip(),
						}
					)
					succeeded = True
					break

				except Exception as exc:
					last_exc = exc
					logger.warning(
						f"[validate_causes] cause={cause_id} attempt={attempt + 1}/{max_retries} failed: {exc}"
					)

			if not succeeded:
				normalized_results.append(
					{
						**cause_payload,
						"evidence_match_status": "no_evidence",
						"supporting_evidence_references": [],
						"confidence": 0.0,
						"rationale": f"Validation failed after {max_retries} attempts: {last_exc}",
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

	VALIDATED_CONFIDENCE_THRESHOLD = 0.90

	try:
		all_results = state.get("cause_validation_results", [])
		validated = [
			result
			for result in all_results
			if result.get("evidence_match_status") in {"matched", "partially_matched"}
			and result.get("supporting_evidence_references")
			and float(result.get("confidence", 0.0)) >= VALIDATED_CONFIDENCE_THRESHOLD
		]

		if validated:
			overall_confidence = state.get("overall_confidence")
			if not isinstance(overall_confidence, (int, float)) or overall_confidence <= 0:
				overall_confidence = round(
					sum(float(item.get("confidence", 0.0)) for item in validated) / len(validated),
					3,
				)
			notes = f"Returning causes with confidence \u2265 {VALIDATED_CONFIDENCE_THRESHOLD} and grounded supporting evidence."
		else:
			overall_confidence = 0.0
			notes = state.get("notes") or f"No causes met the confidence threshold of {VALIDATED_CONFIDENCE_THRESHOLD}."

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
