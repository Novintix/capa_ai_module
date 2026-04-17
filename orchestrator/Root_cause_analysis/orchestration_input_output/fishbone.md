# Fishbone V3 Live Run

## Endpoint
- POST /fishbone-v3/analyze
- POST /fishbone-v3/decide

## Request 1 (Analyze)
```json
{
    "complaint_id":  "CAPA-FISHBONE-2026-09",
    "complaint":  "During final visual inspection of Ceftriaxone for Injection 1g (Vial), Batch CF-882, 142/10,000 vials were rejected for visible white polyester fibers, exceeding AQL.",
    "evidence":  "Forensic microscopy identified polyester fibers matching sterile suit fabric. Gowning record: suit ST-992 reached 45 autoclave cycles (\u003e40 limit). CCTV showed operator reaching over open line after pump intervention. Deviation report confirms line clearance was not performed after pump replacement.",
    "sop":  "SOP-STER-044 Rev 08 requires line clearance after interventions and retirement of sterile garments after 40 cycles.",
    "fmea_document_path":  "fmea_depth_test_large.xlsx"
}
```

## Response 1
```json
{
    "complaint_id":  "CAPA-FISHBONE-2026-09",
    "status":  "ERROR",
    "confidence":  null,
    "mode":  "HITL_V3",
    "total_causes_found":  0,
    "causes_validated_with_evidence":  0,
    "high_confidence_causes_count":  0,
    "low_confidence_causes_count":  0,
    "all_causes_found":  [

                         ],
    "all_categorized_causes":  [

                               ],
    "all_validated_causes":  [

                             ],
    "high_confidence_causes":  [

                               ],
    "low_confidence_causes":  [

                              ],
    "zero_evidence_result":  null,
    "causes_found":  0,
    "causes":  [

               ],
    "category_summary":  null,
    "validated_causes_count":  0,
    "execution_time_seconds":  22.21,
    "stopping_reason":  "no_causes_found",
    "error":  null,
    "execution_trace":  [
                            "1. ListCausesAgent"
                        ]
}
```

## Final Observed Status
```json
{
    "complaint_id":  "CAPA-FISHBONE-2026-09",
    "status":  "ERROR",
    "confidence":  null,
    "mode":  "HITL_V3",
    "total_causes_found":  0,
    "causes_validated_with_evidence":  0,
    "high_confidence_causes_count":  0,
    "low_confidence_causes_count":  0,
    "all_causes_found":  [

                         ],
    "all_categorized_causes":  [

                               ],
    "all_validated_causes":  [

                             ],
    "high_confidence_causes":  [

                               ],
    "low_confidence_causes":  [

                              ],
    "zero_evidence_result":  null,
    "causes_found":  0,
    "causes":  [

               ],
    "category_summary":  null,
    "validated_causes_count":  0,
    "execution_time_seconds":  22.21,
    "stopping_reason":  "no_causes_found",
    "error":  null,
    "execution_trace":  [
                            "1. ListCausesAgent"
                        ]
}
```


---

# Fishbone V3 Live Run (Attempt 2)

## Request 1 (Analyze)
```json
{
    "complaint_id":  "CAPA-FISHBONE-2026-09-2",
    "complaint":  "During the final visual inspection of Ceftriaxone for Injection 1g (Vial), Batch CF-882, a significant spike in Visible Particulate Matter was detected. Out of a batch size of 10,000 vials, 142 vials were rejected for white, lint-like fibers. This exceeds the Acceptable Quality Level (AQL) limit of 0.1% and represents the first occurrence of fiber contamination in this product line this quarter.",
    "evidence":  "Forensic microscopy identifies the particles as polyester-based microfibers consistent with cleanroom garment degradation. Environmental Monitoring logs show a momentary particle spike. Maintenance records indicate a peristaltic pump head replacement. CCTV shows operator reaching over open conveyor line. Gowning logs reveal suit ST-992 had 45 autoclave cycles, above 40-cycle limit. No line clearance or smoke study verification documented post intervention.",
    "sop":  "SOP-STER-044 Rev 08 requires full Clear-Clean-Check and line clearance after intervention, prohibits reaching over open line, and mandates garment retirement after 40 autoclave cycles.",
    "fmea_document_path":  "fmea_depth_test_large.xlsx"
}
```

