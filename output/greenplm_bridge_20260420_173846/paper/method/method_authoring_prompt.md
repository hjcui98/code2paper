# Phase 4 Method Authoring Prompt

Use the frozen Method Evidence, claim contracts, and negative scope to author the Method section.
Prioritize the Authoring View stage packets. Treat background evidence as context, not as contribution.

- latex_expression_preference: balanced

## Authoring View
```json
{
  "project_id": "greenplm",
  "method_name": "Author-Marker Grounded Method Pipeline",
  "method_goal": "Coordinate a method pipeline that establishes projector-language coupling under mostly frozen backbone settings; then expands from simple descriptions to richer instruction/dialog patterns while preserving projector continuity; then uses point-cloud token features and compact token aggregation to transfer prior alignment to 3D inputs; then controls runtime mechanics (trainer save behavior/logging/checkpoint flow).",
  "implementation_scope": "current codebase only",
  "latex_expression_preference": "balanced",
  "author_logic_priority": true,
  "author_logic_mapping": {
    "author_proposed_flow": [
      "Stage I: Text-First Interface Warmup",
      "Stage II: Rich Instruction Alignment",
      "Stage III: Point-Language Transfer",
      "Runtime and saving behavior"
    ],
    "author_supported_flow": [
      "Stage I: Text-First Interface Warmup",
      "Stage II: Rich Instruction Alignment",
      "Stage III: Point-Language Transfer",
      "Runtime and saving behavior"
    ],
    "author_unsupported_parts": []
  },
  "authoring_policy": {
    "primary_rule": "Write from stage_packets.primary_mechanisms and primary_evidence_ids first.",
    "supporting_rule": "Use supporting behavior/equation evidence only when it is linked to a stage, mechanism, or claim.",
    "background_rule": "Background/backbone evidence may be mentioned as implementation context, but must not be promoted to contribution unless a stage or claim explicitly binds it.",
    "excluded_rule": "Generated artifacts and pretrained asset packaging are not method evidence.",
    "overview_rule": "The overview should summarize stage logic and should not enumerate low-level backbone internals."
  },
  "stage_packets": [
    {
      "stage_id": "S1",
      "name": "Stage I: Text-First Interface Warmup",
      "purpose": "Establish projector-language coupling under mostly frozen backbone settings.",
      "inputs": [
        "raw_point_cloud"
      ],
      "outputs": [
        "output_0"
      ],
      "primary_mechanism_ids": [
        "MECH1"
      ],
      "primary_evidence_ids": [
        "E5"
      ],
      "claim_ids": [
        "C1"
      ],
      "modules": [],
      "mechanisms": [
        {
          "mechanism_id": "MECH1",
          "description": "Establish projector-language coupling under mostly frozen backbone settings.",
          "support_status": "supported",
          "evidence_ids": [
            "E5"
          ],
          "confidence": "high",
          "submechanisms": []
        }
      ],
      "frozen_mechanisms": [
        {
          "mechanism_id": "MECH1",
          "mechanism_name": "Stage I: Text-First Interface Warmup",
          "mechanism_description": "Establish projector-language coupling under mostly frozen backbone settings.",
          "parent_stage_id": "S1",
          "inputs": [
            "raw_point_cloud"
          ],
          "outputs": [
            "output_0"
          ],
          "implementation_anchor": {
            "path": "",
            "symbols": []
          },
          "distinguishing_level": "none",
          "author_claim_relation": "supported",
          "evidence_span_ids": [
            "E5"
          ]
        }
      ],
      "writing_instruction": "Use this packet as the main source for the stage paragraph. Do not replace this stage's author-facing purpose with unbound backbone internals."
    },
    {
      "stage_id": "S2",
      "name": "Stage II: Rich Instruction Alignment",
      "purpose": "Expand from simple descriptions to richer instruction/dialog patterns while preserving projector continuity.",
      "inputs": [
        "input_1"
      ],
      "outputs": [
        "output_1"
      ],
      "primary_mechanism_ids": [
        "MECH2"
      ],
      "primary_evidence_ids": [
        "E5"
      ],
      "claim_ids": [
        "C2"
      ],
      "modules": [],
      "mechanisms": [
        {
          "mechanism_id": "MECH2",
          "description": "Expand from simple descriptions to richer instruction/dialog patterns while preserving projector continuity.",
          "support_status": "supported",
          "evidence_ids": [
            "E5"
          ],
          "confidence": "high",
          "submechanisms": []
        }
      ],
      "frozen_mechanisms": [
        {
          "mechanism_id": "MECH2",
          "mechanism_name": "Stage II: Rich Instruction Alignment",
          "mechanism_description": "Expand from simple descriptions to richer instruction/dialog patterns while preserving projector continuity.",
          "parent_stage_id": "S2",
          "inputs": [
            "input_1"
          ],
          "outputs": [
            "output_1"
          ],
          "implementation_anchor": {
            "path": "",
            "symbols": []
          },
          "distinguishing_level": "none",
          "author_claim_relation": "supported",
          "evidence_span_ids": [
            "E5"
          ]
        }
      ],
      "writing_instruction": "Use this packet as the main source for the stage paragraph. Do not replace this stage's author-facing purpose with unbound backbone internals."
    },
    {
      "stage_id": "S3",
      "name": "Stage III: Point-Language Transfer",
      "purpose": "Use point-cloud token features and compact token aggregation to transfer prior alignment to 3D inputs.",
      "inputs": [
        "input_2"
      ],
      "outputs": [
        "output_2"
      ],
      "primary_mechanism_ids": [
        "MECH3"
      ],
      "primary_evidence_ids": [
        "E5",
        "E4",
        "E6",
        "E7",
        "E8",
        "E9",
        "E10"
      ],
      "claim_ids": [
        "C3"
      ],
      "modules": [],
      "mechanisms": [
        {
          "mechanism_id": "MECH3",
          "description": "Use point-cloud token features and compact token aggregation to transfer prior alignment to 3D inputs.",
          "support_status": "supported",
          "evidence_ids": [
            "E5",
            "E4",
            "E5",
            "E6",
            "E7",
            "E8",
            "E9",
            "E10"
          ],
          "confidence": "high",
          "submechanisms": []
        }
      ],
      "frozen_mechanisms": [
        {
          "mechanism_id": "MECH3",
          "mechanism_name": "Stage III: Point-Language Transfer",
          "mechanism_description": "Use point-cloud token features and compact token aggregation to transfer prior alignment to 3D inputs.",
          "parent_stage_id": "S3",
          "inputs": [
            "input_2"
          ],
          "outputs": [
            "output_2"
          ],
          "implementation_anchor": {
            "path": "",
            "symbols": []
          },
          "distinguishing_level": "none",
          "author_claim_relation": "supported",
          "evidence_span_ids": [
            "E5",
            "E4",
            "E5",
            "E6",
            "E7",
            "E8",
            "E9",
            "E10"
          ]
        }
      ],
      "writing_instruction": "Use this packet as the main source for the stage paragraph. Do not replace this stage's author-facing purpose with unbound backbone internals."
    },
    {
      "stage_id": "S4",
      "name": "Runtime and saving behavior",
      "purpose": "Control runtime mechanics (trainer save behavior/logging/checkpoint flow).",
      "inputs": [
        "input_3"
      ],
      "outputs": [
        "output_3"
      ],
      "primary_mechanism_ids": [
        "MECH4"
      ],
      "primary_evidence_ids": [
        "E5"
      ],
      "claim_ids": [
        "C4"
      ],
      "modules": [],
      "mechanisms": [
        {
          "mechanism_id": "MECH4",
          "description": "Control runtime mechanics (trainer save behavior/logging/checkpoint flow).",
          "support_status": "supported",
          "evidence_ids": [
            "E5"
          ],
          "confidence": "high",
          "submechanisms": []
        }
      ],
      "frozen_mechanisms": [
        {
          "mechanism_id": "MECH4",
          "mechanism_name": "Runtime and saving behavior",
          "mechanism_description": "Control runtime mechanics (trainer save behavior/logging/checkpoint flow).",
          "parent_stage_id": "S4",
          "inputs": [
            "input_3"
          ],
          "outputs": [
            "output_3"
          ],
          "implementation_anchor": {
            "path": "",
            "symbols": []
          },
          "distinguishing_level": "none",
          "author_claim_relation": "supported",
          "evidence_span_ids": [
            "E5"
          ]
        }
      ],
      "writing_instruction": "Use this packet as the main source for the stage paragraph. Do not replace this stage's author-facing purpose with unbound backbone internals."
    }
  ],
  "frozen_mechanisms": [
    {
      "mechanism_id": "MECH1",
      "mechanism_name": "Stage I: Text-First Interface Warmup",
      "mechanism_description": "Establish projector-language coupling under mostly frozen backbone settings.",
      "parent_stage_id": "S1",
      "inputs": [
        "raw_point_cloud"
      ],
      "outputs": [
        "output_0"
      ],
      "implementation_anchor": {
        "path": "",
        "symbols": []
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E5"
      ]
    },
    {
      "mechanism_id": "MECH2",
      "mechanism_name": "Stage II: Rich Instruction Alignment",
      "mechanism_description": "Expand from simple descriptions to richer instruction/dialog patterns while preserving projector continuity.",
      "parent_stage_id": "S2",
      "inputs": [
        "input_1"
      ],
      "outputs": [
        "output_1"
      ],
      "implementation_anchor": {
        "path": "",
        "symbols": []
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E5"
      ]
    },
    {
      "mechanism_id": "MECH3",
      "mechanism_name": "Stage III: Point-Language Transfer",
      "mechanism_description": "Use point-cloud token features and compact token aggregation to transfer prior alignment to 3D inputs.",
      "parent_stage_id": "S3",
      "inputs": [
        "input_2"
      ],
      "outputs": [
        "output_2"
      ],
      "implementation_anchor": {
        "path": "",
        "symbols": []
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E5",
        "E4",
        "E5",
        "E6",
        "E7",
        "E8",
        "E9",
        "E10"
      ]
    },
    {
      "mechanism_id": "MECH4",
      "mechanism_name": "Runtime and saving behavior",
      "mechanism_description": "Control runtime mechanics (trainer save behavior/logging/checkpoint flow).",
      "parent_stage_id": "S4",
      "inputs": [
        "input_3"
      ],
      "outputs": [
        "output_3"
      ],
      "implementation_anchor": {
        "path": "",
        "symbols": []
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E5"
      ]
    }
  ],
  "claim_contracts": [
    {
      "claim_id": "C1",
      "claim_intent": "The method contains a paper-facing stage named Stage I: Text-First Interface Warmup.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E5"
      ],
      "allowed_wording_boundary": "Describe Stage I: Text-First Interface Warmup only using its listed evidence-backed inputs, outputs, modules, and mechanisms.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C2",
      "claim_intent": "The method contains a paper-facing stage named Stage II: Rich Instruction Alignment.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E5"
      ],
      "allowed_wording_boundary": "Describe Stage II: Rich Instruction Alignment only using its listed evidence-backed inputs, outputs, modules, and mechanisms.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C3",
      "claim_intent": "The method contains a paper-facing stage named Stage III: Point-Language Transfer.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E5",
        "E4",
        "E6",
        "E7",
        "E8",
        "E9",
        "E10"
      ],
      "allowed_wording_boundary": "Describe Stage III: Point-Language Transfer only using its listed evidence-backed inputs, outputs, modules, and mechanisms.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C4",
      "claim_intent": "The method contains a paper-facing stage named Runtime and saving behavior.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E5"
      ],
      "allowed_wording_boundary": "Describe Runtime and saving behavior only using its listed evidence-backed inputs, outputs, modules, and mechanisms.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C5",
      "claim_intent": "Establish projector-language coupling under mostly frozen backbone settings.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E5"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C6",
      "claim_intent": "Expand from simple descriptions to richer instruction/dialog patterns while preserving projector continuity.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E5"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C7",
      "claim_intent": "Use point-cloud token features and compact token aggregation to transfer prior alignment to 3D inputs.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E5",
        "E4",
        "E5",
        "E6",
        "E7",
        "E8",
        "E9",
        "E10"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C8",
      "claim_intent": "Control runtime mechanics (trainer save behavior/logging/checkpoint flow).",
      "support_status": "supported",
      "evidence_span_ids": [
        "E5"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C9",
      "claim_intent": "Core novelty emphasis is stage design and modality-transfer strategy rather than replacing the base LLM backbone.",
      "support_status": "unsupported",
      "evidence_span_ids": [],
      "allowed_wording_boundary": "Do not include in method prose unless the author supplies hard supporting evidence.",
      "required_qualifiers": [
        "unsupported by current code evidence"
      ],
      "review_question_id": "RQ-9"
    },
    {
      "claim_id": "C10",
      "claim_intent": "Use large text supervision to reduce dependence on scarce point-text pairs.",
      "support_status": "unsupported",
      "evidence_span_ids": [],
      "allowed_wording_boundary": "Do not include in method prose unless the author supplies hard supporting evidence.",
      "required_qualifiers": [
        "unsupported by current code evidence"
      ],
      "review_question_id": "RQ-10"
    },
    {
      "claim_id": "C11",
      "claim_intent": "Keep one projector interface across stages to stabilize transfer from text-side alignment to point-side alignment.",
      "support_status": "unsupported",
      "evidence_span_ids": [],
      "allowed_wording_boundary": "Do not include in method prose unless the author supplies hard supporting evidence.",
      "required_qualifiers": [
        "unsupported by current code evidence"
      ],
      "review_question_id": "RQ-11"
    }
  ],
  "behavior_patterns_by_role": {
    "primary": [],
    "supporting": [],
    "background": [],
    "excluded": []
  },
  "equation_candidates_by_role": {
    "primary": [],
    "supporting": [],
    "background": [],
    "excluded": []
  },
  "architecture_parameters": [],
  "tensor_roles": [],
  "writing_constraints": [
    "Do not mention README-only information.",
    "Do not claim academic novelty without author confirmation.",
    "Do not promote comment-only hints into main method claims."
  ],
  "negative_scope": [
    "README-only statements cannot enter method prose.",
    "Logger, checkpoint, seed, cache, path handling, and distributed setup are infrastructure unless tied to hard method evidence.",
    "Comments and author hints are navigation signals, not standalone fact evidence.",
    "Unsupported author part: Core novelty emphasis is stage design and modality-transfer strategy rather than replacing the base LLM backbone.",
    "Unsupported author part: Use large text supervision to reduce dependence on scarce point-text pairs.",
    "Unsupported author part: Keep one projector interface across stages to stabilize transfer from text-side alignment to point-side alignment."
  ],
  "alignment_notes": [
    "Execution stages and method stages are separated; method prose should follow method stages, not raw execution order.",
    "Author-provided pipeline steps matched: Stage III: Point-Language Transfer.",
    "Unsupported author claims should remain out of the method draft: Core novelty emphasis is stage design and modality-transfer strategy rather than replacing the base LLM backbone., Use large text supervision to reduce dependence on scarce point-text pairs., Keep one projector interface across stages to stabilize transfer from text-side alignment to point-side alignment.."
  ],
  "excluded_sources": []
}
```

