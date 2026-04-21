# Phase 4 Method Authoring Prompt

Use the frozen Method Evidence, claim contracts, and negative scope to author the Method section.

- latex_expression_preference: balanced

## Method Evidence
```json
{
  "project_id": "code",
  "author_mode": "enhanced",
  "author_confirmation_required": false,
  "method_name": "Transformer Translation Training Pipeline",
  "method_goal": "Train a Transformer sequence-to-sequence model from prepared translation data with architecture-level attention components and scheduled optimization.",
  "implementation_scope": "current codebase only",
  "latex_expression_preference": "balanced",
  "entrypoints": [],
  "stages": [
    {
      "stage_id": "S1",
      "name": "Transformer Computation",
      "purpose": "Compute sequence representations through Transformer layers and sublayers.",
      "inputs": [
        "source token sequence",
        "target prefix sequence",
        "model hyperparameters"
      ],
      "outputs": [
        "decoder predictions",
        "attention representations"
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
          "mechanism_id": "MECH1",
          "description": "The method computes sequence representations with Transformer encoder/decoder components built from attention and position-wise feed-forward sublayers.",
          "support_status": "supported",
          "evidence_ids": [
            "E75",
            "E78",
            "E135",
            "E136",
            "E137",
            "E138",
            "E139",
            "E140",
            "E141",
            "E142",
            "E143",
            "E144",
            "E145",
            "E146",
            "E147",
            "E421",
            "E423",
            "E425",
            "E427",
            "E429",
            "E431",
            "E432",
            "E433",
            "E434",
            "E435",
            "E437",
            "E438",
            "E439",
            "E441",
            "E442",
            "E443",
            "E445",
            "E446",
            "E447",
            "E537",
            "E538",
            "E539",
            "E540",
            "E541",
            "E542",
            "E543",
            "E544",
            "E545",
            "E546",
            "E547",
            "E577",
            "E710",
            "E711",
            "E713",
            "E714",
            "E715",
            "E716",
            "E717",
            "E718",
            "E719",
            "E720",
            "E721",
            "E722",
            "E723",
            "E724",
            "E726",
            "E728",
            "E729",
            "E730",
            "E731",
            "E733",
            "E735",
            "E736",
            "E737",
            "E738",
            "E740",
            "E741",
            "E742",
            "E744",
            "E745",
            "E747",
            "E748",
            "E749",
            "E750",
            "E751",
            "E752",
            "E753",
            "E755",
            "E756",
            "E757",
            "E758",
            "E759",
            "E760",
            "E761",
            "E762",
            "E763",
            "E764",
            "E765",
            "E766",
            "E767",
            "E769",
            "E770",
            "E771",
            "E772",
            "E773",
            "E774",
            "E775",
            "E777",
            "E778",
            "E779",
            "E1014",
            "E1043",
            "E1057",
            "E1073",
            "E1074",
            "E1075",
            "E1076",
            "E1077",
            "E1078",
            "E1079",
            "E1080",
            "E1081",
            "E1114",
            "E1115",
            "E1116",
            "E1117",
            "E1118",
            "E1119",
            "E1120",
            "E1121",
            "E1122",
            "E1155",
            "E1156",
            "E1157",
            "E1158",
            "E1159",
            "E1160",
            "E1161",
            "E1162",
            "E1163",
            "E1164",
            "E1192",
            "E1193",
            "E1194",
            "E1195",
            "E1196",
            "E1197",
            "E1198",
            "E1199",
            "E1200",
            "E1253",
            "E1254",
            "E1255",
            "E1256",
            "E1257",
            "E1259",
            "E1261",
            "E1262",
            "E1263",
            "E1264",
            "E1265",
            "E1266",
            "E1267",
            "E1325",
            "E1335",
            "E1336",
            "E1342",
            "E1343",
            "E1344",
            "E1345",
            "E1346",
            "E1347",
            "E1348",
            "E1349",
            "E1350",
            "E1351",
            "E1352",
            "E1353",
            "E1354",
            "E1355",
            "E1356",
            "E1357",
            "E1358",
            "E1359",
            "E1410",
            "E1411",
            "E1413",
            "E1414",
            "E1415",
            "E1416",
            "E1417",
            "E1419",
            "E1421",
            "E1422",
            "E1423",
            "E1425",
            "E1427",
            "E1428",
            "E1429",
            "E1430",
            "E1431",
            "E1432",
            "E1433",
            "E1434",
            "E1521",
            "E1522",
            "E1523",
            "E1524",
            "E1525",
            "E1526",
            "E1527",
            "E1528",
            "E1529",
            "E1530",
            "E1531",
            "E1532",
            "E1596",
            "E1800",
            "E1808",
            "E2038",
            "E2039",
            "E2041",
            "E2042",
            "E2043",
            "E2045",
            "E2108",
            "E2109",
            "E2111",
            "E2112",
            "E2113",
            "E2114",
            "E2116",
            "E2160",
            "E2161",
            "E2162",
            "E2184",
            "E2211",
            "E2212",
            "E2213",
            "E2214",
            "E2215",
            "E2216",
            "E2245",
            "E2246",
            "E2253",
            "E2254",
            "E2264",
            "E2265",
            "E2266",
            "E2267",
            "E2268",
            "E2269",
            "E2270",
            "E2271",
            "E2272",
            "E2273",
            "E2274",
            "E2276",
            "E2277",
            "E2278",
            "E2279",
            "E2280",
            "E2281",
            "E2282",
            "E2283",
            "E2350",
            "E2351",
            "E2352",
            "E2354",
            "E2539",
            "E2622",
            "E2630",
            "E2718",
            "E2720",
            "E2805",
            "E2806",
            "E2807",
            "E2808",
            "E2809",
            "E2810",
            "E2811",
            "E2812",
            "E2813",
            "E2905",
            "E2906",
            "E3299",
            "E3310",
            "E3360",
            "E3364",
            "E3368",
            "E3372",
            "E3377",
            "E3382",
            "E3388",
            "E3393",
            "E3695",
            "E3696",
            "E3697",
            "E3698",
            "E3699",
            "E3700",
            "E3701",
            "E3702",
            "E3704",
            "E3705",
            "E3706",
            "E3708",
            "E3709"
          ],
          "confidence": "high",
          "submechanisms": [
            {
              "submechanism_id": "SUBMECH1",
              "description": "PointLLMLlamaModel exposes generic code behaviors: pointwise transformation. Detected implementation patterns include positionwise feed forward.",
              "behavior_ids": [
                "BEH1"
              ],
              "equation_ids": [
                "EQ1"
              ],
              "parameter_ids": [],
              "tensor_ids": [],
              "evidence_ids": [
                "E136"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH2",
              "description": "PatchDropout exposes generic code behaviors: regularization. Detected implementation patterns include dropout.",
              "behavior_ids": [
                "BEH2"
              ],
              "equation_ids": [],
              "parameter_ids": [
                "PARAM1"
              ],
              "tensor_ids": [
                "TENSOR1"
              ],
              "evidence_ids": [
                "E429"
              ],
              "confidence": "medium"
            },
            {
              "submechanism_id": "SUBMECH3",
              "description": "PointcloudEncoder exposes generic code behaviors: pointwise transformation, regularization. Detected implementation patterns include positionwise feed forward, dropout.",
              "behavior_ids": [
                "BEH3",
                "BEH4"
              ],
              "equation_ids": [
                "EQ2"
              ],
              "parameter_ids": [],
              "tensor_ids": [],
              "evidence_ids": [
                "E445"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH4",
              "description": "SimpleResBlock exposes generic code behaviors: pointwise transformation, normalization. Detected implementation patterns include positionwise feed forward, layer normalization.",
              "behavior_ids": [
                "BEH5",
                "BEH6"
              ],
              "equation_ids": [
                "EQ3"
              ],
              "parameter_ids": [],
              "tensor_ids": [
                "TENSOR3"
              ],
              "evidence_ids": [
                "E541"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH5",
              "description": "Mlp exposes generic code behaviors: pointwise transformation, normalization, regularization. Detected implementation patterns include positionwise feed forward, layer normalization, dropout.",
              "behavior_ids": [
                "BEH7",
                "BEH8",
                "BEH9"
              ],
              "equation_ids": [
                "EQ4"
              ],
              "parameter_ids": [
                "PARAM4"
              ],
              "tensor_ids": [
                "TENSOR4"
              ],
              "evidence_ids": [
                "E544"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH6",
              "description": "build_vision_projector exposes generic code behaviors: pointwise transformation. Detected implementation patterns include positionwise feed forward.",
              "behavior_ids": [
                "BEH10"
              ],
              "equation_ids": [
                "EQ5"
              ],
              "parameter_ids": [
                "PARAM5"
              ],
              "tensor_ids": [],
              "evidence_ids": [
                "E547"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH7",
              "description": "Phi3RMSNorm exposes generic code behaviors: normalization. Detected implementation patterns include layer normalization.",
              "behavior_ids": [
                "BEH11"
              ],
              "equation_ids": [],
              "parameter_ids": [
                "PARAM6"
              ],
              "tensor_ids": [],
              "evidence_ids": [
                "E710"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH8",
              "description": "Phi3RotaryEmbedding exposes generic code behaviors: representation injection. Detected implementation patterns include sinusoidal positional encoding.",
              "behavior_ids": [
                "BEH12"
              ],
              "equation_ids": [
                "EQ6"
              ],
              "parameter_ids": [
                "PARAM7",
                "PARAM8"
              ],
              "tensor_ids": [
                "TENSOR5"
              ],
              "evidence_ids": [
                "E715"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH9",
              "description": "Phi3SuScaledRotaryEmbedding exposes generic code behaviors: representation injection. Detected implementation patterns include sinusoidal positional encoding.",
              "behavior_ids": [
                "BEH13"
              ],
              "equation_ids": [
                "EQ7"
              ],
              "parameter_ids": [],
              "tensor_ids": [
                "TENSOR6"
              ],
              "evidence_ids": [
                "E718"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH10",
              "description": "Phi3YarnScaledRotaryEmbedding exposes generic code behaviors: representation injection. Detected implementation patterns include sinusoidal positional encoding.",
              "behavior_ids": [
                "BEH14"
              ],
              "equation_ids": [
                "EQ8"
              ],
              "parameter_ids": [],
              "tensor_ids": [
                "TENSOR7"
              ],
              "evidence_ids": [
                "E721"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH11",
              "description": "apply_rotary_pos_emb exposes generic code behaviors: representation injection. Detected implementation patterns include sinusoidal positional encoding.",
              "behavior_ids": [
                "BEH15"
              ],
              "equation_ids": [
                "EQ9"
              ],
              "parameter_ids": [
                "PARAM9"
              ],
              "tensor_ids": [
                "TENSOR9",
                "TENSOR10"
              ],
              "evidence_ids": [
                "E726"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH12",
              "description": "Phi3Attention exposes generic code behaviors: weighted aggregation, representation injection, regularization. Detected implementation patterns include scaled dot product attention, sinusoidal positional encoding, dropout.",
              "behavior_ids": [
                "BEH16",
                "BEH17",
                "BEH18"
              ],
              "equation_ids": [
                "EQ10",
                "EQ11"
              ],
              "parameter_ids": [],
              "tensor_ids": [],
              "evidence_ids": [
                "E733"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH13",
              "description": "Phi3FlashAttention2 exposes generic code behaviors: normalization, representation injection, regularization. Detected implementation patterns include layer normalization, sinusoidal positional encoding, dropout.",
              "behavior_ids": [
                "BEH19",
                "BEH20",
                "BEH21"
              ],
              "equation_ids": [
                "EQ12"
              ],
              "parameter_ids": [],
              "tensor_ids": [],
              "evidence_ids": [
                "E738"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH14",
              "description": "Phi3SdpaAttention exposes generic code behaviors: representation injection, regularization. Detected implementation patterns include sinusoidal positional encoding, dropout.",
              "behavior_ids": [
                "BEH22",
                "BEH23"
              ],
              "equation_ids": [
                "EQ13"
              ],
              "parameter_ids": [],
              "tensor_ids": [],
              "evidence_ids": [
                "E745"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH15",
              "description": "Phi3DecoderLayer exposes generic code behaviors: skip connection, normalization, regularization. Detected implementation patterns include residual connection, layer normalization, dropout.",
              "behavior_ids": [
                "BEH24",
                "BEH25",
                "BEH26"
              ],
              "equation_ids": [],
              "parameter_ids": [],
              "tensor_ids": [],
              "evidence_ids": [
                "E748"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH16",
              "description": "Phi3Model exposes generic code behaviors: repeated composition, regularization. Detected implementation patterns include decoder stack, dropout.",
              "behavior_ids": [
                "BEH27",
                "BEH28"
              ],
              "equation_ids": [],
              "parameter_ids": [],
              "tensor_ids": [],
              "evidence_ids": [
                "E753"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH17",
              "description": "Phi3ForTokenClassification exposes generic code behaviors: regularization. Detected implementation patterns include dropout.",
              "behavior_ids": [
                "BEH29"
              ],
              "equation_ids": [],
              "parameter_ids": [],
              "tensor_ids": [],
              "evidence_ids": [
                "E777"
              ],
              "confidence": "medium"
            },
            {
              "submechanism_id": "SUBMECH18",
              "description": "disable_torch_init exposes generic code behaviors: normalization. Detected implementation patterns include layer normalization.",
              "behavior_ids": [
                "BEH30"
              ],
              "equation_ids": [],
              "parameter_ids": [],
              "tensor_ids": [],
              "evidence_ids": [
                "E1417"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH19",
              "description": "PointNet2SemSegMSG exposes generic code behaviors: regularization. Detected implementation patterns include dropout.",
              "behavior_ids": [
                "BEH31"
              ],
              "equation_ids": [],
              "parameter_ids": [],
              "tensor_ids": [],
              "evidence_ids": [
                "E2253"
              ],
              "confidence": "medium"
            },
            {
              "submechanism_id": "SUBMECH20",
              "description": "PointNet2ClassificationSSG exposes generic code behaviors: pointwise transformation, regularization. Detected implementation patterns include positionwise feed forward, dropout.",
              "behavior_ids": [
                "BEH32",
                "BEH33"
              ],
              "equation_ids": [
                "EQ14"
              ],
              "parameter_ids": [],
              "tensor_ids": [],
              "evidence_ids": [
                "E2270"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH21",
              "description": "PointNet2SemSegSSG exposes generic code behaviors: regularization. Detected implementation patterns include dropout.",
              "behavior_ids": [
                "BEH34"
              ],
              "equation_ids": [],
              "parameter_ids": [],
              "tensor_ids": [],
              "evidence_ids": [
                "E2350"
              ],
              "confidence": "medium"
            }
          ]
        }
      ]
    },
    {
      "stage_id": "S2",
      "name": "Input Preparation",
      "purpose": "Prepare tokenized and serialized data for training.",
      "inputs": [
        "raw corpus files",
        "BPE settings",
        "maximum sequence length"
      ],
      "outputs": [
        "serialized data",
        "vocabulary",
        "filtered train and validation examples"
      ],
      "modules": [],
      "mechanisms": [
        {
          "mechanism_id": "MECH2",
          "description": "The pipeline prepares translation data by converting raw corpora into tokenized, filtered, vocabulary-backed serialized training artifacts.",
          "support_status": "supported",
          "evidence_ids": [
            "E311",
            "E312",
            "E1817",
            "E1818",
            "E1819",
            "E1820",
            "E1821",
            "E1822",
            "E1823",
            "E2281",
            "E2282",
            "E2283",
            "E3075",
            "E3076"
          ],
          "confidence": "high",
          "submechanisms": []
        }
      ]
    },
    {
      "stage_id": "S3",
      "name": "Scheduled Optimization",
      "purpose": "Optimize model parameters with loss computation, optional label smoothing, and learning-rate scheduling.",
      "inputs": [
        "model predictions",
        "target tokens",
        "optimizer settings",
        "warmup steps"
      ],
      "outputs": [
        "updated parameters",
        "training metrics",
        "validation metrics",
        "checkpoints"
      ],
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
          "description": "Training optimizes model parameters by combining forward prediction, loss computation, backpropagation, and the scheduled learning-rate update.",
          "support_status": "supported",
          "evidence_ids": [
            "E1657",
            "E2279"
          ],
          "confidence": "high",
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
    "Author-provided pipeline steps matched: Stage I: Text-first interface warmup, Stage II: Rich instruction alignment, Stage III: Point-language transfer, Runtime and saving behavior."
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
      "mechanism_name": "Stage I: Text-first interface warmup",
      "mechanism_description": "Establish projector-language coupling under mostly frozen backbone settings.",
      "parent_stage_id": "S1",
      "inputs": [
        "['raw_point_cloud']"
      ],
      "outputs": [
        "['output_0']"
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
      "mechanism_name": "Stage II: Rich instruction alignment",
      "mechanism_description": "Expand from simple descriptions to richer instruction/dialog patterns while preserving projector continuity.",
      "parent_stage_id": "S2",
      "inputs": [
        "['input_1']"
      ],
      "outputs": [
        "['output_1']"
      ],
      "implementation_anchor": {
        "path": "",
        "symbols": []
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E3590"
      ]
    },
    {
      "mechanism_id": "MECH3",
      "mechanism_name": "Stage III: Point-language transfer",
      "mechanism_description": "Use point-cloud token features and compact token aggregation to transfer prior alignment to 3D inputs.",
      "parent_stage_id": "S3",
      "inputs": [
        "['input_2']"
      ],
      "outputs": [
        "['output_2']"
      ],
      "implementation_anchor": {
        "path": "/home/cuihengjia/agent/PosterGen/data/greenplm/code/llava/model/multimodal_encoder/point_encoder.py",
        "symbols": [
          "__init__",
          "forward"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E370",
        "E371",
        "E372",
        "E373",
        "E374",
        "E375",
        "E376",
        "E377",
        "E378",
        "E379",
        "E380",
        "E419",
        "E421",
        "E422",
        "E423",
        "E424",
        "E425",
        "E426",
        "E427",
        "E428"
      ]
    },
    {
      "mechanism_id": "MECH4",
      "mechanism_name": "Runtime and saving behavior",
      "mechanism_description": "Control runtime mechanics (trainer save behavior/logging/checkpoint flow).",
      "parent_stage_id": "S3",
      "inputs": [
        "['input_3']"
      ],
      "outputs": [
        "['output_3']"
      ],
      "implementation_anchor": {
        "path": "/home/cuihengjia/agent/PosterGen/data/greenplm/code/pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_utils.py",
        "symbols": [
          "__init__",
          "forward"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E3355",
        "E3356",
        "E3357",
        "E3358",
        "E3359",
        "E3360",
        "E3361",
        "E3362",
        "E3363",
        "E3364",
        "E3365",
        "E3366",
        "E3367",
        "E3368",
        "E3369",
        "E3370",
        "E3371",
        "E3372",
        "E3373",
        "E3374"
      ]
    }
  ],
  "distinguishing_mechanisms": [],
  "author_logic_mapping": {
    "author_proposed_flow": [
      "Stage I: Text-first interface warmup",
      "Stage II: Rich instruction alignment",
      "Stage III: Point-language transfer",
      "Runtime and saving behavior"
    ],
    "author_supported_flow": [
      "Stage I: Text-first interface warmup",
      "Stage II: Rich instruction alignment",
      "Stage III: Point-language transfer",
      "Runtime and saving behavior"
    ],
    "author_unsupported_parts": []
  },
  "unsupported_author_parts": [],
  "claim_contracts": [
    {
      "claim_id": "C1",
      "claim_intent": "The method contains a paper-facing stage named Transformer Computation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E75",
        "E78",
        "E135",
        "E136",
        "E137",
        "E138",
        "E139",
        "E140",
        "E141",
        "E142",
        "E143",
        "E144",
        "E145",
        "E146",
        "E147",
        "E421",
        "E423",
        "E425",
        "E427",
        "E429",
        "E431",
        "E432",
        "E433",
        "E434",
        "E435",
        "E437",
        "E438",
        "E439",
        "E441",
        "E442",
        "E443",
        "E445",
        "E446",
        "E447",
        "E537",
        "E538",
        "E539",
        "E540",
        "E541",
        "E542",
        "E543",
        "E544",
        "E545",
        "E546",
        "E547",
        "E577",
        "E710",
        "E711",
        "E713",
        "E714",
        "E715",
        "E716",
        "E717",
        "E718",
        "E719",
        "E720",
        "E721",
        "E722",
        "E723",
        "E724",
        "E726",
        "E728",
        "E729",
        "E730",
        "E731",
        "E733",
        "E735",
        "E736",
        "E737",
        "E738",
        "E740",
        "E741",
        "E742",
        "E744",
        "E745",
        "E747",
        "E748",
        "E749",
        "E750",
        "E751",
        "E752",
        "E753",
        "E755",
        "E756",
        "E757",
        "E758",
        "E759",
        "E760",
        "E761",
        "E762",
        "E763",
        "E764",
        "E765",
        "E766",
        "E767",
        "E769",
        "E770",
        "E771",
        "E772",
        "E773",
        "E774",
        "E775",
        "E777",
        "E778",
        "E779",
        "E1014",
        "E1043",
        "E1057",
        "E1073",
        "E1074",
        "E1075",
        "E1076",
        "E1077",
        "E1078",
        "E1079",
        "E1080",
        "E1081",
        "E1114",
        "E1115",
        "E1116",
        "E1117",
        "E1118",
        "E1119",
        "E1120",
        "E1121",
        "E1122",
        "E1155",
        "E1156",
        "E1157",
        "E1158",
        "E1159",
        "E1160",
        "E1161",
        "E1162",
        "E1163",
        "E1164",
        "E1192",
        "E1193",
        "E1194",
        "E1195",
        "E1196",
        "E1197",
        "E1198",
        "E1199",
        "E1200",
        "E1253",
        "E1254",
        "E1255",
        "E1256",
        "E1257",
        "E1259",
        "E1261",
        "E1262",
        "E1263",
        "E1264",
        "E1265",
        "E1266",
        "E1267",
        "E1325",
        "E1335",
        "E1336",
        "E1342",
        "E1343",
        "E1344",
        "E1345",
        "E1346",
        "E1347",
        "E1348",
        "E1349",
        "E1350",
        "E1351",
        "E1352",
        "E1353",
        "E1354",
        "E1355",
        "E1356",
        "E1357",
        "E1358",
        "E1359",
        "E1410",
        "E1411",
        "E1413",
        "E1414",
        "E1415",
        "E1416",
        "E1417",
        "E1419",
        "E1421",
        "E1422",
        "E1423",
        "E1425",
        "E1427",
        "E1428",
        "E1429",
        "E1430",
        "E1431",
        "E1432",
        "E1433",
        "E1434",
        "E1521",
        "E1522",
        "E1523",
        "E1524",
        "E1525",
        "E1526",
        "E1527",
        "E1528",
        "E1529",
        "E1530",
        "E1531",
        "E1532",
        "E1596",
        "E1800",
        "E1808",
        "E2038",
        "E2039",
        "E2041",
        "E2042",
        "E2043",
        "E2045",
        "E2108",
        "E2109",
        "E2111",
        "E2112",
        "E2113",
        "E2114",
        "E2116",
        "E2160",
        "E2161",
        "E2162",
        "E2184",
        "E2211",
        "E2212",
        "E2213",
        "E2214",
        "E2215",
        "E2216",
        "E2245",
        "E2246",
        "E2253",
        "E2254",
        "E2264",
        "E2265",
        "E2266",
        "E2267",
        "E2268",
        "E2269",
        "E2270",
        "E2271",
        "E2272",
        "E2273",
        "E2274",
        "E2276",
        "E2277",
        "E2278",
        "E2279",
        "E2280",
        "E2281",
        "E2282",
        "E2283",
        "E2350",
        "E2351",
        "E2352",
        "E2354",
        "E2539",
        "E2622",
        "E2630",
        "E2718",
        "E2720",
        "E2805",
        "E2806",
        "E2807",
        "E2808",
        "E2809",
        "E2810",
        "E2811",
        "E2812",
        "E2813",
        "E2905",
        "E2906",
        "E3299",
        "E3310",
        "E3360",
        "E3364",
        "E3368",
        "E3372",
        "E3377",
        "E3382",
        "E3388",
        "E3393",
        "E3695",
        "E3696",
        "E3697",
        "E3698",
        "E3699",
        "E3700",
        "E3701",
        "E3702",
        "E3704",
        "E3705",
        "E3706",
        "E3708",
        "E3709"
      ],
      "allowed_wording_boundary": "Describe Transformer Computation only using its listed evidence-backed inputs, outputs, modules, and mechanisms.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C2",
      "claim_intent": "The method contains a paper-facing stage named Input Preparation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E311",
        "E312",
        "E1817",
        "E1818",
        "E1819",
        "E1820",
        "E1821",
        "E1822",
        "E1823",
        "E2281",
        "E2282",
        "E2283",
        "E3075",
        "E3076"
      ],
      "allowed_wording_boundary": "Describe Input Preparation only using its listed evidence-backed inputs, outputs, modules, and mechanisms.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C3",
      "claim_intent": "The method contains a paper-facing stage named Scheduled Optimization.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E1657",
        "E2279"
      ],
      "allowed_wording_boundary": "Describe Scheduled Optimization only using its listed evidence-backed inputs, outputs, modules, and mechanisms.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C4",
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
      "claim_id": "C5",
      "claim_intent": "Expand from simple descriptions to richer instruction/dialog patterns while preserving projector continuity.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E3590"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C6",
      "claim_intent": "Use point-cloud token features and compact token aggregation to transfer prior alignment to 3D inputs.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E370",
        "E371",
        "E372",
        "E373",
        "E374",
        "E375",
        "E376",
        "E377",
        "E378",
        "E379",
        "E380",
        "E419",
        "E421",
        "E422",
        "E423",
        "E424",
        "E425",
        "E426",
        "E427",
        "E428"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C7",
      "claim_intent": "Control runtime mechanics (trainer save behavior/logging/checkpoint flow).",
      "support_status": "supported",
      "evidence_span_ids": [
        "E3355",
        "E3356",
        "E3357",
        "E3358",
        "E3359",
        "E3360",
        "E3361",
        "E3362",
        "E3363",
        "E3364",
        "E3365",
        "E3366",
        "E3367",
        "E3368",
        "E3369",
        "E3370",
        "E3371",
        "E3372",
        "E3373",
        "E3374"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    }
  ],
  "negative_scope": [
    "README-only statements cannot enter method prose.",
    "Logger, checkpoint, seed, cache, path handling, and distributed setup are infrastructure unless tied to hard method evidence.",
    "Comments and author hints are navigation signals, not standalone fact evidence.",
    "Do not present these support/utility symbols as method mechanisms: pointllm/train/train.py::ModelArguments, pointllm/train/train.py::DataArguments, pointllm/train/train.py::TrainingArguments, pointllm/train/train.py::safe_save_model_for_hf_trainer, pointllm/train/train.py::train, pointllm/train/train.py::safe_save_model_for_hf_trainer->_save, pointllm/train/train.py::safe_save_model_for_hf_trainer->cpu, pointllm/train/train.py::safe_save_model_for_hf_trainer->items, pointllm/train/train.py::safe_save_model_for_hf_trainer->state_dict, pointllm/train/train.py::train->HfArgumentParser, pointllm/train/train.py::train->Path, pointllm/train/train.py::train->PointLLMTrainer, pointllm/train/train.py::train->ValueError, pointllm/train/train.py::train->_from_config, pointllm/train/train.py::train->build_logger, pointllm/train/train.py::train->enumerate, pointllm/train/train.py::train->float, pointllm/train/train.py::train->format, pointllm/train/train.py::train->from_pretrained, pointllm/train/train.py::train->func"
  ]
}
```