## Response 1
```json
{
    "complaint_id":  "CAPA-FISHBONE-2026-09-2",
    "status":  "IN_PROGRESS",
    "confidence":  null,
    "mode":  "HITL_V3",
    "total_causes_found":  1,
    "causes_validated_with_evidence":  0,
    "high_confidence_causes_count":  0,
    "low_confidence_causes_count":  1,
    "all_causes_found":  [
                             {
                                 "cause_id":  "C001",
                                 "cause_text":  "Supplier handling contamination",
                                 "process_step":  "Supplier audit",
                                 "category":  "Material",
                                 "category_confidence":  0.85,
                                 "category_reasoning":  "The root cause describes contamination introduced during supplier handling, which directly affects the material quality (primary Material). The contamination originates from human actions at the supplier site, so a secondary Man factor is also applicable.",
                                 "secondary_categories":  [

                                                          ],
                                 "failure_mode":  "Contaminated raw material",
                                 "potential_effects":  "Safety risk",
                                 "severity":  10,
                                 "occurrence":  2,
                                 "detection":  4,
                                 "current_controls":  null,
                                 "source":  "FMEA",
                                 "validation_status":  "no_evidence",
                                 "validation_confidence":  0.0,
                                 "validation_rationale":  "None of the provided evidence mentions supplier handling; investigation points to internal garment degradation, operator activity, and equipment maintenance as sources.",
                                 "zero_evidence_rank":  1,
                                 "zero_evidence_score":  0.6,
                                 "zero_evidence_reasoning":  "Highest criticality score (8.00) â severity=10, single_point_failure=True, safety_risk=high, safety_blocking=none. LLM reasoning: Contaminated raw material from the supplier can directly introduce fibers into the product, creating the observed particulate spike, poses a high safety risk, and no automatic safety interlocks are described.",
                                 "human_decision":  null,
                                 "human_comment":  null
                             }
                         ],
    "all_categorized_causes":  [
                                   {
                                       "cause_id":  "C001",
                                       "cause_text":  "Supplier handling contamination",
                                       "process_step":  "Supplier audit",
                                       "category":  "Material",
                                       "category_confidence":  0.85,
                                       "category_reasoning":  "The root cause describes contamination introduced during supplier handling, which directly affects the material quality (primary Material). The contamination originates from human actions at the supplier site, so a secondary Man factor is also applicable.",
                                       "secondary_categories":  [

                                                                ],
                                       "failure_mode":  "Contaminated raw material",
                                       "potential_effects":  "Safety risk",
                                       "severity":  10,
                                       "occurrence":  2,
                                       "detection":  4,
                                       "current_controls":  null,
                                       "source":  "FMEA",
                                       "validation_status":  "no_evidence",
                                       "validation_confidence":  0.0,
                                       "validation_rationale":  "None of the provided evidence mentions supplier handling; investigation points to internal garment degradation, operator activity, and equipment maintenance as sources.",
                                       "zero_evidence_rank":  1,
                                       "zero_evidence_score":  0.6,
                                       "zero_evidence_reasoning":  "Highest criticality score (8.00) â severity=10, single_point_failure=True, safety_risk=high, safety_blocking=none. LLM reasoning: Contaminated raw material from the supplier can directly introduce fibers into the product, creating the observed particulate spike, poses a high safety risk, and no automatic safety interlocks are described.",
                                       "human_decision":  null,
                                       "human_comment":  null
                                   }
                               ],
    "all_validated_causes":  [

                             ],
    "high_confidence_causes":  [

                               ],
    "low_confidence_causes":  [
                                  {
                                      "cause_id":  "C001",
                                      "cause_text":  "Supplier handling contamination",
                                      "process_step":  "Supplier audit",
                                      "category":  "Material",
                                      "category_confidence":  0.85,
                                      "category_reasoning":  "The root cause describes contamination introduced during supplier handling, which directly affects the material quality (primary Material). The contamination originates from human actions at the supplier site, so a secondary Man factor is also applicable.",
                                      "secondary_categories":  [

                                                               ],
                                      "failure_mode":  "Contaminated raw material",
                                      "potential_effects":  "Safety risk",
                                      "severity":  10,
                                      "occurrence":  2,
                                      "detection":  4,
                                      "current_controls":  null,
                                      "source":  "FMEA",
                                      "validation_status":  "no_evidence",
                                      "validation_confidence":  0.0,
                                      "validation_rationale":  "None of the provided evidence mentions supplier handling; investigation points to internal garment degradation, operator activity, and equipment maintenance as sources.",
                                      "zero_evidence_rank":  1,
                                      "zero_evidence_score":  0.6,
                                      "zero_evidence_reasoning":  "Highest criticality score (8.00) â severity=10, single_point_failure=True, safety_risk=high, safety_blocking=none. LLM reasoning: Contaminated raw material from the supplier can directly introduce fibers into the product, creating the observed particulate spike, poses a high safety risk, and no automatic safety interlocks are described.",
                                      "human_decision":  null,
                                      "human_comment":  null
                                  }
                              ],
    "zero_evidence_result":  {
                                 "selected_root_cause":  {
                                                             "cause_id":  "C001",
                                                             "cause_text":  "Supplier handling contamination",
                                                             "process_step":  "Supplier audit",
                                                             "reason":  "Highest criticality score (8.00) â severity=10, single_point_failure=True, safety_risk=high, safety_blocking=none. LLM reasoning: Contaminated raw material from the supplier can directly introduce fibers into the product, creating the observed particulate spike, poses a high safety risk, and no automatic safety interlocks are described."
                                                         },
                                 "ranked_causes":  [
                                                       {
                                                           "cause_id":  "C001",
                                                           "cause_text":  "Supplier handling contamination",
                                                           "process_step":  "Supplier audit",
                                                           "failure_mode":  "Contaminated raw material",
                                                           "potential_effects":  "Safety risk",
                                                           "severity":  10,
                                                           "occurrence":  2,
                                                           "detection":  4,
                                                           "current_controls":  null,
                                                           "source":  "FMEA",
                                                           "category":  "Material",
                                                           "category_confidence":  0.85,
                                                           "category_reasoning":  "The root cause describes contamination introduced during supplier handling, which directly affects the material quality (primary Material). The contamination originates from human actions at the supplier site, so a secondary Man factor is also applicable.",
                                                           "validation_status":  "no_evidence",
                                                           "validation_confidence":  0.0,
                                                           "validation_rationale":  "None of the provided evidence mentions supplier handling; investigation points to internal garment degradation, operator activity, and equipment maintenance as sources.",
                                                           "zero_evidence_rank":  1,
                                                           "zero_evidence_score":  0.6,
                                                           "zero_evidence_reasoning":  "Highest criticality score (8.00) â severity=10, single_point_failure=True, safety_risk=high, safety_blocking=none. LLM reasoning: Contaminated raw material from the supplier can directly introduce fibers into the product, creating the observed particulate spike, poses a high safety risk, and no automatic safety interlocks are described."
                                                       }
                                                   ],
                                 "total_ranked":  1
                             },
    "causes_found":  1,
    "causes":  [
                   {
                       "cause_id":  "C001",
                       "cause_text":  "Supplier handling contamination",
                       "process_step":  "Supplier audit",
                       "category":  "Material",
                       "category_confidence":  0.85,
                       "category_reasoning":  "The root cause describes contamination introduced during supplier handling, which directly affects the material quality (primary Material). The contamination originates from human actions at the supplier site, so a secondary Man factor is also applicable.",
                       "secondary_categories":  [

                                                ],
                       "failure_mode":  "Contaminated raw material",
                       "potential_effects":  "Safety risk",
                       "severity":  10,
                       "occurrence":  2,
                       "detection":  4,
                       "current_controls":  null,
                       "source":  "FMEA",
                       "validation_status":  "no_evidence",
                       "validation_confidence":  0.0,
                       "validation_rationale":  "None of the provided evidence mentions supplier handling; investigation points to internal garment degradation, operator activity, and equipment maintenance as sources.",
                       "zero_evidence_rank":  1,
                       "zero_evidence_score":  0.6,
                       "zero_evidence_reasoning":  "Highest criticality score (8.00) â severity=10, single_point_failure=True, safety_risk=high, safety_blocking=none. LLM reasoning: Contaminated raw material from the supplier can directly introduce fibers into the product, creating the observed particulate spike, poses a high safety risk, and no automatic safety interlocks are described.",
                       "human_decision":  null,
                       "human_comment":  null
                   }
               ],
    "category_summary":  {
                             "Man":  1,
                             "Machine":  0,
                             "Method":  0,
                             "Material":  1,
                             "Measurement":  0,
                             "Environment":  0,
                             "Unknown":  0
                         },
    "validated_causes_count":  0,
    "execution_time_seconds":  6.88,
    "stopping_reason":  "completed",
    "error":  null,
    "execution_trace":  [
                            "1. ListCausesAgent",
                            "2. CategorizationAgent",
                            "3. ValidationAgent",
                            "4. ZeroEvidenceAgent (Ranking)"
                        ]
}
```