## Claim Evidence Map
```json
{
  "claims": [
    {
      "claim_id": "C1",
      "claim_text": "Establish projector-language coupling under mostly frozen backbone settings.",
      "support_status": "supported",
      "evidence_ids": [
        "E5"
      ],
      "mechanism_ids": [
        "MECH1"
      ],
      "source": "method_mechanism",
      "caveats": []
    },
    {
      "claim_id": "C2",
      "claim_text": "Expand from simple descriptions to richer instruction/dialog patterns while preserving projector continuity.",
      "support_status": "supported",
      "evidence_ids": [
        "E5"
      ],
      "mechanism_ids": [
        "MECH2"
      ],
      "source": "method_mechanism",
      "caveats": []
    },
    {
      "claim_id": "C3",
      "claim_text": "Use point-cloud token features and compact token aggregation to transfer prior alignment to 3D inputs.",
      "support_status": "supported",
      "evidence_ids": [
        "E5",
        "E4",
        "E5",
        "E6",
        "E7",
        "E8",
        "E9",
        "E10"
      ],
      "mechanism_ids": [
        "MECH3"
      ],
      "source": "method_mechanism",
      "caveats": []
    },
    {
      "claim_id": "C4",
      "claim_text": "Control runtime mechanics (trainer save behavior/logging/checkpoint flow).",
      "support_status": "supported",
      "evidence_ids": [
        "E5"
      ],
      "mechanism_ids": [
        "MECH4"
      ],
      "source": "method_mechanism",
      "caveats": []
    },
    {
      "claim_id": "C5",
      "claim_text": "The method contains a paper-facing stage named Stage I: Text-First Interface Warmup.",
      "support_status": "supported",
      "evidence_ids": [
        "E5"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C1",
      "caveats": []
    },
    {
      "claim_id": "C6",
      "claim_text": "The method contains a paper-facing stage named Stage II: Rich Instruction Alignment.",
      "support_status": "supported",
      "evidence_ids": [
        "E5"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C2",
      "caveats": []
    },
    {
      "claim_id": "C7",
      "claim_text": "The method contains a paper-facing stage named Stage III: Point-Language Transfer.",
      "support_status": "supported",
      "evidence_ids": [
        "E5",
        "E4",
        "E6",
        "E7",
        "E8",
        "E9",
        "E10"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C3",
      "caveats": []
    },
    {
      "claim_id": "C8",
      "claim_text": "The method contains a paper-facing stage named Runtime and saving behavior.",
      "support_status": "supported",
      "evidence_ids": [
        "E5"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C4",
      "caveats": []
    },
    {
      "claim_id": "C9",
      "claim_text": "Establish projector-language coupling under mostly frozen backbone settings.",
      "support_status": "supported",
      "evidence_ids": [
        "E5"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C5",
      "caveats": []
    },
    {
      "claim_id": "C10",
      "claim_text": "Expand from simple descriptions to richer instruction/dialog patterns while preserving projector continuity.",
      "support_status": "supported",
      "evidence_ids": [
        "E5"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C6",
      "caveats": []
    },
    {
      "claim_id": "C11",
      "claim_text": "Use point-cloud token features and compact token aggregation to transfer prior alignment to 3D inputs.",
      "support_status": "supported",
      "evidence_ids": [
        "E5",
        "E4",
        "E5",
        "E6",
        "E7",
        "E8",
        "E9",
        "E10"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C7",
      "caveats": []
    },
    {
      "claim_id": "C12",
      "claim_text": "Control runtime mechanics (trainer save behavior/logging/checkpoint flow).",
      "support_status": "supported",
      "evidence_ids": [
        "E5"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C8",
      "caveats": []
    },
    {
      "claim_id": "C13",
      "claim_text": "A compact local-to-global aggregation path is used before point features are conditioned into the LLM.",
      "support_status": "partial",
      "evidence_ids": [
        "E4",
        "E5",
        "E6",
        "E7",
        "E8",
        "E9",
        "E10"
      ],
      "mechanism_ids": [],
      "source": "author_claim:file",
      "caveats": [
        "Treat parameter-free wording as a hypothesis until all involved operators are checked for learnable parameters."
      ]
    },
    {
      "claim_id": "C14",
      "claim_text": "Core novelty emphasis is stage design and modality-transfer strategy rather than replacing the base LLM backbone.",
      "support_status": "unsupported",
      "evidence_ids": [],
      "mechanism_ids": [],
      "source": "author_claim:none",
      "caveats": [
        "Final trainable subset per stage must be cross-checked with actual launch scripts/arguments.",
        "Author claim is not supported by discovered files or symbols."
      ]
    },
    {
      "claim_id": "C15",
      "claim_text": "Use large text supervision to reduce dependence on scarce point-text pairs.",
      "support_status": "unsupported",
      "evidence_ids": [],
      "mechanism_ids": [],
      "source": "author_claim:none",
      "caveats": [
        "Stage behavior in code is controlled by flags (stage_2, tune_mm_mlp_adapter, fix_llm/fix_pointnet), not explicit Stage-I/II/III classes.",
        "Release scripts should be verified as real content (not LFS pointer) before claiming exact command-level differences.",
        "The method narrative should explain why text-first alignment lowers 3D data pressure.",
        "Author claim is not supported by discovered files or symbols."
      ]
    },
    {
      "claim_id": "C16",
      "claim_text": "Keep one projector interface across stages to stabilize transfer from text-side alignment to point-side alignment.",
      "support_status": "unsupported",
      "evidence_ids": [],
      "mechanism_ids": [],
      "source": "author_claim:none",
      "caveats": [
        "A shared bridge simplifies modality transfer logic and keeps the method storyline coherent.",
        "Author claim is not supported by discovered files or symbols."
      ]
    },
    {
      "claim_id": "C17",
      "claim_text": "Compress point-token sequences before LLM fusion to keep useful structure with manageable token cost.",
      "support_status": "partial",
      "evidence_ids": [
        "E4",
        "E5",
        "E6",
        "E7",
        "E8",
        "E9",
        "E10"
      ],
      "mechanism_ids": [],
      "source": "author_claim:file",
      "caveats": [
        "Phrase as code-aligned aggregation/routing unless parameter counts are explicitly audited at symbol level.",
        "Supports the efficiency-plus-information-retention argument without overloading the language model context."
      ]
    }
  ]
}
```