## Claim Evidence Map
```json
{
  "claims": [
    {
      "claim_id": "C1",
      "claim_text": "The method computes sequence representations with Transformer encoder/decoder components built from attention and position-wise feed-forward sublayers.",
      "support_status": "supported",
      "evidence_ids": [
        "E75",
        "E78",
        "E135",
        "E136",
        "E137",
        "E138",
        "E139",
        "E140",
        "E141",
        "E142",
        "E143",
        "E144",
        "E145",
        "E146",
        "E147",
        "E421",
        "E423",
        "E425",
        "E427",
        "E429",
        "E431",
        "E432",
        "E433",
        "E434",
        "E435",
        "E437",
        "E438",
        "E439",
        "E441",
        "E442",
        "E443",
        "E445",
        "E446",
        "E447",
        "E537",
        "E538",
        "E539",
        "E540",
        "E541",
        "E542",
        "E543",
        "E544",
        "E545",
        "E546",
        "E547",
        "E577",
        "E710",
        "E711",
        "E713",
        "E714",
        "E715",
        "E716",
        "E717",
        "E718",
        "E719",
        "E720",
        "E721",
        "E722",
        "E723",
        "E724",
        "E726",
        "E728",
        "E729",
        "E730",
        "E731",
        "E733",
        "E735",
        "E736",
        "E737",
        "E738",
        "E740",
        "E741",
        "E742",
        "E744",
        "E745",
        "E747",
        "E748",
        "E749",
        "E750",
        "E751",
        "E752",
        "E753",
        "E755",
        "E756",
        "E757",
        "E758",
        "E759",
        "E760",
        "E761",
        "E762",
        "E763",
        "E764",
        "E765",
        "E766",
        "E767",
        "E769",
        "E770",
        "E771",
        "E772",
        "E773",
        "E774",
        "E775",
        "E777",
        "E778",
        "E779",
        "E1014",
        "E1043",
        "E1057",
        "E1073",
        "E1074",
        "E1075",
        "E1076",
        "E1077",
        "E1078",
        "E1079",
        "E1080",
        "E1081",
        "E1114",
        "E1115",
        "E1116",
        "E1117",
        "E1118",
        "E1119",
        "E1120",
        "E1121",
        "E1122",
        "E1155",
        "E1156",
        "E1157",
        "E1158",
        "E1159",
        "E1160",
        "E1161",
        "E1162",
        "E1163",
        "E1164",
        "E1192",
        "E1193",
        "E1194",
        "E1195",
        "E1196",
        "E1197",
        "E1198",
        "E1199",
        "E1200",
        "E1253",
        "E1254",
        "E1255",
        "E1256",
        "E1257",
        "E1259",
        "E1261",
        "E1262",
        "E1263",
        "E1264",
        "E1265",
        "E1266",
        "E1267",
        "E1325",
        "E1335",
        "E1336",
        "E1342",
        "E1343",
        "E1344",
        "E1345",
        "E1346",
        "E1347",
        "E1348",
        "E1349",
        "E1350",
        "E1351",
        "E1352",
        "E1353",
        "E1354",
        "E1355",
        "E1356",
        "E1357",
        "E1358",
        "E1359",
        "E1410",
        "E1411",
        "E1413",
        "E1414",
        "E1415",
        "E1416",
        "E1417",
        "E1419",
        "E1421",
        "E1422",
        "E1423",
        "E1425",
        "E1427",
        "E1428",
        "E1429",
        "E1430",
        "E1431",
        "E1432",
        "E1433",
        "E1434",
        "E1521",
        "E1522",
        "E1523",
        "E1524",
        "E1525",
        "E1526",
        "E1527",
        "E1528",
        "E1529",
        "E1530",
        "E1531",
        "E1532",
        "E1596",
        "E1800",
        "E1808",
        "E2038",
        "E2039",
        "E2041",
        "E2042",
        "E2043",
        "E2045",
        "E2108",
        "E2109",
        "E2111",
        "E2112",
        "E2113",
        "E2114",
        "E2116",
        "E2160",
        "E2161",
        "E2162",
        "E2184",
        "E2211",
        "E2212",
        "E2213",
        "E2214",
        "E2215",
        "E2216",
        "E2245",
        "E2246",
        "E2253",
        "E2254",
        "E2264",
        "E2265",
        "E2266",
        "E2267",
        "E2268",
        "E2269",
        "E2270",
        "E2271",
        "E2272",
        "E2273",
        "E2274",
        "E2276",
        "E2277",
        "E2278",
        "E2279",
        "E2280",
        "E2281",
        "E2282",
        "E2283",
        "E2350",
        "E2351",
        "E2352",
        "E2354",
        "E2539",
        "E2622",
        "E2630",
        "E2718",
        "E2720",
        "E2805",
        "E2806",
        "E2807",
        "E2808",
        "E2809",
        "E2810",
        "E2811",
        "E2812",
        "E2813",
        "E2905",
        "E2906",
        "E3299",
        "E3310",
        "E3360",
        "E3364",
        "E3368",
        "E3372",
        "E3377",
        "E3382",
        "E3388",
        "E3393",
        "E3695",
        "E3696",
        "E3697",
        "E3698",
        "E3699",
        "E3700",
        "E3701",
        "E3702",
        "E3704",
        "E3705",
        "E3706",
        "E3708",
        "E3709"
      ],
      "mechanism_ids": [
        "MECH1"
      ],
      "source": "method_mechanism",
      "caveats": []
    },
    {
      "claim_id": "C2",
      "claim_text": "PointLLMLlamaModel exposes generic code behaviors: pointwise transformation. Detected implementation patterns include positionwise feed forward.",
      "support_status": "supported",
      "evidence_ids": [
        "E136"
      ],
      "mechanism_ids": [
        "MECH1"
      ],
      "source": "submechanism:SUBMECH1",
      "caveats": []
    },
    {
      "claim_id": "C3",
      "claim_text": "PatchDropout exposes generic code behaviors: regularization. Detected implementation patterns include dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E429"
      ],
      "mechanism_ids": [
        "MECH1"
      ],
      "source": "submechanism:SUBMECH2",
      "caveats": []
    },
    {
      "claim_id": "C4",
      "claim_text": "PointcloudEncoder exposes generic code behaviors: pointwise transformation, regularization. Detected implementation patterns include positionwise feed forward, dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E445"
      ],
      "mechanism_ids": [
        "MECH1"
      ],
      "source": "submechanism:SUBMECH3",
      "caveats": []
    },
    {
      "claim_id": "C5",
      "claim_text": "SimpleResBlock exposes generic code behaviors: pointwise transformation, normalization. Detected implementation patterns include positionwise feed forward, layer normalization.",
      "support_status": "supported",
      "evidence_ids": [
        "E541"
      ],
      "mechanism_ids": [
        "MECH1"
      ],
      "source": "submechanism:SUBMECH4",
      "caveats": []
    },
    {
      "claim_id": "C6",
      "claim_text": "Mlp exposes generic code behaviors: pointwise transformation, normalization, regularization. Detected implementation patterns include positionwise feed forward, layer normalization, dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E544"
      ],
      "mechanism_ids": [
        "MECH1"
      ],
      "source": "submechanism:SUBMECH5",
      "caveats": []
    },
    {
      "claim_id": "C7",
      "claim_text": "build_vision_projector exposes generic code behaviors: pointwise transformation. Detected implementation patterns include positionwise feed forward.",
      "support_status": "supported",
      "evidence_ids": [
        "E547"
      ],
      "mechanism_ids": [
        "MECH1"
      ],
      "source": "submechanism:SUBMECH6",
      "caveats": []
    },
    {
      "claim_id": "C8",
      "claim_text": "Phi3RMSNorm exposes generic code behaviors: normalization. Detected implementation patterns include layer normalization.",
      "support_status": "supported",
      "evidence_ids": [
        "E710"
      ],
      "mechanism_ids": [
        "MECH1"
      ],
      "source": "submechanism:SUBMECH7",
      "caveats": []
    },
    {
      "claim_id": "C9",
      "claim_text": "Phi3RotaryEmbedding exposes generic code behaviors: representation injection. Detected implementation patterns include sinusoidal positional encoding.",
      "support_status": "supported",
      "evidence_ids": [
        "E715"
      ],
      "mechanism_ids": [
        "MECH1"
      ],
      "source": "submechanism:SUBMECH8",
      "caveats": []
    },
    {
      "claim_id": "C10",
      "claim_text": "Phi3SuScaledRotaryEmbedding exposes generic code behaviors: representation injection. Detected implementation patterns include sinusoidal positional encoding.",
      "support_status": "supported",
      "evidence_ids": [
        "E718"
      ],
      "mechanism_ids": [
        "MECH1"
      ],
      "source": "submechanism:SUBMECH9",
      "caveats": []
    },
    {
      "claim_id": "C11",
      "claim_text": "Phi3YarnScaledRotaryEmbedding exposes generic code behaviors: representation injection. Detected implementation patterns include sinusoidal positional encoding.",
      "support_status": "supported",
      "evidence_ids": [
        "E721"
      ],
      "mechanism_ids": [
        "MECH1"
      ],
      "source": "submechanism:SUBMECH10",
      "caveats": []
    },
    {
      "claim_id": "C12",
      "claim_text": "apply_rotary_pos_emb exposes generic code behaviors: representation injection. Detected implementation patterns include sinusoidal positional encoding.",
      "support_status": "supported",
      "evidence_ids": [
        "E726"
      ],
      "mechanism_ids": [
        "MECH1"
      ],
      "source": "submechanism:SUBMECH11",
      "caveats": []
    },
    {
      "claim_id": "C13",
      "claim_text": "Phi3Attention exposes generic code behaviors: weighted aggregation, representation injection, regularization. Detected implementation patterns include scaled dot product attention, sinusoidal positional encoding, dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E733"
      ],
      "mechanism_ids": [
        "MECH1"
      ],
      "source": "submechanism:SUBMECH12",
      "caveats": []
    },
    {
      "claim_id": "C14",
      "claim_text": "Phi3FlashAttention2 exposes generic code behaviors: normalization, representation injection, regularization. Detected implementation patterns include layer normalization, sinusoidal positional encoding, dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E738"
      ],
      "mechanism_ids": [
        "MECH1"
      ],
      "source": "submechanism:SUBMECH13",
      "caveats": []
    },
    {
      "claim_id": "C15",
      "claim_text": "Phi3SdpaAttention exposes generic code behaviors: representation injection, regularization. Detected implementation patterns include sinusoidal positional encoding, dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E745"
      ],
      "mechanism_ids": [
        "MECH1"
      ],
      "source": "submechanism:SUBMECH14",
      "caveats": []
    },
    {
      "claim_id": "C16",
      "claim_text": "Phi3DecoderLayer exposes generic code behaviors: skip connection, normalization, regularization. Detected implementation patterns include residual connection, layer normalization, dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E748"
      ],
      "mechanism_ids": [
        "MECH1"
      ],
      "source": "submechanism:SUBMECH15",
      "caveats": []
    },
    {
      "claim_id": "C17",
      "claim_text": "Phi3Model exposes generic code behaviors: repeated composition, regularization. Detected implementation patterns include decoder stack, dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E753"
      ],
      "mechanism_ids": [
        "MECH1"
      ],
      "source": "submechanism:SUBMECH16",
      "caveats": []
    },
    {
      "claim_id": "C18",
      "claim_text": "Phi3ForTokenClassification exposes generic code behaviors: regularization. Detected implementation patterns include dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E777"
      ],
      "mechanism_ids": [
        "MECH1"
      ],
      "source": "submechanism:SUBMECH17",
      "caveats": []
    },
    {
      "claim_id": "C19",
      "claim_text": "disable_torch_init exposes generic code behaviors: normalization. Detected implementation patterns include layer normalization.",
      "support_status": "supported",
      "evidence_ids": [
        "E1417"
      ],
      "mechanism_ids": [
        "MECH1"
      ],
      "source": "submechanism:SUBMECH18",
      "caveats": []
    },
    {
      "claim_id": "C20",
      "claim_text": "PointNet2SemSegMSG exposes generic code behaviors: regularization. Detected implementation patterns include dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E2253"
      ],
      "mechanism_ids": [
        "MECH1"
      ],
      "source": "submechanism:SUBMECH19",
      "caveats": []
    },
    {
      "claim_id": "C21",
      "claim_text": "PointNet2ClassificationSSG exposes generic code behaviors: pointwise transformation, regularization. Detected implementation patterns include positionwise feed forward, dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E2270"
      ],
      "mechanism_ids": [
        "MECH1"
      ],
      "source": "submechanism:SUBMECH20",
      "caveats": []
    },
    {
      "claim_id": "C22",
      "claim_text": "PointNet2SemSegSSG exposes generic code behaviors: regularization. Detected implementation patterns include dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E2350"
      ],
      "mechanism_ids": [
        "MECH1"
      ],
      "source": "submechanism:SUBMECH21",
      "caveats": []
    },
    {
      "claim_id": "C23",
      "claim_text": "The pipeline prepares translation data by converting raw corpora into tokenized, filtered, vocabulary-backed serialized training artifacts.",
      "support_status": "supported",
      "evidence_ids": [
        "E311",
        "E312",
        "E1817",
        "E1818",
        "E1819",
        "E1820",
        "E1821",
        "E1822",
        "E1823",
        "E2281",
        "E2282",
        "E2283",
        "E3075",
        "E3076"
      ],
      "mechanism_ids": [
        "MECH2"
      ],
      "source": "method_mechanism",
      "caveats": []
    },
    {
      "claim_id": "C24",
      "claim_text": "Training optimizes model parameters by combining forward prediction, loss computation, backpropagation, and the scheduled learning-rate update.",
      "support_status": "supported",
      "evidence_ids": [
        "E1657",
        "E2279"
      ],
      "mechanism_ids": [
        "MECH3"
      ],
      "source": "method_mechanism",
      "caveats": []
    },
    {
      "claim_id": "C25",
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
      "claim_id": "C26",
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
      "claim_id": "C27",
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
      "claim_id": "C28",
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
      "claim_id": "C29",
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
      "claim_id": "C30",
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
      "claim_id": "C31",
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
      "claim_id": "C32",
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
      "claim_id": "C33",
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
      "claim_id": "C34",
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
      "claim_id": "C35",
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
      "claim_id": "C36",
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
      "claim_id": "C37",
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
      "claim_id": "C38",
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
      "claim_id": "C39",
      "claim_text": "The method contains a paper-facing stage named Transformer Computation.",
      "support_status": "supported",
      "evidence_ids": [
        "E75",
        "E78",
        "E135",
        "E136",
        "E137",
        "E138",
        "E139",
        "E140",
        "E141",
        "E142",
        "E143",
        "E144",
        "E145",
        "E146",
        "E147",
        "E421",
        "E423",
        "E425",
        "E427",
        "E429",
        "E431",
        "E432",
        "E433",
        "E434",
        "E435",
        "E437",
        "E438",
        "E439",
        "E441",
        "E442",
        "E443",
        "E445",
        "E446",
        "E447",
        "E537",
        "E538",
        "E539",
        "E540",
        "E541",
        "E542",
        "E543",
        "E544",
        "E545",
        "E546",
        "E547",
        "E577",
        "E710",
        "E711",
        "E713",
        "E714",
        "E715",
        "E716",
        "E717",
        "E718",
        "E719",
        "E720",
        "E721",
        "E722",
        "E723",
        "E724",
        "E726",
        "E728",
        "E729",
        "E730",
        "E731",
        "E733",
        "E735",
        "E736",
        "E737",
        "E738",
        "E740",
        "E741",
        "E742",
        "E744",
        "E745",
        "E747",
        "E748",
        "E749",
        "E750",
        "E751",
        "E752",
        "E753",
        "E755",
        "E756",
        "E757",
        "E758",
        "E759",
        "E760",
        "E761",
        "E762",
        "E763",
        "E764",
        "E765",
        "E766",
        "E767",
        "E769",
        "E770",
        "E771",
        "E772",
        "E773",
        "E774",
        "E775",
        "E777",
        "E778",
        "E779",
        "E1014",
        "E1043",
        "E1057",
        "E1073",
        "E1074",
        "E1075",
        "E1076",
        "E1077",
        "E1078",
        "E1079",
        "E1080",
        "E1081",
        "E1114",
        "E1115",
        "E1116",
        "E1117",
        "E1118",
        "E1119",
        "E1120",
        "E1121",
        "E1122",
        "E1155",
        "E1156",
        "E1157",
        "E1158",
        "E1159",
        "E1160",
        "E1161",
        "E1162",
        "E1163",
        "E1164",
        "E1192",
        "E1193",
        "E1194",
        "E1195",
        "E1196",
        "E1197",
        "E1198",
        "E1199",
        "E1200",
        "E1253",
        "E1254",
        "E1255",
        "E1256",
        "E1257",
        "E1259",
        "E1261",
        "E1262",
        "E1263",
        "E1264",
        "E1265",
        "E1266",
        "E1267",
        "E1325",
        "E1335",
        "E1336",
        "E1342",
        "E1343",
        "E1344",
        "E1345",
        "E1346",
        "E1347",
        "E1348",
        "E1349",
        "E1350",
        "E1351",
        "E1352",
        "E1353",
        "E1354",
        "E1355",
        "E1356",
        "E1357",
        "E1358",
        "E1359",
        "E1410",
        "E1411",
        "E1413",
        "E1414",
        "E1415",
        "E1416",
        "E1417",
        "E1419",
        "E1421",
        "E1422",
        "E1423",
        "E1425",
        "E1427",
        "E1428",
        "E1429",
        "E1430",
        "E1431",
        "E1432",
        "E1433",
        "E1434",
        "E1521",
        "E1522",
        "E1523",
        "E1524",
        "E1525",
        "E1526",
        "E1527",
        "E1528",
        "E1529",
        "E1530",
        "E1531",
        "E1532",
        "E1596",
        "E1800",
        "E1808",
        "E2038",
        "E2039",
        "E2041",
        "E2042",
        "E2043",
        "E2045",
        "E2108",
        "E2109",
        "E2111",
        "E2112",
        "E2113",
        "E2114",
        "E2116",
        "E2160",
        "E2161",
        "E2162",
        "E2184",
        "E2211",
        "E2212",
        "E2213",
        "E2214",
        "E2215",
        "E2216",
        "E2245",
        "E2246",
        "E2253",
        "E2254",
        "E2264",
        "E2265",
        "E2266",
        "E2267",
        "E2268",
        "E2269",
        "E2270",
        "E2271",
        "E2272",
        "E2273",
        "E2274",
        "E2276",
        "E2277",
        "E2278",
        "E2279",
        "E2280",
        "E2281",
        "E2282",
        "E2283",
        "E2350",
        "E2351",
        "E2352",
        "E2354",
        "E2539",
        "E2622",
        "E2630",
        "E2718",
        "E2720",
        "E2805",
        "E2806",
        "E2807",
        "E2808",
        "E2809",
        "E2810",
        "E2811",
        "E2812",
        "E2813",
        "E2905",
        "E2906",
        "E3299",
        "E3310",
        "E3360",
        "E3364",
        "E3368",
        "E3372",
        "E3377",
        "E3382",
        "E3388",
        "E3393",
        "E3695",
        "E3696",
        "E3697",
        "E3698",
        "E3699",
        "E3700",
        "E3701",
        "E3702",
        "E3704",
        "E3705",
        "E3706",
        "E3708",
        "E3709"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C1",
      "caveats": []
    },
    {
      "claim_id": "C40",
      "claim_text": "The method contains a paper-facing stage named Input Preparation.",
      "support_status": "supported",
      "evidence_ids": [
        "E311",
        "E312",
        "E1817",
        "E1818",
        "E1819",
        "E1820",
        "E1821",
        "E1822",
        "E1823",
        "E2281",
        "E2282",
        "E2283",
        "E3075",
        "E3076"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C2",
      "caveats": []
    },
    {
      "claim_id": "C41",
      "claim_text": "The method contains a paper-facing stage named Scheduled Optimization.",
      "support_status": "supported",
      "evidence_ids": [
        "E1657",
        "E2279"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C3",
      "caveats": []
    },
    {
      "claim_id": "C42",
      "claim_text": "Establish projector-language coupling under mostly frozen backbone settings.",
      "support_status": "supported",
      "evidence_ids": [
        "E3622"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C4",
      "caveats": []
    },
    {
      "claim_id": "C43",
      "claim_text": "Expand from simple descriptions to richer instruction/dialog patterns while preserving projector continuity.",
      "support_status": "supported",
      "evidence_ids": [
        "E3590"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C5",
      "caveats": []
    },
    {
      "claim_id": "C44",
      "claim_text": "Use point-cloud token features and compact token aggregation to transfer prior alignment to 3D inputs.",
      "support_status": "supported",
      "evidence_ids": [
        "E370",
        "E371",
        "E372",
        "E373",
        "E374",
        "E375",
        "E376",
        "E377",
        "E378",
        "E379",
        "E380",
        "E419",
        "E421",
        "E422",
        "E423",
        "E424",
        "E425",
        "E426",
        "E427",
        "E428"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C6",
      "caveats": []
    },
    {
      "claim_id": "C45",
      "claim_text": "Control runtime mechanics (trainer save behavior/logging/checkpoint flow).",
      "support_status": "supported",
      "evidence_ids": [
        "E3355",
        "E3356",
        "E3357",
        "E3358",
        "E3359",
        "E3360",
        "E3361",
        "E3362",
        "E3363",
        "E3364",
        "E3365",
        "E3366",
        "E3367",
        "E3368",
        "E3369",
        "E3370",
        "E3371",
        "E3372",
        "E3373",
        "E3374"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C7",
      "caveats": []
    },
    {
      "claim_id": "C46",
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
      "claim_id": "C47",
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
      "claim_id": "C48",
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
      "claim_id": "C49",
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
      "claim_id": "C50",
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