## Final Observed Status
```json
{
    "complaint_id":  "CAPA-FISHBONE-2026-09-2",
    "status":  "IN_PROGRESS",
    "confidence":  null,
    "mode":  "HITL_V3",
    "total_causes_found":  1,
    "causes_validated_with_evidence":  0,
    "high_confidence_causes_count":  0,
    "low_confidence_causes_count":  1,
    "all_causes_found":  [
                             {
                                 "cause_id":  "C001",
                                 "cause_text":  "Supplier handling contamination",
                                 "process_step":  "Supplier audit",
                                 "category":  "Material",
                                 "category_confidence":  0.85,
                                 "category_reasoning":  "The root cause describes contamination introduced during supplier handling, which directly affects the material quality (primary Material). The contamination originates from human actions at the supplier site, so a secondary Man factor is also applicable.",
                                 "secondary_categories":  [

                                                          ],
                                 "failure_mode":  "Contaminated raw material",
                                 "potential_effects":  "Safety risk",
                                 "severity":  10,
                                 "occurrence":  2,
                                 "detection":  4,
                                 "current_controls":  null,
                                 "source":  "FMEA",
                                 "validation_status":  "no_evidence",
                                 "validation_confidence":  0.0,
                                 "validation_rationale":  "None of the provided evidence mentions supplier handling; investigation points to internal garment degradation, operator activity, and equipment maintenance as sources.",
                                 "zero_evidence_rank":  1,
                                 "zero_evidence_score":  0.6,
                                 "zero_evidence_reasoning":  "Highest criticality score (8.00) â severity=10, single_point_failure=True, safety_risk=high, safety_blocking=none. LLM reasoning: Contaminated raw material from the supplier can directly introduce fibers into the product, creating the observed particulate spike, poses a high safety risk, and no automatic safety interlocks are described.",
                                 "human_decision":  null,
                                 "human_comment":  null
                             }
                         ],
    "all_categorized_causes":  [
                                   {
                                       "cause_id":  "C001",
                                       "cause_text":  "Supplier handling contamination",
                                       "process_step":  "Supplier audit",
                                       "category":  "Material",
                                       "category_confidence":  0.85,
                                       "category_reasoning":  "The root cause describes contamination introduced during supplier handling, which directly affects the material quality (primary Material). The contamination originates from human actions at the supplier site, so a secondary Man factor is also applicable.",
                                       "secondary_categories":  [

                                                                ],
                                       "failure_mode":  "Contaminated raw material",
                                       "potential_effects":  "Safety risk",
                                       "severity":  10,
                                       "occurrence":  2,
                                       "detection":  4,
                                       "current_controls":  null,
                                       "source":  "FMEA",
                                       "validation_status":  "no_evidence",
                                       "validation_confidence":  0.0,
                                       "validation_rationale":  "None of the provided evidence mentions supplier handling; investigation points to internal garment degradation, operator activity, and equipment maintenance as sources.",
                                       "zero_evidence_rank":  1,
                                       "zero_evidence_score":  0.6,
                                       "zero_evidence_reasoning":  "Highest criticality score (8.00) â severity=10, single_point_failure=True, safety_risk=high, safety_blocking=none. LLM reasoning: Contaminated raw material from the supplier can directly introduce fibers into the product, creating the observed particulate spike, poses a high safety risk, and no automatic safety interlocks are described.",
                                       "human_decision":  null,
                                       "human_comment":  null
                                   }
                               ],
    "all_validated_causes":  [

                             ],
    "high_confidence_causes":  [

                               ],
    "low_confidence_causes":  [
                                  {
                                      "cause_id":  "C001",
                                      "cause_text":  "Supplier handling contamination",
                                      "process_step":  "Supplier audit",
                                      "category":  "Material",
                                      "category_confidence":  0.85,
                                      "category_reasoning":  "The root cause describes contamination introduced during supplier handling, which directly affects the material quality (primary Material). The contamination originates from human actions at the supplier site, so a secondary Man factor is also applicable.",
                                      "secondary_categories":  [

                                                               ],
                                      "failure_mode":  "Contaminated raw material",
                                      "potential_effects":  "Safety risk",
                                      "severity":  10,
                                      "occurrence":  2,
                                      "detection":  4,
                                      "current_controls":  null,
                                      "source":  "FMEA",
                                      "validation_status":  "no_evidence",
                                      "validation_confidence":  0.0,
                                      "validation_rationale":  "None of the provided evidence mentions supplier handling; investigation points to internal garment degradation, operator activity, and equipment maintenance as sources.",
                                      "zero_evidence_rank":  1,
                                      "zero_evidence_score":  0.6,
                                      "zero_evidence_reasoning":  "Highest criticality score (8.00) â severity=10, single_point_failure=True, safety_risk=high, safety_blocking=none. LLM reasoning: Contaminated raw material from the supplier can directly introduce fibers into the product, creating the observed particulate spike, poses a high safety risk, and no automatic safety interlocks are described.",
                                      "human_decision":  null,
                                      "human_comment":  null
                                  }
                              ],
    "zero_evidence_result":  {
                                 "selected_root_cause":  {
                                                             "cause_id":  "C001",
                                                             "cause_text":  "Supplier handling contamination",
                                                             "process_step":  "Supplier audit",
                                                             "reason":  "Highest criticality score (8.00) â severity=10, single_point_failure=True, safety_risk=high, safety_blocking=none. LLM reasoning: Contaminated raw material from the supplier can directly introduce fibers into the product, creating the observed particulate spike, poses a high safety risk, and no automatic safety interlocks are described."
                                                         },
                                 "ranked_causes":  [
                                                       {
                                                           "cause_id":  "C001",
                                                           "cause_text":  "Supplier handling contamination",
                                                           "process_step":  "Supplier audit",
                                                           "failure_mode":  "Contaminated raw material",
                                                           "potential_effects":  "Safety risk",
                                                           "severity":  10,
                                                           "occurrence":  2,
                                                           "detection":  4,
                                                           "current_controls":  null,
                                                           "source":  "FMEA",
                                                           "category":  "Material",
                                                           "category_confidence":  0.85,
                                                           "category_reasoning":  "The root cause describes contamination introduced during supplier handling, which directly affects the material quality (primary Material). The contamination originates from human actions at the supplier site, so a secondary Man factor is also applicable.",
                                                           "validation_status":  "no_evidence",
                                                           "validation_confidence":  0.0,
                                                           "validation_rationale":  "None of the provided evidence mentions supplier handling; investigation points to internal garment degradation, operator activity, and equipment maintenance as sources.",
                                                           "zero_evidence_rank":  1,
                                                           "zero_evidence_score":  0.6,
                                                           "zero_evidence_reasoning":  "Highest criticality score (8.00) â severity=10, single_point_failure=True, safety_risk=high, safety_blocking=none. LLM reasoning: Contaminated raw material from the supplier can directly introduce fibers into the product, creating the observed particulate spike, poses a high safety risk, and no automatic safety interlocks are described."
                                                       }
                                                   ],
                                 "total_ranked":  1
                             },
    "causes_found":  1,
    "causes":  [
                   {
                       "cause_id":  "C001",
                       "cause_text":  "Supplier handling contamination",
                       "process_step":  "Supplier audit",
                       "category":  "Material",
                       "category_confidence":  0.85,
                       "category_reasoning":  "The root cause describes contamination introduced during supplier handling, which directly affects the material quality (primary Material). The contamination originates from human actions at the supplier site, so a secondary Man factor is also applicable.",
                       "secondary_categories":  [

                                                ],
                       "failure_mode":  "Contaminated raw material",
                       "potential_effects":  "Safety risk",
                       "severity":  10,
                       "occurrence":  2,
                       "detection":  4,
                       "current_controls":  null,
                       "source":  "FMEA",
                       "validation_status":  "no_evidence",
                       "validation_confidence":  0.0,
                       "validation_rationale":  "None of the provided evidence mentions supplier handling; investigation points to internal garment degradation, operator activity, and equipment maintenance as sources.",
                       "zero_evidence_rank":  1,
                       "zero_evidence_score":  0.6,
                       "zero_evidence_reasoning":  "Highest criticality score (8.00) â severity=10, single_point_failure=True, safety_risk=high, safety_blocking=none. LLM reasoning: Contaminated raw material from the supplier can directly introduce fibers into the product, creating the observed particulate spike, poses a high safety risk, and no automatic safety interlocks are described.",
                       "human_decision":  null,
                       "human_comment":  null
                   }
               ],
    "category_summary":  {
                             "Man":  1,
                             "Machine":  0,
                             "Method":  0,
                             "Material":  1,
                             "Measurement":  0,
                             "Environment":  0,
                             "Unknown":  0
                         },
    "validated_causes_count":  0,
    "execution_time_seconds":  6.88,
    "stopping_reason":  "completed",
    "error":  null,
    "execution_trace":  [
                            "1. ListCausesAgent",
                            "2. CategorizationAgent",
                            "3. ValidationAgent",
                            "4. ZeroEvidenceAgent (Ranking)"
                        ]
}
```


