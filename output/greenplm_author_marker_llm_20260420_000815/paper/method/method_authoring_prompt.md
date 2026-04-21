# Phase 4 Method Authoring Prompt

Use the frozen Method Evidence, claim contracts, and negative scope to author the Method section.

- latex_expression_preference: balanced

## Method Evidence
```json
{
  "project_id": "greenplm",
  "author_mode": "enhanced",
  "author_confirmation_required": false,
  "method_name": "Author-Marker Grounded Method Pipeline",
  "method_goal": "Show that the model can use large-scale text-based alignment first, then use limited 3D data to connect point-cloud representations to the language model.",
  "implementation_scope": "current codebase only",
  "latex_expression_preference": "balanced",
  "entrypoints": [],
  "stages": [
    {
      "stage_id": "S1",
      "name": "Stage I: Text-First Interface Warmup",
      "purpose": "Establish projector-language coupling under mostly frozen backbone settings.",
      "inputs": [
        "['raw_point_cloud', 'text_descriptions']"
      ],
      "outputs": [
        "['aligned_projector_weights']"
      ],
      "modules": [
        {
          "path": "/home/cuihengjia/agent/PosterGen/data/greenplm/code/swark-output/code2paper_run_full/paper/method/context_packs/source_core_candidates.json",
          "symbols": [],
          "role": "training-stage orchestration via argument combinations",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "/home/cuihengjia/agent/PosterGen/data/greenplm/code/swark-output/code2paper_run_full/paper/method/context_packs/source_core_candidates.json",
          "symbols": [],
          "role": "shared projector from encoder space to LLM hidden space",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "/home/cuihengjia/agent/PosterGen/data/greenplm/code/swark-output/code2paper_run_full/paper/method/context_packs/source_core_candidates.json",
          "symbols": [],
          "role": "trainer-side save/checkpoint behavior",
          "category": "method-core",
          "is_novel": false
        }
      ],
      "mechanisms": [
        {
          "mechanism_id": "MECH1",
          "description": "Establish projector-language coupling under mostly frozen backbone settings.",
          "support_status": "supported",
          "evidence_ids": [
            "E3622",
            "E3622"
          ],
          "confidence": "high",
          "submechanisms": []
        }
      ]
    },
    {
      "stage_id": "S2",
      "name": "Stage II: Rich Instruction Alignment",
      "purpose": "Expand from simple descriptions to richer instruction/dialog patterns while preserving projector continuity.",
      "inputs": [
        "['instruction_dialog']"
      ],
      "outputs": [
        "output"
      ],
      "modules": [
        {
          "path": "pointllm/model/pointllm.py",
          "symbols": [
            "PointLLMConfig"
          ],
          "role": "configuration and runtime wiring",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/model/pointllm.py",
          "symbols": [
            "PointLLMLlamaModel"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/model/pointllm.py",
          "symbols": [
            "PointLLMLlamaModel.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/model/pointllm.py",
          "symbols": [
            "PointLLMLlamaModel.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/model/pointllm.py",
          "symbols": [
            "PointLLMLlamaForCausalLM"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/model/pointllm.py",
          "symbols": [
            "PointLLMLlamaForCausalLM.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/model/pointllm.py",
          "symbols": [
            "PointLLMLlamaForCausalLM.get_model"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/model/pointllm.py",
          "symbols": [
            "PointLLMLlamaForCausalLM.maybe_autocast"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/model/pointllm.py",
          "symbols": [
            "PointLLMLlamaForCausalLM.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/model/pointllm.py",
          "symbols": [
            "PointLLMLlamaForCausalLM.prepare_inputs_for_generation"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/model/pointllm.py",
          "symbols": [
            "PointLLMLlamaForCausalLM.initialize_tokenizer_point_backbone_config_wo_embedding"
          ],
          "role": "data preparation and loading",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/model/pointllm.py",
          "symbols": [
            "PointLLMLlamaForCausalLM.initialize_tokenizer_point_backbone_config"
          ],
          "role": "data preparation and loading",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/point_encoder.py",
          "symbols": [
            "fps"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/point_encoder.py",
          "symbols": [
            "index_points"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/point_encoder.py",
          "symbols": [
            "knn_point"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/point_encoder.py",
          "symbols": [
            "square_distance"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/point_encoder.py",
          "symbols": [
            "PatchDropout"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/point_encoder.py",
          "symbols": [
            "PatchDropout.__init__"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/point_encoder.py",
          "symbols": [
            "PatchDropout.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/point_encoder.py",
          "symbols": [
            "Group"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/point_encoder.py",
          "symbols": [
            "Group.__init__"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/point_encoder.py",
          "symbols": [
            "Group.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/point_encoder.py",
          "symbols": [
            "Encoder"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/point_encoder.py",
          "symbols": [
            "Encoder.__init__"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/point_encoder.py",
          "symbols": [
            "Encoder.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/point_encoder.py",
          "symbols": [
            "skeleton_Group"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/point_encoder.py",
          "symbols": [
            "skeleton_Group.__init__"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/point_encoder.py",
          "symbols": [
            "skeleton_Group.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/point_encoder.py",
          "symbols": [
            "PointcloudEncoder"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/point_encoder.py",
          "symbols": [
            "PointcloudEncoder.__init__"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/point_encoder.py",
          "symbols": [
            "PointcloudEncoder.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_projector/builder.py",
          "symbols": [
            "IdentityMap"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_projector/builder.py",
          "symbols": [
            "IdentityMap.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_projector/builder.py",
          "symbols": [
            "IdentityMap.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_projector/builder.py",
          "symbols": [
            "IdentityMap.config"
          ],
          "role": "configuration and runtime wiring",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_projector/builder.py",
          "symbols": [
            "SimpleResBlock"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_projector/builder.py",
          "symbols": [
            "SimpleResBlock.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_projector/builder.py",
          "symbols": [
            "SimpleResBlock.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_projector/builder.py",
          "symbols": [
            "Mlp"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_projector/builder.py",
          "symbols": [
            "Mlp.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_projector/builder.py",
          "symbols": [
            "Mlp.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_projector/builder.py",
          "symbols": [
            "build_vision_projector"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3RMSNorm"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3RMSNorm.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3RMSNorm.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "_get_unpad_data"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3RotaryEmbedding"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3RotaryEmbedding.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3RotaryEmbedding.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3SuScaledRotaryEmbedding"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3SuScaledRotaryEmbedding.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3SuScaledRotaryEmbedding.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3YarnScaledRotaryEmbedding"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3YarnScaledRotaryEmbedding.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3YarnScaledRotaryEmbedding.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "rotate_half"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "apply_rotary_pos_emb"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3MLP"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3MLP.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3MLP.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "repeat_kv"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3Attention"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3Attention.__init__"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3Attention._init_rope"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3Attention.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3FlashAttention2"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3FlashAttention2.__init__"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3FlashAttention2.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3FlashAttention2._flash_attention_forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3FlashAttention2._upad_input"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3SdpaAttention"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3SdpaAttention.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3DecoderLayer"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3DecoderLayer.__init__"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3DecoderLayer.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3Model"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3Model.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3Model.get_input_embeddings"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3Model.set_input_embeddings"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3Model.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3ForCausalLM"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3ForCausalLM.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3ForCausalLM.get_input_embeddings"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3ForCausalLM.set_input_embeddings"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3ForCausalLM.get_output_embeddings"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3ForCausalLM.set_output_embeddings"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3ForCausalLM.set_decoder"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3ForCausalLM.get_decoder"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3ForCausalLM.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3ForCausalLM.prepare_inputs_for_generation"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3ForCausalLM._reorder_cache"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3ForSequenceClassification"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3ForSequenceClassification.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3ForSequenceClassification.get_input_embeddings"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3ForSequenceClassification.set_input_embeddings"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3ForSequenceClassification.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3ForTokenClassification"
          ],
          "role": "data preparation and loading",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3ForTokenClassification.__init__"
          ],
          "role": "data preparation and loading",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
          "symbols": [
            "Phi3ForTokenClassification.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/apply_delta.py",
          "symbols": [
            "apply_delta"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/consolidate.py",
          "symbols": [
            "consolidate_ckpt"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_llama.py",
          "symbols": [
            "LlavaConfig"
          ],
          "role": "configuration and runtime wiring",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_llama.py",
          "symbols": [
            "LlavaLlamaModel"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_llama.py",
          "symbols": [
            "LlavaLlamaModel.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_llama.py",
          "symbols": [
            "LlavaLlamaForCausalLM"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_llama.py",
          "symbols": [
            "LlavaLlamaForCausalLM.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_llama.py",
          "symbols": [
            "LlavaLlamaForCausalLM.get_model"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_llama.py",
          "symbols": [
            "LlavaLlamaForCausalLM.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_llama.py",
          "symbols": [
            "LlavaLlamaForCausalLM.generate"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_llama.py",
          "symbols": [
            "LlavaLlamaForCausalLM.prepare_inputs_for_generation"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_mistral.py",
          "symbols": [
            "LlavaMistralConfig"
          ],
          "role": "configuration and runtime wiring",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_mistral.py",
          "symbols": [
            "LlavaMistralModel"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_mistral.py",
          "symbols": [
            "LlavaMistralModel.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_mistral.py",
          "symbols": [
            "LlavaMistralForCausalLM"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_mistral.py",
          "symbols": [
            "LlavaMistralForCausalLM.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_mistral.py",
          "symbols": [
            "LlavaMistralForCausalLM.get_model"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_mistral.py",
          "symbols": [
            "LlavaMistralForCausalLM.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_mistral.py",
          "symbols": [
            "LlavaMistralForCausalLM.generate"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_mistral.py",
          "symbols": [
            "LlavaMistralForCausalLM.prepare_inputs_for_generation"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_mpt.py",
          "symbols": [
            "LlavaMptConfig"
          ],
          "role": "configuration and runtime wiring",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_mpt.py",
          "symbols": [
            "LlavaMptModel"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_mpt.py",
          "symbols": [
            "LlavaMptModel.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_mpt.py",
          "symbols": [
            "LlavaMptModel.embed_tokens"
          ],
          "role": "data preparation and loading",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_mpt.py",
          "symbols": [
            "LlavaMptForCausalLM"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_mpt.py",
          "symbols": [
            "LlavaMptForCausalLM.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_mpt.py",
          "symbols": [
            "LlavaMptForCausalLM.get_model"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_mpt.py",
          "symbols": [
            "LlavaMptForCausalLM._set_gradient_checkpointing"
          ],
          "role": "optimization and objective logic",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_mpt.py",
          "symbols": [
            "LlavaMptForCausalLM.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_mpt.py",
          "symbols": [
            "LlavaMptForCausalLM.prepare_inputs_for_generation"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_phi3.py",
          "symbols": [
            "LlavaPhiConfig"
          ],
          "role": "configuration and runtime wiring",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_phi3.py",
          "symbols": [
            "LlavaPhiModel"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_phi3.py",
          "symbols": [
            "LlavaPhiModel.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_phi3.py",
          "symbols": [
            "LlavaPhiForCausalLM"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_phi3.py",
          "symbols": [
            "LlavaPhiForCausalLM.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_phi3.py",
          "symbols": [
            "LlavaPhiForCausalLM.get_model"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_phi3.py",
          "symbols": [
            "LlavaPhiForCausalLM.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_phi3.py",
          "symbols": [
            "LlavaPhiForCausalLM.generate"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/language_model/llava_phi3.py",
          "symbols": [
            "LlavaPhiForCausalLM.prepare_inputs_for_generation"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/llava_arch.py",
          "symbols": [
            "LlavaMetaModel"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/llava_arch.py",
          "symbols": [
            "LlavaMetaModel.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/llava_arch.py",
          "symbols": [
            "LlavaMetaModel.get_vision_tower"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/llava_arch.py",
          "symbols": [
            "LlavaMetaModel.initialize_other_modules"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/llava_arch.py",
          "symbols": [
            "LlavaMetaModel.random_initialize_model"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/llava_arch.py",
          "symbols": [
            "unpad_image"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/llava_arch.py",
          "symbols": [
            "LlavaMetaForCausalLM"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/llava_arch.py",
          "symbols": [
            "LlavaMetaForCausalLM.maybe_autocast"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/llava_arch.py",
          "symbols": [
            "LlavaMetaForCausalLM.get_model"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/llava_arch.py",
          "symbols": [
            "LlavaMetaForCausalLM.get_vision_tower"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/llava_arch.py",
          "symbols": [
            "LlavaMetaForCausalLM.encode_datas"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/llava_arch.py",
          "symbols": [
            "LlavaMetaForCausalLM.prepare_inputs_labels_for_multimodal"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/llava_arch.py",
          "symbols": [
            "LlavaMetaForCausalLM.initialize_vision_tokenizer"
          ],
          "role": "data preparation and loading",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/make_delta.py",
          "symbols": [
            "make_delta"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/builder.py",
          "symbols": [
            "build_text_encoder"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/builder.py",
          "symbols": [
            "build_pc_encoder"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/clip_encoder.py",
          "symbols": [
            "CLIPVisionTower"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/clip_encoder.py",
          "symbols": [
            "CLIPVisionTower.__init__"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/clip_encoder.py",
          "symbols": [
            "CLIPVisionTower.feature_select"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/clip_encoder.py",
          "symbols": [
            "CLIPVisionTower.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/clip_encoder.py",
          "symbols": [
            "CLIPVisionTower.dummy_feature"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/clip_encoder.py",
          "symbols": [
            "CLIPVisionTower.dtype"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/clip_encoder.py",
          "symbols": [
            "CLIPVisionTower.device"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/clip_encoder.py",
          "symbols": [
            "CLIPVisionTower.config"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/clip_encoder.py",
          "symbols": [
            "CLIPVisionTower.hidden_size"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/clip_encoder.py",
          "symbols": [
            "CLIPVisionTower.num_patches_per_side"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/clip_encoder.py",
          "symbols": [
            "CLIPVisionTower.num_patches"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/clip_encoder.py",
          "symbols": [
            "CLIPVisionTowerS2"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/clip_encoder.py",
          "symbols": [
            "CLIPVisionTowerS2.__init__"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/clip_encoder.py",
          "symbols": [
            "CLIPVisionTowerS2.forward_feature"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/clip_encoder.py",
          "symbols": [
            "CLIPVisionTowerS2.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/clip_encoder.py",
          "symbols": [
            "CLIPVisionTowerS2.hidden_size"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/utils.py",
          "symbols": [
            "build_logger"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/utils.py",
          "symbols": [
            "StreamToLogger"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/utils.py",
          "symbols": [
            "StreamToLogger.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/utils.py",
          "symbols": [
            "StreamToLogger.__getattr__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/utils.py",
          "symbols": [
            "StreamToLogger.flush"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/utils.py",
          "symbols": [
            "disable_torch_init"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/utils.py",
          "symbols": [
            "violates_moderation"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/utils.py",
          "symbols": [
            "pretty_print_semaphore"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/utils.py",
          "symbols": [
            "default_bpe"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/utils.py",
          "symbols": [
            "bytes_to_unicode"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/utils.py",
          "symbols": [
            "get_pairs"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/utils.py",
          "symbols": [
            "basic_clean"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/utils.py",
          "symbols": [
            "whitespace_clean"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/utils.py",
          "symbols": [
            "SimpleTokenizer"
          ],
          "role": "data preparation and loading",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/utils.py",
          "symbols": [
            "SimpleTokenizer.__init__"
          ],
          "role": "data preparation and loading",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/utils.py",
          "symbols": [
            "SimpleTokenizer.bpe"
          ],
          "role": "data preparation and loading",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/utils.py",
          "symbols": [
            "SimpleTokenizer.encode"
          ],
          "role": "data preparation and loading",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/utils.py",
          "symbols": [
            "SimpleTokenizer.decode"
          ],
          "role": "data preparation and loading",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/utils.py",
          "symbols": [
            "SimpleTokenizer.__call__"
          ],
          "role": "data preparation and loading",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/serve/model_worker.py",
          "symbols": [
            "heart_beat_worker"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/serve/model_worker.py",
          "symbols": [
            "ModelWorker"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/serve/model_worker.py",
          "symbols": [
            "ModelWorker.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/serve/model_worker.py",
          "symbols": [
            "ModelWorker.register_to_controller"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/serve/model_worker.py",
          "symbols": [
            "ModelWorker.send_heart_beat"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/serve/model_worker.py",
          "symbols": [
            "ModelWorker.get_queue_length"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/serve/model_worker.py",
          "symbols": [
            "ModelWorker.get_status"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/serve/model_worker.py",
          "symbols": [
            "ModelWorker.generate_stream"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/serve/model_worker.py",
          "symbols": [
            "ModelWorker.generate_stream_gate"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/serve/model_worker.py",
          "symbols": [
            "release_model_semaphore"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/serve/model_worker.py",
          "symbols": [
            "generate_stream"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/serve/model_worker.py",
          "symbols": [
            "get_status"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/train/llama_flash_attn_monkey_patch.py",
          "symbols": [
            "_prepare_decoder_attention_mask"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/data/modelnet.py",
          "symbols": [
            "ModelNet"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/data/modelnet.py",
          "symbols": [
            "ModelNet.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/data/modelnet.py",
          "symbols": [
            "ModelNet.__len__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/data/modelnet.py",
          "symbols": [
            "ModelNet._get_item"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/data/modelnet.py",
          "symbols": [
            "ModelNet.pc_norm"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/data/modelnet.py",
          "symbols": [
            "ModelNet.__getitem__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/data/modelnet_show.py",
          "symbols": [
            "ModelNet"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/data/modelnet_show.py",
          "symbols": [
            "ModelNet.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/data/modelnet_show.py",
          "symbols": [
            "ModelNet.__len__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/data/modelnet_show.py",
          "symbols": [
            "ModelNet._get_item"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/data/modelnet_show.py",
          "symbols": [
            "ModelNet.our_get_item"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/data/modelnet_show.py",
          "symbols": [
            "ModelNet.pc_norm"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/data/modelnet_show.py",
          "symbols": [
            "ModelNet.__getitem__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/model/utils.py",
          "symbols": [
            "KeywordsStoppingCriteria"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/model/utils.py",
          "symbols": [
            "KeywordsStoppingCriteria.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/model/utils.py",
          "symbols": [
            "KeywordsStoppingCriteria.__call__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/train/llama_flash_attn_monkey_patch.py",
          "symbols": [
            "_prepare_decoder_attention_mask"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_msg_cls.py",
          "symbols": [
            "PointNet2ClassificationMSG"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_msg_cls.py",
          "symbols": [
            "PointNet2ClassificationMSG._build_model"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_msg_sem.py",
          "symbols": [
            "PointNet2SemSegMSG"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_msg_sem.py",
          "symbols": [
            "PointNet2SemSegMSG._build_model"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py",
          "symbols": [
            "set_bn_momentum_default"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py",
          "symbols": [
            "BNMomentumScheduler"
          ],
          "role": "optimization and objective logic",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py",
          "symbols": [
            "BNMomentumScheduler.__init__"
          ],
          "role": "optimization and objective logic",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py",
          "symbols": [
            "BNMomentumScheduler.step"
          ],
          "role": "optimization and objective logic",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py",
          "symbols": [
            "BNMomentumScheduler.state_dict"
          ],
          "role": "optimization and objective logic",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py",
          "symbols": [
            "PointNet2ClassificationSSG"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py",
          "symbols": [
            "PointNet2ClassificationSSG.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py",
          "symbols": [
            "PointNet2ClassificationSSG._build_model"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py",
          "symbols": [
            "PointNet2ClassificationSSG._break_up_pc"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py",
          "symbols": [
            "PointNet2ClassificationSSG.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py",
          "symbols": [
            "PointNet2ClassificationSSG.validation_step"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py",
          "symbols": [
            "PointNet2ClassificationSSG.validation_end"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py",
          "symbols": [
            "PointNet2ClassificationSSG.prepare_data"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_sem.py",
          "symbols": [
            "PointNet2SemSegSSG"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_sem.py",
          "symbols": [
            "PointNet2SemSegSSG._build_model"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_sem.py",
          "symbols": [
            "PointNet2SemSegSSG.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_sem.py",
          "symbols": [
            "PointNet2SemSegSSG.prepare_data"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/serve/controller.py",
          "symbols": [
            "Controller.list_models"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/serve/controller.py",
          "symbols": [
            "list_models"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/serve/gradio_web_server.py",
          "symbols": [
            "get_model_list"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/serve/sglang_worker.py",
          "symbols": [
            "ModelWorker"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/serve/sglang_worker.py",
          "symbols": [
            "ModelWorker.__init__"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/serve/sglang_worker.py",
          "symbols": [
            "ModelWorker.register_to_controller"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/serve/sglang_worker.py",
          "symbols": [
            "ModelWorker.send_heart_beat"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/serve/sglang_worker.py",
          "symbols": [
            "ModelWorker.get_queue_length"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/serve/sglang_worker.py",
          "symbols": [
            "ModelWorker.get_status"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/serve/sglang_worker.py",
          "symbols": [
            "ModelWorker.generate_stream"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/serve/sglang_worker.py",
          "symbols": [
            "ModelWorker.generate_stream_gate"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/serve/sglang_worker.py",
          "symbols": [
            "release_model_semaphore"
          ],
          "role": "infrastructure utility",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/utils.py",
          "symbols": [
            "SimpleTokenizer.encode"
          ],
          "role": "data preparation and loading",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/utils.py",
          "symbols": [
            "SimpleTokenizer.decode"
          ],
          "role": "data preparation and loading",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_modules.py",
          "symbols": [
            "_PointnetSAModuleBase.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_modules.py",
          "symbols": [
            "PointnetFPModule.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_utils.py",
          "symbols": [
            "FurthestPointSampling.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_utils.py",
          "symbols": [
            "GatherOperation.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_utils.py",
          "symbols": [
            "ThreeNN.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_utils.py",
          "symbols": [
            "ThreeInterpolate.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_utils.py",
          "symbols": [
            "GroupingOperation.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_utils.py",
          "symbols": [
            "BallQuery.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_utils.py",
          "symbols": [
            "QueryAndGroup.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_utils.py",
          "symbols": [
            "GroupAll.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pretrained_weight/eval_model_weight/all-mpnet-base-v2/train_script.py",
          "symbols": [
            "AutoModelForSentenceEmbedding.forward"
          ],
          "role": "model computation block",
          "category": "method-core",
          "is_novel": false
        }
      ],
      "mechanisms": [
        {
          "mechanism_id": "MECH2",
          "description": "Expand from simple descriptions to richer instruction/dialog patterns while preserving projector continuity.",
          "support_status": "supported",
          "evidence_ids": [
            "E2643"
          ],
          "confidence": "high",
          "submechanisms": []
        }
      ]
    },
    {
      "stage_id": "S3",
      "name": "Stage III: Point-Language Transfer",
      "purpose": "Author-marker method stage: Stage III: Point-Language Transfer.",
      "inputs": [],
      "outputs": [],
      "modules": [
        {
          "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py",
          "symbols": [
            "PointNet2ClassificationSSG.configure_optimizers"
          ],
          "role": "optimization and objective logic",
          "category": "method-core",
          "is_novel": false
        }
      ],
      "mechanisms": [
        {
          "mechanism_id": "MECH3",
          "description": "The S3 stage implements author-marker method stage: stage iii: point-language transfer.",
          "support_status": "partial",
          "evidence_ids": [],
          "confidence": "medium",
          "submechanisms": []
        }
      ]
    },
    {
      "stage_id": "S4",
      "name": "Runtime and saving behavior",
      "purpose": "Author-marker method stage: Runtime and saving behavior.",
      "inputs": [],
      "outputs": [],
      "modules": [],
      "mechanisms": [
        {
          "mechanism_id": "MECH4",
          "description": "The S4 stage implements author-marker method stage: runtime and saving behavior.",
          "support_status": "partial",
          "evidence_ids": [],
          "confidence": "medium",
          "submechanisms": []
        }
      ]
    }
  ],
  "behavior_patterns": [
    {
      "behavior_id": "BEH1",
      "behavior_type": "pointwise_transformation",
      "detected_pattern": "positionwise_feed_forward",
      "description": "Applies two point-wise linear transformations with a nonlinear activation between them.",
      "operations": [
        "linear",
        "activation",
        "linear"
      ],
      "path": "pointllm/model/pointllm.py",
      "symbol": "PointLLMLlamaModel",
      "evidence_ids": [
        "E136"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH2",
      "behavior_type": "regularization",
      "detected_pattern": "dropout",
      "description": "Applies dropout inside module computation.",
      "operations": [
        "drop"
      ],
      "path": "llava/model/multimodal_encoder/point_encoder.py",
      "symbol": "PatchDropout",
      "evidence_ids": [
        "E429"
      ],
      "confidence": "medium"
    },
    {
      "behavior_id": "BEH3",
      "behavior_type": "pointwise_transformation",
      "detected_pattern": "positionwise_feed_forward",
      "description": "Applies two point-wise linear transformations with a nonlinear activation between them.",
      "operations": [
        "linear",
        "activation",
        "linear"
      ],
      "path": "llava/model/multimodal_encoder/point_encoder.py",
      "symbol": "PointcloudEncoder",
      "evidence_ids": [
        "E445"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH4",
      "behavior_type": "regularization",
      "detected_pattern": "dropout",
      "description": "Applies dropout inside module computation.",
      "operations": [
        "drop"
      ],
      "path": "llava/model/multimodal_encoder/point_encoder.py",
      "symbol": "PointcloudEncoder",
      "evidence_ids": [
        "E445"
      ],
      "confidence": "medium"
    },
    {
      "behavior_id": "BEH5",
      "behavior_type": "pointwise_transformation",
      "detected_pattern": "positionwise_feed_forward",
      "description": "Applies two point-wise linear transformations with a nonlinear activation between them.",
      "operations": [
        "linear",
        "activation",
        "linear"
      ],
      "path": "llava/model/multimodal_projector/builder.py",
      "symbol": "SimpleResBlock",
      "evidence_ids": [
        "E541"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH6",
      "behavior_type": "normalization",
      "detected_pattern": "layer_normalization",
      "description": "Applies layer normalization around module computation.",
      "operations": [
        "normalize"
      ],
      "path": "llava/model/multimodal_projector/builder.py",
      "symbol": "SimpleResBlock",
      "evidence_ids": [
        "E541"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH7",
      "behavior_type": "pointwise_transformation",
      "detected_pattern": "positionwise_feed_forward",
      "description": "Applies two point-wise linear transformations with a nonlinear activation between them.",
      "operations": [
        "linear",
        "activation",
        "linear"
      ],
      "path": "llava/model/multimodal_projector/builder.py",
      "symbol": "Mlp",
      "evidence_ids": [
        "E544"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH8",
      "behavior_type": "normalization",
      "detected_pattern": "layer_normalization",
      "description": "Applies layer normalization around module computation.",
      "operations": [
        "normalize"
      ],
      "path": "llava/model/multimodal_projector/builder.py",
      "symbol": "Mlp",
      "evidence_ids": [
        "E544"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH9",
      "behavior_type": "regularization",
      "detected_pattern": "dropout",
      "description": "Applies dropout inside module computation.",
      "operations": [
        "drop"
      ],
      "path": "llava/model/multimodal_projector/builder.py",
      "symbol": "Mlp",
      "evidence_ids": [
        "E544"
      ],
      "confidence": "medium"
    },
    {
      "behavior_id": "BEH10",
      "behavior_type": "pointwise_transformation",
      "detected_pattern": "positionwise_feed_forward",
      "description": "Applies two point-wise linear transformations with a nonlinear activation between them.",
      "operations": [
        "linear",
        "activation",
        "linear"
      ],
      "path": "llava/model/multimodal_projector/builder.py",
      "symbol": "build_vision_projector",
      "evidence_ids": [
        "E547"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH11",
      "behavior_type": "normalization",
      "detected_pattern": "layer_normalization",
      "description": "Applies layer normalization around module computation.",
      "operations": [
        "normalize"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3RMSNorm",
      "evidence_ids": [
        "E710"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH12",
      "behavior_type": "representation_injection",
      "detected_pattern": "sinusoidal_positional_encoding",
      "description": "Constructs periodic position encodings and injects them into learned representations.",
      "operations": [
        "construct_encoding",
        "add"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3RotaryEmbedding",
      "evidence_ids": [
        "E715"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH13",
      "behavior_type": "representation_injection",
      "detected_pattern": "sinusoidal_positional_encoding",
      "description": "Constructs periodic position encodings and injects them into learned representations.",
      "operations": [
        "construct_encoding",
        "add"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3SuScaledRotaryEmbedding",
      "evidence_ids": [
        "E718"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH14",
      "behavior_type": "representation_injection",
      "detected_pattern": "sinusoidal_positional_encoding",
      "description": "Constructs periodic position encodings and injects them into learned representations.",
      "operations": [
        "construct_encoding",
        "add"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3YarnScaledRotaryEmbedding",
      "evidence_ids": [
        "E721"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH15",
      "behavior_type": "representation_injection",
      "detected_pattern": "sinusoidal_positional_encoding",
      "description": "Constructs periodic position encodings and injects them into learned representations.",
      "operations": [
        "construct_encoding",
        "add"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "apply_rotary_pos_emb",
      "evidence_ids": [
        "E726"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH16",
      "behavior_type": "weighted_aggregation",
      "detected_pattern": "scaled_dot_product_attention",
      "description": "Computes attention weights from scaled query-key compatibility scores and applies them to values.",
      "operations": [
        "scale",
        "similarity",
        "softmax",
        "weighted_sum"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3Attention",
      "evidence_ids": [
        "E733"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH17",
      "behavior_type": "representation_injection",
      "detected_pattern": "sinusoidal_positional_encoding",
      "description": "Constructs periodic position encodings and injects them into learned representations.",
      "operations": [
        "construct_encoding",
        "add"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3Attention",
      "evidence_ids": [
        "E733"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH18",
      "behavior_type": "regularization",
      "detected_pattern": "dropout",
      "description": "Applies dropout inside module computation.",
      "operations": [
        "drop"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3Attention",
      "evidence_ids": [
        "E733"
      ],
      "confidence": "medium"
    },
    {
      "behavior_id": "BEH19",
      "behavior_type": "normalization",
      "detected_pattern": "layer_normalization",
      "description": "Applies layer normalization around module computation.",
      "operations": [
        "normalize"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3FlashAttention2",
      "evidence_ids": [
        "E738"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH20",
      "behavior_type": "representation_injection",
      "detected_pattern": "sinusoidal_positional_encoding",
      "description": "Constructs periodic position encodings and injects them into learned representations.",
      "operations": [
        "construct_encoding",
        "add"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3FlashAttention2",
      "evidence_ids": [
        "E738"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH21",
      "behavior_type": "regularization",
      "detected_pattern": "dropout",
      "description": "Applies dropout inside module computation.",
      "operations": [
        "drop"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3FlashAttention2",
      "evidence_ids": [
        "E738"
      ],
      "confidence": "medium"
    },
    {
      "behavior_id": "BEH22",
      "behavior_type": "representation_injection",
      "detected_pattern": "sinusoidal_positional_encoding",
      "description": "Constructs periodic position encodings and injects them into learned representations.",
      "operations": [
        "construct_encoding",
        "add"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3SdpaAttention",
      "evidence_ids": [
        "E745"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH23",
      "behavior_type": "regularization",
      "detected_pattern": "dropout",
      "description": "Applies dropout inside module computation.",
      "operations": [
        "drop"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3SdpaAttention",
      "evidence_ids": [
        "E745"
      ],
      "confidence": "medium"
    },
    {
      "behavior_id": "BEH24",
      "behavior_type": "skip_connection",
      "detected_pattern": "residual_connection",
      "description": "Adds a residual connection around a sub-computation.",
      "operations": [
        "preserve",
        "add"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3DecoderLayer",
      "evidence_ids": [
        "E748"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH25",
      "behavior_type": "normalization",
      "detected_pattern": "layer_normalization",
      "description": "Applies layer normalization around module computation.",
      "operations": [
        "normalize"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3DecoderLayer",
      "evidence_ids": [
        "E748"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH26",
      "behavior_type": "regularization",
      "detected_pattern": "dropout",
      "description": "Applies dropout inside module computation.",
      "operations": [
        "drop"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3DecoderLayer",
      "evidence_ids": [
        "E748"
      ],
      "confidence": "medium"
    },
    {
      "behavior_id": "BEH27",
      "behavior_type": "repeated_composition",
      "detected_pattern": "decoder_stack",
      "description": "Builds a representation stack from repeated decoder-like layers.",
      "operations": [
        "repeat",
        "compose"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3Model",
      "evidence_ids": [
        "E753"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH28",
      "behavior_type": "regularization",
      "detected_pattern": "dropout",
      "description": "Applies dropout inside module computation.",
      "operations": [
        "drop"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3Model",
      "evidence_ids": [
        "E753"
      ],
      "confidence": "medium"
    },
    {
      "behavior_id": "BEH29",
      "behavior_type": "regularization",
      "detected_pattern": "dropout",
      "description": "Applies dropout inside module computation.",
      "operations": [
        "drop"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3ForTokenClassification",
      "evidence_ids": [
        "E777"
      ],
      "confidence": "medium"
    },
    {
      "behavior_id": "BEH30",
      "behavior_type": "normalization",
      "detected_pattern": "layer_normalization",
      "description": "Applies layer normalization around module computation.",
      "operations": [
        "normalize"
      ],
      "path": "llava/model/utils.py",
      "symbol": "disable_torch_init",
      "evidence_ids": [
        "E1417"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH31",
      "behavior_type": "regularization",
      "detected_pattern": "dropout",
      "description": "Applies dropout inside module computation.",
      "operations": [
        "drop"
      ],
      "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_msg_sem.py",
      "symbol": "PointNet2SemSegMSG",
      "evidence_ids": [
        "E2253"
      ],
      "confidence": "medium"
    },
    {
      "behavior_id": "BEH32",
      "behavior_type": "pointwise_transformation",
      "detected_pattern": "positionwise_feed_forward",
      "description": "Applies two point-wise linear transformations with a nonlinear activation between them.",
      "operations": [
        "linear",
        "activation",
        "linear"
      ],
      "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py",
      "symbol": "PointNet2ClassificationSSG",
      "evidence_ids": [
        "E2270"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH33",
      "behavior_type": "regularization",
      "detected_pattern": "dropout",
      "description": "Applies dropout inside module computation.",
      "operations": [
        "drop"
      ],
      "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py",
      "symbol": "PointNet2ClassificationSSG",
      "evidence_ids": [
        "E2270"
      ],
      "confidence": "medium"
    },
    {
      "behavior_id": "BEH34",
      "behavior_type": "regularization",
      "detected_pattern": "dropout",
      "description": "Applies dropout inside module computation.",
      "operations": [
        "drop"
      ],
      "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_sem.py",
      "symbol": "PointNet2SemSegSSG",
      "evidence_ids": [
        "E2350"
      ],
      "confidence": "medium"
    }
  ],
  "equation_candidates": [
    {
      "equation_id": "EQ1",
      "name": "Point-wise Feed-Forward Transformation",
      "latex": "\\mathrm{FFN}(x)=\\sigma(xW_1+b_1)W_2+b_2",
      "source": "code_pattern",
      "evidence_ids": [
        "E136"
      ],
      "confidence": "medium",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "equation_id": "EQ2",
      "name": "Point-wise Feed-Forward Transformation",
      "latex": "\\mathrm{FFN}(x)=\\sigma(xW_1+b_1)W_2+b_2",
      "source": "code_pattern",
      "evidence_ids": [
        "E445"
      ],
      "confidence": "medium",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "equation_id": "EQ3",
      "name": "Point-wise Feed-Forward Transformation",
      "latex": "\\mathrm{FFN}(x)=\\sigma(xW_1+b_1)W_2+b_2",
      "source": "code_pattern",
      "evidence_ids": [
        "E541"
      ],
      "confidence": "medium",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "equation_id": "EQ4",
      "name": "Point-wise Feed-Forward Transformation",
      "latex": "\\mathrm{FFN}(x)=\\sigma(xW_1+b_1)W_2+b_2",
      "source": "code_pattern",
      "evidence_ids": [
        "E544"
      ],
      "confidence": "medium",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "equation_id": "EQ5",
      "name": "Point-wise Feed-Forward Transformation",
      "latex": "\\mathrm{FFN}(x)=\\sigma(xW_1+b_1)W_2+b_2",
      "source": "code_pattern",
      "evidence_ids": [
        "E547"
      ],
      "confidence": "medium",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "equation_id": "EQ6",
      "name": "Periodic Positional Encoding",
      "latex": "\\mathrm{PE}_{(pos,2i)}=\\sin(pos/10000^{2i/d}),\\quad \\mathrm{PE}_{(pos,2i+1)}=\\cos(pos/10000^{2i/d})",
      "source": "code_pattern",
      "evidence_ids": [
        "E715"
      ],
      "confidence": "medium",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "equation_id": "EQ7",
      "name": "Periodic Positional Encoding",
      "latex": "\\mathrm{PE}_{(pos,2i)}=\\sin(pos/10000^{2i/d}),\\quad \\mathrm{PE}_{(pos,2i+1)}=\\cos(pos/10000^{2i/d})",
      "source": "code_pattern",
      "evidence_ids": [
        "E718"
      ],
      "confidence": "medium",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "equation_id": "EQ8",
      "name": "Periodic Positional Encoding",
      "latex": "\\mathrm{PE}_{(pos,2i)}=\\sin(pos/10000^{2i/d}),\\quad \\mathrm{PE}_{(pos,2i+1)}=\\cos(pos/10000^{2i/d})",
      "source": "code_pattern",
      "evidence_ids": [
        "E721"
      ],
      "confidence": "medium",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "equation_id": "EQ9",
      "name": "Periodic Positional Encoding",
      "latex": "\\mathrm{PE}_{(pos,2i)}=\\sin(pos/10000^{2i/d}),\\quad \\mathrm{PE}_{(pos,2i+1)}=\\cos(pos/10000^{2i/d})",
      "source": "code_pattern",
      "evidence_ids": [
        "E726"
      ],
      "confidence": "medium",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "equation_id": "EQ10",
      "name": "Scaled Dot-Product Attention",
      "latex": "\\mathrm{Attention}(Q,K,V)=\\mathrm{softmax}(QK^T/\\sqrt{d_k})V",
      "source": "code_pattern",
      "evidence_ids": [
        "E733"
      ],
      "confidence": "medium",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "equation_id": "EQ11",
      "name": "Periodic Positional Encoding",
      "latex": "\\mathrm{PE}_{(pos,2i)}=\\sin(pos/10000^{2i/d}),\\quad \\mathrm{PE}_{(pos,2i+1)}=\\cos(pos/10000^{2i/d})",
      "source": "code_pattern",
      "evidence_ids": [
        "E733"
      ],
      "confidence": "medium",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "equation_id": "EQ12",
      "name": "Periodic Positional Encoding",
      "latex": "\\mathrm{PE}_{(pos,2i)}=\\sin(pos/10000^{2i/d}),\\quad \\mathrm{PE}_{(pos,2i+1)}=\\cos(pos/10000^{2i/d})",
      "source": "code_pattern",
      "evidence_ids": [
        "E738"
      ],
      "confidence": "medium",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "equation_id": "EQ13",
      "name": "Periodic Positional Encoding",
      "latex": "\\mathrm{PE}_{(pos,2i)}=\\sin(pos/10000^{2i/d}),\\quad \\mathrm{PE}_{(pos,2i+1)}=\\cos(pos/10000^{2i/d})",
      "source": "code_pattern",
      "evidence_ids": [
        "E745"
      ],
      "confidence": "medium",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "equation_id": "EQ14",
      "name": "Point-wise Feed-Forward Transformation",
      "latex": "\\mathrm{FFN}(x)=\\sigma(xW_1+b_1)W_2+b_2",
      "source": "code_pattern",
      "evidence_ids": [
        "E2270"
      ],
      "confidence": "medium",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    }
  ],
  "architecture_parameters": [
    {
      "parameter_id": "PARAM1",
      "name": "exclude_first_token",
      "value": true,
      "source": "constructor_default",
      "path": "llava/model/multimodal_encoder/point_encoder.py",
      "symbol": "PatchDropout",
      "evidence_ids": [
        "E429"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM2",
      "name": "num_group",
      "value": 32,
      "source": "constructor_default",
      "path": "llava/model/multimodal_encoder/point_encoder.py",
      "symbol": "skeleton_Group",
      "evidence_ids": [
        "E441"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM3",
      "name": "group_size",
      "value": 8,
      "source": "constructor_default",
      "path": "llava/model/multimodal_encoder/point_encoder.py",
      "symbol": "skeleton_Group",
      "evidence_ids": [
        "E441"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM4",
      "name": "drop",
      "value": 0.0,
      "source": "constructor_default",
      "path": "llava/model/multimodal_projector/builder.py",
      "symbol": "Mlp",
      "evidence_ids": [
        "E544"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM5",
      "name": "delay_load",
      "value": false,
      "source": "constructor_default",
      "path": "llava/model/multimodal_projector/builder.py",
      "symbol": "build_vision_projector",
      "evidence_ids": [
        "E547"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM6",
      "name": "eps",
      "value": 1e-06,
      "source": "constructor_default",
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3RMSNorm",
      "evidence_ids": [
        "E710"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM7",
      "name": "max_position_embeddings",
      "value": 2048,
      "source": "constructor_default",
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3RotaryEmbedding",
      "evidence_ids": [
        "E715"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM8",
      "name": "base",
      "value": 10000,
      "source": "constructor_default",
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3RotaryEmbedding",
      "evidence_ids": [
        "E715"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM9",
      "name": "unsqueeze_dim",
      "value": 1,
      "source": "constructor_default",
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "apply_rotary_pos_emb",
      "evidence_ids": [
        "E726"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM10",
      "name": "delay_load",
      "value": false,
      "source": "constructor_default",
      "path": "llava/model/multimodal_encoder/clip_encoder.py",
      "symbol": "CLIPVisionTower",
      "evidence_ids": [
        "E1342"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM11",
      "name": "delay_load",
      "value": false,
      "source": "constructor_default",
      "path": "llava/model/multimodal_encoder/clip_encoder.py",
      "symbol": "CLIPVisionTowerS2",
      "evidence_ids": [
        "E1354"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM12",
      "name": "use_flash_attn",
      "value": false,
      "source": "constructor_default",
      "path": "llava/serve/model_worker.py",
      "symbol": "ModelWorker",
      "evidence_ids": [
        "E1522"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM13",
      "name": "subset_nums",
      "value": -1,
      "source": "constructor_default",
      "path": "pointllm/data/modelnet.py",
      "symbol": "ModelNet",
      "evidence_ids": [
        "E2038"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM14",
      "name": "use_color",
      "value": false,
      "source": "constructor_default",
      "path": "pointllm/data/modelnet.py",
      "symbol": "ModelNet",
      "evidence_ids": [
        "E2038"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM15",
      "name": "subset_nums",
      "value": -1,
      "source": "constructor_default",
      "path": "pointllm/data/modelnet_show.py",
      "symbol": "ModelNet",
      "evidence_ids": [
        "E2108"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM16",
      "name": "use_color",
      "value": false,
      "source": "constructor_default",
      "path": "pointllm/data/modelnet_show.py",
      "symbol": "ModelNet",
      "evidence_ids": [
        "E2108"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM17",
      "name": "last_epoch",
      "value": -1,
      "source": "constructor_default",
      "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py",
      "symbol": "BNMomentumScheduler",
      "evidence_ids": [
        "E2265"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM18",
      "name": "bn",
      "value": true,
      "source": "constructor_default",
      "path": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_modules.py",
      "symbol": "build_shared_mlp",
      "evidence_ids": [
        "E3296"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM19",
      "name": "bn",
      "value": true,
      "source": "constructor_default",
      "path": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_modules.py",
      "symbol": "PointnetSAModuleMSG",
      "evidence_ids": [
        "E3301"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM20",
      "name": "use_xyz",
      "value": true,
      "source": "constructor_default",
      "path": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_modules.py",
      "symbol": "PointnetSAModuleMSG",
      "evidence_ids": [
        "E3301"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM21",
      "name": "bn",
      "value": true,
      "source": "constructor_default",
      "path": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_modules.py",
      "symbol": "PointnetSAModule",
      "evidence_ids": [
        "E3304"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM22",
      "name": "use_xyz",
      "value": true,
      "source": "constructor_default",
      "path": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_modules.py",
      "symbol": "PointnetSAModule",
      "evidence_ids": [
        "E3304"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM23",
      "name": "bn",
      "value": true,
      "source": "constructor_default",
      "path": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_modules.py",
      "symbol": "PointnetFPModule",
      "evidence_ids": [
        "E3307"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM24",
      "name": "prompt_format",
      "value": "QCM-LEA",
      "source": "constructor_default",
      "path": "scripts/convert_sqa_to_llava.py",
      "symbol": "convert_to_llava",
      "evidence_ids": [
        "E3460"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM25",
      "name": "prompt_format",
      "value": "QCM-LEPA",
      "source": "constructor_default",
      "path": "scripts/convert_sqa_to_llava.py",
      "symbol": "convert_to_jsonl",
      "evidence_ids": [
        "E3461"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM26",
      "name": "test_example",
      "value": true,
      "source": "constructor_default",
      "path": "scripts/convert_sqa_to_llava_base_prompt.py",
      "symbol": "create_one_example_chatbot",
      "evidence_ids": [
        "E3508"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM27",
      "name": "test_example",
      "value": true,
      "source": "constructor_default",
      "path": "scripts/convert_sqa_to_llava_base_prompt.py",
      "symbol": "create_one_example",
      "evidence_ids": [
        "E3509"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM28",
      "name": "test_example",
      "value": true,
      "source": "constructor_default",
      "path": "scripts/convert_sqa_to_llava_base_prompt.py",
      "symbol": "create_one_example_gpt4",
      "evidence_ids": [
        "E3510"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM29",
      "name": "use_caption",
      "value": false,
      "source": "constructor_default",
      "path": "scripts/convert_sqa_to_llava_base_prompt.py",
      "symbol": "build_prompt_chatbot",
      "evidence_ids": [
        "E3511"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM30",
      "name": "is_test",
      "value": false,
      "source": "constructor_default",
      "path": "scripts/convert_sqa_to_llava_base_prompt.py",
      "symbol": "build_prompt_chatbot",
      "evidence_ids": [
        "E3511"
      ],
      "confidence": "high"
    }
  ],
  "tensor_roles": [
    {
      "tensor_id": "TENSOR1",
      "name": "x",
      "role": "layer input representation",
      "path": "llava/model/multimodal_encoder/point_encoder.py",
      "symbol": "PatchDropout",
      "evidence_ids": [
        "E429"
      ],
      "confidence": "medium"
    },
    {
      "tensor_id": "TENSOR2",
      "name": "x",
      "role": "layer input representation",
      "path": "llava/model/multimodal_projector/builder.py",
      "symbol": "IdentityMap",
      "evidence_ids": [
        "E537"
      ],
      "confidence": "medium"
    },
    {
      "tensor_id": "TENSOR3",
      "name": "x",
      "role": "layer input representation",
      "path": "llava/model/multimodal_projector/builder.py",
      "symbol": "SimpleResBlock",
      "evidence_ids": [
        "E541"
      ],
      "confidence": "medium"
    },
    {
      "tensor_id": "TENSOR4",
      "name": "x",
      "role": "layer input representation",
      "path": "llava/model/multimodal_projector/builder.py",
      "symbol": "Mlp",
      "evidence_ids": [
        "E544"
      ],
      "confidence": "medium"
    },
    {
      "tensor_id": "TENSOR5",
      "name": "x",
      "role": "layer input representation",
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3RotaryEmbedding",
      "evidence_ids": [
        "E715"
      ],
      "confidence": "medium"
    },
    {
      "tensor_id": "TENSOR6",
      "name": "x",
      "role": "layer input representation",
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3SuScaledRotaryEmbedding",
      "evidence_ids": [
        "E718"
      ],
      "confidence": "medium"
    },
    {
      "tensor_id": "TENSOR7",
      "name": "x",
      "role": "layer input representation",
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3YarnScaledRotaryEmbedding",
      "evidence_ids": [
        "E721"
      ],
      "confidence": "medium"
    },
    {
      "tensor_id": "TENSOR8",
      "name": "x",
      "role": "layer input representation",
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "rotate_half",
      "evidence_ids": [
        "E724"
      ],
      "confidence": "medium"
    },
    {
      "tensor_id": "TENSOR9",
      "name": "q",
      "role": "query representation",
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "apply_rotary_pos_emb",
      "evidence_ids": [
        "E726"
      ],
      "confidence": "medium"
    },
    {
      "tensor_id": "TENSOR10",
      "name": "k",
      "role": "key representation",
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "apply_rotary_pos_emb",
      "evidence_ids": [
        "E726"
      ],
      "confidence": "medium"
    }
  ],
  "innovation_candidates": [],
  "writing_constraints": [
    "Do not mention README-only information.",
    "Do not claim academic novelty without author confirmation.",
    "Do not promote comment-only hints into main method claims.",
    "Excluded source: README.md (ignored by author markers).",
    "Excluded source: pointnet++/Pointnet2_PyTorch/README.rst (excluded from main evidence chain).",
    "Excluded source: release/paper/weight/stage_3/README.md (excluded from main evidence chain).",
    "Excluded source: release/paper/weight/stage_2/README.md (excluded from main evidence chain).",
    "Excluded source: release/5M_data_seting/weight/stage_3/use_stage_5M_data_lr_1e5/README.md (excluded from main evidence chain).",
    "Excluded source: release/5M_data_seting/weight/stage_2/5M_low_lr_1e5/README.md (excluded from main evidence chain).",
    "Excluded source: lava-vicuna_2024_4_Phi-3-mini-4k-instruct/README.md (excluded from main evidence chain).",
    "Excluded source: pretrained_weight/eval_model_weight/sup-simcse-roberta-large/README.md (excluded from main evidence chain).",
    "Excluded source: pretrained_weight/eval_model_weight/all-mpnet-base-v2/README.md (excluded from main evidence chain).",
    "Excluded source: pretrained_weight/clip_used_in_Uni3D/README.md (excluded from main evidence chain)."
  ],
  "alignment_notes": [
    "Execution stages and method stages are separated; method prose should follow method stages, not raw execution order.",
    "Stage mappings connect implementation execution steps to paper-facing method stages.",
    "Author-provided pipeline steps matched: Stage I: Text-First Interface Warmup, Stage II: Rich Instruction Alignment, Stage III: Point-Language Transfer, Runtime and saving behavior."
  ],
  "excluded_sources": [
    {
      "path": "README.md",
      "reason": "ignored by author markers"
    },
    {
      "path": "pointnet++/Pointnet2_PyTorch/README.rst",
      "reason": "excluded from main evidence chain"
    },
    {
      "path": "release/paper/weight/stage_3/README.md",
      "reason": "excluded from main evidence chain"
    },
    {
      "path": "release/paper/weight/stage_2/README.md",
      "reason": "excluded from main evidence chain"
    },
    {
      "path": "release/5M_data_seting/weight/stage_3/use_stage_5M_data_lr_1e5/README.md",
      "reason": "excluded from main evidence chain"
    },
    {
      "path": "release/5M_data_seting/weight/stage_2/5M_low_lr_1e5/README.md",
      "reason": "excluded from main evidence chain"
    },
    {
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/README.md",
      "reason": "excluded from main evidence chain"
    },
    {
      "path": "pretrained_weight/eval_model_weight/sup-simcse-roberta-large/README.md",
      "reason": "excluded from main evidence chain"
    },
    {
      "path": "pretrained_weight/eval_model_weight/all-mpnet-base-v2/README.md",
      "reason": "excluded from main evidence chain"
    },
    {
      "path": "pretrained_weight/clip_used_in_Uni3D/README.md",
      "reason": "excluded from main evidence chain"
    }
  ],
  "author_logic_priority": true,
  "frozen_mechanisms": [
    {
      "mechanism_id": "MECH1",
      "mechanism_name": "Stage I: Text-First Interface Warmup",
      "mechanism_description": "Establish projector-language coupling under mostly frozen backbone settings.",
      "parent_stage_id": "S1",
      "inputs": [
        "['raw_point_cloud', 'text_descriptions']"
      ],
      "outputs": [
        "['aligned_projector_weights']"
      ],
      "implementation_anchor": {
        "path": "/home/cuihengjia/agent/PosterGen/data/greenplm/code/swark-output/code2paper_run_full/paper/method/context_packs/source_core_candidates.json",
        "symbols": []
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E3622"
      ]
    },
    {
      "mechanism_id": "MECH2",
      "mechanism_name": "Stage II: Rich Instruction Alignment",
      "mechanism_description": "Expand from simple descriptions to richer instruction/dialog patterns while preserving projector continuity.",
      "parent_stage_id": "S2",
      "inputs": [
        "['instruction_dialog']"
      ],
      "outputs": [
        "output"
      ],
      "implementation_anchor": {
        "path": "",
        "symbols": []
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2643"
      ]
    }
  ],
  "distinguishing_mechanisms": [],
  "author_logic_mapping": {
    "author_proposed_flow": [
      "Stage I: Text-First Interface Warmup",
      "Stage II: Rich Instruction Alignment",
      "Stage III: Point-Language Transfer",
      "Runtime and saving behavior"
    ],
    "author_supported_flow": [
      "Stage I: Text-First Interface Warmup",
      "Stage II: Rich Instruction Alignment"
    ],
    "author_unsupported_parts": [
      "Stage III: Point-Language Transfer",
      "Runtime and saving behavior"
    ]
  },
  "unsupported_author_parts": [
    "Stage III: Point-Language Transfer",
    "Runtime and saving behavior"
  ],
  "claim_contracts": [
    {
      "claim_id": "C1",
      "claim_intent": "The method contains a paper-facing stage named Stage I: Text-First Interface Warmup.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E3622"
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
        "E2643"
      ],
      "allowed_wording_boundary": "Describe Stage II: Rich Instruction Alignment only using its listed evidence-backed inputs, outputs, modules, and mechanisms.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C5",
      "claim_intent": "Establish projector-language coupling under mostly frozen backbone settings.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E3622"
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
        "E2643"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    }
  ],
  "negative_scope": [
    "Stage III: Point-Language Transfer",
    "Runtime and saving behavior",
    "README-only statements",
    "Logger, checkpoint, seed, cache, path handling, and distributed setup unless tied to hard method evidence",
    "Comments and author hints as standalone fact evidence",
    "Utility symbols: pointllm/train/train.py::ModelArguments, pointllm/train/train.py::DataArguments, pointllm/train/train.py::TrainingArguments, pointllm/train/train.py::safe_save_model_for_hf_trainer, pointllm/train/train.py::train and related sub-symbols",
    "Evidence spans with soft/semantic_hint strength (E1-E7, E22, E45-E51, E67, E79, E97-E106, E126, E128, E205-E216, E227, E229, E231, E235, E238, E271-E282, E314, E317, E320, E322)"
  ]
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
        "E3622",
        "E3622"
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
        "E2643"
      ],
      "mechanism_ids": [
        "MECH2"
      ],
      "source": "method_mechanism",
      "caveats": []
    },
    {
      "claim_id": "C3",
      "claim_text": "The S3 stage implements author-marker method stage: stage iii: point-language transfer.",
      "support_status": "partial",
      "evidence_ids": [],
      "mechanism_ids": [
        "MECH3"
      ],
      "source": "method_mechanism",
      "caveats": []
    },
    {
      "claim_id": "C4",
      "claim_text": "The S4 stage implements author-marker method stage: runtime and saving behavior.",
      "support_status": "partial",
      "evidence_ids": [],
      "mechanism_ids": [
        "MECH4"
      ],
      "source": "method_mechanism",
      "caveats": []
    },
    {
      "claim_id": "C5",
      "claim_text": "Equation candidate Point-wise Feed-Forward Transformation: \\mathrm{FFN}(x)=\\sigma(xW_1+b_1)W_2+b_2",
      "support_status": "supported",
      "evidence_ids": [
        "E136"
      ],
      "mechanism_ids": [],
      "source": "equation_candidate:EQ1",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "claim_id": "C6",
      "claim_text": "Equation candidate Point-wise Feed-Forward Transformation: \\mathrm{FFN}(x)=\\sigma(xW_1+b_1)W_2+b_2",
      "support_status": "supported",
      "evidence_ids": [
        "E445"
      ],
      "mechanism_ids": [],
      "source": "equation_candidate:EQ2",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "claim_id": "C7",
      "claim_text": "Equation candidate Point-wise Feed-Forward Transformation: \\mathrm{FFN}(x)=\\sigma(xW_1+b_1)W_2+b_2",
      "support_status": "supported",
      "evidence_ids": [
        "E541"
      ],
      "mechanism_ids": [],
      "source": "equation_candidate:EQ3",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "claim_id": "C8",
      "claim_text": "Equation candidate Point-wise Feed-Forward Transformation: \\mathrm{FFN}(x)=\\sigma(xW_1+b_1)W_2+b_2",
      "support_status": "supported",
      "evidence_ids": [
        "E544"
      ],
      "mechanism_ids": [],
      "source": "equation_candidate:EQ4",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "claim_id": "C9",
      "claim_text": "Equation candidate Point-wise Feed-Forward Transformation: \\mathrm{FFN}(x)=\\sigma(xW_1+b_1)W_2+b_2",
      "support_status": "supported",
      "evidence_ids": [
        "E547"
      ],
      "mechanism_ids": [],
      "source": "equation_candidate:EQ5",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "claim_id": "C10",
      "claim_text": "Equation candidate Periodic Positional Encoding: \\mathrm{PE}_{(pos,2i)}=\\sin(pos/10000^{2i/d}),\\quad \\mathrm{PE}_{(pos,2i+1)}=\\cos(pos/10000^{2i/d})",
      "support_status": "supported",
      "evidence_ids": [
        "E715"
      ],
      "mechanism_ids": [],
      "source": "equation_candidate:EQ6",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "claim_id": "C11",
      "claim_text": "Equation candidate Periodic Positional Encoding: \\mathrm{PE}_{(pos,2i)}=\\sin(pos/10000^{2i/d}),\\quad \\mathrm{PE}_{(pos,2i+1)}=\\cos(pos/10000^{2i/d})",
      "support_status": "supported",
      "evidence_ids": [
        "E718"
      ],
      "mechanism_ids": [],
      "source": "equation_candidate:EQ7",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "claim_id": "C12",
      "claim_text": "Equation candidate Periodic Positional Encoding: \\mathrm{PE}_{(pos,2i)}=\\sin(pos/10000^{2i/d}),\\quad \\mathrm{PE}_{(pos,2i+1)}=\\cos(pos/10000^{2i/d})",
      "support_status": "supported",
      "evidence_ids": [
        "E721"
      ],
      "mechanism_ids": [],
      "source": "equation_candidate:EQ8",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "claim_id": "C13",
      "claim_text": "Equation candidate Periodic Positional Encoding: \\mathrm{PE}_{(pos,2i)}=\\sin(pos/10000^{2i/d}),\\quad \\mathrm{PE}_{(pos,2i+1)}=\\cos(pos/10000^{2i/d})",
      "support_status": "supported",
      "evidence_ids": [
        "E726"
      ],
      "mechanism_ids": [],
      "source": "equation_candidate:EQ9",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "claim_id": "C14",
      "claim_text": "Equation candidate Scaled Dot-Product Attention: \\mathrm{Attention}(Q,K,V)=\\mathrm{softmax}(QK^T/\\sqrt{d_k})V",
      "support_status": "supported",
      "evidence_ids": [
        "E733"
      ],
      "mechanism_ids": [],
      "source": "equation_candidate:EQ10",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "claim_id": "C15",
      "claim_text": "Equation candidate Periodic Positional Encoding: \\mathrm{PE}_{(pos,2i)}=\\sin(pos/10000^{2i/d}),\\quad \\mathrm{PE}_{(pos,2i+1)}=\\cos(pos/10000^{2i/d})",
      "support_status": "supported",
      "evidence_ids": [
        "E733"
      ],
      "mechanism_ids": [],
      "source": "equation_candidate:EQ11",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "claim_id": "C16",
      "claim_text": "Equation candidate Periodic Positional Encoding: \\mathrm{PE}_{(pos,2i)}=\\sin(pos/10000^{2i/d}),\\quad \\mathrm{PE}_{(pos,2i+1)}=\\cos(pos/10000^{2i/d})",
      "support_status": "supported",
      "evidence_ids": [
        "E738"
      ],
      "mechanism_ids": [],
      "source": "equation_candidate:EQ12",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "claim_id": "C17",
      "claim_text": "Equation candidate Periodic Positional Encoding: \\mathrm{PE}_{(pos,2i)}=\\sin(pos/10000^{2i/d}),\\quad \\mathrm{PE}_{(pos,2i+1)}=\\cos(pos/10000^{2i/d})",
      "support_status": "supported",
      "evidence_ids": [
        "E745"
      ],
      "mechanism_ids": [],
      "source": "equation_candidate:EQ13",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "claim_id": "C18",
      "claim_text": "Equation candidate Point-wise Feed-Forward Transformation: \\mathrm{FFN}(x)=\\sigma(xW_1+b_1)W_2+b_2",
      "support_status": "supported",
      "evidence_ids": [
        "E2270"
      ],
      "mechanism_ids": [],
      "source": "equation_candidate:EQ14",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "claim_id": "C19",
      "claim_text": "The method contains a paper-facing stage named Stage I: Text-First Interface Warmup.",
      "support_status": "supported",
      "evidence_ids": [
        "E3622"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C1",
      "caveats": []
    },
    {
      "claim_id": "C20",
      "claim_text": "The method contains a paper-facing stage named Stage II: Rich Instruction Alignment.",
      "support_status": "supported",
      "evidence_ids": [
        "E2643"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C2",
      "caveats": []
    },
    {
      "claim_id": "C21",
      "claim_text": "Establish projector-language coupling under mostly frozen backbone settings.",
      "support_status": "supported",
      "evidence_ids": [
        "E3622"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C5",
      "caveats": []
    },
    {
      "claim_id": "C22",
      "claim_text": "Expand from simple descriptions to richer instruction/dialog patterns while preserving projector continuity.",
      "support_status": "supported",
      "evidence_ids": [
        "E2643"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C6",
      "caveats": []
    },
    {
      "claim_id": "C23",
      "claim_text": "A compact local-to-global aggregation path is used before point features are conditioned into the LLM.",
      "support_status": "supported",
      "evidence_ids": [
        "E441",
        "E421",
        "E425"
      ],
      "mechanism_ids": [],
      "source": "author_claim:symbol",
      "caveats": [
        "Treat parameter-free wording as a hypothesis until all involved operators are checked for learnable parameters."
      ]
    },
    {
      "claim_id": "C24",
      "claim_text": "Core novelty emphasis is stage design and modality-transfer strategy rather than replacing the base LLM backbone.",
      "support_status": "supported",
      "evidence_ids": [
        "E80",
        "E136"
      ],
      "mechanism_ids": [],
      "source": "author_claim:symbol",
      "caveats": [
        "Final trainable subset per stage must be cross-checked with actual launch scripts/arguments."
      ]
    },
    {
      "claim_id": "C25",
      "claim_text": "Use large text supervision to reduce dependence on scarce point-text pairs.",
      "support_status": "supported",
      "evidence_ids": [
        "E80",
        "E228"
      ],
      "mechanism_ids": [],
      "source": "author_claim:symbol",
      "caveats": [
        "Stage behavior in code is controlled by flags (stage_2, tune_mm_mlp_adapter, fix_llm/fix_pointnet), not explicit Stage-I/II/III classes.",
        "Release scripts should be verified as real content (not LFS pointer) before claiming exact command-level differences.",
        "The method narrative should explain why text-first alignment lowers 3D data pressure."
      ]
    },
    {
      "claim_id": "C26",
      "claim_text": "Keep one projector interface across stages to stabilize transfer from text-side alignment to point-side alignment.",
      "support_status": "supported",
      "evidence_ids": [
        "E547",
        "E80"
      ],
      "mechanism_ids": [],
      "source": "author_claim:symbol",
      "caveats": [
        "A shared bridge simplifies modality transfer logic and keeps the method storyline coherent."
      ]
    },
    {
      "claim_id": "C27",
      "claim_text": "Compress point-token sequences before LLM fusion to keep useful structure with manageable token cost.",
      "support_status": "supported",
      "evidence_ids": [
        "E441",
        "E139"
      ],
      "mechanism_ids": [],
      "source": "author_claim:symbol",
      "caveats": [
        "Phrase as code-aligned aggregation/routing unless parameter counts are explicitly audited at symbol level.",
        "Supports the efficiency-plus-information-retention argument without overloading the language model context."
      ]
    }
  ]
}
```