---

# Fishbone V3 Live Run (Attempt 3 - HITL Forcing)

## Request 1 (Analyze)
```json
{
    "complaint_id":  "CAPA-FISHBONE-2026-09-3",
    "complaint":  "Visible polyester particulate contamination observed in sterile vial batch during final inspection.",
    "evidence":  "Supplier audit report confirms raw stopper lot RM-447 was contaminated with polyester fibers during supplier handling and packaging. Incoming QC microscopy matched fibers in raw material to fibers found in rejected vials. Supplier CAPA record states handling controls failed during packing on 2026-03-20. Internal process checks found no machine-origin fibers.",
    "sop":  "Supplier quality SOP requires rejection of contaminated incoming material and supplier escalation.",
    "fmea_document_path":  "fmea_depth_test_large.xlsx"
}
```

## Response 1
```json
{
    "complaint_id":  "CAPA-FISHBONE-2026-09-3",
    "status":  "WAIT_FOR_HUMAN",
    "confidence":  null,
    "mode":  "HITL_V3",
    "total_causes_found":  1,
    "causes_validated_with_evidence":  1,
    "high_confidence_causes_count":  1,
    "low_confidence_causes_count":  0,
    "all_causes_found":  [
                             {
                                 "cause_id":  "C001",
                                 "cause_text":  "Supplier handling contamination",
                                 "process_step":  "Supplier audit",
                                 "category":  "Man",
                                 "category_confidence":  0.9,
                                 "category_reasoning":  "The root cause explicitly mentions the supplier\u0027s handling, which is a human action (Man). The resulting particulate contamination affects the material supplied, making Material a relevant secondary category.",
                                 "secondary_categories":  [

                                                          ],
                                 "failure_mode":  "Contaminated raw material",
                                 "potential_effects":  "Safety risk",
                                 "severity":  10,
                                 "occurrence":  2,
                                 "detection":  4,
                                 "current_controls":  null,
                                 "source":  "FMEA",
                                 "validation_status":  "matched",
                                 "validation_confidence":  0.95,
                                 "validation_rationale":  "Investigation report confirms polyester fibers entered the raw stopper lot during supplier handling and packaging, matching fibers found in contaminated vials.",
                                 "zero_evidence_rank":  null,
                                 "zero_evidence_score":  null,
                                 "zero_evidence_reasoning":  null,
                                 "human_decision":  null,
                                 "human_comment":  null
                             }
                         ],
    "all_categorized_causes":  [
                                   {
                                       "cause_id":  "C001",
                                       "cause_text":  "Supplier handling contamination",
                                       "process_step":  "Supplier audit",
                                       "category":  "Man",
                                       "category_confidence":  0.9,
                                       "category_reasoning":  "The root cause explicitly mentions the supplier\u0027s handling, which is a human action (Man). The resulting particulate contamination affects the material supplied, making Material a relevant secondary category.",
                                       "secondary_categories":  [

                                                                ],
                                       "failure_mode":  "Contaminated raw material",
                                       "potential_effects":  "Safety risk",
                                       "severity":  10,
                                       "occurrence":  2,
                                       "detection":  4,
                                       "current_controls":  null,
                                       "source":  "FMEA",
                                       "validation_status":  "matched",
                                       "validation_confidence":  0.95,
                                       "validation_rationale":  "Investigation report confirms polyester fibers entered the raw stopper lot during supplier handling and packaging, matching fibers found in contaminated vials.",
                                       "zero_evidence_rank":  null,
                                       "zero_evidence_score":  null,
                                       "zero_evidence_reasoning":  null,
                                       "human_decision":  null,
                                       "human_comment":  null
                                   }
                               ],
    "all_validated_causes":  [
                                 {
                                     "cause_id":  "C001",
                                     "cause_text":  "Supplier handling contamination",
                                     "process_step":  "Supplier audit",
                                     "category":  "Man",
                                     "category_confidence":  0.9,
                                     "category_reasoning":  "The root cause explicitly mentions the supplier\u0027s handling, which is a human action (Man). The resulting particulate contamination affects the material supplied, making Material a relevant secondary category.",
                                     "secondary_categories":  [

                                                              ],
                                     "failure_mode":  "Contaminated raw material",
                                     "potential_effects":  "Safety risk",
                                     "severity":  10,
                                     "occurrence":  2,
                                     "detection":  4,
                                     "current_controls":  null,
                                     "source":  "FMEA",
                                     "validation_status":  "matched",
                                     "validation_confidence":  0.95,
                                     "validation_rationale":  "Investigation report confirms polyester fibers entered the raw stopper lot during supplier handling and packaging, matching fibers found in contaminated vials.",
                                     "zero_evidence_rank":  null,
                                     "zero_evidence_score":  null,
                                     "zero_evidence_reasoning":  null,
                                     "human_decision":  null,
                                     "human_comment":  null
                                 }
                             ],
    "high_confidence_causes":  [
                                   {
                                       "cause_id":  "C001",
                                       "cause_text":  "Supplier handling contamination",
                                       "process_step":  "Supplier audit",
                                       "category":  "Man",
                                       "category_confidence":  0.9,
                                       "category_reasoning":  "The root cause explicitly mentions the supplier\u0027s handling, which is a human action (Man). The resulting particulate contamination affects the material supplied, making Material a relevant secondary category.",
                                       "secondary_categories":  [

                                                                ],
                                       "failure_mode":  "Contaminated raw material",
                                       "potential_effects":  "Safety risk",
                                       "severity":  10,
                                       "occurrence":  2,
                                       "detection":  4,
                                       "current_controls":  null,
                                       "source":  "FMEA",
                                       "validation_status":  "matched",
                                       "validation_confidence":  0.95,
                                       "validation_rationale":  "Investigation report confirms polyester fibers entered the raw stopper lot during supplier handling and packaging, matching fibers found in contaminated vials.",
                                       "zero_evidence_rank":  null,
                                       "zero_evidence_score":  null,
                                       "zero_evidence_reasoning":  null,
                                       "human_decision":  null,
                                       "human_comment":  null
                                   }
                               ],
    "low_confidence_causes":  [

                              ],
    "zero_evidence_result":  null,
    "causes_found":  1,
    "causes":  [
                   {
                       "cause_id":  "C001",
                       "cause_text":  "Supplier handling contamination",
                       "process_step":  "Supplier audit",
                       "category":  "Man",
                       "category_confidence":  0.9,
                       "category_reasoning":  "The root cause explicitly mentions the supplier\u0027s handling, which is a human action (Man). The resulting particulate contamination affects the material supplied, making Material a relevant secondary category.",
                       "secondary_categories":  [

                                                ],
                       "failure_mode":  "Contaminated raw material",
                       "potential_effects":  "Safety risk",
                       "severity":  10,
                       "occurrence":  2,
                       "detection":  4,
                       "current_controls":  null,
                       "source":  "FMEA",
                       "validation_status":  "matched",
                       "validation_confidence":  0.95,
                       "validation_rationale":  "Investigation report confirms polyester fibers entered the raw stopper lot during supplier handling and packaging, matching fibers found in contaminated vials.",
                       "zero_evidence_rank":  null,
                       "zero_evidence_score":  null,
                       "zero_evidence_reasoning":  null,
                       "human_decision":  null,
                       "human_comment":  null
                   }
               ],
    "category_summary":  {
                             "Man":  1,
                             "Machine":  0,
                             "Method":  0,
                             "Material":  1,
                             "Measurement":  0,
                             "Environment":  0,
                             "Unknown":  0
                         },
    "validated_causes_count":  1,
    "execution_time_seconds":  4.44,
    "stopping_reason":  "hitl_pending",
    "error":  null,
    "execution_trace":  [
                            "1. ListCausesAgent",
                            "2. CategorizationAgent",
                            "3. ValidationAgent"
                        ]
}
```

## Request 2 (HITL Decide)
```json
{
    "complaint_id":  "CAPA-FISHBONE-2026-09-3",
    "decisions":  [
                      {
                          "cause_id":  "C001",
                          "action":  "RCA",
                          "comment":  "Auto HITL test decision for C001"
                      }
                  ]
}
```

## Response 2
```json
{
    "complaint_id":  "CAPA-FISHBONE-2026-09-3",
    "status":  "COMPLETED",
    "confidence":  null,
    "mode":  "HITL_V3",
    "total_causes_found":  0,
    "causes_validated_with_evidence":  0,
    "high_confidence_causes_count":  1,
    "low_confidence_causes_count":  0,
    "all_causes_found":  [

                         ],
    "all_categorized_causes":  [
                                   {
                                       "cause_id":  "C001",
                                       "cause_text":  "Supplier handling contamination",
                                       "process_step":  "Supplier audit",
                                       "category":  "Man",
                                       "category_confidence":  0.9,
                                       "category_reasoning":  "The root cause explicitly mentions the supplier\u0027s handling, which is a human action (Man). The resulting particulate contamination affects the material supplied, making Material a relevant secondary category.",
                                       "secondary_categories":  [

                                                                ],
                                       "failure_mode":  "Contaminated raw material",
                                       "potential_effects":  "Safety risk",
                                       "severity":  10,
                                       "occurrence":  2,
                                       "detection":  4,
                                       "current_controls":  null,
                                       "source":  "FMEA",
                                       "validation_status":  "matched",
                                       "validation_confidence":  0.95,
                                       "validation_rationale":  "Investigation report confirms polyester fibers entered the raw stopper lot during supplier handling and packaging, matching fibers found in contaminated vials.",
                                       "zero_evidence_rank":  null,
                                       "zero_evidence_score":  null,
                                       "zero_evidence_reasoning":  null,
                                       "human_decision":  "RCA",
                                       "human_comment":  "Auto HITL test decision for C001"
                                   }
                               ],
    "all_validated_causes":  [

                             ],
    "high_confidence_causes":  [
                                   {
                                       "cause_id":  "C001",
                                       "cause_text":  "Supplier handling contamination",
                                       "process_step":  "Supplier audit",
                                       "category":  "Man",
                                       "category_confidence":  0.9,
                                       "category_reasoning":  "The root cause explicitly mentions the supplier\u0027s handling, which is a human action (Man). The resulting particulate contamination affects the material supplied, making Material a relevant secondary category.",
                                       "secondary_categories":  [

                                                                ],
                                       "failure_mode":  "Contaminated raw material",
                                       "potential_effects":  "Safety risk",
                                       "severity":  10,
                                       "occurrence":  2,
                                       "detection":  4,
                                       "current_controls":  null,
                                       "source":  "FMEA",
                                       "validation_status":  "matched",
                                       "validation_confidence":  0.95,
                                       "validation_rationale":  "Investigation report confirms polyester fibers entered the raw stopper lot during supplier handling and packaging, matching fibers found in contaminated vials.",
                                       "zero_evidence_rank":  null,
                                       "zero_evidence_score":  null,
                                       "zero_evidence_reasoning":  null,
                                       "human_decision":  "RCA",
                                       "human_comment":  "Auto HITL test decision for C001"
                                   }
                               ],
    "low_confidence_causes":  [

                              ],
    "zero_evidence_result":  null,
    "causes_found":  1,
    "causes":  [
                   {
                       "cause_id":  "C001",
                       "cause_text":  "Supplier handling contamination",
                       "process_step":  "Supplier audit",
                       "category":  "Man",
                       "category_confidence":  0.9,
                       "category_reasoning":  "The root cause explicitly mentions the supplier\u0027s handling, which is a human action (Man). The resulting particulate contamination affects the material supplied, making Material a relevant secondary category.",
                       "secondary_categories":  [

                                                ],
                       "failure_mode":  "Contaminated raw material",
                       "potential_effects":  "Safety risk",
                       "severity":  10,
                       "occurrence":  2,
                       "detection":  4,
                       "current_controls":  null,
                       "source":  "FMEA",
                       "validation_status":  "matched",
                       "validation_confidence":  0.95,
                       "validation_rationale":  "Investigation report confirms polyester fibers entered the raw stopper lot during supplier handling and packaging, matching fibers found in contaminated vials.",
                       "zero_evidence_rank":  null,
                       "zero_evidence_score":  null,
                       "zero_evidence_reasoning":  null,
                       "human_decision":  "RCA",
                       "human_comment":  "Auto HITL test decision for C001"
                   }
               ],
    "category_summary":  {
                             "Man":  1,
                             "Machine":  0,
                             "Method":  0,
                             "Material":  1,
                             "Measurement":  0,
                             "Environment":  0,
                             "Unknown":  0
                         },
    "validated_causes_count":  0,
    "execution_time_seconds":  0.0,
    "stopping_reason":  "hitl_complete",
    "error":  null,
    "execution_trace":  [
                            "1. ListCausesAgent",
                            "2. CategorizationAgent",
                            "3. ValidationAgent"
                        ]
}
```

## Final Observed Status
```json
{
    "complaint_id":  "CAPA-FISHBONE-2026-09-3",
    "status":  "COMPLETED",
    "confidence":  null,
    "mode":  "HITL_V3",
    "total_causes_found":  0,
    "causes_validated_with_evidence":  0,
    "high_confidence_causes_count":  1,
    "low_confidence_causes_count":  0,
    "all_causes_found":  [

                         ],
    "all_categorized_causes":  [
                                   {
                                       "cause_id":  "C001",
                                       "cause_text":  "Supplier handling contamination",
                                       "process_step":  "Supplier audit",
                                       "category":  "Man",
                                       "category_confidence":  0.9,
                                       "category_reasoning":  "The root cause explicitly mentions the supplier\u0027s handling, which is a human action (Man). The resulting particulate contamination affects the material supplied, making Material a relevant secondary category.",
                                       "secondary_categories":  [

                                                                ],
                                       "failure_mode":  "Contaminated raw material",
                                       "potential_effects":  "Safety risk",
                                       "severity":  10,
                                       "occurrence":  2,
                                       "detection":  4,
                                       "current_controls":  null,
                                       "source":  "FMEA",
                                       "validation_status":  "matched",
                                       "validation_confidence":  0.95,
                                       "validation_rationale":  "Investigation report confirms polyester fibers entered the raw stopper lot during supplier handling and packaging, matching fibers found in contaminated vials.",
                                       "zero_evidence_rank":  null,
                                       "zero_evidence_score":  null,
                                       "zero_evidence_reasoning":  null,
                                       "human_decision":  "RCA",
                                       "human_comment":  "Auto HITL test decision for C001"
                                   }
                               ],
    "all_validated_causes":  [

                             ],
    "high_confidence_causes":  [
                                   {
                                       "cause_id":  "C001",
                                       "cause_text":  "Supplier handling contamination",
                                       "process_step":  "Supplier audit",
                                       "category":  "Man",
                                       "category_confidence":  0.9,
                                       "category_reasoning":  "The root cause explicitly mentions the supplier\u0027s handling, which is a human action (Man). The resulting particulate contamination affects the material supplied, making Material a relevant secondary category.",
                                       "secondary_categories":  [

                                                                ],
                                       "failure_mode":  "Contaminated raw material",
                                       "potential_effects":  "Safety risk",
                                       "severity":  10,
                                       "occurrence":  2,
                                       "detection":  4,
                                       "current_controls":  null,
                                       "source":  "FMEA",
                                       "validation_status":  "matched",
                                       "validation_confidence":  0.95,
                                       "validation_rationale":  "Investigation report confirms polyester fibers entered the raw stopper lot during supplier handling and packaging, matching fibers found in contaminated vials.",
                                       "zero_evidence_rank":  null,
                                       "zero_evidence_score":  null,
                                       "zero_evidence_reasoning":  null,
                                       "human_decision":  "RCA",
                                       "human_comment":  "Auto HITL test decision for C001"
                                   }
                               ],
    "low_confidence_causes":  [

                              ],
    "zero_evidence_result":  null,
    "causes_found":  1,
    "causes":  [
                   {
                       "cause_id":  "C001",
                       "cause_text":  "Supplier handling contamination",
                       "process_step":  "Supplier audit",
                       "category":  "Man",
                       "category_confidence":  0.9,
                       "category_reasoning":  "The root cause explicitly mentions the supplier\u0027s handling, which is a human action (Man). The resulting particulate contamination affects the material supplied, making Material a relevant secondary category.",
                       "secondary_categories":  [

                                                ],
                       "failure_mode":  "Contaminated raw material",
                       "potential_effects":  "Safety risk",
                       "severity":  10,
                       "occurrence":  2,
                       "detection":  4,
                       "current_controls":  null,
                       "source":  "FMEA",
                       "validation_status":  "matched",
                       "validation_confidence":  0.95,
                       "validation_rationale":  "Investigation report confirms polyester fibers entered the raw stopper lot during supplier handling and packaging, matching fibers found in contaminated vials.",
                       "zero_evidence_rank":  null,
                       "zero_evidence_score":  null,
                       "zero_evidence_reasoning":  null,
                       "human_decision":  "RCA",
                       "human_comment":  "Auto HITL test decision for C001"
                   }
               ],
    "category_summary":  {
                             "Man":  1,
                             "Machine":  0,
                             "Method":  0,
                             "Material":  1,
                             "Measurement":  0,
                             "Environment":  0,
                             "Unknown":  0
                         },
    "validated_causes_count":  0,
    "execution_time_seconds":  0.0,
    "stopping_reason":  "hitl_complete",
    "error":  null,
    "execution_trace":  [
                            "1. ListCausesAgent",
                            "2. CategorizationAgent",
                            "3. ValidationAgent"
                        ]
}
```

