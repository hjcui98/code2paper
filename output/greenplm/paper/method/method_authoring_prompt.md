# Phase 4 Method Authoring Prompt

Use the frozen Method Evidence, claim contracts, and negative scope to author the Method section.

## Method Evidence
```json
{
  "project_id": "code",
  "author_mode": "none",
  "author_confirmation_required": true,
  "method_name": "Transformer Translation Training Pipeline",
  "method_goal": "Train a Transformer sequence-to-sequence model from prepared translation data with architecture-level attention components and scheduled optimization.",
  "implementation_scope": "current codebase only",
  "entrypoints": [
    "pointnet++/Pointnet2_PyTorch/pointnet2/train.py:main"
  ],
  "stages": [
    {
      "stage_id": "S1",
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
          "mechanism_id": "MECH1",
          "description": "The pipeline prepares translation data by converting raw corpora into tokenized, filtered, vocabulary-backed serialized training artifacts.",
          "support_status": "supported",
          "evidence_ids": [
            "E1418",
            "E1419",
            "E1420",
            "E1421",
            "E1422",
            "E1423",
            "E1424",
            "E2106",
            "E2107",
            "E2108",
            "E2982",
            "E2983",
            "E3074",
            "E3075"
          ],
          "confidence": "medium",
          "submechanisms": []
        }
      ]
    },
    {
      "stage_id": "S2",
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
          "description": "The method computes sequence representations with Transformer encoder/decoder components built from attention and position-wise feed-forward sublayers.",
          "support_status": "supported",
          "evidence_ids": [
            "E107",
            "E108",
            "E110",
            "E111",
            "E112",
            "E113",
            "E114",
            "E115",
            "E116",
            "E117",
            "E118",
            "E119",
            "E120",
            "E121",
            "E123",
            "E125",
            "E126",
            "E127",
            "E128",
            "E130",
            "E132",
            "E133",
            "E134",
            "E135",
            "E137",
            "E138",
            "E139",
            "E141",
            "E142",
            "E144",
            "E145",
            "E146",
            "E147",
            "E148",
            "E149",
            "E150",
            "E152",
            "E153",
            "E154",
            "E155",
            "E156",
            "E157",
            "E158",
            "E159",
            "E160",
            "E161",
            "E162",
            "E163",
            "E164",
            "E166",
            "E167",
            "E168",
            "E169",
            "E170",
            "E171",
            "E172",
            "E174",
            "E175",
            "E176",
            "E411",
            "E440",
            "E454",
            "E470",
            "E471",
            "E472",
            "E473",
            "E474",
            "E475",
            "E476",
            "E477",
            "E478",
            "E511",
            "E512",
            "E513",
            "E514",
            "E515",
            "E516",
            "E517",
            "E518",
            "E519",
            "E552",
            "E553",
            "E554",
            "E555",
            "E556",
            "E557",
            "E558",
            "E559",
            "E560",
            "E561",
            "E589",
            "E590",
            "E591",
            "E592",
            "E593",
            "E594",
            "E595",
            "E596",
            "E597",
            "E650",
            "E651",
            "E652",
            "E653",
            "E654",
            "E656",
            "E658",
            "E659",
            "E660",
            "E661",
            "E662",
            "E663",
            "E664",
            "E722",
            "E732",
            "E733",
            "E739",
            "E740",
            "E741",
            "E742",
            "E743",
            "E744",
            "E745",
            "E746",
            "E747",
            "E748",
            "E749",
            "E750",
            "E751",
            "E752",
            "E753",
            "E754",
            "E755",
            "E756",
            "E848",
            "E850",
            "E852",
            "E854",
            "E856",
            "E858",
            "E859",
            "E860",
            "E861",
            "E862",
            "E864",
            "E865",
            "E866",
            "E868",
            "E869",
            "E870",
            "E872",
            "E873",
            "E874",
            "E964",
            "E965",
            "E966",
            "E967",
            "E968",
            "E969",
            "E970",
            "E971",
            "E972",
            "E973",
            "E974",
            "E1011",
            "E1012",
            "E1014",
            "E1015",
            "E1016",
            "E1017",
            "E1018",
            "E1020",
            "E1022",
            "E1023",
            "E1024",
            "E1026",
            "E1028",
            "E1029",
            "E1030",
            "E1031",
            "E1032",
            "E1033",
            "E1034",
            "E1035",
            "E1122",
            "E1123",
            "E1124",
            "E1125",
            "E1126",
            "E1127",
            "E1128",
            "E1129",
            "E1130",
            "E1131",
            "E1132",
            "E1133",
            "E1197",
            "E1401",
            "E1409",
            "E1639",
            "E1640",
            "E1642",
            "E1643",
            "E1644",
            "E1646",
            "E1709",
            "E1710",
            "E1712",
            "E1713",
            "E1714",
            "E1715",
            "E1717",
            "E1799",
            "E1800",
            "E1801",
            "E1802",
            "E1803",
            "E1804",
            "E1805",
            "E1806",
            "E1807",
            "E1808",
            "E1809",
            "E1810",
            "E1811",
            "E1869",
            "E1870",
            "E1871",
            "E1893",
            "E1910",
            "E2001",
            "E2004",
            "E2036",
            "E2037",
            "E2038",
            "E2039",
            "E2040",
            "E2041",
            "E2070",
            "E2071",
            "E2078",
            "E2079",
            "E2089",
            "E2090",
            "E2091",
            "E2092",
            "E2093",
            "E2094",
            "E2095",
            "E2096",
            "E2097",
            "E2098",
            "E2099",
            "E2101",
            "E2102",
            "E2103",
            "E2104",
            "E2105",
            "E2106",
            "E2107",
            "E2108",
            "E2175",
            "E2176",
            "E2177",
            "E2179",
            "E2373",
            "E2456",
            "E2464",
            "E2552",
            "E2554",
            "E2639",
            "E2640",
            "E2641",
            "E2642",
            "E2643",
            "E2644",
            "E2645",
            "E2646",
            "E2647",
            "E2739",
            "E2740",
            "E3298",
            "E3309",
            "E3359",
            "E3363",
            "E3367",
            "E3371",
            "E3376",
            "E3381",
            "E3387",
            "E3392",
            "E3694",
            "E3695",
            "E3696",
            "E3697",
            "E3698",
            "E3699",
            "E3700",
            "E3701",
            "E3703",
            "E3704",
            "E3705",
            "E3707",
            "E3708"
          ],
          "confidence": "medium",
          "submechanisms": [
            {
              "submechanism_id": "SUBMECH1",
              "description": "Phi3RMSNorm exposes generic code behaviors: normalization. Detected implementation patterns include layer normalization.",
              "behavior_ids": [
                "BEH1"
              ],
              "equation_ids": [],
              "parameter_ids": [
                "PARAM1"
              ],
              "tensor_ids": [],
              "evidence_ids": [
                "E107"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH2",
              "description": "Phi3RotaryEmbedding exposes generic code behaviors: representation injection. Detected implementation patterns include sinusoidal positional encoding.",
              "behavior_ids": [
                "BEH2"
              ],
              "equation_ids": [
                "EQ1"
              ],
              "parameter_ids": [
                "PARAM2",
                "PARAM3"
              ],
              "tensor_ids": [
                "TENSOR1"
              ],
              "evidence_ids": [
                "E112"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH3",
              "description": "Phi3SuScaledRotaryEmbedding exposes generic code behaviors: representation injection. Detected implementation patterns include sinusoidal positional encoding.",
              "behavior_ids": [
                "BEH3"
              ],
              "equation_ids": [
                "EQ2"
              ],
              "parameter_ids": [],
              "tensor_ids": [
                "TENSOR2"
              ],
              "evidence_ids": [
                "E115"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH4",
              "description": "Phi3YarnScaledRotaryEmbedding exposes generic code behaviors: representation injection. Detected implementation patterns include sinusoidal positional encoding.",
              "behavior_ids": [
                "BEH4"
              ],
              "equation_ids": [
                "EQ3"
              ],
              "parameter_ids": [],
              "tensor_ids": [
                "TENSOR3"
              ],
              "evidence_ids": [
                "E118"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH5",
              "description": "apply_rotary_pos_emb exposes generic code behaviors: representation injection. Detected implementation patterns include sinusoidal positional encoding.",
              "behavior_ids": [
                "BEH5"
              ],
              "equation_ids": [
                "EQ4"
              ],
              "parameter_ids": [
                "PARAM4"
              ],
              "tensor_ids": [
                "TENSOR5",
                "TENSOR6"
              ],
              "evidence_ids": [
                "E123"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH6",
              "description": "Phi3Attention exposes generic code behaviors: weighted aggregation, representation injection, regularization. Detected implementation patterns include scaled dot product attention, sinusoidal positional encoding, dropout.",
              "behavior_ids": [
                "BEH6",
                "BEH7",
                "BEH8"
              ],
              "equation_ids": [
                "EQ5",
                "EQ6"
              ],
              "parameter_ids": [],
              "tensor_ids": [],
              "evidence_ids": [
                "E130"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH7",
              "description": "Phi3FlashAttention2 exposes generic code behaviors: normalization, representation injection, regularization. Detected implementation patterns include layer normalization, sinusoidal positional encoding, dropout.",
              "behavior_ids": [
                "BEH9",
                "BEH10",
                "BEH11"
              ],
              "equation_ids": [
                "EQ7"
              ],
              "parameter_ids": [],
              "tensor_ids": [],
              "evidence_ids": [
                "E135"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH8",
              "description": "Phi3SdpaAttention exposes generic code behaviors: representation injection, regularization. Detected implementation patterns include sinusoidal positional encoding, dropout.",
              "behavior_ids": [
                "BEH12",
                "BEH13"
              ],
              "equation_ids": [
                "EQ8"
              ],
              "parameter_ids": [],
              "tensor_ids": [],
              "evidence_ids": [
                "E142"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH9",
              "description": "Phi3DecoderLayer exposes generic code behaviors: skip connection, normalization, regularization. Detected implementation patterns include residual connection, layer normalization, dropout.",
              "behavior_ids": [
                "BEH14",
                "BEH15",
                "BEH16"
              ],
              "equation_ids": [],
              "parameter_ids": [],
              "tensor_ids": [],
              "evidence_ids": [
                "E145"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH10",
              "description": "Phi3Model exposes generic code behaviors: repeated composition, regularization. Detected implementation patterns include decoder stack, dropout.",
              "behavior_ids": [
                "BEH17",
                "BEH18"
              ],
              "equation_ids": [],
              "parameter_ids": [],
              "tensor_ids": [],
              "evidence_ids": [
                "E150"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH11",
              "description": "Phi3ForTokenClassification exposes generic code behaviors: regularization. Detected implementation patterns include dropout.",
              "behavior_ids": [
                "BEH19"
              ],
              "equation_ids": [],
              "parameter_ids": [],
              "tensor_ids": [],
              "evidence_ids": [
                "E174"
              ],
              "confidence": "medium"
            },
            {
              "submechanism_id": "SUBMECH12",
              "description": "PatchDropout exposes generic code behaviors: regularization. Detected implementation patterns include dropout.",
              "behavior_ids": [
                "BEH20"
              ],
              "equation_ids": [],
              "parameter_ids": [
                "PARAM7"
              ],
              "tensor_ids": [
                "TENSOR7"
              ],
              "evidence_ids": [
                "E856"
              ],
              "confidence": "medium"
            },
            {
              "submechanism_id": "SUBMECH13",
              "description": "PointcloudEncoder exposes generic code behaviors: pointwise transformation, regularization. Detected implementation patterns include positionwise feed forward, dropout.",
              "behavior_ids": [
                "BEH21",
                "BEH22"
              ],
              "equation_ids": [
                "EQ9"
              ],
              "parameter_ids": [],
              "tensor_ids": [],
              "evidence_ids": [
                "E872"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH14",
              "description": "SimpleResBlock exposes generic code behaviors: pointwise transformation, normalization. Detected implementation patterns include positionwise feed forward, layer normalization.",
              "behavior_ids": [
                "BEH23",
                "BEH24"
              ],
              "equation_ids": [
                "EQ10"
              ],
              "parameter_ids": [],
              "tensor_ids": [
                "TENSOR9"
              ],
              "evidence_ids": [
                "E968"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH15",
              "description": "Mlp exposes generic code behaviors: pointwise transformation, normalization, regularization. Detected implementation patterns include positionwise feed forward, layer normalization, dropout.",
              "behavior_ids": [
                "BEH25",
                "BEH26",
                "BEH27"
              ],
              "equation_ids": [
                "EQ11"
              ],
              "parameter_ids": [
                "PARAM10"
              ],
              "tensor_ids": [
                "TENSOR10"
              ],
              "evidence_ids": [
                "E971"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH16",
              "description": "build_vision_projector exposes generic code behaviors: pointwise transformation. Detected implementation patterns include positionwise feed forward.",
              "behavior_ids": [
                "BEH28"
              ],
              "equation_ids": [
                "EQ12"
              ],
              "parameter_ids": [
                "PARAM11"
              ],
              "tensor_ids": [],
              "evidence_ids": [
                "E974"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH17",
              "description": "disable_torch_init exposes generic code behaviors: normalization. Detected implementation patterns include layer normalization.",
              "behavior_ids": [
                "BEH29"
              ],
              "equation_ids": [],
              "parameter_ids": [],
              "tensor_ids": [],
              "evidence_ids": [
                "E1018"
              ],
              "confidence": "high"
            },
            {
              "submechanism_id": "SUBMECH18",
              "description": "PointLLMLlamaModel exposes generic code behaviors: pointwise transformation. Detected implementation patterns include positionwise feed forward.",
              "behavior_ids": [
                "BEH30"
              ],
              "equation_ids": [
                "EQ13"
              ],
              "parameter_ids": [],
              "tensor_ids": [],
              "evidence_ids": [
                "E1800"
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
                "E2078"
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
                "E2095"
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
                "E2175"
              ],
              "confidence": "medium"
            }
          ]
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
            "E1258",
            "E2104"
          ],
          "confidence": "medium",
          "submechanisms": []
        }
      ]
    }
  ],
  "behavior_patterns": [
    {
      "behavior_id": "BEH1",
      "behavior_type": "normalization",
      "detected_pattern": "layer_normalization",
      "description": "Applies layer normalization around module computation.",
      "operations": [
        "normalize"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3RMSNorm",
      "evidence_ids": [
        "E107"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH2",
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
        "E112"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH3",
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
        "E115"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH4",
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
        "E118"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH5",
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
        "E123"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH6",
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
        "E130"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH7",
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
        "E130"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH8",
      "behavior_type": "regularization",
      "detected_pattern": "dropout",
      "description": "Applies dropout inside module computation.",
      "operations": [
        "drop"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3Attention",
      "evidence_ids": [
        "E130"
      ],
      "confidence": "medium"
    },
    {
      "behavior_id": "BEH9",
      "behavior_type": "normalization",
      "detected_pattern": "layer_normalization",
      "description": "Applies layer normalization around module computation.",
      "operations": [
        "normalize"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3FlashAttention2",
      "evidence_ids": [
        "E135"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH10",
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
        "E135"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH11",
      "behavior_type": "regularization",
      "detected_pattern": "dropout",
      "description": "Applies dropout inside module computation.",
      "operations": [
        "drop"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3FlashAttention2",
      "evidence_ids": [
        "E135"
      ],
      "confidence": "medium"
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
      "symbol": "Phi3SdpaAttention",
      "evidence_ids": [
        "E142"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH13",
      "behavior_type": "regularization",
      "detected_pattern": "dropout",
      "description": "Applies dropout inside module computation.",
      "operations": [
        "drop"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3SdpaAttention",
      "evidence_ids": [
        "E142"
      ],
      "confidence": "medium"
    },
    {
      "behavior_id": "BEH14",
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
        "E145"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH15",
      "behavior_type": "normalization",
      "detected_pattern": "layer_normalization",
      "description": "Applies layer normalization around module computation.",
      "operations": [
        "normalize"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3DecoderLayer",
      "evidence_ids": [
        "E145"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH16",
      "behavior_type": "regularization",
      "detected_pattern": "dropout",
      "description": "Applies dropout inside module computation.",
      "operations": [
        "drop"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3DecoderLayer",
      "evidence_ids": [
        "E145"
      ],
      "confidence": "medium"
    },
    {
      "behavior_id": "BEH17",
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
        "E150"
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
      "symbol": "Phi3Model",
      "evidence_ids": [
        "E150"
      ],
      "confidence": "medium"
    },
    {
      "behavior_id": "BEH19",
      "behavior_type": "regularization",
      "detected_pattern": "dropout",
      "description": "Applies dropout inside module computation.",
      "operations": [
        "drop"
      ],
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3ForTokenClassification",
      "evidence_ids": [
        "E174"
      ],
      "confidence": "medium"
    },
    {
      "behavior_id": "BEH20",
      "behavior_type": "regularization",
      "detected_pattern": "dropout",
      "description": "Applies dropout inside module computation.",
      "operations": [
        "drop"
      ],
      "path": "llava/model/multimodal_encoder/point_encoder.py",
      "symbol": "PatchDropout",
      "evidence_ids": [
        "E856"
      ],
      "confidence": "medium"
    },
    {
      "behavior_id": "BEH21",
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
        "E872"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH22",
      "behavior_type": "regularization",
      "detected_pattern": "dropout",
      "description": "Applies dropout inside module computation.",
      "operations": [
        "drop"
      ],
      "path": "llava/model/multimodal_encoder/point_encoder.py",
      "symbol": "PointcloudEncoder",
      "evidence_ids": [
        "E872"
      ],
      "confidence": "medium"
    },
    {
      "behavior_id": "BEH23",
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
        "E968"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH24",
      "behavior_type": "normalization",
      "detected_pattern": "layer_normalization",
      "description": "Applies layer normalization around module computation.",
      "operations": [
        "normalize"
      ],
      "path": "llava/model/multimodal_projector/builder.py",
      "symbol": "SimpleResBlock",
      "evidence_ids": [
        "E968"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH25",
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
        "E971"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH26",
      "behavior_type": "normalization",
      "detected_pattern": "layer_normalization",
      "description": "Applies layer normalization around module computation.",
      "operations": [
        "normalize"
      ],
      "path": "llava/model/multimodal_projector/builder.py",
      "symbol": "Mlp",
      "evidence_ids": [
        "E971"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH27",
      "behavior_type": "regularization",
      "detected_pattern": "dropout",
      "description": "Applies dropout inside module computation.",
      "operations": [
        "drop"
      ],
      "path": "llava/model/multimodal_projector/builder.py",
      "symbol": "Mlp",
      "evidence_ids": [
        "E971"
      ],
      "confidence": "medium"
    },
    {
      "behavior_id": "BEH28",
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
        "E974"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH29",
      "behavior_type": "normalization",
      "detected_pattern": "layer_normalization",
      "description": "Applies layer normalization around module computation.",
      "operations": [
        "normalize"
      ],
      "path": "llava/model/utils.py",
      "symbol": "disable_torch_init",
      "evidence_ids": [
        "E1018"
      ],
      "confidence": "high"
    },
    {
      "behavior_id": "BEH30",
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
        "E1800"
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
        "E2078"
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
        "E2095"
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
        "E2095"
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
        "E2175"
      ],
      "confidence": "medium"
    }
  ],
  "equation_candidates": [
    {
      "equation_id": "EQ1",
      "name": "Periodic Positional Encoding",
      "latex": "\\mathrm{PE}_{(pos,2i)}=\\sin(pos/10000^{2i/d}),\\quad \\mathrm{PE}_{(pos,2i+1)}=\\cos(pos/10000^{2i/d})",
      "source": "code_pattern",
      "evidence_ids": [
        "E112"
      ],
      "confidence": "medium",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "equation_id": "EQ2",
      "name": "Periodic Positional Encoding",
      "latex": "\\mathrm{PE}_{(pos,2i)}=\\sin(pos/10000^{2i/d}),\\quad \\mathrm{PE}_{(pos,2i+1)}=\\cos(pos/10000^{2i/d})",
      "source": "code_pattern",
      "evidence_ids": [
        "E115"
      ],
      "confidence": "medium",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "equation_id": "EQ3",
      "name": "Periodic Positional Encoding",
      "latex": "\\mathrm{PE}_{(pos,2i)}=\\sin(pos/10000^{2i/d}),\\quad \\mathrm{PE}_{(pos,2i+1)}=\\cos(pos/10000^{2i/d})",
      "source": "code_pattern",
      "evidence_ids": [
        "E118"
      ],
      "confidence": "medium",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "equation_id": "EQ4",
      "name": "Periodic Positional Encoding",
      "latex": "\\mathrm{PE}_{(pos,2i)}=\\sin(pos/10000^{2i/d}),\\quad \\mathrm{PE}_{(pos,2i+1)}=\\cos(pos/10000^{2i/d})",
      "source": "code_pattern",
      "evidence_ids": [
        "E123"
      ],
      "confidence": "medium",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "equation_id": "EQ5",
      "name": "Scaled Dot-Product Attention",
      "latex": "\\mathrm{Attention}(Q,K,V)=\\mathrm{softmax}(QK^T/\\sqrt{d_k})V",
      "source": "code_pattern",
      "evidence_ids": [
        "E130"
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
        "E130"
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
        "E135"
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
        "E142"
      ],
      "confidence": "medium",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "equation_id": "EQ9",
      "name": "Point-wise Feed-Forward Transformation",
      "latex": "\\mathrm{FFN}(x)=\\sigma(xW_1+b_1)W_2+b_2",
      "source": "code_pattern",
      "evidence_ids": [
        "E872"
      ],
      "confidence": "medium",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "equation_id": "EQ10",
      "name": "Point-wise Feed-Forward Transformation",
      "latex": "\\mathrm{FFN}(x)=\\sigma(xW_1+b_1)W_2+b_2",
      "source": "code_pattern",
      "evidence_ids": [
        "E968"
      ],
      "confidence": "medium",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "equation_id": "EQ11",
      "name": "Point-wise Feed-Forward Transformation",
      "latex": "\\mathrm{FFN}(x)=\\sigma(xW_1+b_1)W_2+b_2",
      "source": "code_pattern",
      "evidence_ids": [
        "E971"
      ],
      "confidence": "medium",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "equation_id": "EQ12",
      "name": "Point-wise Feed-Forward Transformation",
      "latex": "\\mathrm{FFN}(x)=\\sigma(xW_1+b_1)W_2+b_2",
      "source": "code_pattern",
      "evidence_ids": [
        "E974"
      ],
      "confidence": "medium",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "equation_id": "EQ13",
      "name": "Point-wise Feed-Forward Transformation",
      "latex": "\\mathrm{FFN}(x)=\\sigma(xW_1+b_1)W_2+b_2",
      "source": "code_pattern",
      "evidence_ids": [
        "E1800"
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
        "E2095"
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
      "name": "eps",
      "value": 1e-06,
      "source": "constructor_default",
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3RMSNorm",
      "evidence_ids": [
        "E107"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM2",
      "name": "max_position_embeddings",
      "value": 2048,
      "source": "constructor_default",
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3RotaryEmbedding",
      "evidence_ids": [
        "E112"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM3",
      "name": "base",
      "value": 10000,
      "source": "constructor_default",
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3RotaryEmbedding",
      "evidence_ids": [
        "E112"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM4",
      "name": "unsqueeze_dim",
      "value": 1,
      "source": "constructor_default",
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "apply_rotary_pos_emb",
      "evidence_ids": [
        "E123"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM5",
      "name": "delay_load",
      "value": false,
      "source": "constructor_default",
      "path": "llava/model/multimodal_encoder/clip_encoder.py",
      "symbol": "CLIPVisionTower",
      "evidence_ids": [
        "E739"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM6",
      "name": "delay_load",
      "value": false,
      "source": "constructor_default",
      "path": "llava/model/multimodal_encoder/clip_encoder.py",
      "symbol": "CLIPVisionTowerS2",
      "evidence_ids": [
        "E751"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM7",
      "name": "exclude_first_token",
      "value": true,
      "source": "constructor_default",
      "path": "llava/model/multimodal_encoder/point_encoder.py",
      "symbol": "PatchDropout",
      "evidence_ids": [
        "E856"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM8",
      "name": "num_group",
      "value": 32,
      "source": "constructor_default",
      "path": "llava/model/multimodal_encoder/point_encoder.py",
      "symbol": "skeleton_Group",
      "evidence_ids": [
        "E868"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM9",
      "name": "group_size",
      "value": 8,
      "source": "constructor_default",
      "path": "llava/model/multimodal_encoder/point_encoder.py",
      "symbol": "skeleton_Group",
      "evidence_ids": [
        "E868"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM10",
      "name": "drop",
      "value": 0.0,
      "source": "constructor_default",
      "path": "llava/model/multimodal_projector/builder.py",
      "symbol": "Mlp",
      "evidence_ids": [
        "E971"
      ],
      "confidence": "high"
    },
    {
      "parameter_id": "PARAM11",
      "name": "delay_load",
      "value": false,
      "source": "constructor_default",
      "path": "llava/model/multimodal_projector/builder.py",
      "symbol": "build_vision_projector",
      "evidence_ids": [
        "E974"
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
        "E1123"
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
        "E1639"
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
        "E1639"
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
        "E1709"
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
        "E1709"
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
        "E2090"
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
        "E3295"
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
        "E3300"
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
        "E3300"
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
        "E3303"
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
        "E3303"
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
        "E3306"
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
        "E3459"
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
        "E3460"
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
        "E3507"
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
        "E3508"
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
        "E3509"
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
        "E3510"
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
        "E3510"
      ],
      "confidence": "high"
    }
  ],
  "tensor_roles": [
    {
      "tensor_id": "TENSOR1",
      "name": "x",
      "role": "layer input representation",
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3RotaryEmbedding",
      "evidence_ids": [
        "E112"
      ],
      "confidence": "medium"
    },
    {
      "tensor_id": "TENSOR2",
      "name": "x",
      "role": "layer input representation",
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3SuScaledRotaryEmbedding",
      "evidence_ids": [
        "E115"
      ],
      "confidence": "medium"
    },
    {
      "tensor_id": "TENSOR3",
      "name": "x",
      "role": "layer input representation",
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "Phi3YarnScaledRotaryEmbedding",
      "evidence_ids": [
        "E118"
      ],
      "confidence": "medium"
    },
    {
      "tensor_id": "TENSOR4",
      "name": "x",
      "role": "layer input representation",
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "rotate_half",
      "evidence_ids": [
        "E121"
      ],
      "confidence": "medium"
    },
    {
      "tensor_id": "TENSOR5",
      "name": "q",
      "role": "query representation",
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "apply_rotary_pos_emb",
      "evidence_ids": [
        "E123"
      ],
      "confidence": "medium"
    },
    {
      "tensor_id": "TENSOR6",
      "name": "k",
      "role": "key representation",
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
      "symbol": "apply_rotary_pos_emb",
      "evidence_ids": [
        "E123"
      ],
      "confidence": "medium"
    },
    {
      "tensor_id": "TENSOR7",
      "name": "x",
      "role": "layer input representation",
      "path": "llava/model/multimodal_encoder/point_encoder.py",
      "symbol": "PatchDropout",
      "evidence_ids": [
        "E856"
      ],
      "confidence": "medium"
    },
    {
      "tensor_id": "TENSOR8",
      "name": "x",
      "role": "layer input representation",
      "path": "llava/model/multimodal_projector/builder.py",
      "symbol": "IdentityMap",
      "evidence_ids": [
        "E964"
      ],
      "confidence": "medium"
    },
    {
      "tensor_id": "TENSOR9",
      "name": "x",
      "role": "layer input representation",
      "path": "llava/model/multimodal_projector/builder.py",
      "symbol": "SimpleResBlock",
      "evidence_ids": [
        "E968"
      ],
      "confidence": "medium"
    },
    {
      "tensor_id": "TENSOR10",
      "name": "x",
      "role": "layer input representation",
      "path": "llava/model/multimodal_projector/builder.py",
      "symbol": "Mlp",
      "evidence_ids": [
        "E971"
      ],
      "confidence": "medium"
    }
  ],
  "innovation_candidates": [],
  "writing_constraints": [
    "Do not mention README-only information.",
    "Do not claim academic novelty without author confirmation.",
    "Do not promote comment-only hints into main method claims.",
    "No author markers were provided; treat method evidence as needing author confirmation.",
    "Excluded source: README.md (excluded from main evidence chain).",
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
    "Stage mappings connect implementation execution steps to paper-facing method stages."
  ],
  "excluded_sources": [
    {
      "path": "README.md",
      "reason": "excluded from main evidence chain"
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
  "author_logic_priority": false,
  "frozen_mechanisms": [
    {
      "mechanism_id": "MECH-001",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py implements infrastructure utility.",
      "parent_stage_id": "S1",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
        "symbols": [
          "Phi3ForCausalLM",
          "Phi3ForCausalLM.__init__",
          "Phi3ForCausalLM._reorder_cache",
          "Phi3ForCausalLM.get_input_embeddings",
          "Phi3ForCausalLM.get_output_embeddings",
          "Phi3ForCausalLM.prepare_inputs_for_generation",
          "Phi3ForCausalLM.set_input_embeddings",
          "Phi3ForCausalLM.set_output_embeddings",
          "Phi3ForSequenceClassification",
          "Phi3ForSequenceClassification.__init__",
          "Phi3ForSequenceClassification.get_input_embeddings",
          "Phi3ForSequenceClassification.set_input_embeddings",
          "Phi3MLP",
          "Phi3MLP.__init__",
          "Phi3Model",
          "Phi3Model.__init__",
          "Phi3Model.get_input_embeddings",
          "Phi3Model.set_input_embeddings",
          "Phi3RMSNorm",
          "Phi3RMSNorm.__init__",
          "Phi3RotaryEmbedding",
          "Phi3RotaryEmbedding.__init__",
          "Phi3SuScaledRotaryEmbedding",
          "Phi3SuScaledRotaryEmbedding.__init__",
          "Phi3YarnScaledRotaryEmbedding",
          "Phi3YarnScaledRotaryEmbedding.__init__",
          "_get_unpad_data",
          "apply_rotary_pos_emb",
          "repeat_kv",
          "rotate_half"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E107",
        "E108",
        "E111",
        "E112",
        "E113",
        "E115",
        "E116",
        "E118",
        "E119",
        "E121",
        "E123",
        "E125",
        "E126",
        "E128",
        "E150",
        "E152",
        "E153",
        "E154",
        "E156",
        "E157",
        "E158",
        "E159",
        "E160",
        "E161",
        "E166",
        "E167",
        "E168",
        "E169",
        "E170",
        "E171"
      ]
    },
    {
      "mechanism_id": "MECH-002",
      "mechanism_name": "model computation block",
      "mechanism_description": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py implements model computation block.",
      "parent_stage_id": "S2",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
        "symbols": [
          "Phi3Attention",
          "Phi3Attention.__init__",
          "Phi3Attention._init_rope",
          "Phi3Attention.forward",
          "Phi3DecoderLayer",
          "Phi3DecoderLayer.__init__",
          "Phi3DecoderLayer.forward",
          "Phi3FlashAttention2",
          "Phi3FlashAttention2.__init__",
          "Phi3FlashAttention2._flash_attention_forward",
          "Phi3FlashAttention2._upad_input",
          "Phi3FlashAttention2.forward",
          "Phi3ForCausalLM.forward",
          "Phi3ForCausalLM.get_decoder",
          "Phi3ForCausalLM.set_decoder",
          "Phi3ForSequenceClassification.forward",
          "Phi3ForTokenClassification.forward",
          "Phi3MLP.forward",
          "Phi3Model.forward",
          "Phi3RMSNorm.forward",
          "Phi3RotaryEmbedding.forward",
          "Phi3SdpaAttention",
          "Phi3SdpaAttention.forward",
          "Phi3SuScaledRotaryEmbedding.forward",
          "Phi3YarnScaledRotaryEmbedding.forward"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E110",
        "E114",
        "E117",
        "E120",
        "E127",
        "E130",
        "E132",
        "E133",
        "E134",
        "E135",
        "E137",
        "E138",
        "E139",
        "E141",
        "E142",
        "E144",
        "E145",
        "E146",
        "E147",
        "E155",
        "E162",
        "E163",
        "E164",
        "E172",
        "E176"
      ]
    },
    {
      "mechanism_id": "MECH-003",
      "mechanism_name": "data preparation and loading",
      "mechanism_description": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py implements data preparation and loading.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
        "symbols": [
          "Phi3ForTokenClassification",
          "Phi3ForTokenClassification.__init__"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E174",
        "E175"
      ]
    },
    {
      "mechanism_id": "MECH-004",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py",
        "symbols": [
          "Phi3Attention.__init__->Linear",
          "Phi3Attention.__init__->ValueError",
          "Phi3Attention.__init__->__init__",
          "Phi3Attention.__init__->_init_rope",
          "Phi3Attention.__init__->super",
          "Phi3Attention.__init__->warning_once",
          "Phi3Attention._init_rope->Phi3RotaryEmbedding",
          "Phi3Attention._init_rope->Phi3SuScaledRotaryEmbedding",
          "Phi3Attention._init_rope->Phi3YarnScaledRotaryEmbedding",
          "Phi3Attention._init_rope->ValueError",
          "Phi3Attention.forward->ValueError",
          "Phi3Attention.forward->apply_rotary_pos_emb",
          "Phi3Attention.forward->contiguous",
          "Phi3Attention.forward->dropout",
          "Phi3Attention.forward->get_usable_length",
          "Phi3Attention.forward->matmul",
          "Phi3Attention.forward->o_proj",
          "Phi3Attention.forward->qkv_proj",
          "Phi3Attention.forward->repeat_kv",
          "Phi3Attention.forward->reshape",
          "Phi3Attention.forward->rotary_emb",
          "Phi3Attention.forward->size",
          "Phi3DecoderLayer.__init__->Dropout",
          "Phi3DecoderLayer.__init__->Phi3MLP",
          "Phi3DecoderLayer.__init__->Phi3RMSNorm",
          "Phi3DecoderLayer.__init__->__init__",
          "Phi3DecoderLayer.__init__->super",
          "Phi3DecoderLayer.forward->input_layernorm",
          "Phi3DecoderLayer.forward->mlp",
          "Phi3DecoderLayer.forward->post_attention_layernorm",
          "Phi3DecoderLayer.forward->resid_attn_dropout",
          "Phi3DecoderLayer.forward->resid_mlp_dropout",
          "Phi3DecoderLayer.forward->self_attn",
          "Phi3DecoderLayer.forward->warn",
          "Phi3FlashAttention2.__init__->__init__",
          "Phi3FlashAttention2.__init__->is_flash_attn_greater_or_equal_2_10",
          "Phi3FlashAttention2.__init__->super",
          "Phi3FlashAttention2._flash_attention_forward->_upad_input",
          "Phi3FlashAttention2._flash_attention_forward->flash_attn_func",
          "Phi3FlashAttention2._flash_attention_forward->flash_attn_varlen_func",
          "Phi3FlashAttention2._flash_attention_forward->pad_input",
          "Phi3FlashAttention2._upad_input->_get_unpad_data",
          "Phi3FlashAttention2._upad_input->arange",
          "Phi3FlashAttention2._upad_input->index_first_axis",
          "Phi3FlashAttention2._upad_input->reshape",
          "Phi3FlashAttention2._upad_input->squeeze",
          "Phi3FlashAttention2._upad_input->unpad_input",
          "Phi3FlashAttention2.forward->ValueError",
          "Phi3FlashAttention2.forward->_flash_attention_forward",
          "Phi3FlashAttention2.forward->apply_rotary_pos_emb",
          "Phi3FlashAttention2.forward->cat",
          "Phi3FlashAttention2.forward->contiguous",
          "Phi3FlashAttention2.forward->get_autocast_gpu_dtype",
          "Phi3FlashAttention2.forward->get_seq_length",
          "Phi3FlashAttention2.forward->get_usable_length",
          "Phi3FlashAttention2.forward->getattr",
          "Phi3FlashAttention2.forward->hasattr",
          "Phi3FlashAttention2.forward->is_autocast_enabled",
          "Phi3FlashAttention2.forward->item",
          "Phi3ForCausalLM.__init__->Linear",
          "Phi3ForCausalLM.__init__->Phi3Model",
          "Phi3ForCausalLM.__init__->__init__",
          "Phi3ForCausalLM.__init__->post_init",
          "Phi3ForCausalLM.__init__->super",
          "Phi3ForCausalLM._reorder_cache->index_select",
          "Phi3ForCausalLM._reorder_cache->to",
          "Phi3ForCausalLM._reorder_cache->tuple",
          "Phi3ForCausalLM.forward->CausalLMOutputWithPast",
          "Phi3ForCausalLM.forward->CrossEntropyLoss",
          "Phi3ForCausalLM.forward->add_start_docstrings_to_model_forward",
          "Phi3ForCausalLM.forward->contiguous",
          "Phi3ForCausalLM.forward->float",
          "Phi3ForCausalLM.forward->lm_head",
          "Phi3ForCausalLM.forward->loss_fct",
          "Phi3ForCausalLM.forward->model",
          "Phi3ForCausalLM.forward->replace_return_docstrings",
          "Phi3ForCausalLM.forward->to",
          "Phi3ForCausalLM.forward->view",
          "Phi3ForCausalLM.prepare_inputs_for_generation->cumsum",
          "Phi3ForCausalLM.prepare_inputs_for_generation->get",
          "Phi3ForCausalLM.prepare_inputs_for_generation->get_max_length",
          "Phi3ForCausalLM.prepare_inputs_for_generation->get_seq_length",
          "Phi3ForCausalLM.prepare_inputs_for_generation->isinstance",
          "Phi3ForCausalLM.prepare_inputs_for_generation->long",
          "Phi3ForCausalLM.prepare_inputs_for_generation->masked_fill_",
          "Phi3ForCausalLM.prepare_inputs_for_generation->update",
          "Phi3ForSequenceClassification.__init__->Linear",
          "Phi3ForSequenceClassification.__init__->Phi3Model",
          "Phi3ForSequenceClassification.__init__->__init__",
          "Phi3ForSequenceClassification.__init__->post_init",
          "Phi3ForSequenceClassification.__init__->super",
          "Phi3ForSequenceClassification.forward->BCEWithLogitsLoss",
          "Phi3ForSequenceClassification.forward->CrossEntropyLoss",
          "Phi3ForSequenceClassification.forward->MSELoss",
          "Phi3ForSequenceClassification.forward->SequenceClassifierOutputWithPast",
          "Phi3ForSequenceClassification.forward->ValueError",
          "Phi3ForSequenceClassification.forward->add_start_docstrings_to_model_forward",
          "Phi3ForSequenceClassification.forward->arange",
          "Phi3ForSequenceClassification.forward->argmax",
          "Phi3ForSequenceClassification.forward->eq",
          "Phi3ForSequenceClassification.forward->int",
          "Phi3ForSequenceClassification.forward->loss_fct",
          "Phi3ForSequenceClassification.forward->model",
          "Phi3ForTokenClassification.__init__->Dropout",
          "Phi3ForTokenClassification.__init__->Linear",
          "Phi3ForTokenClassification.__init__->Phi3Model",
          "Phi3ForTokenClassification.__init__->__init__",
          "Phi3ForTokenClassification.__init__->hasattr",
          "Phi3ForTokenClassification.__init__->post_init",
          "Phi3ForTokenClassification.__init__->super",
          "Phi3ForTokenClassification.forward->CrossEntropyLoss",
          "Phi3ForTokenClassification.forward->TokenClassifierOutput",
          "Phi3ForTokenClassification.forward->add_code_sample_docstrings",
          "Phi3ForTokenClassification.forward->add_start_docstrings_to_model_forward",
          "Phi3ForTokenClassification.forward->classifier",
          "Phi3ForTokenClassification.forward->dropout",
          "Phi3ForTokenClassification.forward->loss_fct",
          "Phi3ForTokenClassification.forward->model",
          "Phi3ForTokenClassification.forward->to",
          "Phi3ForTokenClassification.forward->view",
          "Phi3MLP.__init__->Linear",
          "Phi3MLP.__init__->__init__",
          "Phi3MLP.__init__->super",
          "Phi3MLP.forward->activation_fn",
          "Phi3MLP.forward->chunk",
          "Phi3MLP.forward->down_proj",
          "Phi3MLP.forward->gate_up_proj",
          "Phi3Model.__init__->Dropout",
          "Phi3Model.__init__->Embedding",
          "Phi3Model.__init__->ModuleList",
          "Phi3Model.__init__->Phi3DecoderLayer",
          "Phi3Model.__init__->Phi3RMSNorm",
          "Phi3Model.__init__->__init__",
          "Phi3Model.__init__->post_init",
          "Phi3Model.__init__->range",
          "Phi3Model.__init__->super",
          "Phi3Model.forward->BaseModelOutputWithPast",
          "Phi3Model.forward->ValueError",
          "Phi3Model.forward->_gradient_checkpointing_func",
          "Phi3Model.forward->_prepare_4d_causal_attention_mask",
          "Phi3Model.forward->add_start_docstrings_to_model_forward",
          "Phi3Model.forward->arange",
          "Phi3Model.forward->decoder_layer",
          "Phi3Model.forward->embed_tokens",
          "Phi3Model.forward->from_legacy_cache",
          "Phi3Model.forward->get_usable_length",
          "Phi3Model.forward->isinstance",
          "Phi3Model.forward->item",
          "Phi3RMSNorm.__init__->Parameter",
          "Phi3RMSNorm.__init__->__init__",
          "Phi3RMSNorm.__init__->ones",
          "Phi3RMSNorm.__init__->super",
          "Phi3RMSNorm.forward->mean",
          "Phi3RMSNorm.forward->pow",
          "Phi3RMSNorm.forward->rsqrt",
          "Phi3RMSNorm.forward->to",
          "Phi3RotaryEmbedding.__init__->__init__",
          "Phi3RotaryEmbedding.__init__->register_buffer",
          "Phi3RotaryEmbedding.__init__->super",
          "Phi3RotaryEmbedding.forward->arange",
          "Phi3RotaryEmbedding.forward->autocast",
          "Phi3RotaryEmbedding.forward->cat",
          "Phi3RotaryEmbedding.forward->cos",
          "Phi3RotaryEmbedding.forward->expand",
          "Phi3RotaryEmbedding.forward->float",
          "Phi3RotaryEmbedding.forward->isinstance",
          "Phi3RotaryEmbedding.forward->no_grad",
          "Phi3RotaryEmbedding.forward->sin",
          "Phi3RotaryEmbedding.forward->to",
          "Phi3RotaryEmbedding.forward->transpose",
          "Phi3SdpaAttention.forward->ValueError",
          "Phi3SdpaAttention.forward->apply_rotary_pos_emb",
          "Phi3SdpaAttention.forward->contiguous",
          "Phi3SdpaAttention.forward->forward",
          "Phi3SdpaAttention.forward->get_usable_length",
          "Phi3SdpaAttention.forward->o_proj",
          "Phi3SdpaAttention.forward->qkv_proj",
          "Phi3SdpaAttention.forward->repeat_kv",
          "Phi3SdpaAttention.forward->rotary_emb",
          "Phi3SdpaAttention.forward->scaled_dot_product_attention",
          "Phi3SdpaAttention.forward->size",
          "Phi3SdpaAttention.forward->super",
          "Phi3SuScaledRotaryEmbedding.__init__->__init__",
          "Phi3SuScaledRotaryEmbedding.__init__->super",
          "Phi3SuScaledRotaryEmbedding.forward->arange",
          "Phi3SuScaledRotaryEmbedding.forward->autocast",
          "Phi3SuScaledRotaryEmbedding.forward->cat",
          "Phi3SuScaledRotaryEmbedding.forward->cos",
          "Phi3SuScaledRotaryEmbedding.forward->expand",
          "Phi3SuScaledRotaryEmbedding.forward->float",
          "Phi3SuScaledRotaryEmbedding.forward->isinstance",
          "Phi3SuScaledRotaryEmbedding.forward->log",
          "Phi3SuScaledRotaryEmbedding.forward->max",
          "Phi3SuScaledRotaryEmbedding.forward->no_grad",
          "Phi3SuScaledRotaryEmbedding.forward->sin",
          "Phi3SuScaledRotaryEmbedding.forward->sqrt",
          "Phi3YarnScaledRotaryEmbedding.__init__->__init__",
          "Phi3YarnScaledRotaryEmbedding.__init__->super",
          "Phi3YarnScaledRotaryEmbedding.forward->arange",
          "Phi3YarnScaledRotaryEmbedding.forward->autocast",
          "Phi3YarnScaledRotaryEmbedding.forward->cat",
          "Phi3YarnScaledRotaryEmbedding.forward->cos",
          "Phi3YarnScaledRotaryEmbedding.forward->expand",
          "Phi3YarnScaledRotaryEmbedding.forward->float",
          "Phi3YarnScaledRotaryEmbedding.forward->isinstance",
          "Phi3YarnScaledRotaryEmbedding.forward->log",
          "Phi3YarnScaledRotaryEmbedding.forward->max",
          "Phi3YarnScaledRotaryEmbedding.forward->no_grad",
          "Phi3YarnScaledRotaryEmbedding.forward->sin",
          "Phi3YarnScaledRotaryEmbedding.forward->tensor",
          "_get_unpad_data->cumsum",
          "_get_unpad_data->flatten",
          "_get_unpad_data->item",
          "_get_unpad_data->max",
          "_get_unpad_data->nonzero",
          "_get_unpad_data->pad",
          "_get_unpad_data->sum",
          "apply_rotary_pos_emb->rotate_half",
          "apply_rotary_pos_emb->unsqueeze",
          "repeat_kv->expand",
          "repeat_kv->reshape",
          "rotate_half->cat"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E178",
        "E179",
        "E180",
        "E181",
        "E182",
        "E183",
        "E184",
        "E185",
        "E186",
        "E187",
        "E188",
        "E189",
        "E190",
        "E191",
        "E192",
        "E193",
        "E194",
        "E195",
        "E196",
        "E197",
        "E198",
        "E199",
        "E200",
        "E201",
        "E202",
        "E203",
        "E204",
        "E205",
        "E206",
        "E207",
        "E208",
        "E209",
        "E210",
        "E211",
        "E212",
        "E213",
        "E214",
        "E215",
        "E216",
        "E217",
        "E218",
        "E219",
        "E220",
        "E221",
        "E222",
        "E223",
        "E224",
        "E225",
        "E226",
        "E227",
        "E228",
        "E229",
        "E230",
        "E231",
        "E232",
        "E233",
        "E234",
        "E235",
        "E236",
        "E237",
        "E238",
        "E239",
        "E240",
        "E241",
        "E242",
        "E243",
        "E244",
        "E245",
        "E246",
        "E247",
        "E248",
        "E249",
        "E250",
        "E251",
        "E252",
        "E253",
        "E254",
        "E255",
        "E256",
        "E257",
        "E258",
        "E259",
        "E260",
        "E261",
        "E262",
        "E263",
        "E264",
        "E265",
        "E266",
        "E267",
        "E268",
        "E269",
        "E270",
        "E271",
        "E272",
        "E273",
        "E274",
        "E275",
        "E276",
        "E277",
        "E278",
        "E279",
        "E280",
        "E281",
        "E282",
        "E283",
        "E284",
        "E285",
        "E286",
        "E287",
        "E288",
        "E289",
        "E290",
        "E291",
        "E292",
        "E293",
        "E294",
        "E295",
        "E296",
        "E297",
        "E298",
        "E299",
        "E300",
        "E301",
        "E302",
        "E303",
        "E304",
        "E305",
        "E306",
        "E307",
        "E308",
        "E309",
        "E310",
        "E311",
        "E312",
        "E313",
        "E314",
        "E315",
        "E316",
        "E317",
        "E321",
        "E322",
        "E323",
        "E324",
        "E325",
        "E326",
        "E327",
        "E328",
        "E329",
        "E330",
        "E331",
        "E332",
        "E333",
        "E334",
        "E335",
        "E336",
        "E337",
        "E338",
        "E339",
        "E340",
        "E341",
        "E342",
        "E343",
        "E344",
        "E345",
        "E346",
        "E347",
        "E348",
        "E349",
        "E350",
        "E351",
        "E352",
        "E353",
        "E354",
        "E355",
        "E356",
        "E357",
        "E358",
        "E359",
        "E360",
        "E361",
        "E362",
        "E363",
        "E364",
        "E365",
        "E366",
        "E367",
        "E368",
        "E369",
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
        "E381",
        "E382",
        "E383",
        "E384",
        "E385",
        "E386",
        "E387",
        "E388",
        "E389",
        "E390",
        "E391",
        "E392",
        "E393",
        "E394",
        "E395",
        "E396",
        "E397",
        "E398",
        "E399",
        "E400",
        "E401",
        "E402"
      ]
    },
    {
      "mechanism_id": "MECH-005",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "llava/model/apply_delta.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/apply_delta.py",
        "symbols": [
          "apply_delta"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E411"
      ]
    },
    {
      "mechanism_id": "MECH-006",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "llava/model/apply_delta.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/apply_delta.py",
        "symbols": [
          "apply_delta->items",
          "apply_delta->print",
          "apply_delta->state_dict",
          "apply_delta->tqdm"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E413",
        "E414",
        "E416",
        "E417"
      ]
    },
    {
      "mechanism_id": "MECH-007",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "llava/model/consolidate.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/consolidate.py",
        "symbols": [
          "consolidate_ckpt"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E454"
      ]
    },
    {
      "mechanism_id": "MECH-008",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "llava/model/consolidate.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/consolidate.py",
        "symbols": [
          "consolidate_ckpt->auto_upgrade",
          "consolidate_ckpt->print"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E455",
        "E457"
      ]
    },
    {
      "mechanism_id": "MECH-009",
      "mechanism_name": "configuration and runtime wiring",
      "mechanism_description": "llava/model/language_model/llava_llama.py implements configuration and runtime wiring.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/language_model/llava_llama.py",
        "symbols": [
          "LlavaConfig"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E470"
      ]
    },
    {
      "mechanism_id": "MECH-010",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "llava/model/language_model/llava_llama.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/language_model/llava_llama.py",
        "symbols": [
          "LlavaLlamaForCausalLM",
          "LlavaLlamaForCausalLM.__init__",
          "LlavaLlamaForCausalLM.generate",
          "LlavaLlamaForCausalLM.get_model",
          "LlavaLlamaForCausalLM.prepare_inputs_for_generation",
          "LlavaLlamaModel",
          "LlavaLlamaModel.__init__"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E471",
        "E472",
        "E473",
        "E474",
        "E475",
        "E477",
        "E478"
      ]
    },
    {
      "mechanism_id": "MECH-011",
      "mechanism_name": "model computation block",
      "mechanism_description": "llava/model/language_model/llava_llama.py implements model computation block.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/language_model/llava_llama.py",
        "symbols": [
          "LlavaLlamaForCausalLM.forward"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E476"
      ]
    },
    {
      "mechanism_id": "MECH-012",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "llava/model/language_model/llava_llama.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/language_model/llava_llama.py",
        "symbols": [
          "LlavaLlamaForCausalLM.__init__->Linear",
          "LlavaLlamaForCausalLM.__init__->LlavaLlamaModel",
          "LlavaLlamaForCausalLM.__init__->__init__",
          "LlavaLlamaForCausalLM.__init__->post_init",
          "LlavaLlamaForCausalLM.__init__->super",
          "LlavaLlamaForCausalLM.forward->forward",
          "LlavaLlamaForCausalLM.forward->prepare_inputs_labels_for_multimodal",
          "LlavaLlamaForCausalLM.forward->super",
          "LlavaLlamaForCausalLM.generate->NotImplementedError",
          "LlavaLlamaForCausalLM.generate->embed_tokens",
          "LlavaLlamaForCausalLM.generate->generate",
          "LlavaLlamaForCausalLM.generate->get_model",
          "LlavaLlamaForCausalLM.generate->no_grad",
          "LlavaLlamaForCausalLM.generate->pop",
          "LlavaLlamaForCausalLM.generate->prepare_inputs_labels_for_multimodal",
          "LlavaLlamaForCausalLM.generate->super",
          "LlavaLlamaForCausalLM.prepare_inputs_for_generation->pop",
          "LlavaLlamaForCausalLM.prepare_inputs_for_generation->prepare_inputs_for_generation",
          "LlavaLlamaForCausalLM.prepare_inputs_for_generation->super",
          "LlavaLlamaModel.__init__->__init__",
          "LlavaLlamaModel.__init__->super"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E479",
        "E480",
        "E481",
        "E482",
        "E483",
        "E484",
        "E485",
        "E486",
        "E487",
        "E488",
        "E489",
        "E490",
        "E491",
        "E492",
        "E493",
        "E494",
        "E495",
        "E496",
        "E497",
        "E498",
        "E499"
      ]
    },
    {
      "mechanism_id": "MECH-013",
      "mechanism_name": "configuration and runtime wiring",
      "mechanism_description": "llava/model/language_model/llava_mistral.py implements configuration and runtime wiring.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/language_model/llava_mistral.py",
        "symbols": [
          "LlavaMistralConfig"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E511"
      ]
    },
    {
      "mechanism_id": "MECH-014",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "llava/model/language_model/llava_mistral.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/language_model/llava_mistral.py",
        "symbols": [
          "LlavaMistralForCausalLM",
          "LlavaMistralForCausalLM.__init__",
          "LlavaMistralForCausalLM.generate",
          "LlavaMistralForCausalLM.get_model",
          "LlavaMistralForCausalLM.prepare_inputs_for_generation",
          "LlavaMistralModel",
          "LlavaMistralModel.__init__"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E512",
        "E513",
        "E514",
        "E515",
        "E516",
        "E518",
        "E519"
      ]
    },
    {
      "mechanism_id": "MECH-015",
      "mechanism_name": "model computation block",
      "mechanism_description": "llava/model/language_model/llava_mistral.py implements model computation block.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/language_model/llava_mistral.py",
        "symbols": [
          "LlavaMistralForCausalLM.forward"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E517"
      ]
    },
    {
      "mechanism_id": "MECH-016",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "llava/model/language_model/llava_mistral.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/language_model/llava_mistral.py",
        "symbols": [
          "LlavaMistralForCausalLM.__init__->Linear",
          "LlavaMistralForCausalLM.__init__->LlavaMistralModel",
          "LlavaMistralForCausalLM.__init__->__init__",
          "LlavaMistralForCausalLM.__init__->post_init",
          "LlavaMistralForCausalLM.__init__->super",
          "LlavaMistralForCausalLM.forward->forward",
          "LlavaMistralForCausalLM.forward->prepare_inputs_labels_for_multimodal",
          "LlavaMistralForCausalLM.forward->super",
          "LlavaMistralForCausalLM.generate->NotImplementedError",
          "LlavaMistralForCausalLM.generate->embed_tokens",
          "LlavaMistralForCausalLM.generate->generate",
          "LlavaMistralForCausalLM.generate->get_model",
          "LlavaMistralForCausalLM.generate->no_grad",
          "LlavaMistralForCausalLM.generate->pop",
          "LlavaMistralForCausalLM.generate->prepare_inputs_labels_for_multimodal",
          "LlavaMistralForCausalLM.generate->super",
          "LlavaMistralForCausalLM.prepare_inputs_for_generation->pop",
          "LlavaMistralForCausalLM.prepare_inputs_for_generation->prepare_inputs_for_generation",
          "LlavaMistralForCausalLM.prepare_inputs_for_generation->super",
          "LlavaMistralModel.__init__->__init__",
          "LlavaMistralModel.__init__->super"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E520",
        "E521",
        "E522",
        "E523",
        "E524",
        "E525",
        "E526",
        "E527",
        "E528",
        "E529",
        "E530",
        "E531",
        "E532",
        "E533",
        "E534",
        "E535",
        "E536",
        "E537",
        "E538",
        "E539",
        "E540"
      ]
    },
    {
      "mechanism_id": "MECH-017",
      "mechanism_name": "configuration and runtime wiring",
      "mechanism_description": "llava/model/language_model/llava_mpt.py implements configuration and runtime wiring.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/language_model/llava_mpt.py",
        "symbols": [
          "LlavaMptConfig"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E552"
      ]
    },
    {
      "mechanism_id": "MECH-018",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "llava/model/language_model/llava_mpt.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/language_model/llava_mpt.py",
        "symbols": [
          "LlavaMptForCausalLM",
          "LlavaMptForCausalLM.__init__",
          "LlavaMptForCausalLM.get_model",
          "LlavaMptForCausalLM.prepare_inputs_for_generation",
          "LlavaMptModel",
          "LlavaMptModel.__init__"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E553",
        "E554",
        "E556",
        "E557",
        "E558",
        "E561"
      ]
    },
    {
      "mechanism_id": "MECH-019",
      "mechanism_name": "data preparation and loading",
      "mechanism_description": "llava/model/language_model/llava_mpt.py implements data preparation and loading.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/language_model/llava_mpt.py",
        "symbols": [
          "LlavaMptModel.embed_tokens"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E555"
      ]
    },
    {
      "mechanism_id": "MECH-020",
      "mechanism_name": "optimization and objective logic",
      "mechanism_description": "llava/model/language_model/llava_mpt.py implements optimization and objective logic.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/language_model/llava_mpt.py",
        "symbols": [
          "LlavaMptForCausalLM._set_gradient_checkpointing"
        ]
      },
      "distinguishing_level": "main",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E559"
      ]
    },
    {
      "mechanism_id": "MECH-021",
      "mechanism_name": "model computation block",
      "mechanism_description": "llava/model/language_model/llava_mpt.py implements model computation block.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/language_model/llava_mpt.py",
        "symbols": [
          "LlavaMptForCausalLM.forward"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E560"
      ]
    },
    {
      "mechanism_id": "MECH-022",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "llava/model/language_model/llava_mpt.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/language_model/llava_mpt.py",
        "symbols": [
          "LlavaMptForCausalLM.__init__->Linear",
          "LlavaMptForCausalLM.__init__->LlavaMptModel",
          "LlavaMptForCausalLM.__init__->__init__",
          "LlavaMptForCausalLM.__init__->post_init",
          "LlavaMptForCausalLM.__init__->super",
          "LlavaMptForCausalLM._set_gradient_checkpointing->isinstance",
          "LlavaMptForCausalLM.forward->forward",
          "LlavaMptForCausalLM.forward->prepare_inputs_labels_for_multimodal",
          "LlavaMptForCausalLM.forward->super",
          "LlavaMptForCausalLM.prepare_inputs_for_generation->pop",
          "LlavaMptForCausalLM.prepare_inputs_for_generation->prepare_inputs_for_generation",
          "LlavaMptForCausalLM.prepare_inputs_for_generation->super",
          "LlavaMptModel.__init__->__init__",
          "LlavaMptModel.__init__->super",
          "LlavaMptModel.embed_tokens->wte"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E562",
        "E563",
        "E564",
        "E565",
        "E566",
        "E567",
        "E568",
        "E569",
        "E570",
        "E571",
        "E572",
        "E573",
        "E574",
        "E575",
        "E576"
      ]
    },
    {
      "mechanism_id": "MECH-023",
      "mechanism_name": "configuration and runtime wiring",
      "mechanism_description": "llava/model/language_model/llava_phi3.py implements configuration and runtime wiring.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/language_model/llava_phi3.py",
        "symbols": [
          "LlavaPhiConfig"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E589"
      ]
    },
    {
      "mechanism_id": "MECH-024",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "llava/model/language_model/llava_phi3.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/language_model/llava_phi3.py",
        "symbols": [
          "LlavaPhiForCausalLM",
          "LlavaPhiForCausalLM.__init__",
          "LlavaPhiForCausalLM.generate",
          "LlavaPhiForCausalLM.get_model",
          "LlavaPhiForCausalLM.prepare_inputs_for_generation",
          "LlavaPhiModel",
          "LlavaPhiModel.__init__"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E590",
        "E591",
        "E592",
        "E593",
        "E594",
        "E596",
        "E597"
      ]
    },
    {
      "mechanism_id": "MECH-025",
      "mechanism_name": "model computation block",
      "mechanism_description": "llava/model/language_model/llava_phi3.py implements model computation block.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/language_model/llava_phi3.py",
        "symbols": [
          "LlavaPhiForCausalLM.forward"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E595"
      ]
    },
    {
      "mechanism_id": "MECH-026",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "llava/model/language_model/llava_phi3.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/language_model/llava_phi3.py",
        "symbols": [
          "LlavaPhiForCausalLM.__init__->Linear",
          "LlavaPhiForCausalLM.__init__->LlavaPhiModel",
          "LlavaPhiForCausalLM.__init__->__init__",
          "LlavaPhiForCausalLM.__init__->post_init",
          "LlavaPhiForCausalLM.__init__->super",
          "LlavaPhiForCausalLM.forward->forward",
          "LlavaPhiForCausalLM.forward->maybe_autocast",
          "LlavaPhiForCausalLM.forward->prepare_inputs_labels_for_multimodal",
          "LlavaPhiForCausalLM.forward->super",
          "LlavaPhiForCausalLM.generate->NotImplementedError",
          "LlavaPhiForCausalLM.generate->embed_tokens",
          "LlavaPhiForCausalLM.generate->generate",
          "LlavaPhiForCausalLM.generate->get_model",
          "LlavaPhiForCausalLM.generate->no_grad",
          "LlavaPhiForCausalLM.generate->pop",
          "LlavaPhiForCausalLM.generate->prepare_inputs_labels_for_multimodal",
          "LlavaPhiForCausalLM.generate->super",
          "LlavaPhiForCausalLM.prepare_inputs_for_generation->pop",
          "LlavaPhiForCausalLM.prepare_inputs_for_generation->prepare_inputs_for_generation",
          "LlavaPhiForCausalLM.prepare_inputs_for_generation->super",
          "LlavaPhiModel.__init__->__init__",
          "LlavaPhiModel.__init__->super"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E598",
        "E599",
        "E600",
        "E601",
        "E602",
        "E603",
        "E604",
        "E605",
        "E606",
        "E607",
        "E608",
        "E609",
        "E610",
        "E611",
        "E612",
        "E613",
        "E614",
        "E615",
        "E616",
        "E617",
        "E618",
        "E619"
      ]
    },
    {
      "mechanism_id": "MECH-027",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "llava/model/llava_arch.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/llava_arch.py",
        "symbols": [
          "LlavaMetaForCausalLM",
          "LlavaMetaForCausalLM.encode_datas",
          "LlavaMetaForCausalLM.get_model",
          "LlavaMetaForCausalLM.get_vision_tower",
          "LlavaMetaForCausalLM.maybe_autocast",
          "LlavaMetaForCausalLM.prepare_inputs_labels_for_multimodal",
          "LlavaMetaModel",
          "LlavaMetaModel.__init__",
          "LlavaMetaModel.get_vision_tower",
          "LlavaMetaModel.initialize_other_modules",
          "LlavaMetaModel.random_initialize_model",
          "unpad_image"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E650",
        "E651",
        "E652",
        "E653",
        "E654",
        "E656",
        "E658",
        "E659",
        "E660",
        "E661",
        "E662",
        "E663"
      ]
    },
    {
      "mechanism_id": "MECH-028",
      "mechanism_name": "data preparation and loading",
      "mechanism_description": "llava/model/llava_arch.py implements data preparation and loading.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/llava_arch.py",
        "symbols": [
          "LlavaMetaForCausalLM.initialize_vision_tokenizer"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E664"
      ]
    },
    {
      "mechanism_id": "MECH-029",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "llava/model/llava_arch.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/llava_arch.py",
        "symbols": [
          "LlavaMetaForCausalLM.encode_datas->encode_text",
          "LlavaMetaForCausalLM.encode_datas->get_model",
          "LlavaMetaForCausalLM.encode_datas->get_vision_tower",
          "LlavaMetaForCausalLM.encode_datas->maybe_autocast",
          "LlavaMetaForCausalLM.encode_datas->mm_projector",
          "LlavaMetaForCausalLM.encode_datas->norm",
          "LlavaMetaForCausalLM.encode_datas->randn_like",
          "LlavaMetaForCausalLM.encode_datas->to",
          "LlavaMetaForCausalLM.encode_datas->unsqueeze",
          "LlavaMetaForCausalLM.get_vision_tower->get_model",
          "LlavaMetaForCausalLM.get_vision_tower->get_vision_tower",
          "LlavaMetaForCausalLM.initialize_vision_tokenizer->ValueError",
          "LlavaMetaForCausalLM.initialize_vision_tokenizer->add_tokens",
          "LlavaMetaForCausalLM.initialize_vision_tokenizer->get_input_embeddings",
          "LlavaMetaForCausalLM.initialize_vision_tokenizer->get_output_embeddings",
          "LlavaMetaForCausalLM.initialize_vision_tokenizer->len",
          "LlavaMetaForCausalLM.initialize_vision_tokenizer->mean",
          "LlavaMetaForCausalLM.initialize_vision_tokenizer->parameters",
          "LlavaMetaForCausalLM.initialize_vision_tokenizer->resize_token_embeddings",
          "LlavaMetaForCausalLM.maybe_autocast->SmoothL1Loss",
          "LlavaMetaForCausalLM.maybe_autocast->autocast",
          "LlavaMetaForCausalLM.maybe_autocast->device",
          "LlavaMetaForCausalLM.maybe_autocast->nullcontext",
          "LlavaMetaForCausalLM.prepare_inputs_labels_for_multimodal->append",
          "LlavaMetaForCausalLM.prepare_inputs_labels_for_multimodal->arange",
          "LlavaMetaForCausalLM.prepare_inputs_labels_for_multimodal->bool",
          "LlavaMetaForCausalLM.prepare_inputs_labels_for_multimodal->cat",
          "LlavaMetaForCausalLM.prepare_inputs_labels_for_multimodal->embed_tokens",
          "LlavaMetaForCausalLM.prepare_inputs_labels_for_multimodal->encode_datas",
          "LlavaMetaForCausalLM.prepare_inputs_labels_for_multimodal->enumerate",
          "LlavaMetaForCausalLM.prepare_inputs_labels_for_multimodal->full",
          "LlavaMetaForCausalLM.prepare_inputs_labels_for_multimodal->full_like",
          "LlavaMetaForCausalLM.prepare_inputs_labels_for_multimodal->get_model",
          "LlavaMetaForCausalLM.prepare_inputs_labels_for_multimodal->getattr",
          "LlavaMetaForCausalLM.prepare_inputs_labels_for_multimodal->len",
          "LlavaMetaModel.__init__->__init__",
          "LlavaMetaModel.__init__->super",
          "LlavaMetaModel.get_vision_tower->getattr",
          "LlavaMetaModel.get_vision_tower->type",
          "LlavaMetaModel.initialize_other_modules->build_pc_encoder",
          "LlavaMetaModel.initialize_other_modules->build_text_encoder",
          "LlavaMetaModel.initialize_other_modules->build_vision_projector",
          "LlavaMetaModel.initialize_other_modules->get_w",
          "LlavaMetaModel.initialize_other_modules->items",
          "LlavaMetaModel.initialize_other_modules->iter",
          "LlavaMetaModel.initialize_other_modules->keys",
          "LlavaMetaModel.initialize_other_modules->len",
          "LlavaMetaModel.initialize_other_modules->list",
          "LlavaMetaModel.initialize_other_modules->next",
          "LlavaMetaModel.random_initialize_model->constant_",
          "LlavaMetaModel.random_initialize_model->named_parameters",
          "LlavaMetaModel.random_initialize_model->normal_",
          "unpad_image->int"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E665",
        "E666",
        "E667",
        "E668",
        "E669",
        "E670",
        "E671",
        "E672",
        "E673",
        "E674",
        "E675",
        "E676",
        "E677",
        "E680",
        "E681",
        "E682",
        "E683",
        "E684",
        "E685",
        "E686",
        "E687",
        "E688",
        "E689",
        "E690",
        "E691",
        "E692",
        "E693",
        "E694",
        "E695",
        "E696",
        "E697",
        "E698",
        "E699",
        "E700",
        "E701",
        "E702",
        "E703",
        "E704",
        "E705",
        "E706",
        "E707",
        "E708",
        "E709",
        "E710",
        "E711",
        "E712",
        "E713",
        "E714",
        "E715",
        "E716",
        "E718",
        "E719",
        "E720"
      ]
    },
    {
      "mechanism_id": "MECH-030",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "llava/model/make_delta.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/make_delta.py",
        "symbols": [
          "make_delta"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E722"
      ]
    },
    {
      "mechanism_id": "MECH-031",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "llava/model/make_delta.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/make_delta.py",
        "symbols": [
          "make_delta->auto_upgrade",
          "make_delta->items",
          "make_delta->print",
          "make_delta->state_dict",
          "make_delta->tqdm"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E723",
        "E725",
        "E726",
        "E728",
        "E729"
      ]
    },
    {
      "mechanism_id": "MECH-032",
      "mechanism_name": "model computation block",
      "mechanism_description": "llava/model/multimodal_encoder/builder.py implements model computation block.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/multimodal_encoder/builder.py",
        "symbols": [
          "build_pc_encoder",
          "build_text_encoder"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E732",
        "E733"
      ]
    },
    {
      "mechanism_id": "MECH-033",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "llava/model/multimodal_encoder/builder.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/multimodal_encoder/builder.py",
        "symbols": [
          "build_pc_encoder->PointcloudEncoder",
          "build_pc_encoder->create_model",
          "build_pc_encoder->getattr",
          "build_text_encoder->create_model_and_transforms"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E734",
        "E735",
        "E736",
        "E737"
      ]
    },
    {
      "mechanism_id": "MECH-034",
      "mechanism_name": "model computation block",
      "mechanism_description": "llava/model/multimodal_encoder/clip_encoder.py implements model computation block.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/multimodal_encoder/clip_encoder.py",
        "symbols": [
          "CLIPVisionTower",
          "CLIPVisionTower.__init__",
          "CLIPVisionTower.config",
          "CLIPVisionTower.device",
          "CLIPVisionTower.dtype",
          "CLIPVisionTower.dummy_feature",
          "CLIPVisionTower.feature_select",
          "CLIPVisionTower.forward",
          "CLIPVisionTower.hidden_size",
          "CLIPVisionTower.num_patches",
          "CLIPVisionTower.num_patches_per_side",
          "CLIPVisionTowerS2",
          "CLIPVisionTowerS2.__init__",
          "CLIPVisionTowerS2.forward",
          "CLIPVisionTowerS2.forward_feature",
          "CLIPVisionTowerS2.hidden_size"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E739",
        "E740",
        "E742",
        "E743",
        "E744",
        "E745",
        "E746",
        "E747",
        "E748",
        "E749",
        "E750",
        "E751",
        "E752",
        "E754",
        "E755",
        "E756"
      ]
    },
    {
      "mechanism_id": "MECH-035",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "llava/model/multimodal_encoder/clip_encoder.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/multimodal_encoder/clip_encoder.py",
        "symbols": [
          "CLIPVisionTower.__init__->__init__",
          "CLIPVisionTower.__init__->from_pretrained",
          "CLIPVisionTower.__init__->getattr",
          "CLIPVisionTower.__init__->super",
          "CLIPVisionTower.dummy_feature->zeros",
          "CLIPVisionTower.feature_select->ValueError",
          "CLIPVisionTower.forward->append",
          "CLIPVisionTower.forward->feature_select",
          "CLIPVisionTower.forward->no_grad",
          "CLIPVisionTower.forward->to",
          "CLIPVisionTower.forward->type",
          "CLIPVisionTower.forward->unsqueeze",
          "CLIPVisionTower.forward->vision_tower",
          "CLIPVisionTowerS2.__init__->ImportError",
          "CLIPVisionTowerS2.__init__->__init__",
          "CLIPVisionTowerS2.__init__->getattr",
          "CLIPVisionTowerS2.__init__->list",
          "CLIPVisionTowerS2.__init__->map",
          "CLIPVisionTowerS2.__init__->sort",
          "CLIPVisionTowerS2.__init__->split",
          "CLIPVisionTowerS2.__init__->super",
          "CLIPVisionTowerS2.forward->append",
          "CLIPVisionTowerS2.forward->multiscale_forward",
          "CLIPVisionTowerS2.forward->no_grad",
          "CLIPVisionTowerS2.forward->type",
          "CLIPVisionTowerS2.forward->unsqueeze",
          "CLIPVisionTowerS2.forward_feature->feature_select",
          "CLIPVisionTowerS2.forward_feature->no_grad",
          "CLIPVisionTowerS2.forward_feature->to",
          "CLIPVisionTowerS2.forward_feature->vision_tower",
          "CLIPVisionTowerS2.hidden_size->len"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E757",
        "E758",
        "E759",
        "E761",
        "E766",
        "E767",
        "E768",
        "E769",
        "E770",
        "E771",
        "E772",
        "E773",
        "E774",
        "E775",
        "E776",
        "E777",
        "E778",
        "E779",
        "E780",
        "E781",
        "E782",
        "E787",
        "E788",
        "E789",
        "E790",
        "E791",
        "E792",
        "E793",
        "E794",
        "E795",
        "E796"
      ]
    },
    {
      "mechanism_id": "MECH-036",
      "mechanism_name": "model computation block",
      "mechanism_description": "llava/model/multimodal_encoder/point_encoder.py implements model computation block.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/multimodal_encoder/point_encoder.py",
        "symbols": [
          "Encoder",
          "Encoder.__init__",
          "Encoder.forward",
          "Group",
          "Group.__init__",
          "Group.forward",
          "PatchDropout",
          "PatchDropout.__init__",
          "PatchDropout.forward",
          "PointcloudEncoder",
          "PointcloudEncoder.__init__",
          "PointcloudEncoder.forward",
          "fps",
          "index_points",
          "knn_point",
          "skeleton_Group",
          "skeleton_Group.__init__",
          "skeleton_Group.forward",
          "square_distance"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E848",
        "E850",
        "E852",
        "E854",
        "E856",
        "E858",
        "E859",
        "E860",
        "E861",
        "E862",
        "E864",
        "E865",
        "E866",
        "E868",
        "E869",
        "E870",
        "E872",
        "E873",
        "E874"
      ]
    },
    {
      "mechanism_id": "MECH-037",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "llava/model/multimodal_encoder/point_encoder.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/multimodal_encoder/point_encoder.py",
        "symbols": [
          "Encoder.__init__->BatchNorm1d",
          "Encoder.__init__->Conv1d",
          "Encoder.__init__->ReLU",
          "Encoder.__init__->Sequential",
          "Encoder.__init__->__init__",
          "Encoder.__init__->super",
          "Encoder.forward->cat",
          "Encoder.forward->expand",
          "Encoder.forward->first_conv",
          "Encoder.forward->max",
          "Encoder.forward->reshape",
          "Encoder.forward->second_conv",
          "Encoder.forward->transpose",
          "Group.__init__->__init__",
          "Group.__init__->super",
          "Group.forward->arange",
          "Group.forward->cat",
          "Group.forward->contiguous",
          "Group.forward->fps",
          "Group.forward->knn_point",
          "Group.forward->size",
          "Group.forward->unsqueeze",
          "Group.forward->view",
          "PatchDropout.__init__->__init__",
          "PatchDropout.__init__->format",
          "PatchDropout.__init__->info",
          "PatchDropout.__init__->super",
          "PatchDropout.forward->annotate",
          "PatchDropout.forward->arange",
          "PatchDropout.forward->cat",
          "PatchDropout.forward->int",
          "PatchDropout.forward->max",
          "PatchDropout.forward->randn",
          "PatchDropout.forward->size",
          "PatchDropout.forward->topk",
          "PointcloudEncoder.__init__->Encoder",
          "PointcloudEncoder.__init__->GELU",
          "PointcloudEncoder.__init__->Group",
          "PointcloudEncoder.__init__->Identity",
          "PointcloudEncoder.__init__->Linear",
          "PointcloudEncoder.__init__->Parameter",
          "PointcloudEncoder.__init__->PatchDropout",
          "PointcloudEncoder.__init__->Sequential",
          "PointcloudEncoder.__init__->__init__",
          "PointcloudEncoder.__init__->randn",
          "PointcloudEncoder.__init__->skeleton_Group",
          "PointcloudEncoder.__init__->super",
          "PointcloudEncoder.forward->blk",
          "PointcloudEncoder.forward->cat",
          "PointcloudEncoder.forward->contiguous",
          "PointcloudEncoder.forward->encoder",
          "PointcloudEncoder.forward->encoder2trans",
          "PointcloudEncoder.forward->enumerate",
          "PointcloudEncoder.forward->expand",
          "PointcloudEncoder.forward->fc_norm",
          "PointcloudEncoder.forward->group_divider",
          "PointcloudEncoder.forward->len",
          "PointcloudEncoder.forward->max",
          "PointcloudEncoder.forward->mean",
          "fps->contiguous",
          "fps->furthest_point_sample",
          "fps->gather_operation",
          "fps->transpose",
          "index_points->arange",
          "index_points->len",
          "index_points->list",
          "index_points->repeat",
          "index_points->to",
          "index_points->view",
          "knn_point->square_distance",
          "knn_point->topk",
          "skeleton_Group.__init__->__init__",
          "skeleton_Group.__init__->super",
          "skeleton_Group.forward->arange",
          "skeleton_Group.forward->contiguous",
          "skeleton_Group.forward->einsum",
          "skeleton_Group.forward->fps",
          "skeleton_Group.forward->knn_point",
          "skeleton_Group.forward->max",
          "skeleton_Group.forward->normalize",
          "skeleton_Group.forward->permute",
          "skeleton_Group.forward->size",
          "skeleton_Group.forward->softmax",
          "skeleton_Group.forward->squeeze",
          "skeleton_Group.forward->unsqueeze",
          "square_distance->matmul",
          "square_distance->permute",
          "square_distance->sum",
          "square_distance->view"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E875",
        "E876",
        "E877",
        "E878",
        "E879",
        "E880",
        "E881",
        "E882",
        "E883",
        "E884",
        "E885",
        "E886",
        "E887",
        "E888",
        "E889",
        "E890",
        "E891",
        "E892",
        "E893",
        "E894",
        "E895",
        "E896",
        "E897",
        "E898",
        "E899",
        "E900",
        "E901",
        "E902",
        "E903",
        "E904",
        "E905",
        "E906",
        "E907",
        "E908",
        "E909",
        "E910",
        "E911",
        "E912",
        "E913",
        "E914",
        "E915",
        "E916",
        "E917",
        "E918",
        "E919",
        "E920",
        "E921",
        "E922",
        "E923",
        "E924",
        "E925",
        "E926",
        "E927",
        "E928",
        "E929",
        "E930",
        "E931",
        "E932",
        "E933",
        "E934",
        "E935",
        "E936",
        "E937",
        "E938",
        "E939",
        "E940",
        "E941",
        "E942",
        "E943",
        "E944",
        "E945",
        "E946",
        "E947",
        "E948",
        "E949",
        "E950",
        "E951",
        "E952",
        "E953",
        "E954",
        "E955",
        "E956",
        "E957",
        "E958",
        "E959",
        "E960",
        "E961",
        "E962",
        "E963"
      ]
    },
    {
      "mechanism_id": "MECH-038",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "llava/model/multimodal_projector/builder.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/multimodal_projector/builder.py",
        "symbols": [
          "IdentityMap",
          "IdentityMap.__init__",
          "Mlp",
          "Mlp.__init__",
          "SimpleResBlock",
          "SimpleResBlock.__init__",
          "build_vision_projector"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E964",
        "E965",
        "E968",
        "E969",
        "E971",
        "E972",
        "E974"
      ]
    },
    {
      "mechanism_id": "MECH-039",
      "mechanism_name": "model computation block",
      "mechanism_description": "llava/model/multimodal_projector/builder.py implements model computation block.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/multimodal_projector/builder.py",
        "symbols": [
          "IdentityMap.forward",
          "Mlp.forward",
          "SimpleResBlock.forward"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E966",
        "E970",
        "E973"
      ]
    },
    {
      "mechanism_id": "MECH-040",
      "mechanism_name": "configuration and runtime wiring",
      "mechanism_description": "llava/model/multimodal_projector/builder.py implements configuration and runtime wiring.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/multimodal_projector/builder.py",
        "symbols": [
          "IdentityMap.config"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E967"
      ]
    },
    {
      "mechanism_id": "MECH-041",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "llava/model/multimodal_projector/builder.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/multimodal_projector/builder.py",
        "symbols": [
          "IdentityMap.__init__->__init__",
          "IdentityMap.__init__->super",
          "Mlp.__init__->Dropout",
          "Mlp.__init__->Linear",
          "Mlp.__init__->__init__",
          "Mlp.__init__->act_layer",
          "Mlp.__init__->norm_layer",
          "Mlp.__init__->super",
          "Mlp.forward->act",
          "Mlp.forward->drop",
          "Mlp.forward->fc1",
          "Mlp.forward->fc2",
          "Mlp.forward->norm1",
          "SimpleResBlock.__init__->GELU",
          "SimpleResBlock.__init__->LayerNorm",
          "SimpleResBlock.__init__->Linear",
          "SimpleResBlock.__init__->Sequential",
          "SimpleResBlock.__init__->__init__",
          "SimpleResBlock.__init__->super",
          "SimpleResBlock.forward->pre_norm",
          "SimpleResBlock.forward->proj"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E975",
        "E976",
        "E977",
        "E978",
        "E979",
        "E980",
        "E981",
        "E982",
        "E983",
        "E984",
        "E985",
        "E986",
        "E987",
        "E988",
        "E989",
        "E990",
        "E991",
        "E992",
        "E993",
        "E994",
        "E995"
      ]
    },
    {
      "mechanism_id": "MECH-042",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "llava/model/utils.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/utils.py",
        "symbols": [
          "StreamToLogger",
          "StreamToLogger.__getattr__",
          "StreamToLogger.__init__",
          "StreamToLogger.flush",
          "basic_clean",
          "build_logger",
          "bytes_to_unicode",
          "default_bpe",
          "disable_torch_init",
          "get_pairs",
          "pretty_print_semaphore",
          "violates_moderation",
          "whitespace_clean"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017",
        "E1018",
        "E1020",
        "E1022",
        "E1023",
        "E1024",
        "E1026",
        "E1028",
        "E1029"
      ]
    },
    {
      "mechanism_id": "MECH-043",
      "mechanism_name": "data preparation and loading",
      "mechanism_description": "llava/model/utils.py implements data preparation and loading.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/utils.py",
        "symbols": [
          "SimpleTokenizer",
          "SimpleTokenizer.__call__",
          "SimpleTokenizer.__init__",
          "SimpleTokenizer.bpe",
          "SimpleTokenizer.decode",
          "SimpleTokenizer.encode"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E1030",
        "E1031",
        "E1032",
        "E1033",
        "E1034",
        "E1035"
      ]
    },
    {
      "mechanism_id": "MECH-044",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "llava/model/utils.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/model/utils.py",
        "symbols": [
          "SimpleTokenizer.__call__->encode",
          "SimpleTokenizer.__call__->enumerate",
          "SimpleTokenizer.__call__->isinstance",
          "SimpleTokenizer.__call__->len",
          "SimpleTokenizer.__call__->tensor",
          "SimpleTokenizer.__call__->zeros",
          "SimpleTokenizer.__init__->append",
          "SimpleTokenizer.__init__->bytes_to_unicode",
          "SimpleTokenizer.__init__->compile",
          "SimpleTokenizer.__init__->decode",
          "SimpleTokenizer.__init__->default_bpe",
          "SimpleTokenizer.__init__->dict",
          "SimpleTokenizer.__init__->extend",
          "SimpleTokenizer.__init__->items",
          "SimpleTokenizer.__init__->join",
          "SimpleTokenizer.__init__->len",
          "SimpleTokenizer.__init__->list",
          "SimpleTokenizer.__init__->open",
          "SimpleTokenizer.bpe->append",
          "SimpleTokenizer.bpe->extend",
          "SimpleTokenizer.bpe->float",
          "SimpleTokenizer.bpe->get",
          "SimpleTokenizer.bpe->get_pairs",
          "SimpleTokenizer.bpe->index",
          "SimpleTokenizer.bpe->join",
          "SimpleTokenizer.bpe->len",
          "SimpleTokenizer.bpe->min",
          "SimpleTokenizer.bpe->tuple",
          "SimpleTokenizer.decode->bytearray",
          "SimpleTokenizer.decode->decode",
          "SimpleTokenizer.decode->join",
          "SimpleTokenizer.decode->replace",
          "SimpleTokenizer.encode->basic_clean",
          "SimpleTokenizer.encode->bpe",
          "SimpleTokenizer.encode->encode",
          "SimpleTokenizer.encode->extend",
          "SimpleTokenizer.encode->findall",
          "SimpleTokenizer.encode->join",
          "SimpleTokenizer.encode->lower",
          "SimpleTokenizer.encode->split",
          "SimpleTokenizer.encode->whitespace_clean",
          "StreamToLogger.__getattr__->getattr",
          "StreamToLogger.flush->log",
          "StreamToLogger.flush->rstrip"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E1048",
        "E1052",
        "E1053",
        "E1079",
        "E1080",
        "E1081",
        "E1082",
        "E1083",
        "E1084",
        "E1085",
        "E1086",
        "E1087",
        "E1088",
        "E1089",
        "E1090",
        "E1091",
        "E1092",
        "E1093",
        "E1094",
        "E1095",
        "E1096",
        "E1097",
        "E1098",
        "E1099",
        "E1100",
        "E1101",
        "E1102",
        "E1103",
        "E1104",
        "E1105",
        "E1106",
        "E1107",
        "E1108",
        "E1109",
        "E1110",
        "E1111",
        "E1112",
        "E1113",
        "E1114",
        "E1115",
        "E1116",
        "E1117",
        "E1118",
        "E1119"
      ]
    },
    {
      "mechanism_id": "MECH-045",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "llava/serve/model_worker.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/serve/model_worker.py",
        "symbols": [
          "ModelWorker",
          "ModelWorker.__init__",
          "ModelWorker.generate_stream",
          "ModelWorker.generate_stream_gate",
          "ModelWorker.get_queue_length",
          "ModelWorker.get_status",
          "ModelWorker.register_to_controller",
          "ModelWorker.send_heart_beat",
          "generate_stream",
          "get_status",
          "heart_beat_worker",
          "release_model_semaphore"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E1122",
        "E1123",
        "E1124",
        "E1125",
        "E1126",
        "E1127",
        "E1128",
        "E1129",
        "E1130",
        "E1131",
        "E1132",
        "E1133"
      ]
    },
    {
      "mechanism_id": "MECH-046",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "llava/serve/model_worker.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/serve/model_worker.py",
        "symbols": [
          "ModelWorker.__init__->endswith",
          "ModelWorker.__init__->info",
          "ModelWorker.__init__->lower",
          "ModelWorker.__init__->register_to_controller",
          "ModelWorker.__init__->split",
          "ModelWorker.__init__->start",
          "ModelWorker.__init__->startswith",
          "ModelWorker.generate_stream->TextIteratorStreamer",
          "ModelWorker.generate_stream->ValueError",
          "ModelWorker.generate_stream->count",
          "ModelWorker.generate_stream->dict",
          "ModelWorker.generate_stream->dumps",
          "ModelWorker.generate_stream->encode",
          "ModelWorker.generate_stream->endswith",
          "ModelWorker.generate_stream->float",
          "ModelWorker.generate_stream->get",
          "ModelWorker.generate_stream->get_vision_tower",
          "ModelWorker.generate_stream->getattr",
          "ModelWorker.generate_stream_gate->dumps",
          "ModelWorker.generate_stream_gate->encode",
          "ModelWorker.generate_stream_gate->generate_stream",
          "ModelWorker.generate_stream_gate->print",
          "ModelWorker.get_queue_length->len",
          "ModelWorker.get_status->get_queue_length",
          "ModelWorker.register_to_controller->get_status",
          "ModelWorker.register_to_controller->info",
          "ModelWorker.register_to_controller->post",
          "ModelWorker.send_heart_beat->error",
          "ModelWorker.send_heart_beat->get_queue_length",
          "ModelWorker.send_heart_beat->info",
          "ModelWorker.send_heart_beat->json",
          "ModelWorker.send_heart_beat->post",
          "ModelWorker.send_heart_beat->pretty_print_semaphore",
          "ModelWorker.send_heart_beat->register_to_controller",
          "ModelWorker.send_heart_beat->sleep",
          "generate_stream->BackgroundTasks",
          "generate_stream->Semaphore",
          "generate_stream->StreamingResponse",
          "generate_stream->acquire",
          "generate_stream->add_task",
          "generate_stream->generate_stream_gate",
          "generate_stream->json",
          "generate_stream->partial",
          "generate_stream->post",
          "generate_stream->send_heart_beat",
          "get_status->get_status",
          "get_status->post",
          "heart_beat_worker->send_heart_beat",
          "heart_beat_worker->sleep",
          "release_model_semaphore->fn",
          "release_model_semaphore->release"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E1134",
        "E1135",
        "E1137",
        "E1138",
        "E1140",
        "E1141",
        "E1142",
        "E1143",
        "E1144",
        "E1145",
        "E1146",
        "E1147",
        "E1148",
        "E1149",
        "E1150",
        "E1151",
        "E1152",
        "E1153",
        "E1154",
        "E1155",
        "E1156",
        "E1157",
        "E1158",
        "E1160",
        "E1161",
        "E1162",
        "E1163",
        "E1164",
        "E1165",
        "E1166",
        "E1167",
        "E1168",
        "E1169",
        "E1170",
        "E1171",
        "E1172",
        "E1173",
        "E1174",
        "E1175",
        "E1176",
        "E1177",
        "E1178",
        "E1179",
        "E1180",
        "E1181",
        "E1182",
        "E1183",
        "E1184",
        "E1185",
        "E1186",
        "E1187"
      ]
    },
    {
      "mechanism_id": "MECH-047",
      "mechanism_name": "model computation block",
      "mechanism_description": "llava/train/llama_flash_attn_monkey_patch.py implements model computation block.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/train/llama_flash_attn_monkey_patch.py",
        "symbols": [
          "_prepare_decoder_attention_mask"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E1197"
      ]
    },
    {
      "mechanism_id": "MECH-048",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "llava/train/llama_flash_attn_monkey_patch.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/train/llama_flash_attn_monkey_patch.py",
        "symbols": [
          "forward->apply_rotary_pos_emb",
          "forward->arange",
          "forward->cat",
          "forward->flash_attn_unpadded_qkvpacked_func",
          "forward->k_proj",
          "forward->o_proj",
          "forward->pad_input",
          "forward->q_proj",
          "forward->repeat_kv",
          "forward->reshape",
          "forward->rotary_emb",
          "forward->size"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E1199",
        "E1200",
        "E1201",
        "E1202",
        "E1203",
        "E1204",
        "E1205",
        "E1206",
        "E1207",
        "E1208",
        "E1209",
        "E1210"
      ]
    },
    {
      "mechanism_id": "MECH-049",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "llava/train/llama_xformers_attn_monkey_patch.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/train/llama_xformers_attn_monkey_patch.py",
        "symbols": [
          "xformers_forward->LowerTriangularMask",
          "xformers_forward->ValueError",
          "xformers_forward->apply_rotary_pos_emb",
          "xformers_forward->cat",
          "xformers_forward->finfo",
          "xformers_forward->k_proj",
          "xformers_forward->matmul",
          "xformers_forward->max",
          "xformers_forward->memory_efficient_attention",
          "xformers_forward->o_proj",
          "xformers_forward->q_proj",
          "xformers_forward->reshape"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E1225",
        "E1226",
        "E1227",
        "E1228",
        "E1229",
        "E1230",
        "E1231",
        "E1232",
        "E1233",
        "E1234",
        "E1235",
        "E1236"
      ]
    },
    {
      "mechanism_id": "MECH-050",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "pointllm/data/modelnet.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointllm/data/modelnet.py",
        "symbols": [
          "ModelNet",
          "ModelNet.__getitem__",
          "ModelNet.__init__",
          "ModelNet.__len__",
          "ModelNet._get_item",
          "ModelNet.pc_norm"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E1639",
        "E1640",
        "E1642",
        "E1643",
        "E1644",
        "E1646"
      ]
    },
    {
      "mechanism_id": "MECH-051",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "pointllm/data/modelnet.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointllm/data/modelnet.py",
        "symbols": [
          "ModelNet.__getitem__->_get_item",
          "ModelNet.__getitem__->arange",
          "ModelNet.__getitem__->copy",
          "ModelNet.__getitem__->float",
          "ModelNet.__getitem__->from_numpy",
          "ModelNet.__getitem__->int",
          "ModelNet.__getitem__->pc_norm",
          "ModelNet.__getitem__->shuffle",
          "ModelNet.__init__->__init__",
          "ModelNet.__init__->cfg_from_yaml_file",
          "ModelNet.__init__->dirname",
          "ModelNet.__init__->exit",
          "ModelNet.__init__->join",
          "ModelNet.__init__->len",
          "ModelNet.__init__->open",
          "ModelNet.__init__->print",
          "ModelNet.__init__->range",
          "ModelNet.__init__->rstrip",
          "ModelNet.__len__->len",
          "ModelNet._get_item->choice",
          "ModelNet._get_item->concatenate",
          "ModelNet._get_item->farthest_point_sample",
          "ModelNet._get_item->item",
          "ModelNet._get_item->min",
          "ModelNet._get_item->pc_normalize",
          "ModelNet._get_item->zeros_like",
          "ModelNet.pc_norm->concatenate",
          "ModelNet.pc_norm->max",
          "ModelNet.pc_norm->mean",
          "ModelNet.pc_norm->sqrt",
          "ModelNet.pc_norm->sum"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E1647",
        "E1648",
        "E1649",
        "E1651",
        "E1652",
        "E1653",
        "E1655",
        "E1656",
        "E1657",
        "E1658",
        "E1659",
        "E1660",
        "E1661",
        "E1662",
        "E1663",
        "E1664",
        "E1665",
        "E1666",
        "E1667",
        "E1668",
        "E1669",
        "E1670",
        "E1671",
        "E1672",
        "E1673",
        "E1674",
        "E1675",
        "E1676",
        "E1677",
        "E1678",
        "E1679"
      ]
    },
    {
      "mechanism_id": "MECH-052",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "pointllm/data/modelnet_show.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointllm/data/modelnet_show.py",
        "symbols": [
          "ModelNet",
          "ModelNet.__getitem__",
          "ModelNet.__init__",
          "ModelNet.__len__",
          "ModelNet._get_item",
          "ModelNet.our_get_item",
          "ModelNet.pc_norm"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E1709",
        "E1710",
        "E1712",
        "E1713",
        "E1714",
        "E1715",
        "E1717"
      ]
    },
    {
      "mechanism_id": "MECH-053",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "pointllm/data/modelnet_show.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointllm/data/modelnet_show.py",
        "symbols": [
          "ModelNet.__getitem__->_get_item",
          "ModelNet.__getitem__->arange",
          "ModelNet.__getitem__->copy",
          "ModelNet.__getitem__->float",
          "ModelNet.__getitem__->from_numpy",
          "ModelNet.__getitem__->int",
          "ModelNet.__getitem__->pc_norm",
          "ModelNet.__getitem__->shuffle",
          "ModelNet.__init__->__init__",
          "ModelNet.__init__->cfg_from_yaml_file",
          "ModelNet.__init__->dirname",
          "ModelNet.__init__->exit",
          "ModelNet.__init__->join",
          "ModelNet.__init__->len",
          "ModelNet.__init__->open",
          "ModelNet.__init__->print",
          "ModelNet.__init__->range",
          "ModelNet.__init__->rstrip",
          "ModelNet.__len__->len",
          "ModelNet._get_item->choice",
          "ModelNet._get_item->concatenate",
          "ModelNet._get_item->farthest_point_sample",
          "ModelNet._get_item->item",
          "ModelNet._get_item->min",
          "ModelNet._get_item->pc_normalize",
          "ModelNet._get_item->zeros_like",
          "ModelNet.our_get_item->choice",
          "ModelNet.our_get_item->concatenate",
          "ModelNet.our_get_item->farthest_point_sample",
          "ModelNet.our_get_item->int",
          "ModelNet.our_get_item->item",
          "ModelNet.our_get_item->min",
          "ModelNet.our_get_item->pc_normalize",
          "ModelNet.our_get_item->zeros_like",
          "ModelNet.pc_norm->concatenate",
          "ModelNet.pc_norm->max",
          "ModelNet.pc_norm->mean",
          "ModelNet.pc_norm->sqrt",
          "ModelNet.pc_norm->sum"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E1718",
        "E1719",
        "E1720",
        "E1722",
        "E1723",
        "E1724",
        "E1726",
        "E1727",
        "E1728",
        "E1729",
        "E1730",
        "E1731",
        "E1732",
        "E1733",
        "E1734",
        "E1735",
        "E1736",
        "E1737",
        "E1738",
        "E1739",
        "E1740",
        "E1741",
        "E1742",
        "E1743",
        "E1744",
        "E1745",
        "E1746",
        "E1747",
        "E1748",
        "E1749",
        "E1750",
        "E1751",
        "E1752",
        "E1753",
        "E1754",
        "E1755",
        "E1756",
        "E1757",
        "E1758"
      ]
    },
    {
      "mechanism_id": "MECH-054",
      "mechanism_name": "configuration and runtime wiring",
      "mechanism_description": "pointllm/model/pointllm.py implements configuration and runtime wiring.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointllm/model/pointllm.py",
        "symbols": [
          "PointLLMConfig"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E1799"
      ]
    },
    {
      "mechanism_id": "MECH-055",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "pointllm/model/pointllm.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointllm/model/pointllm.py",
        "symbols": [
          "PointLLMLlamaForCausalLM",
          "PointLLMLlamaForCausalLM.__init__",
          "PointLLMLlamaForCausalLM.get_model",
          "PointLLMLlamaForCausalLM.maybe_autocast",
          "PointLLMLlamaForCausalLM.prepare_inputs_for_generation",
          "PointLLMLlamaModel",
          "PointLLMLlamaModel.__init__"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E1800",
        "E1801",
        "E1804",
        "E1805",
        "E1806",
        "E1807",
        "E1809"
      ]
    },
    {
      "mechanism_id": "MECH-056",
      "mechanism_name": "model computation block",
      "mechanism_description": "pointllm/model/pointllm.py implements model computation block.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointllm/model/pointllm.py",
        "symbols": [
          "PointLLMLlamaForCausalLM.forward",
          "PointLLMLlamaModel.forward"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E1803",
        "E1808"
      ]
    },
    {
      "mechanism_id": "MECH-057",
      "mechanism_name": "data preparation and loading",
      "mechanism_description": "pointllm/model/pointllm.py implements data preparation and loading.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointllm/model/pointllm.py",
        "symbols": [
          "PointLLMLlamaForCausalLM.initialize_tokenizer_point_backbone_config",
          "PointLLMLlamaForCausalLM.initialize_tokenizer_point_backbone_config_wo_embedding"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E1810",
        "E1811"
      ]
    },
    {
      "mechanism_id": "MECH-058",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "pointllm/model/pointllm.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointllm/model/pointllm.py",
        "symbols": [
          "PointLLMLlamaForCausalLM.__init__->Linear",
          "PointLLMLlamaForCausalLM.__init__->PointLLMLlamaModel",
          "PointLLMLlamaForCausalLM.__init__->__init__",
          "PointLLMLlamaForCausalLM.__init__->post_init",
          "PointLLMLlamaForCausalLM.__init__->super",
          "PointLLMLlamaForCausalLM.forward->CausalLMOutputWithPast",
          "PointLLMLlamaForCausalLM.forward->CrossEntropyLoss",
          "PointLLMLlamaForCausalLM.forward->contiguous",
          "PointLLMLlamaForCausalLM.forward->lm_head",
          "PointLLMLlamaForCausalLM.forward->loss_fct",
          "PointLLMLlamaForCausalLM.forward->model",
          "PointLLMLlamaForCausalLM.forward->to",
          "PointLLMLlamaForCausalLM.forward->view",
          "PointLLMLlamaForCausalLM.initialize_tokenizer_point_backbone_config->add_tokens",
          "PointLLMLlamaForCausalLM.initialize_tokenizer_point_backbone_config->clone",
          "PointLLMLlamaForCausalLM.initialize_tokenizer_point_backbone_config->convert_tokens_to_ids",
          "PointLLMLlamaForCausalLM.initialize_tokenizer_point_backbone_config->get_input_embeddings",
          "PointLLMLlamaForCausalLM.initialize_tokenizer_point_backbone_config->get_model",
          "PointLLMLlamaForCausalLM.initialize_tokenizer_point_backbone_config->get_output_embeddings",
          "PointLLMLlamaForCausalLM.initialize_tokenizer_point_backbone_config->len",
          "PointLLMLlamaForCausalLM.initialize_tokenizer_point_backbone_config->mean",
          "PointLLMLlamaForCausalLM.initialize_tokenizer_point_backbone_config->parameters",
          "PointLLMLlamaForCausalLM.initialize_tokenizer_point_backbone_config->print",
          "PointLLMLlamaForCausalLM.initialize_tokenizer_point_backbone_config->resize_token_embeddings",
          "PointLLMLlamaForCausalLM.initialize_tokenizer_point_backbone_config->to",
          "PointLLMLlamaForCausalLM.initialize_tokenizer_point_backbone_config_wo_embedding->add_tokens",
          "PointLLMLlamaForCausalLM.initialize_tokenizer_point_backbone_config_wo_embedding->convert_tokens_to_ids",
          "PointLLMLlamaForCausalLM.initialize_tokenizer_point_backbone_config_wo_embedding->get_model",
          "PointLLMLlamaForCausalLM.maybe_autocast->autocast",
          "PointLLMLlamaForCausalLM.maybe_autocast->device",
          "PointLLMLlamaForCausalLM.maybe_autocast->nullcontext",
          "PointLLMLlamaForCausalLM.prepare_inputs_for_generation->get",
          "PointLLMLlamaForCausalLM.prepare_inputs_for_generation->update",
          "PointLLMLlamaModel.__init__->GELU",
          "PointLLMLlamaModel.__init__->Linear",
          "PointLLMLlamaModel.__init__->PointTransformer",
          "PointLLMLlamaModel.__init__->Sequential",
          "PointLLMLlamaModel.__init__->__init__",
          "PointLLMLlamaModel.__init__->append",
          "PointLLMLlamaModel.__init__->cfg_from_yaml_file",
          "PointLLMLlamaModel.__init__->dirname",
          "PointLLMLlamaModel.__init__->get",
          "PointLLMLlamaModel.__init__->getattr",
          "PointLLMLlamaModel.__init__->info",
          "PointLLMLlamaModel.__init__->join",
          "PointLLMLlamaModel.forward->ValueError",
          "PointLLMLlamaModel.forward->any",
          "PointLLMLlamaModel.forward->append",
          "PointLLMLlamaModel.forward->arange",
          "PointLLMLlamaModel.forward->cat",
          "PointLLMLlamaModel.forward->detach",
          "PointLLMLlamaModel.forward->embed_tokens",
          "PointLLMLlamaModel.forward->eval",
          "PointLLMLlamaModel.forward->forward",
          "PointLLMLlamaModel.forward->getattr",
          "PointLLMLlamaModel.forward->no_grad",
          "PointLLMLlamaModel.forward->nullcontext"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E1812",
        "E1813",
        "E1814",
        "E1815",
        "E1816",
        "E1817",
        "E1818",
        "E1819",
        "E1820",
        "E1821",
        "E1822",
        "E1823",
        "E1824",
        "E1825",
        "E1826",
        "E1827",
        "E1828",
        "E1829",
        "E1830",
        "E1831",
        "E1832",
        "E1833",
        "E1834",
        "E1835",
        "E1836",
        "E1837",
        "E1838",
        "E1839",
        "E1840",
        "E1841",
        "E1842",
        "E1843",
        "E1844",
        "E1845",
        "E1846",
        "E1847",
        "E1848",
        "E1849",
        "E1850",
        "E1851",
        "E1852",
        "E1853",
        "E1854",
        "E1855",
        "E1856",
        "E1857",
        "E1858",
        "E1859",
        "E1860",
        "E1861",
        "E1862",
        "E1863",
        "E1864",
        "E1865",
        "E1866",
        "E1867",
        "E1868"
      ]
    },
    {
      "mechanism_id": "MECH-059",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "pointllm/model/utils.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointllm/model/utils.py",
        "symbols": [
          "KeywordsStoppingCriteria",
          "KeywordsStoppingCriteria.__call__",
          "KeywordsStoppingCriteria.__init__"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E1869",
        "E1870",
        "E1871"
      ]
    },
    {
      "mechanism_id": "MECH-060",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "pointllm/model/utils.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointllm/model/utils.py",
        "symbols": [
          "KeywordsStoppingCriteria.__call__->batch_decode",
          "KeywordsStoppingCriteria.__init__->len",
          "KeywordsStoppingCriteria.__init__->tokenizer",
          "KeywordsStoppingCriteria.__init__->type"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E1872",
        "E1873",
        "E1874",
        "E1875"
      ]
    },
    {
      "mechanism_id": "MECH-061",
      "mechanism_name": "model computation block",
      "mechanism_description": "pointllm/train/llama_flash_attn_monkey_patch.py implements model computation block.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointllm/train/llama_flash_attn_monkey_patch.py",
        "symbols": [
          "_prepare_decoder_attention_mask"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E1893"
      ]
    },
    {
      "mechanism_id": "MECH-062",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "pointllm/train/llama_flash_attn_monkey_patch.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointllm/train/llama_flash_attn_monkey_patch.py",
        "symbols": [
          "forward->apply_rotary_pos_emb",
          "forward->arange",
          "forward->flash_attn_unpadded_qkvpacked_func",
          "forward->k_proj",
          "forward->o_proj",
          "forward->pad_input",
          "forward->q_proj",
          "forward->rearrange",
          "forward->rotary_emb",
          "forward->size",
          "forward->stack",
          "forward->transpose"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E1895",
        "E1896",
        "E1897",
        "E1898",
        "E1899",
        "E1900",
        "E1901",
        "E1902",
        "E1903",
        "E1904",
        "E1905",
        "E1906"
      ]
    },
    {
      "mechanism_id": "MECH-063",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_msg_cls.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_msg_cls.py",
        "symbols": [
          "PointNet2ClassificationMSG",
          "PointNet2ClassificationMSG._build_model"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2070",
        "E2071"
      ]
    },
    {
      "mechanism_id": "MECH-064",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_msg_cls.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_msg_cls.py",
        "symbols": [
          "PointNet2ClassificationMSG._build_model->ModuleList",
          "PointNet2ClassificationMSG._build_model->PointnetSAModule",
          "PointNet2ClassificationMSG._build_model->PointnetSAModuleMSG",
          "PointNet2ClassificationMSG._build_model->_build_model",
          "PointNet2ClassificationMSG._build_model->append",
          "PointNet2ClassificationMSG._build_model->super"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2072",
        "E2073",
        "E2074",
        "E2075",
        "E2076",
        "E2077"
      ]
    },
    {
      "mechanism_id": "MECH-065",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_msg_sem.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_msg_sem.py",
        "symbols": [
          "PointNet2SemSegMSG",
          "PointNet2SemSegMSG._build_model"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2078",
        "E2079"
      ]
    },
    {
      "mechanism_id": "MECH-066",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_msg_sem.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_msg_sem.py",
        "symbols": [
          "PointNet2SemSegMSG._build_model->BatchNorm1d",
          "PointNet2SemSegMSG._build_model->Conv1d",
          "PointNet2SemSegMSG._build_model->Dropout",
          "PointNet2SemSegMSG._build_model->ModuleList",
          "PointNet2SemSegMSG._build_model->PointnetFPModule",
          "PointNet2SemSegMSG._build_model->PointnetSAModuleMSG",
          "PointNet2SemSegMSG._build_model->ReLU",
          "PointNet2SemSegMSG._build_model->Sequential",
          "PointNet2SemSegMSG._build_model->append"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2080",
        "E2081",
        "E2082",
        "E2083",
        "E2084",
        "E2085",
        "E2086",
        "E2087",
        "E2088"
      ]
    },
    {
      "mechanism_id": "MECH-067",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py",
        "symbols": [
          "PointNet2ClassificationSSG",
          "PointNet2ClassificationSSG.__init__",
          "PointNet2ClassificationSSG._break_up_pc",
          "PointNet2ClassificationSSG._build_model",
          "PointNet2ClassificationSSG.prepare_data",
          "PointNet2ClassificationSSG.validation_end",
          "PointNet2ClassificationSSG.validation_step",
          "set_bn_momentum_default"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2089",
        "E2095",
        "E2096",
        "E2097",
        "E2098",
        "E2102",
        "E2103",
        "E2105"
      ]
    },
    {
      "mechanism_id": "MECH-068",
      "mechanism_name": "optimization and objective logic",
      "mechanism_description": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py implements optimization and objective logic.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py",
        "symbols": [
          "BNMomentumScheduler",
          "BNMomentumScheduler.__init__",
          "BNMomentumScheduler.state_dict",
          "BNMomentumScheduler.step",
          "PointNet2ClassificationSSG.configure_optimizers"
        ]
      },
      "distinguishing_level": "main",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2090",
        "E2091",
        "E2092",
        "E2093",
        "E2104"
      ]
    },
    {
      "mechanism_id": "MECH-069",
      "mechanism_name": "model computation block",
      "mechanism_description": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py implements model computation block.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py",
        "symbols": [
          "PointNet2ClassificationSSG.forward"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2099"
      ]
    },
    {
      "mechanism_id": "MECH-070",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py",
        "symbols": [
          "BNMomentumScheduler.__init__->RuntimeError",
          "BNMomentumScheduler.__init__->format",
          "BNMomentumScheduler.__init__->isinstance",
          "BNMomentumScheduler.__init__->step",
          "BNMomentumScheduler.__init__->type",
          "BNMomentumScheduler.state_dict->dict",
          "BNMomentumScheduler.step->apply",
          "BNMomentumScheduler.step->lmbd",
          "BNMomentumScheduler.step->setter",
          "PointNet2ClassificationSSG.__init__->__init__",
          "PointNet2ClassificationSSG.__init__->_build_model",
          "PointNet2ClassificationSSG.__init__->super",
          "PointNet2ClassificationSSG._break_up_pc->contiguous",
          "PointNet2ClassificationSSG._break_up_pc->size",
          "PointNet2ClassificationSSG._break_up_pc->transpose",
          "PointNet2ClassificationSSG._build_model->BatchNorm1d",
          "PointNet2ClassificationSSG._build_model->Dropout",
          "PointNet2ClassificationSSG._build_model->Linear",
          "PointNet2ClassificationSSG._build_model->ModuleList",
          "PointNet2ClassificationSSG._build_model->PointnetSAModule",
          "PointNet2ClassificationSSG._build_model->ReLU",
          "PointNet2ClassificationSSG._build_model->Sequential",
          "PointNet2ClassificationSSG._build_model->append",
          "PointNet2ClassificationSSG.configure_optimizers->Adam",
          "PointNet2ClassificationSSG.configure_optimizers->BNMomentumScheduler",
          "PointNet2ClassificationSSG.configure_optimizers->LambdaLR",
          "PointNet2ClassificationSSG.configure_optimizers->int",
          "PointNet2ClassificationSSG.configure_optimizers->max",
          "PointNet2ClassificationSSG.configure_optimizers->parameters",
          "PointNet2ClassificationSSG.forward->_break_up_pc",
          "PointNet2ClassificationSSG.forward->fc_layer",
          "PointNet2ClassificationSSG.forward->module",
          "PointNet2ClassificationSSG.forward->squeeze",
          "PointNet2ClassificationSSG.prepare_data->Compose",
          "PointNet2ClassificationSSG.prepare_data->ModelNet40Cls",
          "PointNet2ClassificationSSG.prepare_data->PointcloudJitter",
          "PointNet2ClassificationSSG.prepare_data->PointcloudRandomInputDropout",
          "PointNet2ClassificationSSG.prepare_data->PointcloudRotate",
          "PointNet2ClassificationSSG.prepare_data->PointcloudRotatePerturbation",
          "PointNet2ClassificationSSG.prepare_data->PointcloudScale",
          "PointNet2ClassificationSSG.prepare_data->PointcloudToTensor",
          "PointNet2ClassificationSSG.prepare_data->PointcloudTranslate",
          "PointNet2ClassificationSSG.training_step->forward",
          "PointNet2ClassificationSSG.validation_end->copy",
          "PointNet2ClassificationSSG.validation_end->dict",
          "PointNet2ClassificationSSG.validation_end->get",
          "PointNet2ClassificationSSG.validation_end->mean",
          "PointNet2ClassificationSSG.validation_end->stack",
          "PointNet2ClassificationSSG.validation_end->update",
          "PointNet2ClassificationSSG.validation_step->argmax",
          "PointNet2ClassificationSSG.validation_step->cross_entropy",
          "PointNet2ClassificationSSG.validation_step->dict",
          "PointNet2ClassificationSSG.validation_step->float",
          "PointNet2ClassificationSSG.validation_step->forward",
          "PointNet2ClassificationSSG.validation_step->mean",
          "set_bn_momentum_default->isinstance"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2109",
        "E2110",
        "E2111",
        "E2112",
        "E2113",
        "E2114",
        "E2115",
        "E2116",
        "E2117",
        "E2118",
        "E2120",
        "E2121",
        "E2122",
        "E2123",
        "E2124",
        "E2125",
        "E2126",
        "E2127",
        "E2128",
        "E2129",
        "E2130",
        "E2131",
        "E2132",
        "E2133",
        "E2134",
        "E2135",
        "E2136",
        "E2137",
        "E2142",
        "E2145",
        "E2146",
        "E2147",
        "E2148",
        "E2149",
        "E2150",
        "E2151",
        "E2152",
        "E2153",
        "E2154",
        "E2155",
        "E2156",
        "E2157",
        "E2158",
        "E2159",
        "E2160",
        "E2161",
        "E2162",
        "E2163",
        "E2164",
        "E2165",
        "E2166",
        "E2167",
        "E2168",
        "E2169",
        "E2170",
        "E2171"
      ]
    },
    {
      "mechanism_id": "MECH-071",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_sem.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_sem.py",
        "symbols": [
          "PointNet2SemSegSSG",
          "PointNet2SemSegSSG._build_model",
          "PointNet2SemSegSSG.prepare_data"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2175",
        "E2176",
        "E2179"
      ]
    },
    {
      "mechanism_id": "MECH-072",
      "mechanism_name": "model computation block",
      "mechanism_description": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_sem.py implements model computation block.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_sem.py",
        "symbols": [
          "PointNet2SemSegSSG.forward"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2177"
      ]
    },
    {
      "mechanism_id": "MECH-073",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_sem.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_sem.py",
        "symbols": [
          "PointNet2SemSegSSG._build_model->BatchNorm1d",
          "PointNet2SemSegSSG._build_model->Conv1d",
          "PointNet2SemSegSSG._build_model->Dropout",
          "PointNet2SemSegSSG._build_model->ModuleList",
          "PointNet2SemSegSSG._build_model->PointnetFPModule",
          "PointNet2SemSegSSG._build_model->PointnetSAModule",
          "PointNet2SemSegSSG._build_model->ReLU",
          "PointNet2SemSegSSG._build_model->Sequential",
          "PointNet2SemSegSSG._build_model->append",
          "PointNet2SemSegSSG.forward->_break_up_pc",
          "PointNet2SemSegSSG.forward->append",
          "PointNet2SemSegSSG.forward->fc_lyaer",
          "PointNet2SemSegSSG.forward->len",
          "PointNet2SemSegSSG.forward->range",
          "PointNet2SemSegSSG.prepare_data->Indoor3DSemSeg"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2180",
        "E2181",
        "E2182",
        "E2183",
        "E2184",
        "E2185",
        "E2186",
        "E2187",
        "E2188",
        "E2189",
        "E2190",
        "E2191",
        "E2192",
        "E2193",
        "E2194"
      ]
    },
    {
      "mechanism_id": "MECH-074",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/configuration_phi3.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/configuration_phi3.py",
        "symbols": [
          "Phi3Config.__init__->__init__",
          "Phi3Config.__init__->_rope_scaling_validation",
          "Phi3Config.__init__->super",
          "Phi3Config._rope_scaling_validation->ValueError",
          "Phi3Config._rope_scaling_validation->all",
          "Phi3Config._rope_scaling_validation->get",
          "Phi3Config._rope_scaling_validation->isinstance",
          "Phi3Config._rope_scaling_validation->len"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2278",
        "E2279",
        "E2280",
        "E2281",
        "E2282",
        "E2283",
        "E2284",
        "E2285"
      ]
    },
    {
      "mechanism_id": "MECH-075",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/sample_finetune.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/sample_finetune.py",
        "symbols": [
          "apply_chat_template"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2301"
      ]
    },
    {
      "mechanism_id": "MECH-076",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/sample_finetune.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/sample_finetune.py",
        "symbols": [
          "apply_chat_template->apply_chat_template",
          "apply_chat_template->insert"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2302",
        "E2303"
      ]
    },
    {
      "mechanism_id": "MECH-077",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "llava/conversation.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/conversation.py",
        "symbols": [
          "Conversation.append_message->append",
          "Conversation.copy->Conversation",
          "Conversation.dict->get_images",
          "Conversation.dict->len",
          "Conversation.dict->type",
          "Conversation.get_images->append",
          "Conversation.get_images->enumerate",
          "Conversation.get_images->process_image",
          "Conversation.get_images->type",
          "Conversation.get_prompt->ValueError",
          "Conversation.get_prompt->copy",
          "Conversation.get_prompt->enumerate",
          "Conversation.get_prompt->insert",
          "Conversation.get_prompt->len",
          "Conversation.get_prompt->lstrip",
          "Conversation.get_prompt->replace",
          "Conversation.get_prompt->strip",
          "Conversation.get_prompt->type",
          "Conversation.get_prompt->wrap_inst",
          "Conversation.get_prompt->wrap_sys",
          "Conversation.process_image->BytesIO",
          "Conversation.process_image->ValueError",
          "Conversation.process_image->b64encode",
          "Conversation.process_image->decode",
          "Conversation.process_image->expand2square",
          "Conversation.process_image->getvalue",
          "Conversation.process_image->int",
          "Conversation.process_image->max",
          "Conversation.process_image->min",
          "Conversation.process_image->new",
          "Conversation.process_image->paste",
          "Conversation.process_image->resize",
          "Conversation.to_gradio_chatbot->append",
          "Conversation.to_gradio_chatbot->enumerate",
          "Conversation.to_gradio_chatbot->process_image",
          "Conversation.to_gradio_chatbot->replace",
          "Conversation.to_gradio_chatbot->strip",
          "Conversation.to_gradio_chatbot->type"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2320",
        "E2321",
        "E2322",
        "E2323",
        "E2324",
        "E2325",
        "E2326",
        "E2327",
        "E2328",
        "E2329",
        "E2330",
        "E2331",
        "E2332",
        "E2333",
        "E2334",
        "E2335",
        "E2336",
        "E2337",
        "E2338",
        "E2339",
        "E2340",
        "E2341",
        "E2342",
        "E2343",
        "E2344",
        "E2345",
        "E2346",
        "E2347",
        "E2348",
        "E2349",
        "E2350",
        "E2351",
        "E2352",
        "E2353",
        "E2354",
        "E2355",
        "E2356",
        "E2357"
      ]
    },
    {
      "mechanism_id": "MECH-078",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "llava/mm_utils.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/mm_utils.py",
        "symbols": [
          "KeywordsStoppingCriteria.__call__->all",
          "KeywordsStoppingCriteria.__call__->append",
          "KeywordsStoppingCriteria.__call__->call_for_batch",
          "KeywordsStoppingCriteria.__call__->range",
          "KeywordsStoppingCriteria.__call__->unsqueeze",
          "KeywordsStoppingCriteria.__init__->append",
          "KeywordsStoppingCriteria.__init__->len",
          "KeywordsStoppingCriteria.__init__->tensor",
          "KeywordsStoppingCriteria.__init__->tokenizer",
          "KeywordsStoppingCriteria.call_for_batch->batch_decode",
          "KeywordsStoppingCriteria.call_for_batch->equal",
          "KeywordsStoppingCriteria.call_for_batch->min",
          "KeywordsStoppingCriteria.call_for_batch->to"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2427",
        "E2428",
        "E2429",
        "E2430",
        "E2431",
        "E2432",
        "E2433",
        "E2434",
        "E2435",
        "E2436",
        "E2437",
        "E2438",
        "E2439"
      ]
    },
    {
      "mechanism_id": "MECH-079",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "llava/serve/controller.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/serve/controller.py",
        "symbols": [
          "Controller",
          "Controller.__init__",
          "Controller.get_worker_address",
          "Controller.get_worker_status",
          "Controller.list_models",
          "Controller.receive_heart_beat",
          "Controller.refresh_all_workers",
          "Controller.register_worker",
          "Controller.remove_worker",
          "Controller.worker_api_generate_stream",
          "Controller.worker_api_get_status",
          "DispatchMethod",
          "DispatchMethod.from_str",
          "WorkerInfo",
          "get_worker_address",
          "heart_beat_controller",
          "list_models",
          "receive_heart_beat",
          "refresh_all_workers",
          "register_worker",
          "worker_api_generate_stream",
          "worker_api_get_status"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2446",
        "E2447",
        "E2448",
        "E2449",
        "E2450",
        "E2451",
        "E2452",
        "E2453",
        "E2454",
        "E2455",
        "E2456",
        "E2457",
        "E2458",
        "E2460",
        "E2461",
        "E2462",
        "E2463",
        "E2464",
        "E2465",
        "E2466",
        "E2467",
        "E2468"
      ]
    },
    {
      "mechanism_id": "MECH-080",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "llava/serve/controller.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/serve/controller.py",
        "symbols": [
          "Controller.__init__->from_str",
          "Controller.__init__->info",
          "Controller.__init__->start",
          "Controller.get_worker_address->ValueError",
          "Controller.get_worker_address->append",
          "Controller.get_worker_address->arange",
          "Controller.get_worker_address->argmin",
          "Controller.get_worker_address->array",
          "Controller.get_worker_address->choice",
          "Controller.get_worker_address->get_worker_status",
          "Controller.get_worker_address->info",
          "Controller.get_worker_address->items",
          "Controller.get_worker_address->len",
          "Controller.get_worker_address->remove_worker",
          "Controller.get_worker_address->sum",
          "Controller.get_worker_status->error",
          "Controller.get_worker_status->json",
          "Controller.get_worker_status->post",
          "Controller.list_models->items",
          "Controller.list_models->list",
          "Controller.list_models->set",
          "Controller.list_models->update",
          "Controller.receive_heart_beat->info",
          "Controller.receive_heart_beat->time",
          "Controller.refresh_all_workers->dict",
          "Controller.refresh_all_workers->info",
          "Controller.refresh_all_workers->items",
          "Controller.refresh_all_workers->register_worker",
          "Controller.register_worker->WorkerInfo",
          "Controller.register_worker->get_worker_status",
          "Controller.register_worker->info",
          "Controller.register_worker->time",
          "Controller.remove_stable_workers_by_expiration->append",
          "Controller.remove_stable_workers_by_expiration->items",
          "Controller.remove_stable_workers_by_expiration->remove_worker",
          "Controller.remove_stable_workers_by_expiration->time",
          "Controller.worker_api_generate_stream->dumps",
          "Controller.worker_api_generate_stream->encode",
          "Controller.worker_api_generate_stream->get_worker_address",
          "Controller.worker_api_generate_stream->info",
          "Controller.worker_api_generate_stream->iter_lines",
          "Controller.worker_api_generate_stream->post",
          "Controller.worker_api_get_status->get_worker_status",
          "Controller.worker_api_get_status->list",
          "Controller.worker_api_get_status->set",
          "Controller.worker_api_get_status->update",
          "DispatchMethod.from_str->ValueError",
          "get_worker_address->get_worker_address",
          "get_worker_address->json",
          "get_worker_address->post",
          "heart_beat_controller->sleep",
          "list_models->list_models",
          "list_models->post",
          "receive_heart_beat->json",
          "receive_heart_beat->post",
          "receive_heart_beat->receive_heart_beat",
          "refresh_all_workers->post",
          "refresh_all_workers->refresh_all_workers",
          "register_worker->get",
          "register_worker->json",
          "register_worker->post",
          "register_worker->register_worker",
          "worker_api_generate_stream->StreamingResponse",
          "worker_api_generate_stream->json",
          "worker_api_generate_stream->post",
          "worker_api_generate_stream->worker_api_generate_stream",
          "worker_api_get_status->post",
          "worker_api_get_status->worker_api_get_status"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2469",
        "E2471",
        "E2473",
        "E2474",
        "E2475",
        "E2476",
        "E2477",
        "E2478",
        "E2479",
        "E2480",
        "E2481",
        "E2482",
        "E2483",
        "E2484",
        "E2485",
        "E2486",
        "E2487",
        "E2488",
        "E2489",
        "E2490",
        "E2491",
        "E2492",
        "E2493",
        "E2494",
        "E2495",
        "E2496",
        "E2497",
        "E2498",
        "E2499",
        "E2500",
        "E2501",
        "E2502",
        "E2503",
        "E2504",
        "E2505",
        "E2506",
        "E2507",
        "E2508",
        "E2509",
        "E2510",
        "E2511",
        "E2512",
        "E2513",
        "E2514",
        "E2515",
        "E2516",
        "E2517",
        "E2518",
        "E2519",
        "E2520",
        "E2521",
        "E2522",
        "E2523",
        "E2524",
        "E2525",
        "E2526",
        "E2527",
        "E2528",
        "E2529",
        "E2530",
        "E2531",
        "E2532",
        "E2533",
        "E2534",
        "E2535",
        "E2536",
        "E2537",
        "E2538"
      ]
    },
    {
      "mechanism_id": "MECH-081",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "llava/serve/gradio_web_server.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/serve/gradio_web_server.py",
        "symbols": [
          "get_model_list"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2552"
      ]
    },
    {
      "mechanism_id": "MECH-082",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "llava/serve/sglang_worker.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/serve/sglang_worker.py",
        "symbols": [
          "ModelWorker",
          "ModelWorker.__init__",
          "ModelWorker.generate_stream",
          "ModelWorker.generate_stream_gate",
          "ModelWorker.get_queue_length",
          "ModelWorker.get_status",
          "ModelWorker.register_to_controller",
          "ModelWorker.send_heart_beat",
          "generate_stream",
          "get_status",
          "heart_beat_worker",
          "release_model_semaphore"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2637",
        "E2639",
        "E2640",
        "E2641",
        "E2642",
        "E2643",
        "E2644",
        "E2645",
        "E2646",
        "E2647",
        "E2648",
        "E2649"
      ]
    },
    {
      "mechanism_id": "MECH-083",
      "mechanism_name": "entrypoint orchestration",
      "mechanism_description": "llava/serve/sglang_worker.py implements entrypoint orchestration.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/serve/sglang_worker.py",
        "symbols": [
          "pipeline"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2638"
      ]
    },
    {
      "mechanism_id": "MECH-084",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "llava/serve/sglang_worker.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/serve/sglang_worker.py",
        "symbols": [
          "ModelWorker.__init__->RuntimeEndpoint",
          "ModelWorker.__init__->endswith",
          "ModelWorker.__init__->info",
          "ModelWorker.__init__->register_to_controller",
          "ModelWorker.__init__->set_default_backend",
          "ModelWorker.__init__->split",
          "ModelWorker.__init__->start",
          "ModelWorker.__init__->startswith",
          "ModelWorker.generate_stream->ValueError",
          "ModelWorker.generate_stream->append",
          "ModelWorker.generate_stream->count",
          "ModelWorker.generate_stream->dumps",
          "ModelWorker.generate_stream->encode",
          "ModelWorker.generate_stream->float",
          "ModelWorker.generate_stream->get",
          "ModelWorker.generate_stream->int",
          "ModelWorker.generate_stream->len",
          "ModelWorker.generate_stream->min",
          "ModelWorker.generate_stream->print",
          "ModelWorker.generate_stream_gate->dumps",
          "ModelWorker.generate_stream_gate->encode",
          "ModelWorker.generate_stream_gate->generate_stream",
          "ModelWorker.generate_stream_gate->print",
          "ModelWorker.get_queue_length->len",
          "ModelWorker.get_status->get_queue_length",
          "ModelWorker.register_to_controller->get_status",
          "ModelWorker.register_to_controller->info",
          "ModelWorker.register_to_controller->post",
          "ModelWorker.send_heart_beat->error",
          "ModelWorker.send_heart_beat->get_queue_length",
          "ModelWorker.send_heart_beat->info",
          "ModelWorker.send_heart_beat->json",
          "ModelWorker.send_heart_beat->post",
          "ModelWorker.send_heart_beat->pretty_print_semaphore",
          "ModelWorker.send_heart_beat->register_to_controller",
          "ModelWorker.send_heart_beat->sleep",
          "generate_stream->BackgroundTasks",
          "generate_stream->Semaphore",
          "generate_stream->StreamingResponse",
          "generate_stream->acquire",
          "generate_stream->add_task",
          "generate_stream->generate_stream_gate",
          "generate_stream->json",
          "generate_stream->partial",
          "generate_stream->post",
          "generate_stream->send_heart_beat",
          "get_status->get_status",
          "get_status->post",
          "heart_beat_worker->send_heart_beat",
          "heart_beat_worker->sleep",
          "pipeline->gen",
          "pipeline->image",
          "pipeline->type",
          "release_model_semaphore->fn",
          "release_model_semaphore->release"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2650",
        "E2651",
        "E2652",
        "E2653",
        "E2654",
        "E2655",
        "E2657",
        "E2658",
        "E2659",
        "E2660",
        "E2661",
        "E2662",
        "E2663",
        "E2664",
        "E2665",
        "E2666",
        "E2667",
        "E2668",
        "E2669",
        "E2670",
        "E2671",
        "E2672",
        "E2673",
        "E2674",
        "E2675",
        "E2676",
        "E2677",
        "E2678",
        "E2679",
        "E2680",
        "E2681",
        "E2682",
        "E2683",
        "E2684",
        "E2685",
        "E2687",
        "E2688",
        "E2689",
        "E2690",
        "E2691",
        "E2692",
        "E2693",
        "E2694",
        "E2695",
        "E2696",
        "E2697",
        "E2698",
        "E2699",
        "E2700",
        "E2701",
        "E2702",
        "E2703",
        "E2704",
        "E2705",
        "E2706"
      ]
    },
    {
      "mechanism_id": "MECH-085",
      "mechanism_name": "data preparation and loading",
      "mechanism_description": "llava/utils.py implements data preparation and loading.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/utils.py",
        "symbols": [
          "SimpleTokenizer.decode",
          "SimpleTokenizer.encode"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2739",
        "E2740"
      ]
    },
    {
      "mechanism_id": "MECH-086",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "llava/utils.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/utils.py",
        "symbols": [
          "SimpleTokenizer.__call__->encode",
          "SimpleTokenizer.__call__->enumerate",
          "SimpleTokenizer.__call__->isinstance",
          "SimpleTokenizer.__call__->len",
          "SimpleTokenizer.__call__->tensor",
          "SimpleTokenizer.__call__->zeros",
          "SimpleTokenizer.__init__->append",
          "SimpleTokenizer.__init__->bytes_to_unicode",
          "SimpleTokenizer.__init__->compile",
          "SimpleTokenizer.__init__->decode",
          "SimpleTokenizer.__init__->default_bpe",
          "SimpleTokenizer.__init__->dict",
          "SimpleTokenizer.__init__->extend",
          "SimpleTokenizer.__init__->items",
          "SimpleTokenizer.__init__->join",
          "SimpleTokenizer.__init__->len",
          "SimpleTokenizer.__init__->list",
          "SimpleTokenizer.__init__->open",
          "SimpleTokenizer.bpe->append",
          "SimpleTokenizer.bpe->extend",
          "SimpleTokenizer.bpe->float",
          "SimpleTokenizer.bpe->get",
          "SimpleTokenizer.bpe->get_pairs",
          "SimpleTokenizer.bpe->index",
          "SimpleTokenizer.bpe->join",
          "SimpleTokenizer.bpe->len",
          "SimpleTokenizer.bpe->min",
          "SimpleTokenizer.bpe->tuple",
          "SimpleTokenizer.decode->bytearray",
          "SimpleTokenizer.decode->decode",
          "SimpleTokenizer.decode->join",
          "SimpleTokenizer.decode->replace",
          "SimpleTokenizer.encode->basic_clean",
          "SimpleTokenizer.encode->bpe",
          "SimpleTokenizer.encode->encode",
          "SimpleTokenizer.encode->extend",
          "SimpleTokenizer.encode->findall",
          "SimpleTokenizer.encode->join",
          "SimpleTokenizer.encode->lower",
          "SimpleTokenizer.encode->split",
          "SimpleTokenizer.encode->whitespace_clean",
          "StreamToLogger.__getattr__->getattr",
          "StreamToLogger.flush->log",
          "StreamToLogger.flush->rstrip"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2754",
        "E2758",
        "E2759",
        "E2785",
        "E2786",
        "E2787",
        "E2788",
        "E2789",
        "E2790",
        "E2791",
        "E2792",
        "E2793",
        "E2794",
        "E2795",
        "E2796",
        "E2797",
        "E2798",
        "E2799",
        "E2800",
        "E2801",
        "E2802",
        "E2803",
        "E2804",
        "E2805",
        "E2806",
        "E2807",
        "E2808",
        "E2809",
        "E2810",
        "E2811",
        "E2812",
        "E2813",
        "E2814",
        "E2815",
        "E2816",
        "E2817",
        "E2818",
        "E2819",
        "E2820",
        "E2821",
        "E2822",
        "E2823",
        "E2824",
        "E2825"
      ]
    },
    {
      "mechanism_id": "MECH-087",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "pointllm/conversation.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointllm/conversation.py",
        "symbols": [
          "Conversation.append_message->append",
          "Conversation.copy->Conversation",
          "Conversation.dict->get_images",
          "Conversation.dict->len",
          "Conversation.dict->type",
          "Conversation.get_images->BytesIO",
          "Conversation.get_images->ValueError",
          "Conversation.get_images->append",
          "Conversation.get_images->b64encode",
          "Conversation.get_images->decode",
          "Conversation.get_images->enumerate",
          "Conversation.get_images->expand2square",
          "Conversation.get_images->getvalue",
          "Conversation.get_images->int",
          "Conversation.get_images->max",
          "Conversation.get_images->min",
          "Conversation.get_images->new",
          "Conversation.get_prompt->ValueError",
          "Conversation.get_prompt->enumerate",
          "Conversation.get_prompt->type",
          "Conversation.pop_last_none_message->pop",
          "Conversation.to_gradio_chatbot->BytesIO",
          "Conversation.to_gradio_chatbot->append",
          "Conversation.to_gradio_chatbot->b64encode",
          "Conversation.to_gradio_chatbot->decode",
          "Conversation.to_gradio_chatbot->enumerate",
          "Conversation.to_gradio_chatbot->getvalue",
          "Conversation.to_gradio_chatbot->int",
          "Conversation.to_gradio_chatbot->max",
          "Conversation.to_gradio_chatbot->min",
          "Conversation.to_gradio_chatbot->replace",
          "Conversation.to_gradio_chatbot->resize"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2842",
        "E2843",
        "E2844",
        "E2845",
        "E2846",
        "E2847",
        "E2848",
        "E2849",
        "E2850",
        "E2851",
        "E2852",
        "E2853",
        "E2854",
        "E2855",
        "E2856",
        "E2857",
        "E2858",
        "E2859",
        "E2860",
        "E2861",
        "E2862",
        "E2863",
        "E2864",
        "E2865",
        "E2866",
        "E2867",
        "E2868",
        "E2869",
        "E2871",
        "E2872",
        "E2873",
        "E2874"
      ]
    },
    {
      "mechanism_id": "MECH-088",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "pointllm/data/utils.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointllm/data/utils.py",
        "symbols": [
          "LRUCache.__init__->OrderedDict",
          "LRUCache.__init__->defaultdict",
          "LRUCache.get->pop",
          "LRUCache.get_access_count->get",
          "LRUCache.put->iter",
          "LRUCache.put->len",
          "LRUCache.put->next",
          "LRUCache.put->pop",
          "LRUCache.put->popitem"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E2994",
        "E2995",
        "E2996",
        "E2997",
        "E2998",
        "E2999",
        "E3000",
        "E3001",
        "E3002"
      ]
    },
    {
      "mechanism_id": "MECH-089",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "pointllm/data/utils_backup.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointllm/data/utils_backup.py",
        "symbols": [
          "LRUCache.__init__->OrderedDict",
          "LRUCache.__init__->defaultdict",
          "LRUCache.get->pop",
          "LRUCache.get_access_count->get",
          "LRUCache.put->iter",
          "LRUCache.put->len",
          "LRUCache.put->next",
          "LRUCache.put->pop",
          "LRUCache.put->popitem"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E3086",
        "E3087",
        "E3088",
        "E3089",
        "E3090",
        "E3091",
        "E3092",
        "E3093",
        "E3094"
      ]
    },
    {
      "mechanism_id": "MECH-090",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "pointllm/utils.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointllm/utils.py",
        "symbols": [
          "StreamToLogger.__getattr__->getattr",
          "StreamToLogger.flush->log",
          "StreamToLogger.flush->rstrip"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E3180",
        "E3184",
        "E3185"
      ]
    },
    {
      "mechanism_id": "MECH-091",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "pointnet++/Pointnet2_PyTorch/pointnet2/data/data_utils.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointnet++/Pointnet2_PyTorch/pointnet2/data/data_utils.py",
        "symbols": [
          "PointcloudJitter.__call__->clamp_",
          "PointcloudJitter.__call__->new",
          "PointcloudJitter.__call__->normal_",
          "PointcloudJitter.__call__->size",
          "PointcloudRandomInputDropout.__call__->float",
          "PointcloudRandomInputDropout.__call__->from_numpy",
          "PointcloudRandomInputDropout.__call__->len",
          "PointcloudRandomInputDropout.__call__->numpy",
          "PointcloudRandomInputDropout.__call__->random",
          "PointcloudRandomInputDropout.__call__->where",
          "PointcloudRotate.__call__->angle_axis",
          "PointcloudRotate.__call__->matmul",
          "PointcloudRotate.__call__->size",
          "PointcloudRotate.__call__->t",
          "PointcloudRotate.__call__->uniform",
          "PointcloudRotate.__init__->array",
          "PointcloudRotatePerturbation.__call__->_get_angles",
          "PointcloudRotatePerturbation.__call__->angle_axis",
          "PointcloudRotatePerturbation.__call__->array",
          "PointcloudRotatePerturbation.__call__->matmul",
          "PointcloudRotatePerturbation.__call__->size",
          "PointcloudRotatePerturbation.__call__->t",
          "PointcloudRotatePerturbation._get_angles->clip",
          "PointcloudRotatePerturbation._get_angles->randn",
          "PointcloudScale.__call__->uniform",
          "PointcloudToTensor.__call__->float",
          "PointcloudToTensor.__call__->from_numpy",
          "PointcloudTranslate.__call__->uniform"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E3232",
        "E3233",
        "E3234",
        "E3235",
        "E3236",
        "E3237",
        "E3238",
        "E3239",
        "E3240",
        "E3241",
        "E3242",
        "E3243",
        "E3244",
        "E3245",
        "E3246",
        "E3247",
        "E3248",
        "E3249",
        "E3250",
        "E3251",
        "E3252",
        "E3253",
        "E3254",
        "E3255",
        "E3256",
        "E3257",
        "E3258",
        "E3259"
      ]
    },
    {
      "mechanism_id": "MECH-092",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_modules.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_modules.py",
        "symbols": [
          "PointnetFPModule",
          "PointnetFPModule.__init__",
          "PointnetSAModule",
          "PointnetSAModule.__init__",
          "PointnetSAModuleMSG",
          "PointnetSAModuleMSG.__init__",
          "_PointnetSAModuleBase",
          "_PointnetSAModuleBase.__init__",
          "build_shared_mlp"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E3295",
        "E3296",
        "E3297",
        "E3300",
        "E3302",
        "E3303",
        "E3305",
        "E3306",
        "E3308"
      ]
    },
    {
      "mechanism_id": "MECH-093",
      "mechanism_name": "model computation block",
      "mechanism_description": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_modules.py implements model computation block.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_modules.py",
        "symbols": [
          "PointnetFPModule.forward",
          "_PointnetSAModuleBase.forward"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E3298",
        "E3309"
      ]
    },
    {
      "mechanism_id": "MECH-094",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_modules.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_modules.py",
        "symbols": [
          "PointnetFPModule.__init__->__init__",
          "PointnetFPModule.__init__->build_shared_mlp",
          "PointnetFPModule.__init__->super",
          "PointnetFPModule.forward->cat",
          "PointnetFPModule.forward->expand",
          "PointnetFPModule.forward->mlp",
          "PointnetFPModule.forward->size",
          "PointnetFPModule.forward->squeeze",
          "PointnetFPModule.forward->sum",
          "PointnetFPModule.forward->three_interpolate",
          "PointnetFPModule.forward->three_nn",
          "PointnetFPModule.forward->unsqueeze",
          "PointnetSAModule.__init__->__init__",
          "PointnetSAModule.__init__->super",
          "PointnetSAModuleMSG.__init__->GroupAll",
          "PointnetSAModuleMSG.__init__->ModuleList",
          "PointnetSAModuleMSG.__init__->QueryAndGroup",
          "PointnetSAModuleMSG.__init__->__init__",
          "PointnetSAModuleMSG.__init__->append",
          "PointnetSAModuleMSG.__init__->build_shared_mlp",
          "PointnetSAModuleMSG.__init__->len",
          "PointnetSAModuleMSG.__init__->range",
          "PointnetSAModuleMSG.__init__->super",
          "_PointnetSAModuleBase.__init__->__init__",
          "_PointnetSAModuleBase.__init__->super",
          "_PointnetSAModuleBase.forward->append",
          "_PointnetSAModuleBase.forward->cat",
          "_PointnetSAModuleBase.forward->contiguous",
          "_PointnetSAModuleBase.forward->furthest_point_sample",
          "_PointnetSAModuleBase.forward->gather_operation",
          "_PointnetSAModuleBase.forward->len",
          "_PointnetSAModuleBase.forward->max_pool2d",
          "_PointnetSAModuleBase.forward->range",
          "_PointnetSAModuleBase.forward->size",
          "_PointnetSAModuleBase.forward->squeeze",
          "_PointnetSAModuleBase.forward->transpose",
          "build_shared_mlp->BatchNorm2d",
          "build_shared_mlp->Conv2d",
          "build_shared_mlp->ReLU",
          "build_shared_mlp->Sequential",
          "build_shared_mlp->append",
          "build_shared_mlp->len",
          "build_shared_mlp->range"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E3311",
        "E3312",
        "E3313",
        "E3314",
        "E3315",
        "E3316",
        "E3317",
        "E3318",
        "E3319",
        "E3320",
        "E3321",
        "E3322",
        "E3323",
        "E3324",
        "E3325",
        "E3326",
        "E3327",
        "E3328",
        "E3329",
        "E3330",
        "E3331",
        "E3332",
        "E3333",
        "E3334",
        "E3335",
        "E3336",
        "E3337",
        "E3338",
        "E3339",
        "E3340",
        "E3341",
        "E3342",
        "E3343",
        "E3344",
        "E3345",
        "E3346",
        "E3347",
        "E3348",
        "E3349",
        "E3350",
        "E3351",
        "E3352",
        "E3353"
      ]
    },
    {
      "mechanism_id": "MECH-095",
      "mechanism_name": "model computation block",
      "mechanism_description": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_utils.py implements model computation block.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_utils.py",
        "symbols": [
          "BallQuery.forward",
          "FurthestPointSampling.forward",
          "GatherOperation.forward",
          "GroupAll.forward",
          "GroupingOperation.forward",
          "QueryAndGroup.forward",
          "ThreeInterpolate.forward",
          "ThreeNN.forward"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E3359",
        "E3363",
        "E3367",
        "E3371",
        "E3376",
        "E3381",
        "E3387",
        "E3392"
      ]
    },
    {
      "mechanism_id": "MECH-096",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_utils.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_utils.py",
        "symbols": [
          "BallQuery.forward->ball_query",
          "BallQuery.forward->mark_non_differentiable",
          "FurthestPointSampling.forward->furthest_point_sampling",
          "FurthestPointSampling.forward->mark_non_differentiable",
          "GatherOperation.backward->contiguous",
          "GatherOperation.backward->gather_points_grad",
          "GatherOperation.backward->size",
          "GatherOperation.forward->gather_points",
          "GroupAll.__init__->__init__",
          "GroupAll.__init__->super",
          "GroupAll.forward->cat",
          "GroupAll.forward->transpose",
          "GroupAll.forward->unsqueeze",
          "GroupingOperation.backward->contiguous",
          "GroupingOperation.backward->group_points_grad",
          "GroupingOperation.backward->size",
          "GroupingOperation.backward->zeros_like",
          "GroupingOperation.forward->group_points",
          "QueryAndGroup.__init__->__init__",
          "QueryAndGroup.__init__->super",
          "QueryAndGroup.forward->ball_query",
          "QueryAndGroup.forward->cat",
          "QueryAndGroup.forward->contiguous",
          "QueryAndGroup.forward->grouping_operation",
          "QueryAndGroup.forward->transpose",
          "QueryAndGroup.forward->unsqueeze",
          "ThreeInterpolate.backward->contiguous",
          "ThreeInterpolate.backward->size",
          "ThreeInterpolate.backward->three_interpolate_grad",
          "ThreeInterpolate.backward->zeros_like",
          "ThreeInterpolate.forward->three_interpolate",
          "ThreeNN.forward->mark_non_differentiable",
          "ThreeNN.forward->sqrt",
          "ThreeNN.forward->three_nn"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E3394",
        "E3395",
        "E3396",
        "E3398",
        "E3399",
        "E3400",
        "E3401",
        "E3402",
        "E3403",
        "E3405",
        "E3406",
        "E3407",
        "E3408",
        "E3409",
        "E3410",
        "E3412",
        "E3413",
        "E3414",
        "E3415",
        "E3416",
        "E3417",
        "E3418",
        "E3419",
        "E3420",
        "E3421",
        "E3422",
        "E3423",
        "E3424",
        "E3425",
        "E3426",
        "E3427",
        "E3428",
        "E3429",
        "E3430"
      ]
    },
    {
      "mechanism_id": "MECH-097",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "scripts/convert_sqa_to_llava.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "scripts/convert_sqa_to_llava.py",
        "symbols": [
          "convert_to_jsonl",
          "convert_to_llava"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E3459",
        "E3460"
      ]
    },
    {
      "mechanism_id": "MECH-098",
      "mechanism_name": "entrypoint orchestration",
      "mechanism_description": "scripts/convert_sqa_to_llava.py implements entrypoint orchestration.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "scripts/convert_sqa_to_llava.py",
        "symbols": [
          "main"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E3461"
      ]
    },
    {
      "mechanism_id": "MECH-099",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "scripts/convert_sqa_to_llava.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "scripts/convert_sqa_to_llava.py",
        "symbols": [
          "convert_to_jsonl->build_prompt_chatbot",
          "convert_to_jsonl->close",
          "convert_to_jsonl->dumps",
          "convert_to_jsonl->items",
          "convert_to_jsonl->join",
          "convert_to_jsonl->open",
          "convert_to_jsonl->replace",
          "convert_to_jsonl->startswith",
          "convert_to_llava->append",
          "convert_to_llava->build_prompt_chatbot",
          "convert_to_llava->dump",
          "convert_to_llava->items",
          "convert_to_llava->join",
          "convert_to_llava->len",
          "convert_to_llava->open",
          "convert_to_llava->print",
          "convert_to_llava->replace",
          "convert_to_llava->startswith",
          "main->globals"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E3462",
        "E3463",
        "E3464",
        "E3465",
        "E3466",
        "E3467",
        "E3469",
        "E3470",
        "E3471",
        "E3472",
        "E3473",
        "E3474",
        "E3475",
        "E3476",
        "E3477",
        "E3479",
        "E3480",
        "E3481",
        "E3483"
      ]
    },
    {
      "mechanism_id": "MECH-100",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "scripts/convert_sqa_to_llava_base_prompt.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "scripts/convert_sqa_to_llava_base_prompt.py",
        "symbols": [
          "build_prompt",
          "build_prompt_chatbot",
          "build_prompt_gpt4",
          "create_one_example",
          "create_one_example_chatbot",
          "create_one_example_gpt4",
          "get_answer",
          "get_choice_text",
          "get_context_text",
          "get_lecture_text"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E3502",
        "E3503",
        "E3504",
        "E3505",
        "E3507",
        "E3508",
        "E3509",
        "E3510",
        "E3511",
        "E3512"
      ]
    },
    {
      "mechanism_id": "MECH-101",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "scripts/convert_sqa_to_llava_base_prompt.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "scripts/convert_sqa_to_llava_base_prompt.py",
        "symbols": [
          "build_prompt->append",
          "build_prompt->create_one_example",
          "build_prompt->get_answer",
          "build_prompt->get_choice_text",
          "build_prompt->get_context_text",
          "build_prompt->get_lecture_text",
          "build_prompt->join",
          "build_prompt_chatbot->create_one_example_chatbot",
          "build_prompt_chatbot->get_answer",
          "build_prompt_chatbot->get_choice_text",
          "build_prompt_chatbot->get_context_text",
          "build_prompt_chatbot->get_lecture_text",
          "build_prompt_chatbot->replace",
          "build_prompt_gpt4->append",
          "build_prompt_gpt4->create_one_example_gpt4",
          "build_prompt_gpt4->get_answer",
          "build_prompt_gpt4->get_choice_text",
          "build_prompt_gpt4->get_context_text",
          "build_prompt_gpt4->get_lecture_text",
          "create_one_example->endswith",
          "create_one_example->replace",
          "create_one_example->split",
          "create_one_example->strip",
          "create_one_example_chatbot->endswith",
          "create_one_example_chatbot->len",
          "create_one_example_chatbot->replace",
          "create_one_example_chatbot->split",
          "create_one_example_chatbot->strip",
          "create_one_example_gpt4->endswith",
          "create_one_example_gpt4->replace",
          "create_one_example_gpt4->split",
          "create_one_example_gpt4->strip",
          "get_choice_text->append",
          "get_choice_text->enumerate",
          "get_choice_text->format",
          "get_choice_text->join",
          "get_context_text->join",
          "get_context_text->strip",
          "get_lecture_text->replace"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E3513",
        "E3514",
        "E3515",
        "E3516",
        "E3517",
        "E3518",
        "E3519",
        "E3521",
        "E3522",
        "E3523",
        "E3524",
        "E3525",
        "E3526",
        "E3527",
        "E3528",
        "E3529",
        "E3530",
        "E3531",
        "E3532",
        "E3533",
        "E3534",
        "E3535",
        "E3536",
        "E3537",
        "E3538",
        "E3541",
        "E3542",
        "E3543",
        "E3544",
        "E3545",
        "E3546",
        "E3547",
        "E3550",
        "E3551",
        "E3552",
        "E3553",
        "E3554",
        "E3555",
        "E3556"
      ]
    },
    {
      "mechanism_id": "MECH-102",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "scripts/extract_mm_projector.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "scripts/extract_mm_projector.py",
        "symbols": [
          "parse_args"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E3569"
      ]
    },
    {
      "mechanism_id": "MECH-103",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "scripts/extract_mm_projector.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "scripts/extract_mm_projector.py",
        "symbols": [
          "parse_args->ArgumentParser",
          "parse_args->add_argument",
          "parse_args->parse_args"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E3570",
        "E3571",
        "E3572"
      ]
    },
    {
      "mechanism_id": "MECH-104",
      "mechanism_name": "infrastructure utility",
      "mechanism_description": "scripts/merge_lora_weights.py implements infrastructure utility.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "scripts/merge_lora_weights.py",
        "symbols": [
          "merge_lora"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E3588"
      ]
    },
    {
      "mechanism_id": "MECH-105",
      "mechanism_name": "model computation block",
      "mechanism_description": "pretrained_weight/eval_model_weight/all-mpnet-base-v2/train_script.py implements model computation block.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pretrained_weight/eval_model_weight/all-mpnet-base-v2/train_script.py",
        "symbols": [
          "AutoModelForSentenceEmbedding.forward"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E3696"
      ]
    },
    {
      "mechanism_id": "MECH-106",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "pretrained_weight/eval_model_weight/all-mpnet-base-v2/train_script.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "pretrained_weight/eval_model_weight/all-mpnet-base-v2/train_script.py",
        "symbols": [
          "AutoModelForSentenceEmbedding.forward->mean_pooling",
          "AutoModelForSentenceEmbedding.forward->model",
          "AutoModelForSentenceEmbedding.forward->normalize",
          "train_function->CrossEntropyLoss",
          "train_function->cross_entropy_loss"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E3712",
        "E3713",
        "E3714",
        "E3728",
        "E3733"
      ]
    },
    {
      "mechanism_id": "MECH-107",
      "mechanism_name": "entrypoint orchestration",
      "mechanism_description": "llava/serve/test_message.py implements entrypoint orchestration.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/serve/test_message.py",
        "symbols": [
          "main"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E3762"
      ]
    },
    {
      "mechanism_id": "MECH-108",
      "mechanism_name": "call-chain flow relation",
      "mechanism_description": "llava/serve/test_message.py implements call-chain flow relation.",
      "parent_stage_id": "S3",
      "inputs": [],
      "outputs": [],
      "implementation_anchor": {
        "path": "llava/serve/test_message.py",
        "symbols": [
          "main->append_message",
          "main->copy",
          "main->decode",
          "main->get_prompt",
          "main->iter_lines",
          "main->json",
          "main->post",
          "main->print",
          "main->replace",
          "main->sort",
          "main->split"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E3763",
        "E3764",
        "E3765",
        "E3766",
        "E3767",
        "E3768",
        "E3770",
        "E3771",
        "E3772",
        "E3773",
        "E3774"
      ]
    }
  ],
  "distinguishing_mechanisms": [
    "MECH-020",
    "MECH-068"
  ],
  "author_logic_mapping": {
    "author_proposed_flow": [],
    "author_supported_flow": [],
    "author_unsupported_parts": []
  },
  "unsupported_author_parts": [],
  "claim_contracts": [
    {
      "claim_id": "C1",
      "claim_intent": "The method contains a paper-facing stage named Input Preparation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E1418",
        "E1419",
        "E1420",
        "E1421",
        "E1422",
        "E1423",
        "E1424",
        "E2106",
        "E2107",
        "E2108",
        "E2982",
        "E2983",
        "E3074",
        "E3075"
      ],
      "allowed_wording_boundary": "Describe Input Preparation only using its listed evidence-backed inputs, outputs, modules, and mechanisms.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C2",
      "claim_intent": "The method contains a paper-facing stage named Transformer Computation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E107",
        "E108",
        "E110",
        "E111",
        "E112",
        "E113",
        "E114",
        "E115",
        "E116",
        "E117",
        "E118",
        "E119",
        "E120",
        "E121",
        "E123",
        "E125",
        "E126",
        "E127",
        "E128",
        "E130",
        "E132",
        "E133",
        "E134",
        "E135",
        "E137",
        "E138",
        "E139",
        "E141",
        "E142",
        "E144",
        "E145",
        "E146",
        "E147",
        "E148",
        "E149",
        "E150",
        "E152",
        "E153",
        "E154",
        "E155",
        "E156",
        "E157",
        "E158",
        "E159",
        "E160",
        "E161",
        "E162",
        "E163",
        "E164",
        "E166",
        "E167",
        "E168",
        "E169",
        "E170",
        "E171",
        "E172",
        "E174",
        "E175",
        "E176",
        "E411",
        "E440",
        "E454",
        "E470",
        "E471",
        "E472",
        "E473",
        "E474",
        "E475",
        "E476",
        "E477",
        "E478",
        "E511",
        "E512",
        "E513",
        "E514",
        "E515",
        "E516",
        "E517",
        "E518",
        "E519",
        "E552",
        "E553",
        "E554",
        "E555",
        "E556",
        "E557",
        "E558",
        "E559",
        "E560",
        "E561",
        "E589",
        "E590",
        "E591",
        "E592",
        "E593",
        "E594",
        "E595",
        "E596",
        "E597",
        "E650",
        "E651",
        "E652",
        "E653",
        "E654",
        "E656",
        "E658",
        "E659",
        "E660",
        "E661",
        "E662",
        "E663",
        "E664",
        "E722",
        "E732",
        "E733",
        "E739",
        "E740",
        "E741",
        "E742",
        "E743",
        "E744",
        "E745",
        "E746",
        "E747",
        "E748",
        "E749",
        "E750",
        "E751",
        "E752",
        "E753",
        "E754",
        "E755",
        "E756",
        "E848",
        "E850",
        "E852",
        "E854",
        "E856",
        "E858",
        "E859",
        "E860",
        "E861",
        "E862",
        "E864",
        "E865",
        "E866",
        "E868",
        "E869",
        "E870",
        "E872",
        "E873",
        "E874",
        "E964",
        "E965",
        "E966",
        "E967",
        "E968",
        "E969",
        "E970",
        "E971",
        "E972",
        "E973",
        "E974",
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1016",
        "E1017",
        "E1018",
        "E1020",
        "E1022",
        "E1023",
        "E1024",
        "E1026",
        "E1028",
        "E1029",
        "E1030",
        "E1031",
        "E1032",
        "E1033",
        "E1034",
        "E1035",
        "E1122",
        "E1123",
        "E1124",
        "E1125",
        "E1126",
        "E1127",
        "E1128",
        "E1129",
        "E1130",
        "E1131",
        "E1132",
        "E1133",
        "E1197",
        "E1401",
        "E1409",
        "E1639",
        "E1640",
        "E1642",
        "E1643",
        "E1644",
        "E1646",
        "E1709",
        "E1710",
        "E1712",
        "E1713",
        "E1714",
        "E1715",
        "E1717",
        "E1799",
        "E1800",
        "E1801",
        "E1802",
        "E1803",
        "E1804",
        "E1805",
        "E1806",
        "E1807",
        "E1808",
        "E1809",
        "E1810",
        "E1811",
        "E1869",
        "E1870",
        "E1871",
        "E1893",
        "E1910",
        "E2001",
        "E2004",
        "E2036",
        "E2037",
        "E2038",
        "E2039",
        "E2040",
        "E2041",
        "E2070",
        "E2071",
        "E2078",
        "E2079",
        "E2089",
        "E2090",
        "E2091",
        "E2092",
        "E2093",
        "E2094",
        "E2095",
        "E2096",
        "E2097",
        "E2098",
        "E2099",
        "E2101",
        "E2102",
        "E2103",
        "E2104",
        "E2105",
        "E2106",
        "E2107",
        "E2108",
        "E2175",
        "E2176",
        "E2177",
        "E2179",
        "E2373",
        "E2456",
        "E2464",
        "E2552",
        "E2554",
        "E2639",
        "E2640",
        "E2641",
        "E2642",
        "E2643",
        "E2644",
        "E2645",
        "E2646",
        "E2647",
        "E2739",
        "E2740",
        "E3298",
        "E3309",
        "E3359",
        "E3363",
        "E3367",
        "E3371",
        "E3376",
        "E3381",
        "E3387",
        "E3392",
        "E3694",
        "E3695",
        "E3696",
        "E3697",
        "E3698",
        "E3699",
        "E3700",
        "E3701",
        "E3703",
        "E3704",
        "E3705",
        "E3707",
        "E3708"
      ],
      "allowed_wording_boundary": "Describe Transformer Computation only using its listed evidence-backed inputs, outputs, modules, and mechanisms.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C3",
      "claim_intent": "The method contains a paper-facing stage named Scheduled Optimization.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E1258",
        "E2104"
      ],
      "allowed_wording_boundary": "Describe Scheduled Optimization only using its listed evidence-backed inputs, outputs, modules, and mechanisms.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C4",
      "claim_intent": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E107",
        "E108",
        "E111",
        "E112",
        "E113",
        "E115",
        "E116",
        "E118",
        "E119",
        "E121",
        "E123",
        "E125",
        "E126",
        "E128",
        "E150",
        "E152",
        "E153",
        "E154",
        "E156",
        "E157",
        "E158",
        "E159",
        "E160",
        "E161",
        "E166",
        "E167",
        "E168",
        "E169",
        "E170",
        "E171"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C5",
      "claim_intent": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py implements model computation block.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E110",
        "E114",
        "E117",
        "E120",
        "E127",
        "E130",
        "E132",
        "E133",
        "E134",
        "E135",
        "E137",
        "E138",
        "E139",
        "E141",
        "E142",
        "E144",
        "E145",
        "E146",
        "E147",
        "E155",
        "E162",
        "E163",
        "E164",
        "E172",
        "E176"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C6",
      "claim_intent": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py implements data preparation and loading.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E174",
        "E175"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C7",
      "claim_intent": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E178",
        "E179",
        "E180",
        "E181",
        "E182",
        "E183",
        "E184",
        "E185",
        "E186",
        "E187",
        "E188",
        "E189",
        "E190",
        "E191",
        "E192",
        "E193",
        "E194",
        "E195",
        "E196",
        "E197",
        "E198",
        "E199",
        "E200",
        "E201",
        "E202",
        "E203",
        "E204",
        "E205",
        "E206",
        "E207",
        "E208",
        "E209",
        "E210",
        "E211",
        "E212",
        "E213",
        "E214",
        "E215",
        "E216",
        "E217",
        "E218",
        "E219",
        "E220",
        "E221",
        "E222",
        "E223",
        "E224",
        "E225",
        "E226",
        "E227",
        "E228",
        "E229",
        "E230",
        "E231",
        "E232",
        "E233",
        "E234",
        "E235",
        "E236",
        "E237",
        "E238",
        "E239",
        "E240",
        "E241",
        "E242",
        "E243",
        "E244",
        "E245",
        "E246",
        "E247",
        "E248",
        "E249",
        "E250",
        "E251",
        "E252",
        "E253",
        "E254",
        "E255",
        "E256",
        "E257",
        "E258",
        "E259",
        "E260",
        "E261",
        "E262",
        "E263",
        "E264",
        "E265",
        "E266",
        "E267",
        "E268",
        "E269",
        "E270",
        "E271",
        "E272",
        "E273",
        "E274",
        "E275",
        "E276",
        "E277",
        "E278",
        "E279",
        "E280",
        "E281",
        "E282",
        "E283",
        "E284",
        "E285",
        "E286",
        "E287",
        "E288",
        "E289",
        "E290",
        "E291",
        "E292",
        "E293",
        "E294",
        "E295",
        "E296",
        "E297",
        "E298",
        "E299",
        "E300",
        "E301",
        "E302",
        "E303",
        "E304",
        "E305",
        "E306",
        "E307",
        "E308",
        "E309",
        "E310",
        "E311",
        "E312",
        "E313",
        "E314",
        "E315",
        "E316",
        "E317",
        "E321",
        "E322",
        "E323",
        "E324",
        "E325",
        "E326",
        "E327",
        "E328",
        "E329",
        "E330",
        "E331",
        "E332",
        "E333",
        "E334",
        "E335",
        "E336",
        "E337",
        "E338",
        "E339",
        "E340",
        "E341",
        "E342",
        "E343",
        "E344",
        "E345",
        "E346",
        "E347",
        "E348",
        "E349",
        "E350",
        "E351",
        "E352",
        "E353",
        "E354",
        "E355",
        "E356",
        "E357",
        "E358",
        "E359",
        "E360",
        "E361",
        "E362",
        "E363",
        "E364",
        "E365",
        "E366",
        "E367",
        "E368",
        "E369",
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
        "E381",
        "E382",
        "E383",
        "E384",
        "E385",
        "E386",
        "E387",
        "E388",
        "E389",
        "E390",
        "E391",
        "E392",
        "E393",
        "E394",
        "E395",
        "E396",
        "E397",
        "E398",
        "E399",
        "E400",
        "E401",
        "E402"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C8",
      "claim_intent": "llava/model/apply_delta.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E411"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C9",
      "claim_intent": "llava/model/apply_delta.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E413",
        "E414",
        "E416",
        "E417"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C10",
      "claim_intent": "llava/model/consolidate.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E454"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C11",
      "claim_intent": "llava/model/consolidate.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E455",
        "E457"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C12",
      "claim_intent": "llava/model/language_model/llava_llama.py implements configuration and runtime wiring.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E470"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C13",
      "claim_intent": "llava/model/language_model/llava_llama.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E471",
        "E472",
        "E473",
        "E474",
        "E475",
        "E477",
        "E478"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C14",
      "claim_intent": "llava/model/language_model/llava_llama.py implements model computation block.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E476"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C15",
      "claim_intent": "llava/model/language_model/llava_llama.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E479",
        "E480",
        "E481",
        "E482",
        "E483",
        "E484",
        "E485",
        "E486",
        "E487",
        "E488",
        "E489",
        "E490",
        "E491",
        "E492",
        "E493",
        "E494",
        "E495",
        "E496",
        "E497",
        "E498",
        "E499"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C16",
      "claim_intent": "llava/model/language_model/llava_mistral.py implements configuration and runtime wiring.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E511"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C17",
      "claim_intent": "llava/model/language_model/llava_mistral.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E512",
        "E513",
        "E514",
        "E515",
        "E516",
        "E518",
        "E519"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C18",
      "claim_intent": "llava/model/language_model/llava_mistral.py implements model computation block.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E517"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C19",
      "claim_intent": "llava/model/language_model/llava_mistral.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E520",
        "E521",
        "E522",
        "E523",
        "E524",
        "E525",
        "E526",
        "E527",
        "E528",
        "E529",
        "E530",
        "E531",
        "E532",
        "E533",
        "E534",
        "E535",
        "E536",
        "E537",
        "E538",
        "E539",
        "E540"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C20",
      "claim_intent": "llava/model/language_model/llava_mpt.py implements configuration and runtime wiring.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E552"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C21",
      "claim_intent": "llava/model/language_model/llava_mpt.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E553",
        "E554",
        "E556",
        "E557",
        "E558",
        "E561"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C22",
      "claim_intent": "llava/model/language_model/llava_mpt.py implements data preparation and loading.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E555"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C23",
      "claim_intent": "llava/model/language_model/llava_mpt.py implements optimization and objective logic.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E559"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C24",
      "claim_intent": "llava/model/language_model/llava_mpt.py implements model computation block.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E560"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C25",
      "claim_intent": "llava/model/language_model/llava_mpt.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E562",
        "E563",
        "E564",
        "E565",
        "E566",
        "E567",
        "E568",
        "E569",
        "E570",
        "E571",
        "E572",
        "E573",
        "E574",
        "E575",
        "E576"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C26",
      "claim_intent": "llava/model/language_model/llava_phi3.py implements configuration and runtime wiring.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E589"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C27",
      "claim_intent": "llava/model/language_model/llava_phi3.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E590",
        "E591",
        "E592",
        "E593",
        "E594",
        "E596",
        "E597"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C28",
      "claim_intent": "llava/model/language_model/llava_phi3.py implements model computation block.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E595"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C29",
      "claim_intent": "llava/model/language_model/llava_phi3.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E598",
        "E599",
        "E600",
        "E601",
        "E602",
        "E603",
        "E604",
        "E605",
        "E606",
        "E607",
        "E608",
        "E609",
        "E610",
        "E611",
        "E612",
        "E613",
        "E614",
        "E615",
        "E616",
        "E617",
        "E618",
        "E619"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C30",
      "claim_intent": "llava/model/llava_arch.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E650",
        "E651",
        "E652",
        "E653",
        "E654",
        "E656",
        "E658",
        "E659",
        "E660",
        "E661",
        "E662",
        "E663"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C31",
      "claim_intent": "llava/model/llava_arch.py implements data preparation and loading.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E664"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C32",
      "claim_intent": "llava/model/llava_arch.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E665",
        "E666",
        "E667",
        "E668",
        "E669",
        "E670",
        "E671",
        "E672",
        "E673",
        "E674",
        "E675",
        "E676",
        "E677",
        "E680",
        "E681",
        "E682",
        "E683",
        "E684",
        "E685",
        "E686",
        "E687",
        "E688",
        "E689",
        "E690",
        "E691",
        "E692",
        "E693",
        "E694",
        "E695",
        "E696",
        "E697",
        "E698",
        "E699",
        "E700",
        "E701",
        "E702",
        "E703",
        "E704",
        "E705",
        "E706",
        "E707",
        "E708",
        "E709",
        "E710",
        "E711",
        "E712",
        "E713",
        "E714",
        "E715",
        "E716",
        "E718",
        "E719",
        "E720"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C33",
      "claim_intent": "llava/model/make_delta.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E722"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C34",
      "claim_intent": "llava/model/make_delta.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E723",
        "E725",
        "E726",
        "E728",
        "E729"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C35",
      "claim_intent": "llava/model/multimodal_encoder/builder.py implements model computation block.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E732",
        "E733"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C36",
      "claim_intent": "llava/model/multimodal_encoder/builder.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E734",
        "E735",
        "E736",
        "E737"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C37",
      "claim_intent": "llava/model/multimodal_encoder/clip_encoder.py implements model computation block.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E739",
        "E740",
        "E742",
        "E743",
        "E744",
        "E745",
        "E746",
        "E747",
        "E748",
        "E749",
        "E750",
        "E751",
        "E752",
        "E754",
        "E755",
        "E756"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C38",
      "claim_intent": "llava/model/multimodal_encoder/clip_encoder.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E757",
        "E758",
        "E759",
        "E761",
        "E766",
        "E767",
        "E768",
        "E769",
        "E770",
        "E771",
        "E772",
        "E773",
        "E774",
        "E775",
        "E776",
        "E777",
        "E778",
        "E779",
        "E780",
        "E781",
        "E782",
        "E787",
        "E788",
        "E789",
        "E790",
        "E791",
        "E792",
        "E793",
        "E794",
        "E795",
        "E796"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C39",
      "claim_intent": "llava/model/multimodal_encoder/point_encoder.py implements model computation block.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E848",
        "E850",
        "E852",
        "E854",
        "E856",
        "E858",
        "E859",
        "E860",
        "E861",
        "E862",
        "E864",
        "E865",
        "E866",
        "E868",
        "E869",
        "E870",
        "E872",
        "E873",
        "E874"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C40",
      "claim_intent": "llava/model/multimodal_encoder/point_encoder.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E875",
        "E876",
        "E877",
        "E878",
        "E879",
        "E880",
        "E881",
        "E882",
        "E883",
        "E884",
        "E885",
        "E886",
        "E887",
        "E888",
        "E889",
        "E890",
        "E891",
        "E892",
        "E893",
        "E894",
        "E895",
        "E896",
        "E897",
        "E898",
        "E899",
        "E900",
        "E901",
        "E902",
        "E903",
        "E904",
        "E905",
        "E906",
        "E907",
        "E908",
        "E909",
        "E910",
        "E911",
        "E912",
        "E913",
        "E914",
        "E915",
        "E916",
        "E917",
        "E918",
        "E919",
        "E920",
        "E921",
        "E922",
        "E923",
        "E924",
        "E925",
        "E926",
        "E927",
        "E928",
        "E929",
        "E930",
        "E931",
        "E932",
        "E933",
        "E934",
        "E935",
        "E936",
        "E937",
        "E938",
        "E939",
        "E940",
        "E941",
        "E942",
        "E943",
        "E944",
        "E945",
        "E946",
        "E947",
        "E948",
        "E949",
        "E950",
        "E951",
        "E952",
        "E953",
        "E954",
        "E955",
        "E956",
        "E957",
        "E958",
        "E959",
        "E960",
        "E961",
        "E962",
        "E963"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C41",
      "claim_intent": "llava/model/multimodal_projector/builder.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E964",
        "E965",
        "E968",
        "E969",
        "E971",
        "E972",
        "E974"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C42",
      "claim_intent": "llava/model/multimodal_projector/builder.py implements model computation block.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E966",
        "E970",
        "E973"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C43",
      "claim_intent": "llava/model/multimodal_projector/builder.py implements configuration and runtime wiring.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E967"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C44",
      "claim_intent": "llava/model/multimodal_projector/builder.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E975",
        "E976",
        "E977",
        "E978",
        "E979",
        "E980",
        "E981",
        "E982",
        "E983",
        "E984",
        "E985",
        "E986",
        "E987",
        "E988",
        "E989",
        "E990",
        "E991",
        "E992",
        "E993",
        "E994",
        "E995"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C45",
      "claim_intent": "llava/model/utils.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017",
        "E1018",
        "E1020",
        "E1022",
        "E1023",
        "E1024",
        "E1026",
        "E1028",
        "E1029"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C46",
      "claim_intent": "llava/model/utils.py implements data preparation and loading.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E1030",
        "E1031",
        "E1032",
        "E1033",
        "E1034",
        "E1035"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C47",
      "claim_intent": "llava/model/utils.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E1048",
        "E1052",
        "E1053",
        "E1079",
        "E1080",
        "E1081",
        "E1082",
        "E1083",
        "E1084",
        "E1085",
        "E1086",
        "E1087",
        "E1088",
        "E1089",
        "E1090",
        "E1091",
        "E1092",
        "E1093",
        "E1094",
        "E1095",
        "E1096",
        "E1097",
        "E1098",
        "E1099",
        "E1100",
        "E1101",
        "E1102",
        "E1103",
        "E1104",
        "E1105",
        "E1106",
        "E1107",
        "E1108",
        "E1109",
        "E1110",
        "E1111",
        "E1112",
        "E1113",
        "E1114",
        "E1115",
        "E1116",
        "E1117",
        "E1118",
        "E1119"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C48",
      "claim_intent": "llava/serve/model_worker.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E1122",
        "E1123",
        "E1124",
        "E1125",
        "E1126",
        "E1127",
        "E1128",
        "E1129",
        "E1130",
        "E1131",
        "E1132",
        "E1133"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C49",
      "claim_intent": "llava/serve/model_worker.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E1134",
        "E1135",
        "E1137",
        "E1138",
        "E1140",
        "E1141",
        "E1142",
        "E1143",
        "E1144",
        "E1145",
        "E1146",
        "E1147",
        "E1148",
        "E1149",
        "E1150",
        "E1151",
        "E1152",
        "E1153",
        "E1154",
        "E1155",
        "E1156",
        "E1157",
        "E1158",
        "E1160",
        "E1161",
        "E1162",
        "E1163",
        "E1164",
        "E1165",
        "E1166",
        "E1167",
        "E1168",
        "E1169",
        "E1170",
        "E1171",
        "E1172",
        "E1173",
        "E1174",
        "E1175",
        "E1176",
        "E1177",
        "E1178",
        "E1179",
        "E1180",
        "E1181",
        "E1182",
        "E1183",
        "E1184",
        "E1185",
        "E1186",
        "E1187"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C50",
      "claim_intent": "llava/train/llama_flash_attn_monkey_patch.py implements model computation block.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E1197"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C51",
      "claim_intent": "llava/train/llama_flash_attn_monkey_patch.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E1199",
        "E1200",
        "E1201",
        "E1202",
        "E1203",
        "E1204",
        "E1205",
        "E1206",
        "E1207",
        "E1208",
        "E1209",
        "E1210"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C52",
      "claim_intent": "llava/train/llama_xformers_attn_monkey_patch.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E1225",
        "E1226",
        "E1227",
        "E1228",
        "E1229",
        "E1230",
        "E1231",
        "E1232",
        "E1233",
        "E1234",
        "E1235",
        "E1236"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C53",
      "claim_intent": "pointllm/data/modelnet.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E1639",
        "E1640",
        "E1642",
        "E1643",
        "E1644",
        "E1646"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C54",
      "claim_intent": "pointllm/data/modelnet.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E1647",
        "E1648",
        "E1649",
        "E1651",
        "E1652",
        "E1653",
        "E1655",
        "E1656",
        "E1657",
        "E1658",
        "E1659",
        "E1660",
        "E1661",
        "E1662",
        "E1663",
        "E1664",
        "E1665",
        "E1666",
        "E1667",
        "E1668",
        "E1669",
        "E1670",
        "E1671",
        "E1672",
        "E1673",
        "E1674",
        "E1675",
        "E1676",
        "E1677",
        "E1678",
        "E1679"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C55",
      "claim_intent": "pointllm/data/modelnet_show.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E1709",
        "E1710",
        "E1712",
        "E1713",
        "E1714",
        "E1715",
        "E1717"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C56",
      "claim_intent": "pointllm/data/modelnet_show.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E1718",
        "E1719",
        "E1720",
        "E1722",
        "E1723",
        "E1724",
        "E1726",
        "E1727",
        "E1728",
        "E1729",
        "E1730",
        "E1731",
        "E1732",
        "E1733",
        "E1734",
        "E1735",
        "E1736",
        "E1737",
        "E1738",
        "E1739",
        "E1740",
        "E1741",
        "E1742",
        "E1743",
        "E1744",
        "E1745",
        "E1746",
        "E1747",
        "E1748",
        "E1749",
        "E1750",
        "E1751",
        "E1752",
        "E1753",
        "E1754",
        "E1755",
        "E1756",
        "E1757",
        "E1758"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C57",
      "claim_intent": "pointllm/model/pointllm.py implements configuration and runtime wiring.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E1799"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C58",
      "claim_intent": "pointllm/model/pointllm.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E1800",
        "E1801",
        "E1804",
        "E1805",
        "E1806",
        "E1807",
        "E1809"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C59",
      "claim_intent": "pointllm/model/pointllm.py implements model computation block.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E1803",
        "E1808"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C60",
      "claim_intent": "pointllm/model/pointllm.py implements data preparation and loading.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E1810",
        "E1811"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C61",
      "claim_intent": "pointllm/model/pointllm.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E1812",
        "E1813",
        "E1814",
        "E1815",
        "E1816",
        "E1817",
        "E1818",
        "E1819",
        "E1820",
        "E1821",
        "E1822",
        "E1823",
        "E1824",
        "E1825",
        "E1826",
        "E1827",
        "E1828",
        "E1829",
        "E1830",
        "E1831",
        "E1832",
        "E1833",
        "E1834",
        "E1835",
        "E1836",
        "E1837",
        "E1838",
        "E1839",
        "E1840",
        "E1841",
        "E1842",
        "E1843",
        "E1844",
        "E1845",
        "E1846",
        "E1847",
        "E1848",
        "E1849",
        "E1850",
        "E1851",
        "E1852",
        "E1853",
        "E1854",
        "E1855",
        "E1856",
        "E1857",
        "E1858",
        "E1859",
        "E1860",
        "E1861",
        "E1862",
        "E1863",
        "E1864",
        "E1865",
        "E1866",
        "E1867",
        "E1868"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C62",
      "claim_intent": "pointllm/model/utils.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E1869",
        "E1870",
        "E1871"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C63",
      "claim_intent": "pointllm/model/utils.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E1872",
        "E1873",
        "E1874",
        "E1875"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C64",
      "claim_intent": "pointllm/train/llama_flash_attn_monkey_patch.py implements model computation block.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E1893"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C65",
      "claim_intent": "pointllm/train/llama_flash_attn_monkey_patch.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E1895",
        "E1896",
        "E1897",
        "E1898",
        "E1899",
        "E1900",
        "E1901",
        "E1902",
        "E1903",
        "E1904",
        "E1905",
        "E1906"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C66",
      "claim_intent": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_msg_cls.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2070",
        "E2071"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C67",
      "claim_intent": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_msg_cls.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2072",
        "E2073",
        "E2074",
        "E2075",
        "E2076",
        "E2077"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C68",
      "claim_intent": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_msg_sem.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2078",
        "E2079"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C69",
      "claim_intent": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_msg_sem.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2080",
        "E2081",
        "E2082",
        "E2083",
        "E2084",
        "E2085",
        "E2086",
        "E2087",
        "E2088"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C70",
      "claim_intent": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2089",
        "E2095",
        "E2096",
        "E2097",
        "E2098",
        "E2102",
        "E2103",
        "E2105"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C71",
      "claim_intent": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py implements optimization and objective logic.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2090",
        "E2091",
        "E2092",
        "E2093",
        "E2104"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C72",
      "claim_intent": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py implements model computation block.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2099"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C73",
      "claim_intent": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2109",
        "E2110",
        "E2111",
        "E2112",
        "E2113",
        "E2114",
        "E2115",
        "E2116",
        "E2117",
        "E2118",
        "E2120",
        "E2121",
        "E2122",
        "E2123",
        "E2124",
        "E2125",
        "E2126",
        "E2127",
        "E2128",
        "E2129",
        "E2130",
        "E2131",
        "E2132",
        "E2133",
        "E2134",
        "E2135",
        "E2136",
        "E2137",
        "E2142",
        "E2145",
        "E2146",
        "E2147",
        "E2148",
        "E2149",
        "E2150",
        "E2151",
        "E2152",
        "E2153",
        "E2154",
        "E2155",
        "E2156",
        "E2157",
        "E2158",
        "E2159",
        "E2160",
        "E2161",
        "E2162",
        "E2163",
        "E2164",
        "E2165",
        "E2166",
        "E2167",
        "E2168",
        "E2169",
        "E2170",
        "E2171"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C74",
      "claim_intent": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_sem.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2175",
        "E2176",
        "E2179"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C75",
      "claim_intent": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_sem.py implements model computation block.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2177"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C76",
      "claim_intent": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_sem.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2180",
        "E2181",
        "E2182",
        "E2183",
        "E2184",
        "E2185",
        "E2186",
        "E2187",
        "E2188",
        "E2189",
        "E2190",
        "E2191",
        "E2192",
        "E2193",
        "E2194"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C77",
      "claim_intent": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/configuration_phi3.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2278",
        "E2279",
        "E2280",
        "E2281",
        "E2282",
        "E2283",
        "E2284",
        "E2285"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C78",
      "claim_intent": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/sample_finetune.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2301"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C79",
      "claim_intent": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/sample_finetune.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2302",
        "E2303"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C80",
      "claim_intent": "llava/conversation.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2320",
        "E2321",
        "E2322",
        "E2323",
        "E2324",
        "E2325",
        "E2326",
        "E2327",
        "E2328",
        "E2329",
        "E2330",
        "E2331",
        "E2332",
        "E2333",
        "E2334",
        "E2335",
        "E2336",
        "E2337",
        "E2338",
        "E2339",
        "E2340",
        "E2341",
        "E2342",
        "E2343",
        "E2344",
        "E2345",
        "E2346",
        "E2347",
        "E2348",
        "E2349",
        "E2350",
        "E2351",
        "E2352",
        "E2353",
        "E2354",
        "E2355",
        "E2356",
        "E2357"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C81",
      "claim_intent": "llava/mm_utils.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2427",
        "E2428",
        "E2429",
        "E2430",
        "E2431",
        "E2432",
        "E2433",
        "E2434",
        "E2435",
        "E2436",
        "E2437",
        "E2438",
        "E2439"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C82",
      "claim_intent": "llava/serve/controller.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2446",
        "E2447",
        "E2448",
        "E2449",
        "E2450",
        "E2451",
        "E2452",
        "E2453",
        "E2454",
        "E2455",
        "E2456",
        "E2457",
        "E2458",
        "E2460",
        "E2461",
        "E2462",
        "E2463",
        "E2464",
        "E2465",
        "E2466",
        "E2467",
        "E2468"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C83",
      "claim_intent": "llava/serve/controller.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2469",
        "E2471",
        "E2473",
        "E2474",
        "E2475",
        "E2476",
        "E2477",
        "E2478",
        "E2479",
        "E2480",
        "E2481",
        "E2482",
        "E2483",
        "E2484",
        "E2485",
        "E2486",
        "E2487",
        "E2488",
        "E2489",
        "E2490",
        "E2491",
        "E2492",
        "E2493",
        "E2494",
        "E2495",
        "E2496",
        "E2497",
        "E2498",
        "E2499",
        "E2500",
        "E2501",
        "E2502",
        "E2503",
        "E2504",
        "E2505",
        "E2506",
        "E2507",
        "E2508",
        "E2509",
        "E2510",
        "E2511",
        "E2512",
        "E2513",
        "E2514",
        "E2515",
        "E2516",
        "E2517",
        "E2518",
        "E2519",
        "E2520",
        "E2521",
        "E2522",
        "E2523",
        "E2524",
        "E2525",
        "E2526",
        "E2527",
        "E2528",
        "E2529",
        "E2530",
        "E2531",
        "E2532",
        "E2533",
        "E2534",
        "E2535",
        "E2536",
        "E2537",
        "E2538"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C84",
      "claim_intent": "llava/serve/gradio_web_server.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2552"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C85",
      "claim_intent": "llava/serve/sglang_worker.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2637",
        "E2639",
        "E2640",
        "E2641",
        "E2642",
        "E2643",
        "E2644",
        "E2645",
        "E2646",
        "E2647",
        "E2648",
        "E2649"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C86",
      "claim_intent": "llava/serve/sglang_worker.py implements entrypoint orchestration.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2638"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C87",
      "claim_intent": "llava/serve/sglang_worker.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2650",
        "E2651",
        "E2652",
        "E2653",
        "E2654",
        "E2655",
        "E2657",
        "E2658",
        "E2659",
        "E2660",
        "E2661",
        "E2662",
        "E2663",
        "E2664",
        "E2665",
        "E2666",
        "E2667",
        "E2668",
        "E2669",
        "E2670",
        "E2671",
        "E2672",
        "E2673",
        "E2674",
        "E2675",
        "E2676",
        "E2677",
        "E2678",
        "E2679",
        "E2680",
        "E2681",
        "E2682",
        "E2683",
        "E2684",
        "E2685",
        "E2687",
        "E2688",
        "E2689",
        "E2690",
        "E2691",
        "E2692",
        "E2693",
        "E2694",
        "E2695",
        "E2696",
        "E2697",
        "E2698",
        "E2699",
        "E2700",
        "E2701",
        "E2702",
        "E2703",
        "E2704",
        "E2705",
        "E2706"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C88",
      "claim_intent": "llava/utils.py implements data preparation and loading.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2739",
        "E2740"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C89",
      "claim_intent": "llava/utils.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2754",
        "E2758",
        "E2759",
        "E2785",
        "E2786",
        "E2787",
        "E2788",
        "E2789",
        "E2790",
        "E2791",
        "E2792",
        "E2793",
        "E2794",
        "E2795",
        "E2796",
        "E2797",
        "E2798",
        "E2799",
        "E2800",
        "E2801",
        "E2802",
        "E2803",
        "E2804",
        "E2805",
        "E2806",
        "E2807",
        "E2808",
        "E2809",
        "E2810",
        "E2811",
        "E2812",
        "E2813",
        "E2814",
        "E2815",
        "E2816",
        "E2817",
        "E2818",
        "E2819",
        "E2820",
        "E2821",
        "E2822",
        "E2823",
        "E2824",
        "E2825"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C90",
      "claim_intent": "pointllm/conversation.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2842",
        "E2843",
        "E2844",
        "E2845",
        "E2846",
        "E2847",
        "E2848",
        "E2849",
        "E2850",
        "E2851",
        "E2852",
        "E2853",
        "E2854",
        "E2855",
        "E2856",
        "E2857",
        "E2858",
        "E2859",
        "E2860",
        "E2861",
        "E2862",
        "E2863",
        "E2864",
        "E2865",
        "E2866",
        "E2867",
        "E2868",
        "E2869",
        "E2871",
        "E2872",
        "E2873",
        "E2874"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C91",
      "claim_intent": "pointllm/data/utils.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E2994",
        "E2995",
        "E2996",
        "E2997",
        "E2998",
        "E2999",
        "E3000",
        "E3001",
        "E3002"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C92",
      "claim_intent": "pointllm/data/utils_backup.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E3086",
        "E3087",
        "E3088",
        "E3089",
        "E3090",
        "E3091",
        "E3092",
        "E3093",
        "E3094"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C93",
      "claim_intent": "pointllm/utils.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E3180",
        "E3184",
        "E3185"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C94",
      "claim_intent": "pointnet++/Pointnet2_PyTorch/pointnet2/data/data_utils.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E3232",
        "E3233",
        "E3234",
        "E3235",
        "E3236",
        "E3237",
        "E3238",
        "E3239",
        "E3240",
        "E3241",
        "E3242",
        "E3243",
        "E3244",
        "E3245",
        "E3246",
        "E3247",
        "E3248",
        "E3249",
        "E3250",
        "E3251",
        "E3252",
        "E3253",
        "E3254",
        "E3255",
        "E3256",
        "E3257",
        "E3258",
        "E3259"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C95",
      "claim_intent": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_modules.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E3295",
        "E3296",
        "E3297",
        "E3300",
        "E3302",
        "E3303",
        "E3305",
        "E3306",
        "E3308"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C96",
      "claim_intent": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_modules.py implements model computation block.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E3298",
        "E3309"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C97",
      "claim_intent": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_modules.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E3311",
        "E3312",
        "E3313",
        "E3314",
        "E3315",
        "E3316",
        "E3317",
        "E3318",
        "E3319",
        "E3320",
        "E3321",
        "E3322",
        "E3323",
        "E3324",
        "E3325",
        "E3326",
        "E3327",
        "E3328",
        "E3329",
        "E3330",
        "E3331",
        "E3332",
        "E3333",
        "E3334",
        "E3335",
        "E3336",
        "E3337",
        "E3338",
        "E3339",
        "E3340",
        "E3341",
        "E3342",
        "E3343",
        "E3344",
        "E3345",
        "E3346",
        "E3347",
        "E3348",
        "E3349",
        "E3350",
        "E3351",
        "E3352",
        "E3353"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C98",
      "claim_intent": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_utils.py implements model computation block.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E3359",
        "E3363",
        "E3367",
        "E3371",
        "E3376",
        "E3381",
        "E3387",
        "E3392"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C99",
      "claim_intent": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_utils.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E3394",
        "E3395",
        "E3396",
        "E3398",
        "E3399",
        "E3400",
        "E3401",
        "E3402",
        "E3403",
        "E3405",
        "E3406",
        "E3407",
        "E3408",
        "E3409",
        "E3410",
        "E3412",
        "E3413",
        "E3414",
        "E3415",
        "E3416",
        "E3417",
        "E3418",
        "E3419",
        "E3420",
        "E3421",
        "E3422",
        "E3423",
        "E3424",
        "E3425",
        "E3426",
        "E3427",
        "E3428",
        "E3429",
        "E3430"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C100",
      "claim_intent": "scripts/convert_sqa_to_llava.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E3459",
        "E3460"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C101",
      "claim_intent": "scripts/convert_sqa_to_llava.py implements entrypoint orchestration.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E3461"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C102",
      "claim_intent": "scripts/convert_sqa_to_llava.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E3462",
        "E3463",
        "E3464",
        "E3465",
        "E3466",
        "E3467",
        "E3469",
        "E3470",
        "E3471",
        "E3472",
        "E3473",
        "E3474",
        "E3475",
        "E3476",
        "E3477",
        "E3479",
        "E3480",
        "E3481",
        "E3483"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C103",
      "claim_intent": "scripts/convert_sqa_to_llava_base_prompt.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E3502",
        "E3503",
        "E3504",
        "E3505",
        "E3507",
        "E3508",
        "E3509",
        "E3510",
        "E3511",
        "E3512"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C104",
      "claim_intent": "scripts/convert_sqa_to_llava_base_prompt.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E3513",
        "E3514",
        "E3515",
        "E3516",
        "E3517",
        "E3518",
        "E3519",
        "E3521",
        "E3522",
        "E3523",
        "E3524",
        "E3525",
        "E3526",
        "E3527",
        "E3528",
        "E3529",
        "E3530",
        "E3531",
        "E3532",
        "E3533",
        "E3534",
        "E3535",
        "E3536",
        "E3537",
        "E3538",
        "E3541",
        "E3542",
        "E3543",
        "E3544",
        "E3545",
        "E3546",
        "E3547",
        "E3550",
        "E3551",
        "E3552",
        "E3553",
        "E3554",
        "E3555",
        "E3556"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C105",
      "claim_intent": "scripts/extract_mm_projector.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E3569"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C106",
      "claim_intent": "scripts/extract_mm_projector.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E3570",
        "E3571",
        "E3572"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C107",
      "claim_intent": "scripts/merge_lora_weights.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E3588"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C108",
      "claim_intent": "pretrained_weight/eval_model_weight/all-mpnet-base-v2/train_script.py implements model computation block.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E3696"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C109",
      "claim_intent": "pretrained_weight/eval_model_weight/all-mpnet-base-v2/train_script.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E3712",
        "E3713",
        "E3714",
        "E3728",
        "E3733"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C110",
      "claim_intent": "llava/serve/test_message.py implements entrypoint orchestration.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E3762"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C111",
      "claim_intent": "llava/serve/test_message.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E3763",
        "E3764",
        "E3765",
        "E3766",
        "E3767",
        "E3768",
        "E3770",
        "E3771",
        "E3772",
        "E3773",
        "E3774"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C112",
      "claim_intent": "Module docstring hint: PyTorch Phi-3 model.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-112"
    },
    {
      "claim_id": "C113",
      "claim_intent": "Python inline comment hint: x: [bs, num_attention_heads, seq_len, head_size]",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-113"
    },
    {
      "claim_id": "C114",
      "claim_intent": "Python inline comment hint: upcast attention to fp32",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-114"
    },
    {
      "claim_id": "C115",
      "claim_intent": "Python inline comment hint: Copied from transformers.models.llama.modeling_llama.LlamaFlashAttention2.__init__",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-115"
    },
    {
      "claim_id": "C116",
      "claim_intent": "Python inline comment hint: flash_attn<2.1 generates top-left aligned causal mask, while what is needed here is bottom-right alignement, that was made default for flash_attn>=2.1. This attribute is used to handle this difference. Reference: https://github.com/Dao-AILab/flash-attention/releases/tag/v2.1.0.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-116"
    },
    {
      "claim_id": "C117",
      "claim_intent": "Python inline comment hint: Phi3FlashAttention2 attention does not support output_attentions",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-117"
    },
    {
      "claim_id": "C118",
      "claim_intent": "Python inline comment hint: overwrite attention_mask with padding_mask",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-118"
    },
    {
      "claim_id": "C119",
      "claim_intent": "Python inline comment hint: Flash attention requires the input to have the shape",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-119"
    },
    {
      "claim_id": "C120",
      "claim_intent": "Python inline comment hint: Reashape to the expected shape for Flash Attention",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-120"
    },
    {
      "claim_id": "C121",
      "claim_intent": "Python inline comment hint: Copied from transformers.models.mistral.modeling_mistral.MistralFlashAttention2._flash_attention_forward",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-121"
    },
    {
      "claim_id": "C122",
      "claim_intent": "Python inline comment hint: Copied from transformers.models.mistral.modeling_mistral.MistralFlashAttention2._upad_input",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-122"
    },
    {
      "claim_id": "C123",
      "claim_intent": "Docstring hint for Phi3RMSNorm.__init__: Phi3RMSNorm is equivalent to T5LayerNorm",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-123"
    },
    {
      "claim_id": "C124",
      "claim_intent": "Docstring hint for rotate_half: Rotates half the hidden dims of the input.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-124"
    },
    {
      "claim_id": "C125",
      "claim_intent": "Docstring hint for repeat_kv: This is the equivalent of torch.repeat_interleave(x, dim=1, repeats=n_rep). The hidden states go from (batch, num_key_value_heads, seqlen, head_dim) to (batch, num_attention_heads, seqlen, head_dim)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-125"
    },
    {
      "claim_id": "C126",
      "claim_intent": "Docstring hint for Phi3Attention: Multi-headed attention from 'Attention Is All You Need' paper",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-126"
    },
    {
      "claim_id": "C127",
      "claim_intent": "Docstring hint for Phi3FlashAttention2: Phi-3 flash attention module. This module inherits from `Phi3Attention` as the weights of the module stays untouched. The only required change would be on the forward pass where it needs to correctly call the public API of flash attention and deal with padding tokens in case the input contains any of them.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-127"
    },
    {
      "claim_id": "C128",
      "claim_intent": "Docstring hint for Phi3FlashAttention2._flash_attention_forward: Calls the forward method of Flash Attention - if the input hidden states contain at least one padding token first unpad the input, then computes the attention scores and pad the final attention scores. Args: query_states (`torch.Tensor`): Input query states to be passed to Flash Attention API key_states (`torch.Tensor`): Input key states to be passed to Flash Attention API value_states (`torch.Tensor`): Input value states to be passed to Flash Attention API attention_mask (`torch.Tensor`): The padding mask - corresponds to a tensor of size `(batch_size, seq_len)` where 0 stands for the position of padding tokens and 1 for the position of non-padding tokens. dropout (`float`): Attention dropout softmax_scale (`float`, *optional*): The scaling of QK^T before applying softmax. Default to 1 / sqrt(head_dim) use_sliding_windows (`bool`, *optional*): Whether to activate sliding window attention.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-128"
    },
    {
      "claim_id": "C129",
      "claim_intent": "Docstring hint for Phi3SdpaAttention: Phi3 attention module using torch.nn.functional.scaled_dot_product_attention. This module inherits from `Phi3Attention` as the weights of the module stays untouched. The only changes are on the forward pass to adapt to SDPA API.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-129"
    },
    {
      "claim_id": "C130",
      "claim_intent": "Docstring hint for Phi3Model: Transformer decoder consisting of *config.num_hidden_layers* layers. Each layer is a [`Phi3DecoderLayer`] Args: config: Phi3Config",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-130"
    },
    {
      "claim_id": "C131",
      "claim_intent": "Docstring hint for Phi3ForCausalLM.forward: Args: labels (`torch.LongTensor` of shape `(batch_size, sequence_length)`, *optional*): Labels for computing the masked language modeling loss. Indices should either be in `[0, ..., config.vocab_size]` or -100 (see `input_ids` docstring). Tokens with indices set to `-100` are ignored (masked), the loss is only computed for the tokens with labels in `[0, ..., config.vocab_size]`. Returns: Example: ```python >>> from transformers import AutoTokenizer, Phi3ForCausalLM >>> model = Phi3ForCausalLM.from_pretrained(\"microsoft/phi-3-mini-4k-instruct\") >>> tokenizer = AutoTokenizer.from_pretrained(\"microsoft/phi-3-mini-4k-instruct\") >>> prompt = \"This is an example script .\" >>> inputs = tokenizer(prompt, return_tensors=\"pt\") >>> # Generate >>> generate_ids = model.generate(inputs.input_ids, max_length=30) >>> tokenizer.batch_decode(generate_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0] 'This is an example script .\\n Certainly! Below is a sample script that demonstrates a simple task, such as calculating the sum' ```",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-131"
    },
    {
      "claim_id": "C132",
      "claim_intent": "Docstring hint for Phi3ForSequenceClassification.forward: labels (`torch.LongTensor` of shape `(batch_size,)`, *optional*): Labels for computing the sequence classification/regression loss. Indices should be in `[0, ..., config.num_labels - 1]`. If `config.num_labels == 1` a regression loss is computed (Mean-Square loss), If `config.num_labels > 1` a classification loss is computed (Cross-Entropy).",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-132"
    },
    {
      "claim_id": "C133",
      "claim_intent": "Docstring hint for Phi3ForTokenClassification.forward: labels (`torch.LongTensor` of shape `(batch_size,)`, *optional*): Labels for computing the sequence classification/regression loss. Indices should be in `[0, ..., config.num_labels - 1]`. If `config.num_labels == 1` a regression loss is computed (Mean-Square loss), If `config.num_labels > 1` a classification loss is computed (Cross-Entropy).",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-133"
    },
    {
      "claim_id": "C134",
      "claim_intent": "Python inline comment hint: try:",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-134"
    },
    {
      "claim_id": "C135",
      "claim_intent": "Python inline comment hint: from .language_model.llava_llama import LlavaLlamaForCausalLM, LlavaConfig",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-135"
    },
    {
      "claim_id": "C136",
      "claim_intent": "Python inline comment hint: from .language_model.llava_mpt import LlavaMptForCausalLM, LlavaMptConfig",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-136"
    },
    {
      "claim_id": "C137",
      "claim_intent": "Python inline comment hint: from .language_model.llava_mistral import LlavaMistralForCausalLM, LlavaMistralConfig",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-137"
    },
    {
      "claim_id": "C138",
      "claim_intent": "Python inline comment hint: from .language_model.llava_phi3 import LlavaPhiForCausalLM, LlavaPhiConfig",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-138"
    },
    {
      "claim_id": "C139",
      "claim_intent": "Python inline comment hint: except:",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-139"
    },
    {
      "claim_id": "C140",
      "claim_intent": "Python inline comment hint: pass",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-140"
    },
    {
      "claim_id": "C141",
      "claim_intent": "Module docstring hint: Usage: python3 -m fastchat.model.apply_delta --base ~/model_weights/llama-7b --target ~/model_weights/vicuna-7b --delta lmsys/vicuna-7b-delta",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-141"
    },
    {
      "claim_id": "C142",
      "claim_intent": "Python inline comment hint: Modified from LLaVA: https://github.com/haotian-liu/LLaVA.git",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-142"
    },
    {
      "claim_id": "C143",
      "claim_intent": "Python inline comment hint: Copyright 2023 Haotian Liu",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-143"
    },
    {
      "claim_id": "C144",
      "claim_intent": "Python inline comment hint: Licensed under the Apache License, Version 2.0 (the \"License\");",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-144"
    },
    {
      "claim_id": "C145",
      "claim_intent": "Python inline comment hint: you may not use this file except in compliance with the License.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-145"
    },
    {
      "claim_id": "C146",
      "claim_intent": "Python inline comment hint: You may obtain a copy of the License at",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-146"
    },
    {
      "claim_id": "C147",
      "claim_intent": "Python inline comment hint: http://www.apache.org/licenses/LICENSE-2.0",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-147"
    },
    {
      "claim_id": "C148",
      "claim_intent": "Python inline comment hint: Unless required by applicable law or agreed to in writing, software",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-148"
    },
    {
      "claim_id": "C149",
      "claim_intent": "Python inline comment hint: distributed under the License is distributed on an \"AS IS\" BASIS,",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-149"
    },
    {
      "claim_id": "C150",
      "claim_intent": "Python inline comment hint: WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-150"
    },
    {
      "claim_id": "C151",
      "claim_intent": "Python inline comment hint: See the License for the specific language governing permissions and",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-151"
    },
    {
      "claim_id": "C152",
      "claim_intent": "Python inline comment hint: limitations under the License.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-152"
    },
    {
      "claim_id": "C153",
      "claim_intent": "Python inline comment hint: Load LLaVA model",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-153"
    },
    {
      "claim_id": "C154",
      "claim_intent": "Module docstring hint: Usage: python3 -m llava.model.consolidate --src ~/model_weights/llava-7b --dst ~/model_weights/llava-7b_consolidate",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-154"
    },
    {
      "claim_id": "C155",
      "claim_intent": "Python inline comment hint: Copyright 2023 Haotian Liu",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-155"
    },
    {
      "claim_id": "C156",
      "claim_intent": "Python inline comment hint: Licensed under the Apache License, Version 2.0 (the \"License\");",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-156"
    },
    {
      "claim_id": "C157",
      "claim_intent": "Python inline comment hint: you may not use this file except in compliance with the License.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-157"
    },
    {
      "claim_id": "C158",
      "claim_intent": "Python inline comment hint: You may obtain a copy of the License at",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-158"
    },
    {
      "claim_id": "C159",
      "claim_intent": "Python inline comment hint: http://www.apache.org/licenses/LICENSE-2.0",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-159"
    },
    {
      "claim_id": "C160",
      "claim_intent": "Python inline comment hint: Unless required by applicable law or agreed to in writing, software",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-160"
    },
    {
      "claim_id": "C161",
      "claim_intent": "Python inline comment hint: distributed under the License is distributed on an \"AS IS\" BASIS,",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-161"
    },
    {
      "claim_id": "C162",
      "claim_intent": "Python inline comment hint: WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-162"
    },
    {
      "claim_id": "C163",
      "claim_intent": "Python inline comment hint: See the License for the specific language governing permissions and",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-163"
    },
    {
      "claim_id": "C164",
      "claim_intent": "Python inline comment hint: limitations under the License.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-164"
    },
    {
      "claim_id": "C165",
      "claim_intent": "Python inline comment hint: Initialize weights and apply final processing",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-165"
    },
    {
      "claim_id": "C166",
      "claim_intent": "Python inline comment hint: Copyright 2023 Haotian Liu",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-166"
    },
    {
      "claim_id": "C167",
      "claim_intent": "Python inline comment hint: Licensed under the Apache License, Version 2.0 (the \"License\");",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-167"
    },
    {
      "claim_id": "C168",
      "claim_intent": "Python inline comment hint: you may not use this file except in compliance with the License.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-168"
    },
    {
      "claim_id": "C169",
      "claim_intent": "Python inline comment hint: You may obtain a copy of the License at",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-169"
    },
    {
      "claim_id": "C170",
      "claim_intent": "Python inline comment hint: http://www.apache.org/licenses/LICENSE-2.0",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-170"
    },
    {
      "claim_id": "C171",
      "claim_intent": "Python inline comment hint: Unless required by applicable law or agreed to in writing, software",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-171"
    },
    {
      "claim_id": "C172",
      "claim_intent": "Python inline comment hint: distributed under the License is distributed on an \"AS IS\" BASIS,",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-172"
    },
    {
      "claim_id": "C173",
      "claim_intent": "Python inline comment hint: WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-173"
    },
    {
      "claim_id": "C174",
      "claim_intent": "Python inline comment hint: See the License for the specific language governing permissions and",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-174"
    },
    {
      "claim_id": "C175",
      "claim_intent": "Python inline comment hint: limitations under the License.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-175"
    },
    {
      "claim_id": "C176",
      "claim_intent": "Python inline comment hint: Initialize weights and apply final processing",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-176"
    },
    {
      "claim_id": "C177",
      "claim_intent": "Python inline comment hint: Copyright 2023 Haotian Liu",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-177"
    },
    {
      "claim_id": "C178",
      "claim_intent": "Python inline comment hint: Licensed under the Apache License, Version 2.0 (the \"License\");",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-178"
    },
    {
      "claim_id": "C179",
      "claim_intent": "Python inline comment hint: you may not use this file except in compliance with the License.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-179"
    },
    {
      "claim_id": "C180",
      "claim_intent": "Python inline comment hint: You may obtain a copy of the License at",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-180"
    },
    {
      "claim_id": "C181",
      "claim_intent": "Python inline comment hint: http://www.apache.org/licenses/LICENSE-2.0",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-181"
    },
    {
      "claim_id": "C182",
      "claim_intent": "Python inline comment hint: Unless required by applicable law or agreed to in writing, software",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-182"
    },
    {
      "claim_id": "C183",
      "claim_intent": "Python inline comment hint: distributed under the License is distributed on an \"AS IS\" BASIS,",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-183"
    },
    {
      "claim_id": "C184",
      "claim_intent": "Python inline comment hint: WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-184"
    },
    {
      "claim_id": "C185",
      "claim_intent": "Python inline comment hint: See the License for the specific language governing permissions and",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-185"
    },
    {
      "claim_id": "C186",
      "claim_intent": "Python inline comment hint: limitations under the License.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-186"
    },
    {
      "claim_id": "C187",
      "claim_intent": "Python inline comment hint: Initialize weights and apply final processing",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-187"
    },
    {
      "claim_id": "C188",
      "claim_intent": "Python inline comment hint: Modified from LLaVA: https://github.com/haotian-liu/LLaVA.git",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-188"
    },
    {
      "claim_id": "C189",
      "claim_intent": "Python inline comment hint: Copyright 2023 Haotian Liu",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-189"
    },
    {
      "claim_id": "C190",
      "claim_intent": "Python inline comment hint: Licensed under the Apache License, Version 2.0 (the \"License\");",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-190"
    },
    {
      "claim_id": "C191",
      "claim_intent": "Python inline comment hint: you may not use this file except in compliance with the License.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-191"
    },
    {
      "claim_id": "C192",
      "claim_intent": "Python inline comment hint: You may obtain a copy of the License at",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-192"
    },
    {
      "claim_id": "C193",
      "claim_intent": "Python inline comment hint: http://www.apache.org/licenses/LICENSE-2.0",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-193"
    },
    {
      "claim_id": "C194",
      "claim_intent": "Python inline comment hint: Unless required by applicable law or agreed to in writing, software",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-194"
    },
    {
      "claim_id": "C195",
      "claim_intent": "Python inline comment hint: distributed under the License is distributed on an \"AS IS\" BASIS,",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-195"
    },
    {
      "claim_id": "C196",
      "claim_intent": "Python inline comment hint: WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-196"
    },
    {
      "claim_id": "C197",
      "claim_intent": "Python inline comment hint: See the License for the specific language governing permissions and",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-197"
    },
    {
      "claim_id": "C198",
      "claim_intent": "Python inline comment hint: limitations under the License.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-198"
    },
    {
      "claim_id": "C199",
      "claim_intent": "Python inline comment hint: Initialize weights and apply final processing",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-199"
    },
    {
      "claim_id": "C200",
      "claim_intent": "Python inline comment hint: Copyright 2023 Haotian Liu",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-200"
    },
    {
      "claim_id": "C201",
      "claim_intent": "Python inline comment hint: Licensed under the Apache License, Version 2.0 (the \"License\");",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-201"
    },
    {
      "claim_id": "C202",
      "claim_intent": "Python inline comment hint: you may not use this file except in compliance with the License.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-202"
    },
    {
      "claim_id": "C203",
      "claim_intent": "Python inline comment hint: You may obtain a copy of the License at",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-203"
    },
    {
      "claim_id": "C204",
      "claim_intent": "Python inline comment hint: http://www.apache.org/licenses/LICENSE-2.0",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-204"
    },
    {
      "claim_id": "C205",
      "claim_intent": "Python inline comment hint: Unless required by applicable law or agreed to in writing, software",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-205"
    },
    {
      "claim_id": "C206",
      "claim_intent": "Python inline comment hint: distributed under the License is distributed on an \"AS IS\" BASIS,",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-206"
    },
    {
      "claim_id": "C207",
      "claim_intent": "Python inline comment hint: WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-207"
    },
    {
      "claim_id": "C208",
      "claim_intent": "Python inline comment hint: See the License for the specific language governing permissions and",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-208"
    },
    {
      "claim_id": "C209",
      "claim_intent": "Python inline comment hint: limitations under the License.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-209"
    },
    {
      "claim_id": "C210",
      "claim_intent": "Python inline comment hint: 从这初始化的encoder 和 projector",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-210"
    },
    {
      "claim_id": "C211",
      "claim_intent": "Docstring hint for LlavaMetaModel.random_initialize_model: 随机初始化给定模型的所有参数。 参数: - model (nn.Module): 要初始化的PyTorch模型实例。 - mean (float): 权重初始化的均值，默认为0.0。 - std (float): 权重初始化的标准差，默认为0.02。",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-211"
    },
    {
      "claim_id": "C212",
      "claim_intent": "Docstring hint for unpad_image: Unpads a PyTorch tensor of a padded and resized image. Args: tensor (torch.Tensor): The image tensor, assumed to be in CxHxW format. original_size (tuple): The original size of PIL image (width, height). Returns: torch.Tensor: The unpadded image tensor.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-212"
    },
    {
      "claim_id": "C213",
      "claim_intent": "Module docstring hint: Usage: python3 -m llava.model.make_delta --base ~/model_weights/llama-7b --target ~/model_weights/llava-7b --delta ~/model_weights/llava-7b-delta --hub-repo-id liuhaotian/llava-7b-delta",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-213"
    },
    {
      "claim_id": "C214",
      "claim_intent": "Python inline comment hint: create transformer blocks for point cloud via timm",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-214"
    },
    {
      "claim_id": "C215",
      "claim_intent": "Python inline comment hint: create whole point cloud encoder",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-215"
    },
    {
      "claim_id": "C216",
      "claim_intent": "Python inline comment hint: change resize/crop size in preprocessing to the largest image size in s2_scale",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-216"
    },
    {
      "claim_id": "C217",
      "claim_intent": "Python inline comment hint: https://github.com/Strawberry-Eat-Mango/PCT_Pytorch/blob/main/util.py",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-217"
    },
    {
      "claim_id": "C218",
      "claim_intent": "Python inline comment hint: exclude CLS token",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-218"
    },
    {
      "claim_id": "C219",
      "claim_intent": "Python inline comment hint: if not self.training or self.prob == 0.:",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-219"
    },
    {
      "claim_id": "C220",
      "claim_intent": "Python inline comment hint: return x",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-220"
    },
    {
      "claim_id": "C221",
      "claim_intent": "Python inline comment hint: fps the centers out",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-221"
    },
    {
      "claim_id": "C222",
      "claim_intent": "Python inline comment hint: B G 3",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-222"
    },
    {
      "claim_id": "C223",
      "claim_intent": "Python inline comment hint: knn to get the neighborhood",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-223"
    },
    {
      "claim_id": "C224",
      "claim_intent": "Python inline comment hint: _, idx = self.knn(xyz, center) # B G M",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-224"
    },
    {
      "claim_id": "C225",
      "claim_intent": "Python inline comment hint: B G M",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-225"
    },
    {
      "claim_id": "C226",
      "claim_intent": "Python inline comment hint: normalize",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-226"
    },
    {
      "claim_id": "C227",
      "claim_intent": "Python inline comment hint: encoder",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-227"
    },
    {
      "claim_id": "C228",
      "claim_intent": "Python inline comment hint: ModuleList not support forward",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-228"
    },
    {
      "claim_id": "C229",
      "claim_intent": "Docstring hint for fps: data B N 3 number int",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-229"
    },
    {
      "claim_id": "C230",
      "claim_intent": "Docstring hint for index_points: Input: points: input points data, [B, N, C] idx: sample index data, [B, S] Return: new_points:, indexed points data, [B, S, C]",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-230"
    },
    {
      "claim_id": "C231",
      "claim_intent": "Docstring hint for knn_point: Input: nsample: max sample number in local region xyz: all points, [B, N, C] new_xyz: query points, [B, S, C] Return: group_idx: grouped points index, [B, S, nsample]",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-231"
    },
    {
      "claim_id": "C232",
      "claim_intent": "Docstring hint for square_distance: Calculate Euclid distance between each two points. src^T * dst = xn * xm + yn * ym + zn * zm; sum(src^2, dim=-1) = xn*xn + yn*yn + zn*zn; sum(dst^2, dim=-1) = xm*xm + ym*ym + zm*zm; dist = (xn - xm)^2 + (yn - ym)^2 + (zn - zm)^2 = sum(src**2,dim=-1)+sum(dst**2,dim=-1)-2*src^T*dst Input: src: source points, [B, N, C] dst: target points, [B, M, C] Output: dist: per-point square distance, [B, N, M]",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-232"
    },
    {
      "claim_id": "C233",
      "claim_intent": "Docstring hint for PatchDropout: https://arxiv.org/abs/2212.00794",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-233"
    },
    {
      "claim_id": "C234",
      "claim_intent": "Docstring hint for Group.forward: input: B N 3 --------------------------- output: B G M 3 center : B G 3",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-234"
    },
    {
      "claim_id": "C235",
      "claim_intent": "Docstring hint for Encoder.forward: point_groups : B G N 3 ----------------- feature_global : B G C",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-235"
    },
    {
      "claim_id": "C236",
      "claim_intent": "Docstring hint for skeleton_Group.forward: xyz: 所有token的xyz input: B N 3 --------------------------- output: B G M 3 center : B G 3",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-236"
    },
    {
      "claim_id": "C237",
      "claim_intent": "Python inline comment hint: Set the format of root handlers",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-237"
    },
    {
      "claim_id": "C238",
      "claim_intent": "Python inline comment hint: Redirect stdout and stderr to loggers",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-238"
    },
    {
      "claim_id": "C239",
      "claim_intent": "Python inline comment hint: Get logger",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-239"
    },
    {
      "claim_id": "C240",
      "claim_intent": "Python inline comment hint: Add a file handler for all loggers",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-240"
    },
    {
      "claim_id": "C241",
      "claim_intent": "Python inline comment hint: From the io.TextIOWrapper docs:",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-241"
    },
    {
      "claim_id": "C242",
      "claim_intent": "Python inline comment hint: On output, if newline is None, any '\\n' characters written",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-242"
    },
    {
      "claim_id": "C243",
      "claim_intent": "Python inline comment hint: are translated to the system default line separator.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-243"
    },
    {
      "claim_id": "C244",
      "claim_intent": "Python inline comment hint: By default sys.stdout.write() expects '\\n' newlines and then",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-244"
    },
    {
      "claim_id": "C245",
      "claim_intent": "Python inline comment hint: translates them so this is still cross platform.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-245"
    },
    {
      "claim_id": "C246",
      "claim_intent": "Python inline comment hint: Modified from github.com/openai/CLIP",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-246"
    },
    {
      "claim_id": "C247",
      "claim_intent": "Docstring hint for StreamToLogger: Fake file-like stream object that redirects writes to a logger instance.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-247"
    },
    {
      "claim_id": "C248",
      "claim_intent": "Docstring hint for disable_torch_init: Disable the redundant torch default initialization to accelerate model creation.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-248"
    },
    {
      "claim_id": "C249",
      "claim_intent": "Docstring hint for violates_moderation: Check whether the text violates OpenAI moderation API.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-249"
    },
    {
      "claim_id": "C250",
      "claim_intent": "Docstring hint for bytes_to_unicode: Returns list of utf-8 byte and a corresponding list of unicode strings. The reversible bpe codes work on unicode strings. This means you need a large # of unicode characters in your vocab if you want to avoid UNKs. When you're at something like a 10B token dataset you end up needing around 5K for decent coverage. This is a signficant percentage of your normal, say, 32K bpe vocab. To avoid that, we want lookup tables between utf-8 bytes and unicode strings. And avoids mapping to whitespace/control characters the bpe code barfs on.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-250"
    },
    {
      "claim_id": "C251",
      "claim_intent": "Docstring hint for get_pairs: Return set of symbol pairs in a word. Word is represented as tuple of symbols (symbols being variable-length strings).",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-251"
    },
    {
      "claim_id": "C252",
      "claim_intent": "Module docstring hint: A model worker executes the model.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-252"
    },
    {
      "claim_id": "C253",
      "claim_intent": "Python inline comment hint: stopping_criteria = KeywordsStoppingCriteria(keywords, tokenizer, input_ids)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-253"
    },
    {
      "claim_id": "C254",
      "claim_intent": "Python inline comment hint: shape: (b, num_heads, s, head_dim)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-254"
    },
    {
      "claim_id": "C255",
      "claim_intent": "Python inline comment hint: reuse k, v",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-255"
    },
    {
      "claim_id": "C256",
      "claim_intent": "Python inline comment hint: repeat k/v heads if n_kv_heads < n_heads",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-256"
    },
    {
      "claim_id": "C257",
      "claim_intent": "Python inline comment hint: Transform the data into the format required by flash attention",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-257"
    },
    {
      "claim_id": "C258",
      "claim_intent": "Python inline comment hint: shape: [b, s, 3, num_heads, head_dim]",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-258"
    },
    {
      "claim_id": "C259",
      "claim_intent": "Python inline comment hint: Disable the transformation of the attention mask in LlamaModel as the flash attention",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-259"
    },
    {
      "claim_id": "C260",
      "claim_intent": "Python inline comment hint: requires the attention mask to be the same as the key_padding_mask",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-260"
    },
    {
      "claim_id": "C261",
      "claim_intent": "Python inline comment hint: [bsz, seq_len]",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-261"
    },
    {
      "claim_id": "C262",
      "claim_intent": "Module docstring hint: Directly copied the code from https://raw.githubusercontent.com/oobabooga/text-generation-webui/main/modules/llama_attn_hijack.py and made some adjustments",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-262"
    },
    {
      "claim_id": "C263",
      "claim_intent": "Python inline comment hint: pylint: disable=duplicate-code",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-263"
    },
    {
      "claim_id": "C264",
      "claim_intent": "Python inline comment hint: [bsz, nh, t, hd]",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-264"
    },
    {
      "claim_id": "C265",
      "claim_intent": "Python inline comment hint: reuse k, v, self_attention",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-265"
    },
    {
      "claim_id": "C266",
      "claim_intent": "Python inline comment hint: We only apply xformers optimizations if we don't need to output the whole attention matrix",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-266"
    },
    {
      "claim_id": "C267",
      "claim_intent": "Python inline comment hint: We therefore check if one element in the upper triangular portion is zero. If it is, then the mask is all zeros.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-267"
    },
    {
      "claim_id": "C268",
      "claim_intent": "Python inline comment hint: input and output should be of form (bsz, q_len, num_heads, head_dim)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-268"
    },
    {
      "claim_id": "C269",
      "claim_intent": "Python inline comment hint: input and output should be of form (bsz, q_len, num_heads, head_dim)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-269"
    },
    {
      "claim_id": "C270",
      "claim_intent": "Python inline comment hint: upcast attention to fp32",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-270"
    },
    {
      "claim_id": "C271",
      "claim_intent": "Python inline comment hint: Borrowed from peft.utils.get_peft_model_state_dict",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-271"
    },
    {
      "claim_id": "C272",
      "claim_intent": "Python inline comment hint: all samples are in the same modality",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-272"
    },
    {
      "claim_id": "C273",
      "claim_intent": "Python inline comment hint: Only save Adapter",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-273"
    },
    {
      "claim_id": "C274",
      "claim_intent": "Python inline comment hint: self.model.save_pretrained(output_dir, state_dict=state_dict)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-274"
    },
    {
      "claim_id": "C275",
      "claim_intent": "Docstring hint for split_to_even_chunks: Split a list of indices into `chunks` chunks of roughly equal lengths.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-275"
    },
    {
      "claim_id": "C276",
      "claim_intent": "Docstring hint for LengthGroupedSampler: Sampler that samples indices in a way that groups together features of the dataset of roughly the same length while keeping a bit of randomness.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-276"
    },
    {
      "claim_id": "C277",
      "claim_intent": "Docstring hint for LLaVATrainer.create_optimizer: Setup the optimizer. We provide a reasonable default that works well. If you want to use something else, you can pass a tuple in the Trainer's init through `optimizers`, or subclass and override this method in a subclass.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-277"
    },
    {
      "claim_id": "C278",
      "claim_intent": "Python inline comment hint: Modified from LLaVA: https://github.com/haotian-liu/LLaVA.git",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-278"
    },
    {
      "claim_id": "C279",
      "claim_intent": "Python inline comment hint: Adopted from https://github.com/lm-sys/FastChat. Below is the original copyright:",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-279"
    },
    {
      "claim_id": "C280",
      "claim_intent": "Python inline comment hint: Adopted from tatsu-lab@stanford_alpaca. Below is the original copyright:",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-280"
    },
    {
      "claim_id": "C281",
      "claim_intent": "Python inline comment hint: Copyright 2023 Rohan Taori, Ishaan Gulrajani, Tianyi Zhang, Yann Dubois, Xuechen Li",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-281"
    },
    {
      "claim_id": "C282",
      "claim_intent": "Python inline comment hint: Licensed under the Apache License, Version 2.0 (the \"License\");",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-282"
    },
    {
      "claim_id": "C283",
      "claim_intent": "Python inline comment hint: you may not use this file except in compliance with the License.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-283"
    },
    {
      "claim_id": "C284",
      "claim_intent": "Python inline comment hint: You may obtain a copy of the License at",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-284"
    },
    {
      "claim_id": "C285",
      "claim_intent": "Python inline comment hint: http://www.apache.org/licenses/LICENSE-2.0",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-285"
    },
    {
      "claim_id": "C286",
      "claim_intent": "Python inline comment hint: Unless required by applicable law or agreed to in writing, software",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-286"
    },
    {
      "claim_id": "C287",
      "claim_intent": "Python inline comment hint: \"CLS\": inference of stage 1, 2",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-287"
    },
    {
      "claim_id": "C288",
      "claim_intent": "Python inline comment hint: \"OM_Pooling\":  training and inference of  stage 3",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-288"
    },
    {
      "claim_id": "C289",
      "claim_intent": "Python inline comment hint: stage 2 or stage 3",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-289"
    },
    {
      "claim_id": "C290",
      "claim_intent": "Docstring hint for pc_norm: pc: NxC, return NxC",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-290"
    },
    {
      "claim_id": "C291",
      "claim_intent": "Docstring hint for safe_save_model_for_hf_trainer: Collects the state dict and dump to disk.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-291"
    },
    {
      "claim_id": "C292",
      "claim_intent": "Docstring hint for smart_tokenizer_and_embedding_resize: Resize tokenizer and embedding. Note: This is the unoptimized version that may make your embedding size not be divisible by 64.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-292"
    },
    {
      "claim_id": "C293",
      "claim_intent": "Docstring hint for _tokenize_fn: Tokenize a list of strings.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-293"
    },
    {
      "claim_id": "C294",
      "claim_intent": "Docstring hint for _add_speaker_and_signal: Add speaker and start/end signal on each round.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-294"
    },
    {
      "claim_id": "C295",
      "claim_intent": "Docstring hint for preprocess: Given a list of sources, each is a conversation list. This transform: 1. Add signal '### ' at the beginning each sentence, with end signal ' '; 2. Concatenate conversations together; 3. Tokenize the concatenated conversation; 4. Make a deepcopy as the target. Mask human words with IGNORE_INDEX.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-295"
    },
    {
      "claim_id": "C296",
      "claim_intent": "Docstring hint for LazySupervisedDataset: Dataset for supervised fine-tuning.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-296"
    },
    {
      "claim_id": "C297",
      "claim_intent": "Docstring hint for DataCollatorForSupervisedDataset: Collate examples for supervised fine-tuning.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-297"
    },
    {
      "claim_id": "C298",
      "claim_intent": "Docstring hint for make_supervised_data_module: Make dataset and collator for supervised fine-tuning.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-298"
    },
    {
      "claim_id": "C299",
      "claim_intent": "Python inline comment hint: Make it more memory efficient by monkey patching the LLaMA model with xformers attention.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-299"
    },
    {
      "claim_id": "C300",
      "claim_intent": "Python inline comment hint: Need to call this before importing transformers.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-300"
    },
    {
      "claim_id": "C301",
      "claim_intent": "Python inline comment hint: * use the default config file in the same dir",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-301"
    },
    {
      "claim_id": "C302",
      "claim_intent": "Python inline comment hint: * check data path",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-302"
    },
    {
      "claim_id": "C303",
      "claim_intent": "Python inline comment hint: * should be 40",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-303"
    },
    {
      "claim_id": "C304",
      "claim_intent": "Python inline comment hint: \"tv_stand\" -> \"tv stand\"",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-304"
    },
    {
      "claim_id": "C305",
      "claim_intent": "Python inline comment hint: * list of category names",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-305"
    },
    {
      "claim_id": "C306",
      "claim_intent": "Python inline comment hint: * ndarray of N, C: (8192, 6) (xyz and normals)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-306"
    },
    {
      "claim_id": "C307",
      "claim_intent": "Python inline comment hint: * set random seed",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-307"
    },
    {
      "claim_id": "C308",
      "claim_intent": "Python inline comment hint: * random choose subset_nums",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-308"
    },
    {
      "claim_id": "C309",
      "claim_intent": "Python inline comment hint: * print len",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-309"
    },
    {
      "claim_id": "C310",
      "claim_intent": "Python inline comment hint: * random sample",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-310"
    },
    {
      "claim_id": "C311",
      "claim_intent": "Python inline comment hint: point_set = np.concatenate((point_set, np.zeros_like(point_set)), axis=-1) if self.use_color else point_set",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-311"
    },
    {
      "claim_id": "C312",
      "claim_intent": "Python inline comment hint: point_set = np.concatenate((point_set, np.ones_like(point_set)*0.4), axis=-1) if self.use_color else point_set",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-312"
    },
    {
      "claim_id": "C313",
      "claim_intent": "Docstring hint for ModelNet.__init__: Args: data_args: split: train or test",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-313"
    },
    {
      "claim_id": "C314",
      "claim_intent": "Docstring hint for ModelNet.pc_norm: pc: NxC, return NxC",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-314"
    },
    {
      "claim_id": "C315",
      "claim_intent": "Python inline comment hint: * use the default config file in the same dir",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-315"
    },
    {
      "claim_id": "C316",
      "claim_intent": "Python inline comment hint: * check data path",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-316"
    },
    {
      "claim_id": "C317",
      "claim_intent": "Python inline comment hint: * should be 40",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-317"
    },
    {
      "claim_id": "C318",
      "claim_intent": "Python inline comment hint: \"tv_stand\" -> \"tv stand\"",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-318"
    },
    {
      "claim_id": "C319",
      "claim_intent": "Python inline comment hint: * list of category names",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-319"
    },
    {
      "claim_id": "C320",
      "claim_intent": "Python inline comment hint: * ndarray of N, C: (8192, 6) (xyz and normals)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-320"
    },
    {
      "claim_id": "C321",
      "claim_intent": "Python inline comment hint: * set random seed",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-321"
    },
    {
      "claim_id": "C322",
      "claim_intent": "Python inline comment hint: * random choose subset_nums",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-322"
    },
    {
      "claim_id": "C323",
      "claim_intent": "Python inline comment hint: * print len",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-323"
    },
    {
      "claim_id": "C324",
      "claim_intent": "Python inline comment hint: * random sample",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-324"
    },
    {
      "claim_id": "C325",
      "claim_intent": "Python inline comment hint: * ndarray, int",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-325"
    },
    {
      "claim_id": "C326",
      "claim_intent": "Python inline comment hint: * random sample",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-326"
    },
    {
      "claim_id": "C327",
      "claim_intent": "Docstring hint for ModelNet.__init__: Args: data_args: split: train or test",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-327"
    },
    {
      "claim_id": "C328",
      "claim_intent": "Docstring hint for ModelNet.pc_norm: pc: NxC, return NxC",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-328"
    },
    {
      "claim_id": "C329",
      "claim_intent": "Python inline comment hint: from .pointllm import PointLLMLlamaForCausalLM, PointLLMConfig",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-329"
    },
    {
      "claim_id": "C330",
      "claim_intent": "Python inline comment hint: from .pointbert.point_encoder import PointTransformer",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-330"
    },
    {
      "claim_id": "C331",
      "claim_intent": "Python inline comment hint: Copyright 2023 Runsen Xu",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-331"
    },
    {
      "claim_id": "C332",
      "claim_intent": "Python inline comment hint: * add logger",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-332"
    },
    {
      "claim_id": "C333",
      "claim_intent": "Python inline comment hint: address of config file, in the same dir of this file",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-333"
    },
    {
      "claim_id": "C334",
      "claim_intent": "Python inline comment hint: * default for v1.1, v1.2 uses PointTransformer_8192point_2layer.yaml",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-334"
    },
    {
      "claim_id": "C335",
      "claim_intent": "Python inline comment hint: * default is false",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-335"
    },
    {
      "claim_id": "C336",
      "claim_intent": "Python inline comment hint: * number of output features, with cls token",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-336"
    },
    {
      "claim_id": "C337",
      "claim_intent": "Python inline comment hint: a list",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-337"
    },
    {
      "claim_id": "C338",
      "claim_intent": "Python inline comment hint: * print relevant info with projection layers",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-338"
    },
    {
      "claim_id": "C339",
      "claim_intent": "Python inline comment hint: Add projection layer with linear layers and GELU activation",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-339"
    },
    {
      "claim_id": "C340",
      "claim_intent": "Python inline comment hint: Single layer",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-340"
    },
    {
      "claim_id": "C341",
      "claim_intent": "Python inline comment hint: Enable model/pipeline parallelism",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-341"
    },
    {
      "claim_id": "C342",
      "claim_intent": "Python inline comment hint: * called when stage2 or inference or inference without pre-training, assume tokenizer has point tokens",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-342"
    },
    {
      "claim_id": "C343",
      "claim_intent": "Python inline comment hint: Adopted from https://github.com/lm-sys/FastChat. Below is the original copyright:",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-343"
    },
    {
      "claim_id": "C344",
      "claim_intent": "Python inline comment hint: * some version is changed to flash_attn_varlen_qkvpacked_func, so need to check",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-344"
    },
    {
      "claim_id": "C345",
      "claim_intent": "Python inline comment hint: [bsz, q_len, nh, hd]",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-345"
    },
    {
      "claim_id": "C346",
      "claim_intent": "Python inline comment hint: [bsz, nh, q_len, hd]",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-346"
    },
    {
      "claim_id": "C347",
      "claim_intent": "Python inline comment hint: [bsz, nh, t, hd]",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-347"
    },
    {
      "claim_id": "C348",
      "claim_intent": "Python inline comment hint: Flash attention codes from",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-348"
    },
    {
      "claim_id": "C349",
      "claim_intent": "Python inline comment hint: https://github.com/HazyResearch/flash-attention/blob/main/flash_attn/flash_attention.py",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-349"
    },
    {
      "claim_id": "C350",
      "claim_intent": "Python inline comment hint: transform the data into the format required by flash attention",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-350"
    },
    {
      "claim_id": "C351",
      "claim_intent": "Python inline comment hint: We have disabled _prepare_decoder_attention_mask in LlamaModel",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-351"
    },
    {
      "claim_id": "C352",
      "claim_intent": "Python inline comment hint: the attention_mask should be the same as the key_padding_mask",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-352"
    },
    {
      "claim_id": "C353",
      "claim_intent": "Python inline comment hint: Disable the transformation of the attention mask in LlamaModel as the flash attention",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-353"
    },
    {
      "claim_id": "C354",
      "claim_intent": "Python inline comment hint: requires the attention mask to be the same as the key_padding_mask",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-354"
    },
    {
      "claim_id": "C355",
      "claim_intent": "Docstring hint for forward: Input shape: Batch x Time x Channel attention_mask: [bsz, q_len]",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-355"
    },
    {
      "claim_id": "C356",
      "claim_intent": "Python inline comment hint: since there could be multiple levels of wrapping, unwrap recursively",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-356"
    },
    {
      "claim_id": "C357",
      "claim_intent": "Python inline comment hint: Save the model",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-357"
    },
    {
      "claim_id": "C358",
      "claim_intent": "Python inline comment hint: Only save the model itself if we are using distributed training",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-358"
    },
    {
      "claim_id": "C359",
      "claim_intent": "Docstring hint for unwrap_model: Recursively unwraps a model from potential containers (as used in distributed training). Args: model (`torch.nn.Module`): The model to unwrap.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-359"
    },
    {
      "claim_id": "C360",
      "claim_intent": "Python inline comment hint: Adopted from https://github.com/lm-sys/FastChat. Below is the original copyright:",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-360"
    },
    {
      "claim_id": "C361",
      "claim_intent": "Python inline comment hint: Adopted from tatsu-lab@stanford_alpaca. Below is the original copyright:",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-361"
    },
    {
      "claim_id": "C362",
      "claim_intent": "Python inline comment hint: Copyright 2023 Rohan Taori, Ishaan Gulrajani, Tianyi Zhang, Yann Dubois, Xuechen Li",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-362"
    },
    {
      "claim_id": "C363",
      "claim_intent": "Python inline comment hint: Licensed under the Apache License, Version 2.0 (the \"License\");",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-363"
    },
    {
      "claim_id": "C364",
      "claim_intent": "Python inline comment hint: you may not use this file except in compliance with the License.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-364"
    },
    {
      "claim_id": "C365",
      "claim_intent": "Python inline comment hint: You may obtain a copy of the License at",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-365"
    },
    {
      "claim_id": "C366",
      "claim_intent": "Python inline comment hint: * for two stage training",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-366"
    },
    {
      "claim_id": "C367",
      "claim_intent": "Python inline comment hint: * use with torch.inference_mode to control, not requires_grad for fsdp for second stage",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-367"
    },
    {
      "claim_id": "C368",
      "claim_intent": "Python inline comment hint: * fix pointnet for first stage, need for fsdp in stage2",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-368"
    },
    {
      "claim_id": "C369",
      "claim_intent": "Python inline comment hint: * we assume in stage2, llm, point_backbone, and projection layer can be loaded from the model checkpoint",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-369"
    },
    {
      "claim_id": "C370",
      "claim_intent": "Python inline comment hint: * stage2",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-370"
    },
    {
      "claim_id": "C371",
      "claim_intent": "Python inline comment hint: layer.register_forward_hook(print_layer_output)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-371"
    },
    {
      "claim_id": "C372",
      "claim_intent": "Docstring hint for safe_save_model_for_hf_trainer: Collects the state dict and dump to disk.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-372"
    },
    {
      "claim_id": "C373",
      "claim_intent": "Python inline comment hint: Adopted from https://github.com/lm-sys/FastChat. Below is the original copyright:",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-373"
    },
    {
      "claim_id": "C374",
      "claim_intent": "Python inline comment hint: Adopted from tatsu-lab@stanford_alpaca. Below is the original copyright:",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-374"
    },
    {
      "claim_id": "C375",
      "claim_intent": "Python inline comment hint: Make it more memory efficient by monkey patching the LLaMA model with FlashAttn.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-375"
    },
    {
      "claim_id": "C376",
      "claim_intent": "Python inline comment hint: Need to call this before importing transformers.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-376"
    },
    {
      "claim_id": "C377",
      "claim_intent": "Python inline comment hint: from pointllm.train.llama_flash_attn_monkey_patch import replace_llama_attn_with_flash_attn",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-377"
    },
    {
      "claim_id": "C378",
      "claim_intent": "Python inline comment hint: replace_llama_attn_with_flash_attn()",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-378"
    },
    {
      "claim_id": "C379",
      "claim_intent": "Python inline comment hint: list of (shape_name, shape_txt_file_path) tuple",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-379"
    },
    {
      "claim_id": "C380",
      "claim_intent": "Docstring hint for PointNet2ClassificationSSG.forward: Forward pass of the network Parameters ---------- pointcloud: Variable(torch.cuda.FloatTensor) (B, N, 3 + input_channels) tensor Point cloud to run predicts on Each point in the point-cloud MUST be formated as (x, y, z, features...)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-380"
    },
    {
      "claim_id": "C381",
      "claim_intent": "Docstring hint for PointNet2SemSegSSG.forward: Forward pass of the network Parameters ---------- pointcloud: Variable(torch.cuda.FloatTensor) (B, N, 3 + input_channels) tensor Point cloud to run predicts on Each point in the point-cloud MUST be formated as (x, y, z, features...)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-381"
    },
    {
      "claim_id": "C382",
      "claim_intent": "Module docstring hint: Phi-3 model configuration",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-382"
    },
    {
      "claim_id": "C383",
      "claim_intent": "Python inline comment hint: coding=utf-8",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-383"
    },
    {
      "claim_id": "C384",
      "claim_intent": "Python inline comment hint: Copyright 2024 Microsoft and the HuggingFace Inc. team. All rights reserved.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-384"
    },
    {
      "claim_id": "C385",
      "claim_intent": "Python inline comment hint: Licensed under the Apache License, Version 2.0 (the \"License\");",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-385"
    },
    {
      "claim_id": "C386",
      "claim_intent": "Python inline comment hint: you may not use this file except in compliance with the License.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-386"
    },
    {
      "claim_id": "C387",
      "claim_intent": "Python inline comment hint: You may obtain a copy of the License at",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-387"
    },
    {
      "claim_id": "C388",
      "claim_intent": "Python inline comment hint: http://www.apache.org/licenses/LICENSE-2.0",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-388"
    },
    {
      "claim_id": "C389",
      "claim_intent": "Python inline comment hint: Unless required by applicable law or agreed to in writing, software",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-389"
    },
    {
      "claim_id": "C390",
      "claim_intent": "Python inline comment hint: distributed under the License is distributed on an \"AS IS\" BASIS,",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-390"
    },
    {
      "claim_id": "C391",
      "claim_intent": "Python inline comment hint: WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-391"
    },
    {
      "claim_id": "C392",
      "claim_intent": "Python inline comment hint: See the License for the specific language governing permissions and",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-392"
    },
    {
      "claim_id": "C393",
      "claim_intent": "Python inline comment hint: limitations under the License.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-393"
    },
    {
      "claim_id": "C394",
      "claim_intent": "Docstring hint for Phi3Config: This is the configuration class to store the configuration of a [`Phi3Model`]. It is used to instantiate a Phi-3 model according to the specified arguments, defining the model architecture. Instantiating a configuration with the defaults will yield a similar configuration to that of the [microsoft/Phi-3-mini-4k-instruct](https://huggingface.co/microsoft/Phi-3-mini-4k-instruct). Configuration objects inherit from [`PretrainedConfig`] and can be used to control the model outputs. Read the documentation from [`PretrainedConfig`] for more information. Args: vocab_size (`int`, *optional*, defaults to 32064): Vocabulary size of the Phi-3 model. Defines the number of different tokens that can be represented by the `inputs_ids` passed when calling [`Phi3Model`]. hidden_size (`int`, *optional*, defaults to 3072): Dimension of the hidden representations. intermediate_size (`int`, *optional*, defaults to 8192): Dimension of the MLP representations. num_hidden_layers (`int`, *optional*, defaults to 32): Number of hidden layers in the Transformer decoder. num_attention_heads (`int`, *optional*, defaults to 32): Number of attention heads for each attention layer in the Transformer decoder. num_key_value_heads (`int`, *optional*): This is the number of key_value heads that should be used to implement Grouped Query Attention. If `num_key_value_heads=num_attention_heads`, the model will use Multi Head Attention (MHA), if `num_key_value_heads=1 the model will use Multi Query Attention (MQA) otherwise GQA is used. When converting a multi-head checkpoint to a GQA checkpoint, each group key and value head should be constructed by meanpooling all the original heads within that group. For more details checkout [this paper](https://arxiv.org/pdf/2305.13245.pdf). If it is not specified, will default to `num_attention_heads`. resid_pdrop (`float`, *optional*, defaults to 0.0): Dropout probability for mlp outputs. embd_pdrop (`int`, *optional*, defaults to 0.0): The dropout ratio for the embeddings. attention_dropout (`float`, *optional*, defaults to 0.0): The dropout ratio after computing the attention scores. hidden_act (`str` or `function`, *optional*, defaults to `\"silu\"`): The non-linear activation function (function or string) in the decoder. max_position_embeddings (`int`, *optional*, defaults to 4096): The maximum sequence length that this model might ever be used with. original_max_position_embeddings (`int`, *optional*, defaults to 4096): The maximum sequence length that this model was trained with. This is used to determine the size of the original RoPE embeddings when using long scaling. initializer_range (`float`, *optional*, defaults to 0.02): The standard deviation of the truncated_normal_initializer for initializing all weight matrices. rms_norm_eps (`float`, *optional*, defaults to 1e-05): The epsilon value used for the RMSNorm. use_cache (`bool`, *optional*, defaults to `True`): Whether or not the model should return the last key/values attentions (not used by all models). Only relevant if `config.is_decoder=True`. Whether to tie weight embeddings or not. tie_word_embeddings (`bool`, *optional*, defaults to `False`): Whether to tie weight embeddings rope_theta (`float`, *optional*, defaults to 10000.0): The base period of the RoPE embeddings. rope_scaling (`dict`, *optional*): The scaling strategy for the RoPE embeddings. If `None`, no scaling is applied. If a dictionary, it must contain the following keys: `type`, `short_factor` and `long_factor`. The `type` must be either `su` or `yarn` and the `short_factor` and `long_factor` must be lists of numbers with the same length as the hidden size divided by the number of attention heads divided by 2. bos_token_id (`int`, *optional*, defaults to 1): The id of the \"beginning-of-sequence\" token. eos_token_id (`int`, *optional*, defaults to 32000): The id of the \"end-of-sequence\" token. pad_token_id (`int`, *optional*, defaults to 32000): The id of the padding token. sliding_window (`int`, *optional*): Sliding window attention window size. If `None`, no sliding window is applied. Example: ```python >>> from transformers import Phi3Model, Phi3Config >>> # Initializing a Phi-3 style configuration >>> configuration = Phi3Config.from_pretrained(\"microsoft/Phi-3-mini-4k-instruct\") >>> # Initializing a model from the configuration >>> model = Phi3Model(configuration) >>> # Accessing the model configuration >>> configuration = model.config ```",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-394"
    },
    {
      "claim_id": "C395",
      "claim_intent": "Docstring hint for Phi3Config._rope_scaling_validation: Validate the `rope_scaling` configuration.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-395"
    },
    {
      "claim_id": "C396",
      "claim_intent": "Python inline comment hint: Hyper-parameters",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-396"
    },
    {
      "claim_id": "C397",
      "claim_intent": "Python inline comment hint: Log on each process a small summary",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-397"
    },
    {
      "claim_id": "C398",
      "claim_intent": "Python inline comment hint: Modle Loading",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-398"
    },
    {
      "claim_id": "C399",
      "claim_intent": "Python inline comment hint: loading the model with flash-attenstion support",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-399"
    },
    {
      "claim_id": "C400",
      "claim_intent": "Python inline comment hint: use unk rather than eos token to prevent endless generation",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-400"
    },
    {
      "claim_id": "C401",
      "claim_intent": "Python inline comment hint: Data Processing",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-401"
    },
    {
      "claim_id": "C402",
      "claim_intent": "Python inline comment hint: Add an empty system message if there is none",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-402"
    },
    {
      "claim_id": "C403",
      "claim_intent": "Python inline comment hint: Training",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-403"
    },
    {
      "claim_id": "C404",
      "claim_intent": "Python inline comment hint: Evaluation",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-404"
    },
    {
      "claim_id": "C405",
      "claim_intent": "Python inline comment hint: ############",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-405"
    },
    {
      "claim_id": "C406",
      "claim_intent": "Python inline comment hint: Model Constants",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-406"
    },
    {
      "claim_id": "C407",
      "claim_intent": "Python inline comment hint: Modified from LLaVA: https://github.com/haotian-liu/LLaVA.git",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-407"
    },
    {
      "claim_id": "C408",
      "claim_intent": "Docstring hint for SeparatorStyle: Different separator style.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-408"
    },
    {
      "claim_id": "C409",
      "claim_intent": "Docstring hint for Conversation: A class that keeps all conversation history.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-409"
    },
    {
      "claim_id": "C410",
      "claim_intent": "Python inline comment hint: Resize the image",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-410"
    },
    {
      "claim_id": "C411",
      "claim_intent": "Docstring hint for select_best_resolution: Selects the best resolution from a list of possible resolutions based on the original size. Args: original_size (tuple): The original size of the image in the format (width, height). possible_resolutions (list): A list of possible resolutions in the format [(width1, height1), (width2, height2), ...]. Returns: tuple: The best fit resolution in the format (width, height).",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-411"
    },
    {
      "claim_id": "C412",
      "claim_intent": "Docstring hint for resize_and_pad_image: Resize and pad an image to a target resolution while maintaining aspect ratio. Args: image (PIL.Image.Image): The input image. target_resolution (tuple): The target resolution (width, height) of the image. Returns: PIL.Image.Image: The resized and padded image.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-412"
    },
    {
      "claim_id": "C413",
      "claim_intent": "Docstring hint for divide_to_patches: Divides an image into patches of a specified size. Args: image (PIL.Image.Image): The input image. patch_size (int): The size of each patch. Returns: list: A list of PIL.Image.Image objects representing the patches.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-413"
    },
    {
      "claim_id": "C414",
      "claim_intent": "Docstring hint for get_anyres_image_grid_shape: Calculate the shape of the image patch grid after the preprocessing for images of any resolution. Args: image_size (tuple): The size of the input image in the format (width, height). grid_pinpoints (str): A string representation of a list of possible resolutions. patch_size (int): The size of each image patch. Returns: tuple: The shape of the image patch grid in the format (width, height).",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-414"
    },
    {
      "claim_id": "C415",
      "claim_intent": "Docstring hint for process_anyres_image: Process an image with variable resolutions. Args: image (PIL.Image.Image): The input image to be processed. processor: The image processor object. grid_pinpoints (str): A string representation of a list of possible resolutions. Returns: torch.Tensor: A tensor containing the processed image patches.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-415"
    },
    {
      "claim_id": "C416",
      "claim_intent": "Module docstring hint: A controller manages distributed workers. It sends worker addresses to clients.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-416"
    },
    {
      "claim_id": "C417",
      "claim_intent": "Python inline comment hint: Dict[str -> WorkerInfo]",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-417"
    },
    {
      "claim_id": "C418",
      "claim_intent": "Python inline comment hint: Directly return address",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-418"
    },
    {
      "claim_id": "C419",
      "claim_intent": "Python inline comment hint: Check status before returning",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-419"
    },
    {
      "claim_id": "C420",
      "claim_intent": "Python inline comment hint: Let the controller act as a worker to achieve hierarchical",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-420"
    },
    {
      "claim_id": "C421",
      "claim_intent": "Python inline comment hint: management. This can be used to connect isolated sub networks.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-421"
    },
    {
      "claim_id": "C422",
      "claim_intent": "Python inline comment hint: Hard cut-off",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-422"
    },
    {
      "claim_id": "C423",
      "claim_intent": "Python inline comment hint: Hard cut-off for images",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-423"
    },
    {
      "claim_id": "C424",
      "claim_intent": "Python inline comment hint: text = '<Image><image></Image>' + text",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-424"
    },
    {
      "claim_id": "C425",
      "claim_intent": "Python inline comment hint: This generate call is skipped due to invalid inputs",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-425"
    },
    {
      "claim_id": "C426",
      "claim_intent": "Python inline comment hint: First round of conversation",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-426"
    },
    {
      "claim_id": "C427",
      "claim_intent": "Python inline comment hint: Query worker address",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-427"
    },
    {
      "claim_id": "C428",
      "claim_intent": "Python inline comment hint: No available worker",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-428"
    },
    {
      "claim_id": "C429",
      "claim_intent": "Python inline comment hint: Construct prompt",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-429"
    },
    {
      "claim_id": "C430",
      "claim_intent": "Python inline comment hint: Make requests",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-430"
    },
    {
      "claim_id": "C431",
      "claim_intent": "Python inline comment hint: Stream output",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-431"
    },
    {
      "claim_id": "C432",
      "claim_intent": "Python inline comment hint: stop_btn = gr.Button(value=\"⏹️  Stop Generation\", interactive=False)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-432"
    },
    {
      "claim_id": "C433",
      "claim_intent": "Python inline comment hint: Register listeners",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-433"
    },
    {
      "claim_id": "C434",
      "claim_intent": "Module docstring hint: Manually register workers. Usage: python3 -m fastchat.serve.register_worker --controller http://localhost:21001 --worker-name http://localhost:21002",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-434"
    },
    {
      "claim_id": "C435",
      "claim_intent": "Module docstring hint: A model worker executes the model.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-435"
    },
    {
      "claim_id": "C436",
      "claim_intent": "Python inline comment hint: Select backend",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-436"
    },
    {
      "claim_id": "C437",
      "claim_intent": "Python inline comment hint: replace_token = DEFAULT_IMAGE_TOKEN",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-437"
    },
    {
      "claim_id": "C438",
      "claim_intent": "Python inline comment hint: if getattr(self.model.config, 'mm_use_im_start_end', False):",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-438"
    },
    {
      "claim_id": "C439",
      "claim_intent": "Python inline comment hint: replace_token = DEFAULT_IM_START_TOKEN + replace_token + DEFAULT_IM_END_TOKEN",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-439"
    },
    {
      "claim_id": "C440",
      "claim_intent": "Python inline comment hint: prompt = prompt.replace(DEFAULT_IMAGE_TOKEN, replace_token)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-440"
    },
    {
      "claim_id": "C441",
      "claim_intent": "Python inline comment hint: max_context_length = getattr(model.config, 'max_position_embeddings', 2048)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-441"
    },
    {
      "claim_id": "C442",
      "claim_intent": "Python inline comment hint: Set the format of root handlers",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-442"
    },
    {
      "claim_id": "C443",
      "claim_intent": "Python inline comment hint: Redirect stdout and stderr to loggers",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-443"
    },
    {
      "claim_id": "C444",
      "claim_intent": "Python inline comment hint: Get logger",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-444"
    },
    {
      "claim_id": "C445",
      "claim_intent": "Python inline comment hint: Add a file handler for all loggers",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-445"
    },
    {
      "claim_id": "C446",
      "claim_intent": "Python inline comment hint: From the io.TextIOWrapper docs:",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-446"
    },
    {
      "claim_id": "C447",
      "claim_intent": "Python inline comment hint: On output, if newline is None, any '\\n' characters written",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-447"
    },
    {
      "claim_id": "C448",
      "claim_intent": "Python inline comment hint: are translated to the system default line separator.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-448"
    },
    {
      "claim_id": "C449",
      "claim_intent": "Python inline comment hint: By default sys.stdout.write() expects '\\n' newlines and then",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-449"
    },
    {
      "claim_id": "C450",
      "claim_intent": "Python inline comment hint: translates them so this is still cross platform.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-450"
    },
    {
      "claim_id": "C451",
      "claim_intent": "Python inline comment hint: Modified from github.com/openai/CLIP",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-451"
    },
    {
      "claim_id": "C452",
      "claim_intent": "Docstring hint for StreamToLogger: Fake file-like stream object that redirects writes to a logger instance.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-452"
    },
    {
      "claim_id": "C453",
      "claim_intent": "Docstring hint for disable_torch_init: Disable the redundant torch default initialization to accelerate model creation.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-453"
    },
    {
      "claim_id": "C454",
      "claim_intent": "Docstring hint for violates_moderation: Check whether the text violates OpenAI moderation API.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-454"
    },
    {
      "claim_id": "C455",
      "claim_intent": "Docstring hint for bytes_to_unicode: Returns list of utf-8 byte and a corresponding list of unicode strings. The reversible bpe codes work on unicode strings. This means you need a large # of unicode characters in your vocab if you want to avoid UNKs. When you're at something like a 10B token dataset you end up needing around 5K for decent coverage. This is a signficant percentage of your normal, say, 32K bpe vocab. To avoid that, we want lookup tables between utf-8 bytes and unicode strings. And avoids mapping to whitespace/control characters the bpe code barfs on.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-455"
    },
    {
      "claim_id": "C456",
      "claim_intent": "Docstring hint for get_pairs: Return set of symbol pairs in a word. Word is represented as tuple of symbols (symbols being variable-length strings).",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-456"
    },
    {
      "claim_id": "C457",
      "claim_intent": "Python inline comment hint: from .model import PointLLMLlamaForCausalLM",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-457"
    },
    {
      "claim_id": "C458",
      "claim_intent": "Python inline comment hint: * pop the last message if it's None, this is used for multi-round dialogue",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-458"
    },
    {
      "claim_id": "C459",
      "claim_intent": "Python inline comment hint: image = image.resize((224, 224))",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-459"
    },
    {
      "claim_id": "C460",
      "claim_intent": "Python inline comment hint: fastchat",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-460"
    },
    {
      "claim_id": "C461",
      "claim_intent": "Docstring hint for SeparatorStyle: Different separator style.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-461"
    },
    {
      "claim_id": "C462",
      "claim_intent": "Docstring hint for Conversation: A class that keeps all conversation history.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-462"
    },
    {
      "claim_id": "C463",
      "claim_intent": "Python inline comment hint: from .scanobjectNN import ScanObjectNN",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-463"
    },
    {
      "claim_id": "C464",
      "claim_intent": "Python inline comment hint: * make a val dataset",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-464"
    },
    {
      "claim_id": "C465",
      "claim_intent": "Python inline comment hint: * load train split",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-465"
    },
    {
      "claim_id": "C466",
      "claim_intent": "Python inline comment hint: * use all data as training data",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-466"
    },
    {
      "claim_id": "C467",
      "claim_intent": "Python inline comment hint: * default is simple_des, used for stage1 pre-train",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-467"
    },
    {
      "claim_id": "C468",
      "claim_intent": "Python inline comment hint: Load the data list from JSON",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-468"
    },
    {
      "claim_id": "C469",
      "claim_intent": "Python inline comment hint: * print the conversations_type",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-469"
    },
    {
      "claim_id": "C470",
      "claim_intent": "Python inline comment hint: * print before filtering",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-470"
    },
    {
      "claim_id": "C471",
      "claim_intent": "Python inline comment hint: * iterate the list and filter",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-471"
    },
    {
      "claim_id": "C472",
      "claim_intent": "Python inline comment hint: * these two ids have corrupted colored point files, so filter them when use_color is True",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-472"
    },
    {
      "claim_id": "C473",
      "claim_intent": "Python inline comment hint: Iterate the list, filter those \"conversation_type\" not in self.conversation_types",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-473"
    },
    {
      "claim_id": "C474",
      "claim_intent": "Python inline comment hint: * print after filtering",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-474"
    },
    {
      "claim_id": "C475",
      "claim_intent": "Python inline comment hint: * print the size of different conversation_type",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-475"
    },
    {
      "claim_id": "C476",
      "claim_intent": "Docstring hint for make_object_point_data_module: Make dataset and collator for Joint3Ddataset with text and point cloud data.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-476"
    },
    {
      "claim_id": "C477",
      "claim_intent": "Docstring hint for ObjectPointCloudDataset: Dataset utilities for objaverse.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-477"
    },
    {
      "claim_id": "C478",
      "claim_intent": "Docstring hint for ObjectPointCloudDataset.__init__: split: only considered when data_args.split_train_val is True. conversation_types: tuple, used to filter the data, default is ('simple_description'), other types is: \"detailed_description\", \"single_round\", \"multi_round\". tokenizer: load point clouds only if None",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-478"
    },
    {
      "claim_id": "C479",
      "claim_intent": "Docstring hint for ObjectPointCloudDataset.pc_norm: pc: NxC, return NxC",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-479"
    },
    {
      "claim_id": "C480",
      "claim_intent": "Docstring hint for ObjectPointCloudDataset.__len__: Return number of utterances.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-480"
    },
    {
      "claim_id": "C481",
      "claim_intent": "Python inline comment hint: * Sample Usage:",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-481"
    },
    {
      "claim_id": "C482",
      "claim_intent": "Python inline comment hint: * from utils import LRUCache",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-482"
    },
    {
      "claim_id": "C483",
      "claim_intent": "Python inline comment hint: * cache = LRUCache(capacity, max_access_count)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-483"
    },
    {
      "claim_id": "C484",
      "claim_intent": "Python inline comment hint: if self.cache is None:",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-484"
    },
    {
      "claim_id": "C485",
      "claim_intent": "Python inline comment hint: info_data = self.multiview_scannet[info_index]",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-485"
    },
    {
      "claim_id": "C486",
      "claim_intent": "Python inline comment hint: else:",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-486"
    },
    {
      "claim_id": "C487",
      "claim_intent": "Python inline comment hint: info_data = self.cache.get(info_index)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-487"
    },
    {
      "claim_id": "C488",
      "claim_intent": "Python inline comment hint: if info_data is None or self.cache.get_access_count(info_index) >= self.cache.max_access_count:",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-488"
    },
    {
      "claim_id": "C489",
      "claim_intent": "Python inline comment hint: # If not in cache, or accessed max_access_count times, load it and put it in cache",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-489"
    },
    {
      "claim_id": "C490",
      "claim_intent": "Python inline comment hint: info_data = self.multiview_scannet[info_index]",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-490"
    },
    {
      "claim_id": "C491",
      "claim_intent": "Python inline comment hint: self.cache.put(info_index, info_data)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-491"
    },
    {
      "claim_id": "C492",
      "claim_intent": "Python inline comment hint: self.cache.reset_access_count(info_index)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-492"
    },
    {
      "claim_id": "C493",
      "claim_intent": "Docstring hint for pc_norm: pc: NxC, return NxC",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-493"
    },
    {
      "claim_id": "C494",
      "claim_intent": "Docstring hint for DataCollatorForPointTextDataset: Collate examples for mixed dataset with text and point cloud data.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-494"
    },
    {
      "claim_id": "C495",
      "claim_intent": "Docstring hint for farthest_point_sample: Input: xyz: pointcloud data, [N, D] npoint: number of samples Return: centroids: sampled pointcloud index, [npoint, D]",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-495"
    },
    {
      "claim_id": "C496",
      "claim_intent": "Docstring hint for pc_normalize: pc: Nx3 array This functions normalizes a point cloud to fit within a unit sphere. It first calculates the centroid of the point cloud and then subtracts it from all points before scaling all points to fit within a unit sphere.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-496"
    },
    {
      "claim_id": "C497",
      "claim_intent": "Python inline comment hint: * Sample Usage:",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-497"
    },
    {
      "claim_id": "C498",
      "claim_intent": "Python inline comment hint: * from utils import LRUCache",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-498"
    },
    {
      "claim_id": "C499",
      "claim_intent": "Python inline comment hint: * cache = LRUCache(capacity, max_access_count)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-499"
    },
    {
      "claim_id": "C500",
      "claim_intent": "Python inline comment hint: if self.cache is None:",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-500"
    },
    {
      "claim_id": "C501",
      "claim_intent": "Python inline comment hint: info_data = self.multiview_scannet[info_index]",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-501"
    },
    {
      "claim_id": "C502",
      "claim_intent": "Python inline comment hint: else:",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-502"
    },
    {
      "claim_id": "C503",
      "claim_intent": "Python inline comment hint: info_data = self.cache.get(info_index)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-503"
    },
    {
      "claim_id": "C504",
      "claim_intent": "Python inline comment hint: if info_data is None or self.cache.get_access_count(info_index) >= self.cache.max_access_count:",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-504"
    },
    {
      "claim_id": "C505",
      "claim_intent": "Python inline comment hint: # If not in cache, or accessed max_access_count times, load it and put it in cache",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-505"
    },
    {
      "claim_id": "C506",
      "claim_intent": "Python inline comment hint: info_data = self.multiview_scannet[info_index]",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-506"
    },
    {
      "claim_id": "C507",
      "claim_intent": "Python inline comment hint: self.cache.put(info_index, info_data)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-507"
    },
    {
      "claim_id": "C508",
      "claim_intent": "Python inline comment hint: self.cache.reset_access_count(info_index)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-508"
    },
    {
      "claim_id": "C509",
      "claim_intent": "Docstring hint for pc_norm: pc: NxC, return NxC",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-509"
    },
    {
      "claim_id": "C510",
      "claim_intent": "Docstring hint for DataCollatorForPointTextDataset: Collate examples for mixed dataset with text and point cloud data.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-510"
    },
    {
      "claim_id": "C511",
      "claim_intent": "Docstring hint for farthest_point_sample: Input: xyz: pointcloud data, [N, D] npoint: number of samples Return: centroids: sampled pointcloud index, [npoint, D]",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-511"
    },
    {
      "claim_id": "C512",
      "claim_intent": "Docstring hint for pc_normalize: pc: Nx3 array This functions normalizes a point cloud to fit within a unit sphere. It first calculates the centroid of the point cloud and then subtracts it from all points before scaling all points to fit within a unit sphere.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-512"
    },
    {
      "claim_id": "C513",
      "claim_intent": "Python inline comment hint: Set the format of root handlers",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-513"
    },
    {
      "claim_id": "C514",
      "claim_intent": "Python inline comment hint: Redirect stdout and stderr to loggers",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-514"
    },
    {
      "claim_id": "C515",
      "claim_intent": "Python inline comment hint: Get logger",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-515"
    },
    {
      "claim_id": "C516",
      "claim_intent": "Python inline comment hint: Add a file handler for all loggers",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-516"
    },
    {
      "claim_id": "C517",
      "claim_intent": "Python inline comment hint: * get the logger_file's directory, and create it if not exist",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-517"
    },
    {
      "claim_id": "C518",
      "claim_intent": "Python inline comment hint: From the io.TextIOWrapper docs:",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-518"
    },
    {
      "claim_id": "C519",
      "claim_intent": "Python inline comment hint: On output, if newline is None, any '\\n' characters written",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-519"
    },
    {
      "claim_id": "C520",
      "claim_intent": "Python inline comment hint: are translated to the system default line separator.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-520"
    },
    {
      "claim_id": "C521",
      "claim_intent": "Python inline comment hint: By default sys.stdout.write() expects '\\n' newlines and then",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-521"
    },
    {
      "claim_id": "C522",
      "claim_intent": "Python inline comment hint: translates them so this is still cross platform.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-522"
    },
    {
      "claim_id": "C523",
      "claim_intent": "Python inline comment hint: url = \"https://api.chatanywhere.tech/v1/moderations\"",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-523"
    },
    {
      "claim_id": "C524",
      "claim_intent": "Docstring hint for StreamToLogger: Fake file-like stream object that redirects writes to a logger instance.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-524"
    },
    {
      "claim_id": "C525",
      "claim_intent": "Docstring hint for disable_torch_init: Disable the redundant torch default initialization to accelerate model creation.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-525"
    },
    {
      "claim_id": "C526",
      "claim_intent": "Docstring hint for violates_moderation: Check whether the text violates OpenAI moderation API.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-526"
    },
    {
      "claim_id": "C527",
      "claim_intent": "Python inline comment hint: yapf: disable",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-527"
    },
    {
      "claim_id": "C528",
      "claim_intent": "Python inline comment hint: yapf: enable",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-528"
    },
    {
      "claim_id": "C529",
      "claim_intent": "Python inline comment hint: 0~0.875",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-529"
    },
    {
      "claim_id": "C530",
      "claim_intent": "Python inline comment hint: set to the first point",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-530"
    },
    {
      "claim_id": "C531",
      "claim_intent": "Docstring hint for angle_axis: Returns a 4x4 rotation matrix that performs a rotation around axis by angle Parameters ---------- angle : float Angle to rotate by axis: np.ndarray Axis to rotate about Returns ------- torch.Tensor 3x3 rotation matrix",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-531"
    },
    {
      "claim_id": "C532",
      "claim_intent": "Python inline comment hint: (B, C, npoint, nsample)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-532"
    },
    {
      "claim_id": "C533",
      "claim_intent": "Python inline comment hint: (B, mlp[-1], npoint, nsample)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-533"
    },
    {
      "claim_id": "C534",
      "claim_intent": "Python inline comment hint: (B, mlp[-1], npoint, 1)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-534"
    },
    {
      "claim_id": "C535",
      "claim_intent": "Python inline comment hint: (B, mlp[-1], npoint)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-535"
    },
    {
      "claim_id": "C536",
      "claim_intent": "Python inline comment hint: (B, C2 + C1, n)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-536"
    },
    {
      "claim_id": "C537",
      "claim_intent": "Docstring hint for _PointnetSAModuleBase.forward: Parameters ---------- xyz : torch.Tensor (B, N, 3) tensor of the xyz coordinates of the features features : torch.Tensor (B, C, N) tensor of the descriptors of the the features Returns ------- new_xyz : torch.Tensor (B, npoint, 3) tensor of the new features' xyz new_features : torch.Tensor (B, \\sum_k(mlps[k][-1]), npoint) tensor of the new_features descriptors",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-537"
    },
    {
      "claim_id": "C538",
      "claim_intent": "Docstring hint for PointnetSAModuleMSG: Pointnet set abstrction layer with multiscale grouping Parameters ---------- npoint : int Number of features radii : list of float32 list of radii to group with nsamples : list of int32 Number of samples in each ball query mlps : list of list of int32 Spec of the pointnet before the global max_pool for each scale bn : bool Use batchnorm",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-538"
    },
    {
      "claim_id": "C539",
      "claim_intent": "Docstring hint for PointnetSAModule: Pointnet set abstrction layer Parameters ---------- npoint : int Number of features radius : float Radius of ball nsample : int Number of samples in the ball query mlp : list Spec of the pointnet before the global max_pool bn : bool Use batchnorm",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-539"
    },
    {
      "claim_id": "C540",
      "claim_intent": "Docstring hint for PointnetFPModule: Propigates the features of one set to another Parameters ---------- mlp : list Pointnet module parameters bn : bool Use batchnorm",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-540"
    },
    {
      "claim_id": "C541",
      "claim_intent": "Docstring hint for PointnetFPModule.forward: Parameters ---------- unknown : torch.Tensor (B, n, 3) tensor of the xyz positions of the unknown features known : torch.Tensor (B, m, 3) tensor of the xyz positions of the known features unknow_feats : torch.Tensor (B, C1, n) tensor of the features to be propigated to known_feats : torch.Tensor (B, C2, m) tensor of features to be propigated Returns ------- new_features : torch.Tensor (B, mlp[-1], n) tensor of the features of the unknown features",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-541"
    },
    {
      "claim_id": "C542",
      "claim_intent": "Python inline comment hint: type(Any, torch.Tensor, torch.Tensor, torch.Tensor) -> Torch.Tensor",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-542"
    },
    {
      "claim_id": "C543",
      "claim_intent": "Python inline comment hint: (B, 3, npoint, nsample)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-543"
    },
    {
      "claim_id": "C544",
      "claim_intent": "Python inline comment hint: (B, C + 3, npoint, nsample)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-544"
    },
    {
      "claim_id": "C545",
      "claim_intent": "Python inline comment hint: (B, 3 + C, 1, N)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-545"
    },
    {
      "claim_id": "C546",
      "claim_intent": "Docstring hint for FurthestPointSampling.forward: Uses iterative furthest point sampling to select a set of npoint features that have the largest minimum distance Parameters ---------- xyz : torch.Tensor (B, N, 3) tensor where N > npoint npoint : int32 number of features in the sampled set Returns ------- torch.Tensor (B, npoint) tensor containing the set",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-546"
    },
    {
      "claim_id": "C547",
      "claim_intent": "Docstring hint for GatherOperation.forward: Parameters ---------- features : torch.Tensor (B, C, N) tensor idx : torch.Tensor (B, npoint) tensor of the features to gather Returns ------- torch.Tensor (B, C, npoint) tensor",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-547"
    },
    {
      "claim_id": "C548",
      "claim_intent": "Docstring hint for ThreeNN.forward: Find the three nearest neighbors of unknown in known Parameters ---------- unknown : torch.Tensor (B, n, 3) tensor of known features known : torch.Tensor (B, m, 3) tensor of unknown features Returns ------- dist : torch.Tensor (B, n, 3) l2 distance to the three nearest neighbors idx : torch.Tensor (B, n, 3) index of 3 nearest neighbors",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-548"
    },
    {
      "claim_id": "C549",
      "claim_intent": "Docstring hint for ThreeInterpolate.forward: Performs weight linear interpolation on 3 features Parameters ---------- features : torch.Tensor (B, c, m) Features descriptors to be interpolated from idx : torch.Tensor (B, n, 3) three nearest neighbors of the target features in features weight : torch.Tensor (B, n, 3) weights Returns ------- torch.Tensor (B, c, n) tensor of the interpolated features",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-549"
    },
    {
      "claim_id": "C550",
      "claim_intent": "Docstring hint for ThreeInterpolate.backward: Parameters ---------- grad_out : torch.Tensor (B, c, n) tensor with gradients of ouputs Returns ------- grad_features : torch.Tensor (B, c, m) tensor with gradients of features None None",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-550"
    },
    {
      "claim_id": "C551",
      "claim_intent": "Docstring hint for GroupingOperation.forward: Parameters ---------- features : torch.Tensor (B, C, N) tensor of features to group idx : torch.Tensor (B, npoint, nsample) tensor containing the indicies of features to group with Returns ------- torch.Tensor (B, C, npoint, nsample) tensor",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-551"
    },
    {
      "claim_id": "C552",
      "claim_intent": "Docstring hint for GroupingOperation.backward: Parameters ---------- grad_out : torch.Tensor (B, C, npoint, nsample) tensor of the gradients of the output from forward Returns ------- torch.Tensor (B, C, N) gradient of the features None",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-552"
    },
    {
      "claim_id": "C553",
      "claim_intent": "Docstring hint for BallQuery.forward: Parameters ---------- radius : float radius of the balls nsample : int maximum number of features in the balls xyz : torch.Tensor (B, N, 3) xyz coordinates of the features new_xyz : torch.Tensor (B, npoint, 3) centers of the ball query Returns ------- torch.Tensor (B, npoint, nsample) tensor with the indicies of the features that form the query balls",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-553"
    },
    {
      "claim_id": "C554",
      "claim_intent": "Docstring hint for QueryAndGroup: Groups with a ball query of radius Parameters --------- radius : float32 Radius of ball nsample : int32 Maximum number of features to gather in the ball",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-554"
    },
    {
      "claim_id": "C555",
      "claim_intent": "Docstring hint for QueryAndGroup.forward: Parameters ---------- xyz : torch.Tensor xyz coordinates of the features (B, N, 3) new_xyz : torch.Tensor centriods (B, npoint, 3) features : torch.Tensor Descriptors of the features (B, C, N) Returns ------- new_features : torch.Tensor (B, 3 + C, npoint, nsample) tensor",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-555"
    },
    {
      "claim_id": "C556",
      "claim_intent": "Docstring hint for GroupAll: Groups all features Parameters ---------",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-556"
    },
    {
      "claim_id": "C557",
      "claim_intent": "Docstring hint for GroupAll.forward: Parameters ---------- xyz : torch.Tensor xyz coordinates of the features (B, N, 3) new_xyz : torch.Tensor Ignored features : torch.Tensor Descriptors of the features (B, C, N) Returns ------- new_features : torch.Tensor (B, C + 3, 1, N) tensor",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-557"
    },
    {
      "claim_id": "C558",
      "claim_intent": "Python inline comment hint: print(choice_txt)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-558"
    },
    {
      "claim_id": "C559",
      "claim_intent": "Python inline comment hint: \\\\n: GPT-3 can generate the lecture with more tokens.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-559"
    },
    {
      "claim_id": "C560",
      "claim_intent": "Python inline comment hint: \\\\n: GPT-3 can generate the solution with more tokens",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-560"
    },
    {
      "claim_id": "C561",
      "claim_intent": "Python inline comment hint: Inputs",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-561"
    },
    {
      "claim_id": "C562",
      "claim_intent": "Python inline comment hint: upper bound experiment",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-562"
    },
    {
      "claim_id": "C563",
      "claim_intent": "Python inline comment hint: Outputs",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-563"
    },
    {
      "claim_id": "C564",
      "claim_intent": "Python inline comment hint: Inputs",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-564"
    },
    {
      "claim_id": "C565",
      "claim_intent": "Python inline comment hint: upper bound experiment",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-565"
    },
    {
      "claim_id": "C566",
      "claim_intent": "Python inline comment hint: Outputs",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-566"
    },
    {
      "claim_id": "C567",
      "claim_intent": "Python inline comment hint: Inputs",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-567"
    },
    {
      "claim_id": "C568",
      "claim_intent": "Python inline comment hint: upper bound experiment",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-568"
    },
    {
      "claim_id": "C569",
      "claim_intent": "Python inline comment hint: Outputs",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-569"
    },
    {
      "claim_id": "C570",
      "claim_intent": "Module docstring hint: This is just a utility that I use to extract the projector for quantized models. It is NOT necessary at all to train, or run inference/serve demos. Use this script ONLY if you fully understand its implications.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-570"
    },
    {
      "claim_id": "C571",
      "claim_intent": "Python inline comment hint: Smaller models or model checkpoints saved by DeepSpeed.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-571"
    },
    {
      "claim_id": "C572",
      "claim_intent": "Module docstring hint: Train script for a single file Need to set the TPU address first: export XRT_TPU_CONFIG=\"localservice;0;localhost:51011\"",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-572"
    },
    {
      "claim_id": "C573",
      "claim_intent": "Python inline comment hint: First element of model_output contains all token embeddings",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-573"
    },
    {
      "claim_id": "C574",
      "claim_intent": "Python inline comment hint: Train Loop",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-574"
    },
    {
      "claim_id": "C575",
      "claim_intent": "Python inline comment hint: Instantiate optimizer",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-575"
    },
    {
      "claim_id": "C576",
      "claim_intent": "Python inline comment hint: Now we train the model",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-576"
    },
    {
      "claim_id": "C577",
      "claim_intent": "Python inline comment hint: Get the batch data",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-577"
    },
    {
      "claim_id": "C578",
      "claim_intent": "Python inline comment hint: print(index, \"batch {}x{}\".format(len(batch), \",\".join([str(len(b)) for b in batch])))",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-578"
    },
    {
      "claim_id": "C579",
      "claim_intent": "Python inline comment hint: (anchor, positive)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-579"
    },
    {
      "claim_id": "C580",
      "claim_intent": "Python inline comment hint: Compute embeddings",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-580"
    },
    {
      "claim_id": "C581",
      "claim_intent": "Python inline comment hint: Compute cross-entropy loss",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-581"
    },
    {
      "claim_id": "C582",
      "claim_intent": "Python inline comment hint: Symmetric loss as in CLIP",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-582"
    },
    {
      "claim_id": "C583",
      "claim_intent": "Python inline comment hint: Compute cross-entropy loss",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-583"
    },
    {
      "claim_id": "C584",
      "claim_intent": "Python inline comment hint: One-way loss",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-584"
    },
    {
      "claim_id": "C585",
      "claim_intent": "Docstring hint for RedditDataset: A class that handles the reddit data files",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-585"
    },
    {
      "claim_id": "C586",
      "claim_intent": "Docstring hint for Dataset: A class that handles one dataset",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-586"
    }
  ],
  "negative_scope": [
    "README-only statements cannot enter method prose.",
    "Logger, checkpoint, seed, cache, path handling, and distributed setup are infrastructure unless tied to hard method evidence.",
    "Comments and author hints are navigation signals, not standalone fact evidence.",
    "Do not present these support/utility symbols as method mechanisms: lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py::Phi3PreTrainedModel, lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py::Phi3PreTrainedModel._init_weights, lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py::Phi3PreTrainedModel._init_weights->isinstance, lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py::Phi3PreTrainedModel._init_weights->normal_, lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py::Phi3PreTrainedModel._init_weights->zero_, llava/model/apply_delta.py::apply_delta->from_pretrained, llava/model/apply_delta.py::apply_delta->save_pretrained, llava/model/builder.py::load_pretrained_model, llava/model/builder.py::load_pretrained_model->BitsAndBytesConfig, llava/model/builder.py::load_pretrained_model->Parameter, llava/model/builder.py::load_pretrained_model->add_tokens, llava/model/builder.py::load_pretrained_model->any, llava/model/builder.py::load_pretrained_model->copyfile, llava/model/builder.py::load_pretrained_model->empty, llava/model/builder.py::load_pretrained_model->exists, llava/model/builder.py::load_pretrained_model->from_pretrained, llava/model/builder.py::load_pretrained_model->getattr, llava/model/builder.py::load_pretrained_model->hasattr, llava/model/builder.py::load_pretrained_model->hf_hub_download, llava/model/builder.py::load_pretrained_model->isfile",
    "No author markers were provided; author confirmation is required before claiming method intent."
  ]
}
```

## Claim Evidence Map
```json
{
  "claims": [
    {
      "claim_id": "C1",
      "claim_text": "The pipeline prepares translation data by converting raw corpora into tokenized, filtered, vocabulary-backed serialized training artifacts.",
      "support_status": "supported",
      "evidence_ids": [
        "E1418",
        "E1419",
        "E1420",
        "E1421",
        "E1422",
        "E1423",
        "E1424",
        "E2106",
        "E2107",
        "E2108",
        "E2982",
        "E2983",
        "E3074",
        "E3075"
      ],
      "mechanism_ids": [
        "MECH1"
      ],
      "source": "method_mechanism",
      "caveats": []
    },
    {
      "claim_id": "C2",
      "claim_text": "The method computes sequence representations with Transformer encoder/decoder components built from attention and position-wise feed-forward sublayers.",
      "support_status": "supported",
      "evidence_ids": [
        "E107",
        "E108",
        "E110",
        "E111",
        "E112",
        "E113",
        "E114",
        "E115",
        "E116",
        "E117",
        "E118",
        "E119",
        "E120",
        "E121",
        "E123",
        "E125",
        "E126",
        "E127",
        "E128",
        "E130",
        "E132",
        "E133",
        "E134",
        "E135",
        "E137",
        "E138",
        "E139",
        "E141",
        "E142",
        "E144",
        "E145",
        "E146",
        "E147",
        "E148",
        "E149",
        "E150",
        "E152",
        "E153",
        "E154",
        "E155",
        "E156",
        "E157",
        "E158",
        "E159",
        "E160",
        "E161",
        "E162",
        "E163",
        "E164",
        "E166",
        "E167",
        "E168",
        "E169",
        "E170",
        "E171",
        "E172",
        "E174",
        "E175",
        "E176",
        "E411",
        "E440",
        "E454",
        "E470",
        "E471",
        "E472",
        "E473",
        "E474",
        "E475",
        "E476",
        "E477",
        "E478",
        "E511",
        "E512",
        "E513",
        "E514",
        "E515",
        "E516",
        "E517",
        "E518",
        "E519",
        "E552",
        "E553",
        "E554",
        "E555",
        "E556",
        "E557",
        "E558",
        "E559",
        "E560",
        "E561",
        "E589",
        "E590",
        "E591",
        "E592",
        "E593",
        "E594",
        "E595",
        "E596",
        "E597",
        "E650",
        "E651",
        "E652",
        "E653",
        "E654",
        "E656",
        "E658",
        "E659",
        "E660",
        "E661",
        "E662",
        "E663",
        "E664",
        "E722",
        "E732",
        "E733",
        "E739",
        "E740",
        "E741",
        "E742",
        "E743",
        "E744",
        "E745",
        "E746",
        "E747",
        "E748",
        "E749",
        "E750",
        "E751",
        "E752",
        "E753",
        "E754",
        "E755",
        "E756",
        "E848",
        "E850",
        "E852",
        "E854",
        "E856",
        "E858",
        "E859",
        "E860",
        "E861",
        "E862",
        "E864",
        "E865",
        "E866",
        "E868",
        "E869",
        "E870",
        "E872",
        "E873",
        "E874",
        "E964",
        "E965",
        "E966",
        "E967",
        "E968",
        "E969",
        "E970",
        "E971",
        "E972",
        "E973",
        "E974",
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1016",
        "E1017",
        "E1018",
        "E1020",
        "E1022",
        "E1023",
        "E1024",
        "E1026",
        "E1028",
        "E1029",
        "E1030",
        "E1031",
        "E1032",
        "E1033",
        "E1034",
        "E1035",
        "E1122",
        "E1123",
        "E1124",
        "E1125",
        "E1126",
        "E1127",
        "E1128",
        "E1129",
        "E1130",
        "E1131",
        "E1132",
        "E1133",
        "E1197",
        "E1401",
        "E1409",
        "E1639",
        "E1640",
        "E1642",
        "E1643",
        "E1644",
        "E1646",
        "E1709",
        "E1710",
        "E1712",
        "E1713",
        "E1714",
        "E1715",
        "E1717",
        "E1799",
        "E1800",
        "E1801",
        "E1802",
        "E1803",
        "E1804",
        "E1805",
        "E1806",
        "E1807",
        "E1808",
        "E1809",
        "E1810",
        "E1811",
        "E1869",
        "E1870",
        "E1871",
        "E1893",
        "E1910",
        "E2001",
        "E2004",
        "E2036",
        "E2037",
        "E2038",
        "E2039",
        "E2040",
        "E2041",
        "E2070",
        "E2071",
        "E2078",
        "E2079",
        "E2089",
        "E2090",
        "E2091",
        "E2092",
        "E2093",
        "E2094",
        "E2095",
        "E2096",
        "E2097",
        "E2098",
        "E2099",
        "E2101",
        "E2102",
        "E2103",
        "E2104",
        "E2105",
        "E2106",
        "E2107",
        "E2108",
        "E2175",
        "E2176",
        "E2177",
        "E2179",
        "E2373",
        "E2456",
        "E2464",
        "E2552",
        "E2554",
        "E2639",
        "E2640",
        "E2641",
        "E2642",
        "E2643",
        "E2644",
        "E2645",
        "E2646",
        "E2647",
        "E2739",
        "E2740",
        "E3298",
        "E3309",
        "E3359",
        "E3363",
        "E3367",
        "E3371",
        "E3376",
        "E3381",
        "E3387",
        "E3392",
        "E3694",
        "E3695",
        "E3696",
        "E3697",
        "E3698",
        "E3699",
        "E3700",
        "E3701",
        "E3703",
        "E3704",
        "E3705",
        "E3707",
        "E3708"
      ],
      "mechanism_ids": [
        "MECH2"
      ],
      "source": "method_mechanism",
      "caveats": []
    },
    {
      "claim_id": "C3",
      "claim_text": "Phi3RMSNorm exposes generic code behaviors: normalization. Detected implementation patterns include layer normalization.",
      "support_status": "supported",
      "evidence_ids": [
        "E107"
      ],
      "mechanism_ids": [
        "MECH2"
      ],
      "source": "submechanism:SUBMECH1",
      "caveats": []
    },
    {
      "claim_id": "C4",
      "claim_text": "Phi3RotaryEmbedding exposes generic code behaviors: representation injection. Detected implementation patterns include sinusoidal positional encoding.",
      "support_status": "supported",
      "evidence_ids": [
        "E112"
      ],
      "mechanism_ids": [
        "MECH2"
      ],
      "source": "submechanism:SUBMECH2",
      "caveats": []
    },
    {
      "claim_id": "C5",
      "claim_text": "Phi3SuScaledRotaryEmbedding exposes generic code behaviors: representation injection. Detected implementation patterns include sinusoidal positional encoding.",
      "support_status": "supported",
      "evidence_ids": [
        "E115"
      ],
      "mechanism_ids": [
        "MECH2"
      ],
      "source": "submechanism:SUBMECH3",
      "caveats": []
    },
    {
      "claim_id": "C6",
      "claim_text": "Phi3YarnScaledRotaryEmbedding exposes generic code behaviors: representation injection. Detected implementation patterns include sinusoidal positional encoding.",
      "support_status": "supported",
      "evidence_ids": [
        "E118"
      ],
      "mechanism_ids": [
        "MECH2"
      ],
      "source": "submechanism:SUBMECH4",
      "caveats": []
    },
    {
      "claim_id": "C7",
      "claim_text": "apply_rotary_pos_emb exposes generic code behaviors: representation injection. Detected implementation patterns include sinusoidal positional encoding.",
      "support_status": "supported",
      "evidence_ids": [
        "E123"
      ],
      "mechanism_ids": [
        "MECH2"
      ],
      "source": "submechanism:SUBMECH5",
      "caveats": []
    },
    {
      "claim_id": "C8",
      "claim_text": "Phi3Attention exposes generic code behaviors: weighted aggregation, representation injection, regularization. Detected implementation patterns include scaled dot product attention, sinusoidal positional encoding, dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E130"
      ],
      "mechanism_ids": [
        "MECH2"
      ],
      "source": "submechanism:SUBMECH6",
      "caveats": []
    },
    {
      "claim_id": "C9",
      "claim_text": "Phi3FlashAttention2 exposes generic code behaviors: normalization, representation injection, regularization. Detected implementation patterns include layer normalization, sinusoidal positional encoding, dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E135"
      ],
      "mechanism_ids": [
        "MECH2"
      ],
      "source": "submechanism:SUBMECH7",
      "caveats": []
    },
    {
      "claim_id": "C10",
      "claim_text": "Phi3SdpaAttention exposes generic code behaviors: representation injection, regularization. Detected implementation patterns include sinusoidal positional encoding, dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E142"
      ],
      "mechanism_ids": [
        "MECH2"
      ],
      "source": "submechanism:SUBMECH8",
      "caveats": []
    },
    {
      "claim_id": "C11",
      "claim_text": "Phi3DecoderLayer exposes generic code behaviors: skip connection, normalization, regularization. Detected implementation patterns include residual connection, layer normalization, dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E145"
      ],
      "mechanism_ids": [
        "MECH2"
      ],
      "source": "submechanism:SUBMECH9",
      "caveats": []
    },
    {
      "claim_id": "C12",
      "claim_text": "Phi3Model exposes generic code behaviors: repeated composition, regularization. Detected implementation patterns include decoder stack, dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E150"
      ],
      "mechanism_ids": [
        "MECH2"
      ],
      "source": "submechanism:SUBMECH10",
      "caveats": []
    },
    {
      "claim_id": "C13",
      "claim_text": "Phi3ForTokenClassification exposes generic code behaviors: regularization. Detected implementation patterns include dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E174"
      ],
      "mechanism_ids": [
        "MECH2"
      ],
      "source": "submechanism:SUBMECH11",
      "caveats": []
    },
    {
      "claim_id": "C14",
      "claim_text": "PatchDropout exposes generic code behaviors: regularization. Detected implementation patterns include dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E856"
      ],
      "mechanism_ids": [
        "MECH2"
      ],
      "source": "submechanism:SUBMECH12",
      "caveats": []
    },
    {
      "claim_id": "C15",
      "claim_text": "PointcloudEncoder exposes generic code behaviors: pointwise transformation, regularization. Detected implementation patterns include positionwise feed forward, dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E872"
      ],
      "mechanism_ids": [
        "MECH2"
      ],
      "source": "submechanism:SUBMECH13",
      "caveats": []
    },
    {
      "claim_id": "C16",
      "claim_text": "SimpleResBlock exposes generic code behaviors: pointwise transformation, normalization. Detected implementation patterns include positionwise feed forward, layer normalization.",
      "support_status": "supported",
      "evidence_ids": [
        "E968"
      ],
      "mechanism_ids": [
        "MECH2"
      ],
      "source": "submechanism:SUBMECH14",
      "caveats": []
    },
    {
      "claim_id": "C17",
      "claim_text": "Mlp exposes generic code behaviors: pointwise transformation, normalization, regularization. Detected implementation patterns include positionwise feed forward, layer normalization, dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E971"
      ],
      "mechanism_ids": [
        "MECH2"
      ],
      "source": "submechanism:SUBMECH15",
      "caveats": []
    },
    {
      "claim_id": "C18",
      "claim_text": "build_vision_projector exposes generic code behaviors: pointwise transformation. Detected implementation patterns include positionwise feed forward.",
      "support_status": "supported",
      "evidence_ids": [
        "E974"
      ],
      "mechanism_ids": [
        "MECH2"
      ],
      "source": "submechanism:SUBMECH16",
      "caveats": []
    },
    {
      "claim_id": "C19",
      "claim_text": "disable_torch_init exposes generic code behaviors: normalization. Detected implementation patterns include layer normalization.",
      "support_status": "supported",
      "evidence_ids": [
        "E1018"
      ],
      "mechanism_ids": [
        "MECH2"
      ],
      "source": "submechanism:SUBMECH17",
      "caveats": []
    },
    {
      "claim_id": "C20",
      "claim_text": "PointLLMLlamaModel exposes generic code behaviors: pointwise transformation. Detected implementation patterns include positionwise feed forward.",
      "support_status": "supported",
      "evidence_ids": [
        "E1800"
      ],
      "mechanism_ids": [
        "MECH2"
      ],
      "source": "submechanism:SUBMECH18",
      "caveats": []
    },
    {
      "claim_id": "C21",
      "claim_text": "PointNet2SemSegMSG exposes generic code behaviors: regularization. Detected implementation patterns include dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E2078"
      ],
      "mechanism_ids": [
        "MECH2"
      ],
      "source": "submechanism:SUBMECH19",
      "caveats": []
    },
    {
      "claim_id": "C22",
      "claim_text": "PointNet2ClassificationSSG exposes generic code behaviors: pointwise transformation, regularization. Detected implementation patterns include positionwise feed forward, dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E2095"
      ],
      "mechanism_ids": [
        "MECH2"
      ],
      "source": "submechanism:SUBMECH20",
      "caveats": []
    },
    {
      "claim_id": "C23",
      "claim_text": "PointNet2SemSegSSG exposes generic code behaviors: regularization. Detected implementation patterns include dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E2175"
      ],
      "mechanism_ids": [
        "MECH2"
      ],
      "source": "submechanism:SUBMECH21",
      "caveats": []
    },
    {
      "claim_id": "C24",
      "claim_text": "Training optimizes model parameters by combining forward prediction, loss computation, backpropagation, and the scheduled learning-rate update.",
      "support_status": "supported",
      "evidence_ids": [
        "E1258",
        "E2104"
      ],
      "mechanism_ids": [
        "MECH3"
      ],
      "source": "method_mechanism",
      "caveats": []
    },
    {
      "claim_id": "C25",
      "claim_text": "Equation candidate Periodic Positional Encoding: \\mathrm{PE}_{(pos,2i)}=\\sin(pos/10000^{2i/d}),\\quad \\mathrm{PE}_{(pos,2i+1)}=\\cos(pos/10000^{2i/d})",
      "support_status": "supported",
      "evidence_ids": [
        "E112"
      ],
      "mechanism_ids": [],
      "source": "equation_candidate:EQ1",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "claim_id": "C26",
      "claim_text": "Equation candidate Periodic Positional Encoding: \\mathrm{PE}_{(pos,2i)}=\\sin(pos/10000^{2i/d}),\\quad \\mathrm{PE}_{(pos,2i+1)}=\\cos(pos/10000^{2i/d})",
      "support_status": "supported",
      "evidence_ids": [
        "E115"
      ],
      "mechanism_ids": [],
      "source": "equation_candidate:EQ2",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "claim_id": "C27",
      "claim_text": "Equation candidate Periodic Positional Encoding: \\mathrm{PE}_{(pos,2i)}=\\sin(pos/10000^{2i/d}),\\quad \\mathrm{PE}_{(pos,2i+1)}=\\cos(pos/10000^{2i/d})",
      "support_status": "supported",
      "evidence_ids": [
        "E118"
      ],
      "mechanism_ids": [],
      "source": "equation_candidate:EQ3",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "claim_id": "C28",
      "claim_text": "Equation candidate Periodic Positional Encoding: \\mathrm{PE}_{(pos,2i)}=\\sin(pos/10000^{2i/d}),\\quad \\mathrm{PE}_{(pos,2i+1)}=\\cos(pos/10000^{2i/d})",
      "support_status": "supported",
      "evidence_ids": [
        "E123"
      ],
      "mechanism_ids": [],
      "source": "equation_candidate:EQ4",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "claim_id": "C29",
      "claim_text": "Equation candidate Scaled Dot-Product Attention: \\mathrm{Attention}(Q,K,V)=\\mathrm{softmax}(QK^T/\\sqrt{d_k})V",
      "support_status": "supported",
      "evidence_ids": [
        "E130"
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
        "E130"
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
        "E135"
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
        "E142"
      ],
      "mechanism_ids": [],
      "source": "equation_candidate:EQ8",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "claim_id": "C33",
      "claim_text": "Equation candidate Point-wise Feed-Forward Transformation: \\mathrm{FFN}(x)=\\sigma(xW_1+b_1)W_2+b_2",
      "support_status": "supported",
      "evidence_ids": [
        "E872"
      ],
      "mechanism_ids": [],
      "source": "equation_candidate:EQ9",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "claim_id": "C34",
      "claim_text": "Equation candidate Point-wise Feed-Forward Transformation: \\mathrm{FFN}(x)=\\sigma(xW_1+b_1)W_2+b_2",
      "support_status": "supported",
      "evidence_ids": [
        "E968"
      ],
      "mechanism_ids": [],
      "source": "equation_candidate:EQ10",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "claim_id": "C35",
      "claim_text": "Equation candidate Point-wise Feed-Forward Transformation: \\mathrm{FFN}(x)=\\sigma(xW_1+b_1)W_2+b_2",
      "support_status": "supported",
      "evidence_ids": [
        "E971"
      ],
      "mechanism_ids": [],
      "source": "equation_candidate:EQ11",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "claim_id": "C36",
      "claim_text": "Equation candidate Point-wise Feed-Forward Transformation: \\mathrm{FFN}(x)=\\sigma(xW_1+b_1)W_2+b_2",
      "support_status": "supported",
      "evidence_ids": [
        "E974"
      ],
      "mechanism_ids": [],
      "source": "equation_candidate:EQ12",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "claim_id": "C37",
      "claim_text": "Equation candidate Point-wise Feed-Forward Transformation: \\mathrm{FFN}(x)=\\sigma(xW_1+b_1)W_2+b_2",
      "support_status": "supported",
      "evidence_ids": [
        "E1800"
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
        "E2095"
      ],
      "mechanism_ids": [],
      "source": "equation_candidate:EQ14",
      "caveats": [
        "Generated from a recognized code pattern; verify notation before paper submission."
      ]
    },
    {
      "claim_id": "C39",
      "claim_text": "The method contains a paper-facing stage named Input Preparation.",
      "support_status": "supported",
      "evidence_ids": [
        "E1418",
        "E1419",
        "E1420",
        "E1421",
        "E1422",
        "E1423",
        "E1424",
        "E2106",
        "E2107",
        "E2108",
        "E2982",
        "E2983",
        "E3074",
        "E3075"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C1",
      "caveats": []
    },
    {
      "claim_id": "C40",
      "claim_text": "The method contains a paper-facing stage named Transformer Computation.",
      "support_status": "supported",
      "evidence_ids": [
        "E107",
        "E108",
        "E110",
        "E111",
        "E112",
        "E113",
        "E114",
        "E115",
        "E116",
        "E117",
        "E118",
        "E119",
        "E120",
        "E121",
        "E123",
        "E125",
        "E126",
        "E127",
        "E128",
        "E130",
        "E132",
        "E133",
        "E134",
        "E135",
        "E137",
        "E138",
        "E139",
        "E141",
        "E142",
        "E144",
        "E145",
        "E146",
        "E147",
        "E148",
        "E149",
        "E150",
        "E152",
        "E153",
        "E154",
        "E155",
        "E156",
        "E157",
        "E158",
        "E159",
        "E160",
        "E161",
        "E162",
        "E163",
        "E164",
        "E166",
        "E167",
        "E168",
        "E169",
        "E170",
        "E171",
        "E172",
        "E174",
        "E175",
        "E176",
        "E411",
        "E440",
        "E454",
        "E470",
        "E471",
        "E472",
        "E473",
        "E474",
        "E475",
        "E476",
        "E477",
        "E478",
        "E511",
        "E512",
        "E513",
        "E514",
        "E515",
        "E516",
        "E517",
        "E518",
        "E519",
        "E552",
        "E553",
        "E554",
        "E555",
        "E556",
        "E557",
        "E558",
        "E559",
        "E560",
        "E561",
        "E589",
        "E590",
        "E591",
        "E592",
        "E593",
        "E594",
        "E595",
        "E596",
        "E597",
        "E650",
        "E651",
        "E652",
        "E653",
        "E654",
        "E656",
        "E658",
        "E659",
        "E660",
        "E661",
        "E662",
        "E663",
        "E664",
        "E722",
        "E732",
        "E733",
        "E739",
        "E740",
        "E741",
        "E742",
        "E743",
        "E744",
        "E745",
        "E746",
        "E747",
        "E748",
        "E749",
        "E750",
        "E751",
        "E752",
        "E753",
        "E754",
        "E755",
        "E756",
        "E848",
        "E850",
        "E852",
        "E854",
        "E856",
        "E858",
        "E859",
        "E860",
        "E861",
        "E862",
        "E864",
        "E865",
        "E866",
        "E868",
        "E869",
        "E870",
        "E872",
        "E873",
        "E874",
        "E964",
        "E965",
        "E966",
        "E967",
        "E968",
        "E969",
        "E970",
        "E971",
        "E972",
        "E973",
        "E974",
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1016",
        "E1017",
        "E1018",
        "E1020",
        "E1022",
        "E1023",
        "E1024",
        "E1026",
        "E1028",
        "E1029",
        "E1030",
        "E1031",
        "E1032",
        "E1033",
        "E1034",
        "E1035",
        "E1122",
        "E1123",
        "E1124",
        "E1125",
        "E1126",
        "E1127",
        "E1128",
        "E1129",
        "E1130",
        "E1131",
        "E1132",
        "E1133",
        "E1197",
        "E1401",
        "E1409",
        "E1639",
        "E1640",
        "E1642",
        "E1643",
        "E1644",
        "E1646",
        "E1709",
        "E1710",
        "E1712",
        "E1713",
        "E1714",
        "E1715",
        "E1717",
        "E1799",
        "E1800",
        "E1801",
        "E1802",
        "E1803",
        "E1804",
        "E1805",
        "E1806",
        "E1807",
        "E1808",
        "E1809",
        "E1810",
        "E1811",
        "E1869",
        "E1870",
        "E1871",
        "E1893",
        "E1910",
        "E2001",
        "E2004",
        "E2036",
        "E2037",
        "E2038",
        "E2039",
        "E2040",
        "E2041",
        "E2070",
        "E2071",
        "E2078",
        "E2079",
        "E2089",
        "E2090",
        "E2091",
        "E2092",
        "E2093",
        "E2094",
        "E2095",
        "E2096",
        "E2097",
        "E2098",
        "E2099",
        "E2101",
        "E2102",
        "E2103",
        "E2104",
        "E2105",
        "E2106",
        "E2107",
        "E2108",
        "E2175",
        "E2176",
        "E2177",
        "E2179",
        "E2373",
        "E2456",
        "E2464",
        "E2552",
        "E2554",
        "E2639",
        "E2640",
        "E2641",
        "E2642",
        "E2643",
        "E2644",
        "E2645",
        "E2646",
        "E2647",
        "E2739",
        "E2740",
        "E3298",
        "E3309",
        "E3359",
        "E3363",
        "E3367",
        "E3371",
        "E3376",
        "E3381",
        "E3387",
        "E3392",
        "E3694",
        "E3695",
        "E3696",
        "E3697",
        "E3698",
        "E3699",
        "E3700",
        "E3701",
        "E3703",
        "E3704",
        "E3705",
        "E3707",
        "E3708"
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
        "E1258",
        "E2104"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C3",
      "caveats": []
    },
    {
      "claim_id": "C42",
      "claim_text": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E107",
        "E108",
        "E111",
        "E112",
        "E113",
        "E115",
        "E116",
        "E118",
        "E119",
        "E121",
        "E123",
        "E125",
        "E126",
        "E128",
        "E150",
        "E152",
        "E153",
        "E154",
        "E156",
        "E157",
        "E158",
        "E159",
        "E160",
        "E161",
        "E166",
        "E167",
        "E168",
        "E169",
        "E170",
        "E171"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C4",
      "caveats": []
    },
    {
      "claim_id": "C43",
      "claim_text": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py implements model computation block.",
      "support_status": "supported",
      "evidence_ids": [
        "E110",
        "E114",
        "E117",
        "E120",
        "E127",
        "E130",
        "E132",
        "E133",
        "E134",
        "E135",
        "E137",
        "E138",
        "E139",
        "E141",
        "E142",
        "E144",
        "E145",
        "E146",
        "E147",
        "E155",
        "E162",
        "E163",
        "E164",
        "E172",
        "E176"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C5",
      "caveats": []
    },
    {
      "claim_id": "C44",
      "claim_text": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py implements data preparation and loading.",
      "support_status": "supported",
      "evidence_ids": [
        "E174",
        "E175"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C6",
      "caveats": []
    },
    {
      "claim_id": "C45",
      "claim_text": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/modeling_phi3.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E178",
        "E179",
        "E180",
        "E181",
        "E182",
        "E183",
        "E184",
        "E185",
        "E186",
        "E187",
        "E188",
        "E189",
        "E190",
        "E191",
        "E192",
        "E193",
        "E194",
        "E195",
        "E196",
        "E197",
        "E198",
        "E199",
        "E200",
        "E201",
        "E202",
        "E203",
        "E204",
        "E205",
        "E206",
        "E207",
        "E208",
        "E209",
        "E210",
        "E211",
        "E212",
        "E213",
        "E214",
        "E215",
        "E216",
        "E217",
        "E218",
        "E219",
        "E220",
        "E221",
        "E222",
        "E223",
        "E224",
        "E225",
        "E226",
        "E227",
        "E228",
        "E229",
        "E230",
        "E231",
        "E232",
        "E233",
        "E234",
        "E235",
        "E236",
        "E237",
        "E238",
        "E239",
        "E240",
        "E241",
        "E242",
        "E243",
        "E244",
        "E245",
        "E246",
        "E247",
        "E248",
        "E249",
        "E250",
        "E251",
        "E252",
        "E253",
        "E254",
        "E255",
        "E256",
        "E257",
        "E258",
        "E259",
        "E260",
        "E261",
        "E262",
        "E263",
        "E264",
        "E265",
        "E266",
        "E267",
        "E268",
        "E269",
        "E270",
        "E271",
        "E272",
        "E273",
        "E274",
        "E275",
        "E276",
        "E277",
        "E278",
        "E279",
        "E280",
        "E281",
        "E282",
        "E283",
        "E284",
        "E285",
        "E286",
        "E287",
        "E288",
        "E289",
        "E290",
        "E291",
        "E292",
        "E293",
        "E294",
        "E295",
        "E296",
        "E297",
        "E298",
        "E299",
        "E300",
        "E301",
        "E302",
        "E303",
        "E304",
        "E305",
        "E306",
        "E307",
        "E308",
        "E309",
        "E310",
        "E311",
        "E312",
        "E313",
        "E314",
        "E315",
        "E316",
        "E317",
        "E321",
        "E322",
        "E323",
        "E324",
        "E325",
        "E326",
        "E327",
        "E328",
        "E329",
        "E330",
        "E331",
        "E332",
        "E333",
        "E334",
        "E335",
        "E336",
        "E337",
        "E338",
        "E339",
        "E340",
        "E341",
        "E342",
        "E343",
        "E344",
        "E345",
        "E346",
        "E347",
        "E348",
        "E349",
        "E350",
        "E351",
        "E352",
        "E353",
        "E354",
        "E355",
        "E356",
        "E357",
        "E358",
        "E359",
        "E360",
        "E361",
        "E362",
        "E363",
        "E364",
        "E365",
        "E366",
        "E367",
        "E368",
        "E369",
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
        "E381",
        "E382",
        "E383",
        "E384",
        "E385",
        "E386",
        "E387",
        "E388",
        "E389",
        "E390",
        "E391",
        "E392",
        "E393",
        "E394",
        "E395",
        "E396",
        "E397",
        "E398",
        "E399",
        "E400",
        "E401",
        "E402"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C7",
      "caveats": []
    },
    {
      "claim_id": "C46",
      "claim_text": "llava/model/apply_delta.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E411"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C8",
      "caveats": []
    },
    {
      "claim_id": "C47",
      "claim_text": "llava/model/apply_delta.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E413",
        "E414",
        "E416",
        "E417"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C9",
      "caveats": []
    },
    {
      "claim_id": "C48",
      "claim_text": "llava/model/consolidate.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E454"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C10",
      "caveats": []
    },
    {
      "claim_id": "C49",
      "claim_text": "llava/model/consolidate.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E455",
        "E457"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C11",
      "caveats": []
    },
    {
      "claim_id": "C50",
      "claim_text": "llava/model/language_model/llava_llama.py implements configuration and runtime wiring.",
      "support_status": "supported",
      "evidence_ids": [
        "E470"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C12",
      "caveats": []
    },
    {
      "claim_id": "C51",
      "claim_text": "llava/model/language_model/llava_llama.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E471",
        "E472",
        "E473",
        "E474",
        "E475",
        "E477",
        "E478"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C13",
      "caveats": []
    },
    {
      "claim_id": "C52",
      "claim_text": "llava/model/language_model/llava_llama.py implements model computation block.",
      "support_status": "supported",
      "evidence_ids": [
        "E476"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C14",
      "caveats": []
    },
    {
      "claim_id": "C53",
      "claim_text": "llava/model/language_model/llava_llama.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E479",
        "E480",
        "E481",
        "E482",
        "E483",
        "E484",
        "E485",
        "E486",
        "E487",
        "E488",
        "E489",
        "E490",
        "E491",
        "E492",
        "E493",
        "E494",
        "E495",
        "E496",
        "E497",
        "E498",
        "E499"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C15",
      "caveats": []
    },
    {
      "claim_id": "C54",
      "claim_text": "llava/model/language_model/llava_mistral.py implements configuration and runtime wiring.",
      "support_status": "supported",
      "evidence_ids": [
        "E511"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C16",
      "caveats": []
    },
    {
      "claim_id": "C55",
      "claim_text": "llava/model/language_model/llava_mistral.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E512",
        "E513",
        "E514",
        "E515",
        "E516",
        "E518",
        "E519"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C17",
      "caveats": []
    },
    {
      "claim_id": "C56",
      "claim_text": "llava/model/language_model/llava_mistral.py implements model computation block.",
      "support_status": "supported",
      "evidence_ids": [
        "E517"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C18",
      "caveats": []
    },
    {
      "claim_id": "C57",
      "claim_text": "llava/model/language_model/llava_mistral.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E520",
        "E521",
        "E522",
        "E523",
        "E524",
        "E525",
        "E526",
        "E527",
        "E528",
        "E529",
        "E530",
        "E531",
        "E532",
        "E533",
        "E534",
        "E535",
        "E536",
        "E537",
        "E538",
        "E539",
        "E540"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C19",
      "caveats": []
    },
    {
      "claim_id": "C58",
      "claim_text": "llava/model/language_model/llava_mpt.py implements configuration and runtime wiring.",
      "support_status": "supported",
      "evidence_ids": [
        "E552"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C20",
      "caveats": []
    },
    {
      "claim_id": "C59",
      "claim_text": "llava/model/language_model/llava_mpt.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E553",
        "E554",
        "E556",
        "E557",
        "E558",
        "E561"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C21",
      "caveats": []
    },
    {
      "claim_id": "C60",
      "claim_text": "llava/model/language_model/llava_mpt.py implements data preparation and loading.",
      "support_status": "supported",
      "evidence_ids": [
        "E555"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C22",
      "caveats": []
    },
    {
      "claim_id": "C61",
      "claim_text": "llava/model/language_model/llava_mpt.py implements optimization and objective logic.",
      "support_status": "supported",
      "evidence_ids": [
        "E559"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C23",
      "caveats": []
    },
    {
      "claim_id": "C62",
      "claim_text": "llava/model/language_model/llava_mpt.py implements model computation block.",
      "support_status": "supported",
      "evidence_ids": [
        "E560"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C24",
      "caveats": []
    },
    {
      "claim_id": "C63",
      "claim_text": "llava/model/language_model/llava_mpt.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E562",
        "E563",
        "E564",
        "E565",
        "E566",
        "E567",
        "E568",
        "E569",
        "E570",
        "E571",
        "E572",
        "E573",
        "E574",
        "E575",
        "E576"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C25",
      "caveats": []
    },
    {
      "claim_id": "C64",
      "claim_text": "llava/model/language_model/llava_phi3.py implements configuration and runtime wiring.",
      "support_status": "supported",
      "evidence_ids": [
        "E589"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C26",
      "caveats": []
    },
    {
      "claim_id": "C65",
      "claim_text": "llava/model/language_model/llava_phi3.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E590",
        "E591",
        "E592",
        "E593",
        "E594",
        "E596",
        "E597"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C27",
      "caveats": []
    },
    {
      "claim_id": "C66",
      "claim_text": "llava/model/language_model/llava_phi3.py implements model computation block.",
      "support_status": "supported",
      "evidence_ids": [
        "E595"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C28",
      "caveats": []
    },
    {
      "claim_id": "C67",
      "claim_text": "llava/model/language_model/llava_phi3.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E598",
        "E599",
        "E600",
        "E601",
        "E602",
        "E603",
        "E604",
        "E605",
        "E606",
        "E607",
        "E608",
        "E609",
        "E610",
        "E611",
        "E612",
        "E613",
        "E614",
        "E615",
        "E616",
        "E617",
        "E618",
        "E619"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C29",
      "caveats": []
    },
    {
      "claim_id": "C68",
      "claim_text": "llava/model/llava_arch.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E650",
        "E651",
        "E652",
        "E653",
        "E654",
        "E656",
        "E658",
        "E659",
        "E660",
        "E661",
        "E662",
        "E663"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C30",
      "caveats": []
    },
    {
      "claim_id": "C69",
      "claim_text": "llava/model/llava_arch.py implements data preparation and loading.",
      "support_status": "supported",
      "evidence_ids": [
        "E664"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C31",
      "caveats": []
    },
    {
      "claim_id": "C70",
      "claim_text": "llava/model/llava_arch.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E665",
        "E666",
        "E667",
        "E668",
        "E669",
        "E670",
        "E671",
        "E672",
        "E673",
        "E674",
        "E675",
        "E676",
        "E677",
        "E680",
        "E681",
        "E682",
        "E683",
        "E684",
        "E685",
        "E686",
        "E687",
        "E688",
        "E689",
        "E690",
        "E691",
        "E692",
        "E693",
        "E694",
        "E695",
        "E696",
        "E697",
        "E698",
        "E699",
        "E700",
        "E701",
        "E702",
        "E703",
        "E704",
        "E705",
        "E706",
        "E707",
        "E708",
        "E709",
        "E710",
        "E711",
        "E712",
        "E713",
        "E714",
        "E715",
        "E716",
        "E718",
        "E719",
        "E720"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C32",
      "caveats": []
    },
    {
      "claim_id": "C71",
      "claim_text": "llava/model/make_delta.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E722"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C33",
      "caveats": []
    },
    {
      "claim_id": "C72",
      "claim_text": "llava/model/make_delta.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E723",
        "E725",
        "E726",
        "E728",
        "E729"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C34",
      "caveats": []
    },
    {
      "claim_id": "C73",
      "claim_text": "llava/model/multimodal_encoder/builder.py implements model computation block.",
      "support_status": "supported",
      "evidence_ids": [
        "E732",
        "E733"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C35",
      "caveats": []
    },
    {
      "claim_id": "C74",
      "claim_text": "llava/model/multimodal_encoder/builder.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E734",
        "E735",
        "E736",
        "E737"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C36",
      "caveats": []
    },
    {
      "claim_id": "C75",
      "claim_text": "llava/model/multimodal_encoder/clip_encoder.py implements model computation block.",
      "support_status": "supported",
      "evidence_ids": [
        "E739",
        "E740",
        "E742",
        "E743",
        "E744",
        "E745",
        "E746",
        "E747",
        "E748",
        "E749",
        "E750",
        "E751",
        "E752",
        "E754",
        "E755",
        "E756"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C37",
      "caveats": []
    },
    {
      "claim_id": "C76",
      "claim_text": "llava/model/multimodal_encoder/clip_encoder.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E757",
        "E758",
        "E759",
        "E761",
        "E766",
        "E767",
        "E768",
        "E769",
        "E770",
        "E771",
        "E772",
        "E773",
        "E774",
        "E775",
        "E776",
        "E777",
        "E778",
        "E779",
        "E780",
        "E781",
        "E782",
        "E787",
        "E788",
        "E789",
        "E790",
        "E791",
        "E792",
        "E793",
        "E794",
        "E795",
        "E796"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C38",
      "caveats": []
    },
    {
      "claim_id": "C77",
      "claim_text": "llava/model/multimodal_encoder/point_encoder.py implements model computation block.",
      "support_status": "supported",
      "evidence_ids": [
        "E848",
        "E850",
        "E852",
        "E854",
        "E856",
        "E858",
        "E859",
        "E860",
        "E861",
        "E862",
        "E864",
        "E865",
        "E866",
        "E868",
        "E869",
        "E870",
        "E872",
        "E873",
        "E874"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C39",
      "caveats": []
    },
    {
      "claim_id": "C78",
      "claim_text": "llava/model/multimodal_encoder/point_encoder.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E875",
        "E876",
        "E877",
        "E878",
        "E879",
        "E880",
        "E881",
        "E882",
        "E883",
        "E884",
        "E885",
        "E886",
        "E887",
        "E888",
        "E889",
        "E890",
        "E891",
        "E892",
        "E893",
        "E894",
        "E895",
        "E896",
        "E897",
        "E898",
        "E899",
        "E900",
        "E901",
        "E902",
        "E903",
        "E904",
        "E905",
        "E906",
        "E907",
        "E908",
        "E909",
        "E910",
        "E911",
        "E912",
        "E913",
        "E914",
        "E915",
        "E916",
        "E917",
        "E918",
        "E919",
        "E920",
        "E921",
        "E922",
        "E923",
        "E924",
        "E925",
        "E926",
        "E927",
        "E928",
        "E929",
        "E930",
        "E931",
        "E932",
        "E933",
        "E934",
        "E935",
        "E936",
        "E937",
        "E938",
        "E939",
        "E940",
        "E941",
        "E942",
        "E943",
        "E944",
        "E945",
        "E946",
        "E947",
        "E948",
        "E949",
        "E950",
        "E951",
        "E952",
        "E953",
        "E954",
        "E955",
        "E956",
        "E957",
        "E958",
        "E959",
        "E960",
        "E961",
        "E962",
        "E963"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C40",
      "caveats": []
    },
    {
      "claim_id": "C79",
      "claim_text": "llava/model/multimodal_projector/builder.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E964",
        "E965",
        "E968",
        "E969",
        "E971",
        "E972",
        "E974"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C41",
      "caveats": []
    },
    {
      "claim_id": "C80",
      "claim_text": "llava/model/multimodal_projector/builder.py implements model computation block.",
      "support_status": "supported",
      "evidence_ids": [
        "E966",
        "E970",
        "E973"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C42",
      "caveats": []
    },
    {
      "claim_id": "C81",
      "claim_text": "llava/model/multimodal_projector/builder.py implements configuration and runtime wiring.",
      "support_status": "supported",
      "evidence_ids": [
        "E967"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C43",
      "caveats": []
    },
    {
      "claim_id": "C82",
      "claim_text": "llava/model/multimodal_projector/builder.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E975",
        "E976",
        "E977",
        "E978",
        "E979",
        "E980",
        "E981",
        "E982",
        "E983",
        "E984",
        "E985",
        "E986",
        "E987",
        "E988",
        "E989",
        "E990",
        "E991",
        "E992",
        "E993",
        "E994",
        "E995"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C44",
      "caveats": []
    },
    {
      "claim_id": "C83",
      "claim_text": "llava/model/utils.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017",
        "E1018",
        "E1020",
        "E1022",
        "E1023",
        "E1024",
        "E1026",
        "E1028",
        "E1029"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C45",
      "caveats": []
    },
    {
      "claim_id": "C84",
      "claim_text": "llava/model/utils.py implements data preparation and loading.",
      "support_status": "supported",
      "evidence_ids": [
        "E1030",
        "E1031",
        "E1032",
        "E1033",
        "E1034",
        "E1035"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C46",
      "caveats": []
    },
    {
      "claim_id": "C85",
      "claim_text": "llava/model/utils.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E1048",
        "E1052",
        "E1053",
        "E1079",
        "E1080",
        "E1081",
        "E1082",
        "E1083",
        "E1084",
        "E1085",
        "E1086",
        "E1087",
        "E1088",
        "E1089",
        "E1090",
        "E1091",
        "E1092",
        "E1093",
        "E1094",
        "E1095",
        "E1096",
        "E1097",
        "E1098",
        "E1099",
        "E1100",
        "E1101",
        "E1102",
        "E1103",
        "E1104",
        "E1105",
        "E1106",
        "E1107",
        "E1108",
        "E1109",
        "E1110",
        "E1111",
        "E1112",
        "E1113",
        "E1114",
        "E1115",
        "E1116",
        "E1117",
        "E1118",
        "E1119"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C47",
      "caveats": []
    },
    {
      "claim_id": "C86",
      "claim_text": "llava/serve/model_worker.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E1122",
        "E1123",
        "E1124",
        "E1125",
        "E1126",
        "E1127",
        "E1128",
        "E1129",
        "E1130",
        "E1131",
        "E1132",
        "E1133"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C48",
      "caveats": []
    },
    {
      "claim_id": "C87",
      "claim_text": "llava/serve/model_worker.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E1134",
        "E1135",
        "E1137",
        "E1138",
        "E1140",
        "E1141",
        "E1142",
        "E1143",
        "E1144",
        "E1145",
        "E1146",
        "E1147",
        "E1148",
        "E1149",
        "E1150",
        "E1151",
        "E1152",
        "E1153",
        "E1154",
        "E1155",
        "E1156",
        "E1157",
        "E1158",
        "E1160",
        "E1161",
        "E1162",
        "E1163",
        "E1164",
        "E1165",
        "E1166",
        "E1167",
        "E1168",
        "E1169",
        "E1170",
        "E1171",
        "E1172",
        "E1173",
        "E1174",
        "E1175",
        "E1176",
        "E1177",
        "E1178",
        "E1179",
        "E1180",
        "E1181",
        "E1182",
        "E1183",
        "E1184",
        "E1185",
        "E1186",
        "E1187"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C49",
      "caveats": []
    },
    {
      "claim_id": "C88",
      "claim_text": "llava/train/llama_flash_attn_monkey_patch.py implements model computation block.",
      "support_status": "supported",
      "evidence_ids": [
        "E1197"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C50",
      "caveats": []
    },
    {
      "claim_id": "C89",
      "claim_text": "llava/train/llama_flash_attn_monkey_patch.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E1199",
        "E1200",
        "E1201",
        "E1202",
        "E1203",
        "E1204",
        "E1205",
        "E1206",
        "E1207",
        "E1208",
        "E1209",
        "E1210"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C51",
      "caveats": []
    },
    {
      "claim_id": "C90",
      "claim_text": "llava/train/llama_xformers_attn_monkey_patch.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E1225",
        "E1226",
        "E1227",
        "E1228",
        "E1229",
        "E1230",
        "E1231",
        "E1232",
        "E1233",
        "E1234",
        "E1235",
        "E1236"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C52",
      "caveats": []
    },
    {
      "claim_id": "C91",
      "claim_text": "pointllm/data/modelnet.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E1639",
        "E1640",
        "E1642",
        "E1643",
        "E1644",
        "E1646"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C53",
      "caveats": []
    },
    {
      "claim_id": "C92",
      "claim_text": "pointllm/data/modelnet.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E1647",
        "E1648",
        "E1649",
        "E1651",
        "E1652",
        "E1653",
        "E1655",
        "E1656",
        "E1657",
        "E1658",
        "E1659",
        "E1660",
        "E1661",
        "E1662",
        "E1663",
        "E1664",
        "E1665",
        "E1666",
        "E1667",
        "E1668",
        "E1669",
        "E1670",
        "E1671",
        "E1672",
        "E1673",
        "E1674",
        "E1675",
        "E1676",
        "E1677",
        "E1678",
        "E1679"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C54",
      "caveats": []
    },
    {
      "claim_id": "C93",
      "claim_text": "pointllm/data/modelnet_show.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E1709",
        "E1710",
        "E1712",
        "E1713",
        "E1714",
        "E1715",
        "E1717"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C55",
      "caveats": []
    },
    {
      "claim_id": "C94",
      "claim_text": "pointllm/data/modelnet_show.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E1718",
        "E1719",
        "E1720",
        "E1722",
        "E1723",
        "E1724",
        "E1726",
        "E1727",
        "E1728",
        "E1729",
        "E1730",
        "E1731",
        "E1732",
        "E1733",
        "E1734",
        "E1735",
        "E1736",
        "E1737",
        "E1738",
        "E1739",
        "E1740",
        "E1741",
        "E1742",
        "E1743",
        "E1744",
        "E1745",
        "E1746",
        "E1747",
        "E1748",
        "E1749",
        "E1750",
        "E1751",
        "E1752",
        "E1753",
        "E1754",
        "E1755",
        "E1756",
        "E1757",
        "E1758"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C56",
      "caveats": []
    },
    {
      "claim_id": "C95",
      "claim_text": "pointllm/model/pointllm.py implements configuration and runtime wiring.",
      "support_status": "supported",
      "evidence_ids": [
        "E1799"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C57",
      "caveats": []
    },
    {
      "claim_id": "C96",
      "claim_text": "pointllm/model/pointllm.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E1800",
        "E1801",
        "E1804",
        "E1805",
        "E1806",
        "E1807",
        "E1809"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C58",
      "caveats": []
    },
    {
      "claim_id": "C97",
      "claim_text": "pointllm/model/pointllm.py implements model computation block.",
      "support_status": "supported",
      "evidence_ids": [
        "E1803",
        "E1808"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C59",
      "caveats": []
    },
    {
      "claim_id": "C98",
      "claim_text": "pointllm/model/pointllm.py implements data preparation and loading.",
      "support_status": "supported",
      "evidence_ids": [
        "E1810",
        "E1811"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C60",
      "caveats": []
    },
    {
      "claim_id": "C99",
      "claim_text": "pointllm/model/pointllm.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E1812",
        "E1813",
        "E1814",
        "E1815",
        "E1816",
        "E1817",
        "E1818",
        "E1819",
        "E1820",
        "E1821",
        "E1822",
        "E1823",
        "E1824",
        "E1825",
        "E1826",
        "E1827",
        "E1828",
        "E1829",
        "E1830",
        "E1831",
        "E1832",
        "E1833",
        "E1834",
        "E1835",
        "E1836",
        "E1837",
        "E1838",
        "E1839",
        "E1840",
        "E1841",
        "E1842",
        "E1843",
        "E1844",
        "E1845",
        "E1846",
        "E1847",
        "E1848",
        "E1849",
        "E1850",
        "E1851",
        "E1852",
        "E1853",
        "E1854",
        "E1855",
        "E1856",
        "E1857",
        "E1858",
        "E1859",
        "E1860",
        "E1861",
        "E1862",
        "E1863",
        "E1864",
        "E1865",
        "E1866",
        "E1867",
        "E1868"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C61",
      "caveats": []
    },
    {
      "claim_id": "C100",
      "claim_text": "pointllm/model/utils.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E1869",
        "E1870",
        "E1871"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C62",
      "caveats": []
    },
    {
      "claim_id": "C101",
      "claim_text": "pointllm/model/utils.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E1872",
        "E1873",
        "E1874",
        "E1875"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C63",
      "caveats": []
    },
    {
      "claim_id": "C102",
      "claim_text": "pointllm/train/llama_flash_attn_monkey_patch.py implements model computation block.",
      "support_status": "supported",
      "evidence_ids": [
        "E1893"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C64",
      "caveats": []
    },
    {
      "claim_id": "C103",
      "claim_text": "pointllm/train/llama_flash_attn_monkey_patch.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E1895",
        "E1896",
        "E1897",
        "E1898",
        "E1899",
        "E1900",
        "E1901",
        "E1902",
        "E1903",
        "E1904",
        "E1905",
        "E1906"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C65",
      "caveats": []
    },
    {
      "claim_id": "C104",
      "claim_text": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_msg_cls.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E2070",
        "E2071"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C66",
      "caveats": []
    },
    {
      "claim_id": "C105",
      "claim_text": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_msg_cls.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E2072",
        "E2073",
        "E2074",
        "E2075",
        "E2076",
        "E2077"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C67",
      "caveats": []
    },
    {
      "claim_id": "C106",
      "claim_text": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_msg_sem.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E2078",
        "E2079"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C68",
      "caveats": []
    },
    {
      "claim_id": "C107",
      "claim_text": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_msg_sem.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E2080",
        "E2081",
        "E2082",
        "E2083",
        "E2084",
        "E2085",
        "E2086",
        "E2087",
        "E2088"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C69",
      "caveats": []
    },
    {
      "claim_id": "C108",
      "claim_text": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E2089",
        "E2095",
        "E2096",
        "E2097",
        "E2098",
        "E2102",
        "E2103",
        "E2105"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C70",
      "caveats": []
    },
    {
      "claim_id": "C109",
      "claim_text": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py implements optimization and objective logic.",
      "support_status": "supported",
      "evidence_ids": [
        "E2090",
        "E2091",
        "E2092",
        "E2093",
        "E2104"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C71",
      "caveats": []
    },
    {
      "claim_id": "C110",
      "claim_text": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py implements model computation block.",
      "support_status": "supported",
      "evidence_ids": [
        "E2099"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C72",
      "caveats": []
    },
    {
      "claim_id": "C111",
      "claim_text": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_cls.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E2109",
        "E2110",
        "E2111",
        "E2112",
        "E2113",
        "E2114",
        "E2115",
        "E2116",
        "E2117",
        "E2118",
        "E2120",
        "E2121",
        "E2122",
        "E2123",
        "E2124",
        "E2125",
        "E2126",
        "E2127",
        "E2128",
        "E2129",
        "E2130",
        "E2131",
        "E2132",
        "E2133",
        "E2134",
        "E2135",
        "E2136",
        "E2137",
        "E2142",
        "E2145",
        "E2146",
        "E2147",
        "E2148",
        "E2149",
        "E2150",
        "E2151",
        "E2152",
        "E2153",
        "E2154",
        "E2155",
        "E2156",
        "E2157",
        "E2158",
        "E2159",
        "E2160",
        "E2161",
        "E2162",
        "E2163",
        "E2164",
        "E2165",
        "E2166",
        "E2167",
        "E2168",
        "E2169",
        "E2170",
        "E2171"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C73",
      "caveats": []
    },
    {
      "claim_id": "C112",
      "claim_text": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_sem.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E2175",
        "E2176",
        "E2179"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C74",
      "caveats": []
    },
    {
      "claim_id": "C113",
      "claim_text": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_sem.py implements model computation block.",
      "support_status": "supported",
      "evidence_ids": [
        "E2177"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C75",
      "caveats": []
    },
    {
      "claim_id": "C114",
      "claim_text": "pointnet++/Pointnet2_PyTorch/pointnet2/models/pointnet2_ssg_sem.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E2180",
        "E2181",
        "E2182",
        "E2183",
        "E2184",
        "E2185",
        "E2186",
        "E2187",
        "E2188",
        "E2189",
        "E2190",
        "E2191",
        "E2192",
        "E2193",
        "E2194"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C76",
      "caveats": []
    },
    {
      "claim_id": "C115",
      "claim_text": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/configuration_phi3.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E2278",
        "E2279",
        "E2280",
        "E2281",
        "E2282",
        "E2283",
        "E2284",
        "E2285"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C77",
      "caveats": []
    },
    {
      "claim_id": "C116",
      "claim_text": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/sample_finetune.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E2301"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C78",
      "caveats": []
    },
    {
      "claim_id": "C117",
      "claim_text": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/sample_finetune.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E2302",
        "E2303"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C79",
      "caveats": []
    },
    {
      "claim_id": "C118",
      "claim_text": "llava/conversation.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E2320",
        "E2321",
        "E2322",
        "E2323",
        "E2324",
        "E2325",
        "E2326",
        "E2327",
        "E2328",
        "E2329",
        "E2330",
        "E2331",
        "E2332",
        "E2333",
        "E2334",
        "E2335",
        "E2336",
        "E2337",
        "E2338",
        "E2339",
        "E2340",
        "E2341",
        "E2342",
        "E2343",
        "E2344",
        "E2345",
        "E2346",
        "E2347",
        "E2348",
        "E2349",
        "E2350",
        "E2351",
        "E2352",
        "E2353",
        "E2354",
        "E2355",
        "E2356",
        "E2357"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C80",
      "caveats": []
    },
    {
      "claim_id": "C119",
      "claim_text": "llava/mm_utils.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E2427",
        "E2428",
        "E2429",
        "E2430",
        "E2431",
        "E2432",
        "E2433",
        "E2434",
        "E2435",
        "E2436",
        "E2437",
        "E2438",
        "E2439"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C81",
      "caveats": []
    },
    {
      "claim_id": "C120",
      "claim_text": "llava/serve/controller.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E2446",
        "E2447",
        "E2448",
        "E2449",
        "E2450",
        "E2451",
        "E2452",
        "E2453",
        "E2454",
        "E2455",
        "E2456",
        "E2457",
        "E2458",
        "E2460",
        "E2461",
        "E2462",
        "E2463",
        "E2464",
        "E2465",
        "E2466",
        "E2467",
        "E2468"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C82",
      "caveats": []
    },
    {
      "claim_id": "C121",
      "claim_text": "llava/serve/controller.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E2469",
        "E2471",
        "E2473",
        "E2474",
        "E2475",
        "E2476",
        "E2477",
        "E2478",
        "E2479",
        "E2480",
        "E2481",
        "E2482",
        "E2483",
        "E2484",
        "E2485",
        "E2486",
        "E2487",
        "E2488",
        "E2489",
        "E2490",
        "E2491",
        "E2492",
        "E2493",
        "E2494",
        "E2495",
        "E2496",
        "E2497",
        "E2498",
        "E2499",
        "E2500",
        "E2501",
        "E2502",
        "E2503",
        "E2504",
        "E2505",
        "E2506",
        "E2507",
        "E2508",
        "E2509",
        "E2510",
        "E2511",
        "E2512",
        "E2513",
        "E2514",
        "E2515",
        "E2516",
        "E2517",
        "E2518",
        "E2519",
        "E2520",
        "E2521",
        "E2522",
        "E2523",
        "E2524",
        "E2525",
        "E2526",
        "E2527",
        "E2528",
        "E2529",
        "E2530",
        "E2531",
        "E2532",
        "E2533",
        "E2534",
        "E2535",
        "E2536",
        "E2537",
        "E2538"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C83",
      "caveats": []
    },
    {
      "claim_id": "C122",
      "claim_text": "llava/serve/gradio_web_server.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E2552"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C84",
      "caveats": []
    },
    {
      "claim_id": "C123",
      "claim_text": "llava/serve/sglang_worker.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E2637",
        "E2639",
        "E2640",
        "E2641",
        "E2642",
        "E2643",
        "E2644",
        "E2645",
        "E2646",
        "E2647",
        "E2648",
        "E2649"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C85",
      "caveats": []
    },
    {
      "claim_id": "C124",
      "claim_text": "llava/serve/sglang_worker.py implements entrypoint orchestration.",
      "support_status": "supported",
      "evidence_ids": [
        "E2638"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C86",
      "caveats": []
    },
    {
      "claim_id": "C125",
      "claim_text": "llava/serve/sglang_worker.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E2650",
        "E2651",
        "E2652",
        "E2653",
        "E2654",
        "E2655",
        "E2657",
        "E2658",
        "E2659",
        "E2660",
        "E2661",
        "E2662",
        "E2663",
        "E2664",
        "E2665",
        "E2666",
        "E2667",
        "E2668",
        "E2669",
        "E2670",
        "E2671",
        "E2672",
        "E2673",
        "E2674",
        "E2675",
        "E2676",
        "E2677",
        "E2678",
        "E2679",
        "E2680",
        "E2681",
        "E2682",
        "E2683",
        "E2684",
        "E2685",
        "E2687",
        "E2688",
        "E2689",
        "E2690",
        "E2691",
        "E2692",
        "E2693",
        "E2694",
        "E2695",
        "E2696",
        "E2697",
        "E2698",
        "E2699",
        "E2700",
        "E2701",
        "E2702",
        "E2703",
        "E2704",
        "E2705",
        "E2706"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C87",
      "caveats": []
    },
    {
      "claim_id": "C126",
      "claim_text": "llava/utils.py implements data preparation and loading.",
      "support_status": "supported",
      "evidence_ids": [
        "E2739",
        "E2740"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C88",
      "caveats": []
    },
    {
      "claim_id": "C127",
      "claim_text": "llava/utils.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E2754",
        "E2758",
        "E2759",
        "E2785",
        "E2786",
        "E2787",
        "E2788",
        "E2789",
        "E2790",
        "E2791",
        "E2792",
        "E2793",
        "E2794",
        "E2795",
        "E2796",
        "E2797",
        "E2798",
        "E2799",
        "E2800",
        "E2801",
        "E2802",
        "E2803",
        "E2804",
        "E2805",
        "E2806",
        "E2807",
        "E2808",
        "E2809",
        "E2810",
        "E2811",
        "E2812",
        "E2813",
        "E2814",
        "E2815",
        "E2816",
        "E2817",
        "E2818",
        "E2819",
        "E2820",
        "E2821",
        "E2822",
        "E2823",
        "E2824",
        "E2825"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C89",
      "caveats": []
    },
    {
      "claim_id": "C128",
      "claim_text": "pointllm/conversation.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E2842",
        "E2843",
        "E2844",
        "E2845",
        "E2846",
        "E2847",
        "E2848",
        "E2849",
        "E2850",
        "E2851",
        "E2852",
        "E2853",
        "E2854",
        "E2855",
        "E2856",
        "E2857",
        "E2858",
        "E2859",
        "E2860",
        "E2861",
        "E2862",
        "E2863",
        "E2864",
        "E2865",
        "E2866",
        "E2867",
        "E2868",
        "E2869",
        "E2871",
        "E2872",
        "E2873",
        "E2874"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C90",
      "caveats": []
    },
    {
      "claim_id": "C129",
      "claim_text": "pointllm/data/utils.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E2994",
        "E2995",
        "E2996",
        "E2997",
        "E2998",
        "E2999",
        "E3000",
        "E3001",
        "E3002"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C91",
      "caveats": []
    },
    {
      "claim_id": "C130",
      "claim_text": "pointllm/data/utils_backup.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E3086",
        "E3087",
        "E3088",
        "E3089",
        "E3090",
        "E3091",
        "E3092",
        "E3093",
        "E3094"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C92",
      "caveats": []
    },
    {
      "claim_id": "C131",
      "claim_text": "pointllm/utils.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E3180",
        "E3184",
        "E3185"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C93",
      "caveats": []
    },
    {
      "claim_id": "C132",
      "claim_text": "pointnet++/Pointnet2_PyTorch/pointnet2/data/data_utils.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E3232",
        "E3233",
        "E3234",
        "E3235",
        "E3236",
        "E3237",
        "E3238",
        "E3239",
        "E3240",
        "E3241",
        "E3242",
        "E3243",
        "E3244",
        "E3245",
        "E3246",
        "E3247",
        "E3248",
        "E3249",
        "E3250",
        "E3251",
        "E3252",
        "E3253",
        "E3254",
        "E3255",
        "E3256",
        "E3257",
        "E3258",
        "E3259"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C94",
      "caveats": []
    },
    {
      "claim_id": "C133",
      "claim_text": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_modules.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E3295",
        "E3296",
        "E3297",
        "E3300",
        "E3302",
        "E3303",
        "E3305",
        "E3306",
        "E3308"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C95",
      "caveats": []
    },
    {
      "claim_id": "C134",
      "claim_text": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_modules.py implements model computation block.",
      "support_status": "supported",
      "evidence_ids": [
        "E3298",
        "E3309"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C96",
      "caveats": []
    },
    {
      "claim_id": "C135",
      "claim_text": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_modules.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E3311",
        "E3312",
        "E3313",
        "E3314",
        "E3315",
        "E3316",
        "E3317",
        "E3318",
        "E3319",
        "E3320",
        "E3321",
        "E3322",
        "E3323",
        "E3324",
        "E3325",
        "E3326",
        "E3327",
        "E3328",
        "E3329",
        "E3330",
        "E3331",
        "E3332",
        "E3333",
        "E3334",
        "E3335",
        "E3336",
        "E3337",
        "E3338",
        "E3339",
        "E3340",
        "E3341",
        "E3342",
        "E3343",
        "E3344",
        "E3345",
        "E3346",
        "E3347",
        "E3348",
        "E3349",
        "E3350",
        "E3351",
        "E3352",
        "E3353"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C97",
      "caveats": []
    },
    {
      "claim_id": "C136",
      "claim_text": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_utils.py implements model computation block.",
      "support_status": "supported",
      "evidence_ids": [
        "E3359",
        "E3363",
        "E3367",
        "E3371",
        "E3376",
        "E3381",
        "E3387",
        "E3392"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C98",
      "caveats": []
    },
    {
      "claim_id": "C137",
      "claim_text": "pointnet++/Pointnet2_PyTorch/pointnet2_ops_lib/pointnet2_ops/pointnet2_utils.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E3394",
        "E3395",
        "E3396",
        "E3398",
        "E3399",
        "E3400",
        "E3401",
        "E3402",
        "E3403",
        "E3405",
        "E3406",
        "E3407",
        "E3408",
        "E3409",
        "E3410",
        "E3412",
        "E3413",
        "E3414",
        "E3415",
        "E3416",
        "E3417",
        "E3418",
        "E3419",
        "E3420",
        "E3421",
        "E3422",
        "E3423",
        "E3424",
        "E3425",
        "E3426",
        "E3427",
        "E3428",
        "E3429",
        "E3430"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C99",
      "caveats": []
    },
    {
      "claim_id": "C138",
      "claim_text": "scripts/convert_sqa_to_llava.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E3459",
        "E3460"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C100",
      "caveats": []
    },
    {
      "claim_id": "C139",
      "claim_text": "scripts/convert_sqa_to_llava.py implements entrypoint orchestration.",
      "support_status": "supported",
      "evidence_ids": [
        "E3461"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C101",
      "caveats": []
    },
    {
      "claim_id": "C140",
      "claim_text": "scripts/convert_sqa_to_llava.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E3462",
        "E3463",
        "E3464",
        "E3465",
        "E3466",
        "E3467",
        "E3469",
        "E3470",
        "E3471",
        "E3472",
        "E3473",
        "E3474",
        "E3475",
        "E3476",
        "E3477",
        "E3479",
        "E3480",
        "E3481",
        "E3483"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C102",
      "caveats": []
    },
    {
      "claim_id": "C141",
      "claim_text": "scripts/convert_sqa_to_llava_base_prompt.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E3502",
        "E3503",
        "E3504",
        "E3505",
        "E3507",
        "E3508",
        "E3509",
        "E3510",
        "E3511",
        "E3512"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C103",
      "caveats": []
    },
    {
      "claim_id": "C142",
      "claim_text": "scripts/convert_sqa_to_llava_base_prompt.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E3513",
        "E3514",
        "E3515",
        "E3516",
        "E3517",
        "E3518",
        "E3519",
        "E3521",
        "E3522",
        "E3523",
        "E3524",
        "E3525",
        "E3526",
        "E3527",
        "E3528",
        "E3529",
        "E3530",
        "E3531",
        "E3532",
        "E3533",
        "E3534",
        "E3535",
        "E3536",
        "E3537",
        "E3538",
        "E3541",
        "E3542",
        "E3543",
        "E3544",
        "E3545",
        "E3546",
        "E3547",
        "E3550",
        "E3551",
        "E3552",
        "E3553",
        "E3554",
        "E3555",
        "E3556"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C104",
      "caveats": []
    },
    {
      "claim_id": "C143",
      "claim_text": "scripts/extract_mm_projector.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E3569"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C105",
      "caveats": []
    },
    {
      "claim_id": "C144",
      "claim_text": "scripts/extract_mm_projector.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E3570",
        "E3571",
        "E3572"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C106",
      "caveats": []
    },
    {
      "claim_id": "C145",
      "claim_text": "scripts/merge_lora_weights.py implements infrastructure utility.",
      "support_status": "supported",
      "evidence_ids": [
        "E3588"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C107",
      "caveats": []
    },
    {
      "claim_id": "C146",
      "claim_text": "pretrained_weight/eval_model_weight/all-mpnet-base-v2/train_script.py implements model computation block.",
      "support_status": "supported",
      "evidence_ids": [
        "E3696"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C108",
      "caveats": []
    },
    {
      "claim_id": "C147",
      "claim_text": "pretrained_weight/eval_model_weight/all-mpnet-base-v2/train_script.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E3712",
        "E3713",
        "E3714",
        "E3728",
        "E3733"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C109",
      "caveats": []
    },
    {
      "claim_id": "C148",
      "claim_text": "llava/serve/test_message.py implements entrypoint orchestration.",
      "support_status": "supported",
      "evidence_ids": [
        "E3762"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C110",
      "caveats": []
    },
    {
      "claim_id": "C149",
      "claim_text": "llava/serve/test_message.py implements call-chain flow relation.",
      "support_status": "supported",
      "evidence_ids": [
        "E3763",
        "E3764",
        "E3765",
        "E3766",
        "E3767",
        "E3768",
        "E3770",
        "E3771",
        "E3772",
        "E3773",
        "E3774"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C111",
      "caveats": []
    },
    {
      "claim_id": "C150",
      "claim_text": "Module docstring hint: PyTorch Phi-3 model.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C112",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C151",
      "claim_text": "Python inline comment hint: x: [bs, num_attention_heads, seq_len, head_size]",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C113",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C152",
      "claim_text": "Python inline comment hint: upcast attention to fp32",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C114",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C153",
      "claim_text": "Python inline comment hint: Copied from transformers.models.llama.modeling_llama.LlamaFlashAttention2.__init__",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C115",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C154",
      "claim_text": "Python inline comment hint: flash_attn<2.1 generates top-left aligned causal mask, while what is needed here is bottom-right alignement, that was made default for flash_attn>=2.1. This attribute is used to handle this difference. Reference: https://github.com/Dao-AILab/flash-attention/releases/tag/v2.1.0.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C116",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C155",
      "claim_text": "Python inline comment hint: Phi3FlashAttention2 attention does not support output_attentions",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C117",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C156",
      "claim_text": "Python inline comment hint: overwrite attention_mask with padding_mask",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C118",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C157",
      "claim_text": "Python inline comment hint: Flash attention requires the input to have the shape",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C119",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C158",
      "claim_text": "Python inline comment hint: Reashape to the expected shape for Flash Attention",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C120",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C159",
      "claim_text": "Python inline comment hint: Copied from transformers.models.mistral.modeling_mistral.MistralFlashAttention2._flash_attention_forward",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C121",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C160",
      "claim_text": "Python inline comment hint: Copied from transformers.models.mistral.modeling_mistral.MistralFlashAttention2._upad_input",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C122",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C161",
      "claim_text": "Docstring hint for Phi3RMSNorm.__init__: Phi3RMSNorm is equivalent to T5LayerNorm",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C123",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C162",
      "claim_text": "Docstring hint for rotate_half: Rotates half the hidden dims of the input.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C124",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C163",
      "claim_text": "Docstring hint for repeat_kv: This is the equivalent of torch.repeat_interleave(x, dim=1, repeats=n_rep). The hidden states go from (batch, num_key_value_heads, seqlen, head_dim) to (batch, num_attention_heads, seqlen, head_dim)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C125",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C164",
      "claim_text": "Docstring hint for Phi3Attention: Multi-headed attention from 'Attention Is All You Need' paper",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C126",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C165",
      "claim_text": "Docstring hint for Phi3FlashAttention2: Phi-3 flash attention module. This module inherits from `Phi3Attention` as the weights of the module stays untouched. The only required change would be on the forward pass where it needs to correctly call the public API of flash attention and deal with padding tokens in case the input contains any of them.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C127",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C166",
      "claim_text": "Docstring hint for Phi3FlashAttention2._flash_attention_forward: Calls the forward method of Flash Attention - if the input hidden states contain at least one padding token first unpad the input, then computes the attention scores and pad the final attention scores. Args: query_states (`torch.Tensor`): Input query states to be passed to Flash Attention API key_states (`torch.Tensor`): Input key states to be passed to Flash Attention API value_states (`torch.Tensor`): Input value states to be passed to Flash Attention API attention_mask (`torch.Tensor`): The padding mask - corresponds to a tensor of size `(batch_size, seq_len)` where 0 stands for the position of padding tokens and 1 for the position of non-padding tokens. dropout (`float`): Attention dropout softmax_scale (`float`, *optional*): The scaling of QK^T before applying softmax. Default to 1 / sqrt(head_dim) use_sliding_windows (`bool`, *optional*): Whether to activate sliding window attention.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C128",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C167",
      "claim_text": "Docstring hint for Phi3SdpaAttention: Phi3 attention module using torch.nn.functional.scaled_dot_product_attention. This module inherits from `Phi3Attention` as the weights of the module stays untouched. The only changes are on the forward pass to adapt to SDPA API.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C129",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C168",
      "claim_text": "Docstring hint for Phi3Model: Transformer decoder consisting of *config.num_hidden_layers* layers. Each layer is a [`Phi3DecoderLayer`] Args: config: Phi3Config",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C130",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C169",
      "claim_text": "Docstring hint for Phi3ForCausalLM.forward: Args: labels (`torch.LongTensor` of shape `(batch_size, sequence_length)`, *optional*): Labels for computing the masked language modeling loss. Indices should either be in `[0, ..., config.vocab_size]` or -100 (see `input_ids` docstring). Tokens with indices set to `-100` are ignored (masked), the loss is only computed for the tokens with labels in `[0, ..., config.vocab_size]`. Returns: Example: ```python >>> from transformers import AutoTokenizer, Phi3ForCausalLM >>> model = Phi3ForCausalLM.from_pretrained(\"microsoft/phi-3-mini-4k-instruct\") >>> tokenizer = AutoTokenizer.from_pretrained(\"microsoft/phi-3-mini-4k-instruct\") >>> prompt = \"This is an example script .\" >>> inputs = tokenizer(prompt, return_tensors=\"pt\") >>> # Generate >>> generate_ids = model.generate(inputs.input_ids, max_length=30) >>> tokenizer.batch_decode(generate_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0] 'This is an example script .\\n Certainly! Below is a sample script that demonstrates a simple task, such as calculating the sum' ```",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C131",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C170",
      "claim_text": "Docstring hint for Phi3ForSequenceClassification.forward: labels (`torch.LongTensor` of shape `(batch_size,)`, *optional*): Labels for computing the sequence classification/regression loss. Indices should be in `[0, ..., config.num_labels - 1]`. If `config.num_labels == 1` a regression loss is computed (Mean-Square loss), If `config.num_labels > 1` a classification loss is computed (Cross-Entropy).",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C132",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C171",
      "claim_text": "Docstring hint for Phi3ForTokenClassification.forward: labels (`torch.LongTensor` of shape `(batch_size,)`, *optional*): Labels for computing the sequence classification/regression loss. Indices should be in `[0, ..., config.num_labels - 1]`. If `config.num_labels == 1` a regression loss is computed (Mean-Square loss), If `config.num_labels > 1` a classification loss is computed (Cross-Entropy).",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C133",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C172",
      "claim_text": "Python inline comment hint: try:",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C134",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C173",
      "claim_text": "Python inline comment hint: from .language_model.llava_llama import LlavaLlamaForCausalLM, LlavaConfig",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C135",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C174",
      "claim_text": "Python inline comment hint: from .language_model.llava_mpt import LlavaMptForCausalLM, LlavaMptConfig",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C136",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C175",
      "claim_text": "Python inline comment hint: from .language_model.llava_mistral import LlavaMistralForCausalLM, LlavaMistralConfig",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C137",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C176",
      "claim_text": "Python inline comment hint: from .language_model.llava_phi3 import LlavaPhiForCausalLM, LlavaPhiConfig",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C138",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C177",
      "claim_text": "Python inline comment hint: except:",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C139",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C178",
      "claim_text": "Python inline comment hint: pass",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C140",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C179",
      "claim_text": "Module docstring hint: Usage: python3 -m fastchat.model.apply_delta --base ~/model_weights/llama-7b --target ~/model_weights/vicuna-7b --delta lmsys/vicuna-7b-delta",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C141",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C180",
      "claim_text": "Python inline comment hint: Modified from LLaVA: https://github.com/haotian-liu/LLaVA.git",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C142",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C181",
      "claim_text": "Python inline comment hint: Copyright 2023 Haotian Liu",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C143",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C182",
      "claim_text": "Python inline comment hint: Licensed under the Apache License, Version 2.0 (the \"License\");",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C144",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C183",
      "claim_text": "Python inline comment hint: you may not use this file except in compliance with the License.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C145",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C184",
      "claim_text": "Python inline comment hint: You may obtain a copy of the License at",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C146",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C185",
      "claim_text": "Python inline comment hint: http://www.apache.org/licenses/LICENSE-2.0",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C147",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C186",
      "claim_text": "Python inline comment hint: Unless required by applicable law or agreed to in writing, software",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C148",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C187",
      "claim_text": "Python inline comment hint: distributed under the License is distributed on an \"AS IS\" BASIS,",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C149",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C188",
      "claim_text": "Python inline comment hint: WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C150",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C189",
      "claim_text": "Python inline comment hint: See the License for the specific language governing permissions and",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C151",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C190",
      "claim_text": "Python inline comment hint: limitations under the License.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C152",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C191",
      "claim_text": "Python inline comment hint: Load LLaVA model",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C153",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C192",
      "claim_text": "Module docstring hint: Usage: python3 -m llava.model.consolidate --src ~/model_weights/llava-7b --dst ~/model_weights/llava-7b_consolidate",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C154",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C193",
      "claim_text": "Python inline comment hint: Copyright 2023 Haotian Liu",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C155",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C194",
      "claim_text": "Python inline comment hint: Licensed under the Apache License, Version 2.0 (the \"License\");",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C156",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C195",
      "claim_text": "Python inline comment hint: you may not use this file except in compliance with the License.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C157",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C196",
      "claim_text": "Python inline comment hint: You may obtain a copy of the License at",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C158",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C197",
      "claim_text": "Python inline comment hint: http://www.apache.org/licenses/LICENSE-2.0",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C159",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C198",
      "claim_text": "Python inline comment hint: Unless required by applicable law or agreed to in writing, software",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C160",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C199",
      "claim_text": "Python inline comment hint: distributed under the License is distributed on an \"AS IS\" BASIS,",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C161",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C200",
      "claim_text": "Python inline comment hint: WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C162",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C201",
      "claim_text": "Python inline comment hint: See the License for the specific language governing permissions and",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C163",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C202",
      "claim_text": "Python inline comment hint: limitations under the License.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C164",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C203",
      "claim_text": "Python inline comment hint: Initialize weights and apply final processing",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C165",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C204",
      "claim_text": "Python inline comment hint: Copyright 2023 Haotian Liu",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C166",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C205",
      "claim_text": "Python inline comment hint: Licensed under the Apache License, Version 2.0 (the \"License\");",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C167",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C206",
      "claim_text": "Python inline comment hint: you may not use this file except in compliance with the License.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C168",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C207",
      "claim_text": "Python inline comment hint: You may obtain a copy of the License at",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C169",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C208",
      "claim_text": "Python inline comment hint: http://www.apache.org/licenses/LICENSE-2.0",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C170",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C209",
      "claim_text": "Python inline comment hint: Unless required by applicable law or agreed to in writing, software",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C171",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C210",
      "claim_text": "Python inline comment hint: distributed under the License is distributed on an \"AS IS\" BASIS,",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C172",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C211",
      "claim_text": "Python inline comment hint: WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C173",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C212",
      "claim_text": "Python inline comment hint: See the License for the specific language governing permissions and",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C174",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C213",
      "claim_text": "Python inline comment hint: limitations under the License.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C175",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C214",
      "claim_text": "Python inline comment hint: Initialize weights and apply final processing",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C176",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C215",
      "claim_text": "Python inline comment hint: Copyright 2023 Haotian Liu",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C177",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C216",
      "claim_text": "Python inline comment hint: Licensed under the Apache License, Version 2.0 (the \"License\");",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C178",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C217",
      "claim_text": "Python inline comment hint: you may not use this file except in compliance with the License.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C179",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C218",
      "claim_text": "Python inline comment hint: You may obtain a copy of the License at",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C180",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C219",
      "claim_text": "Python inline comment hint: http://www.apache.org/licenses/LICENSE-2.0",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C181",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C220",
      "claim_text": "Python inline comment hint: Unless required by applicable law or agreed to in writing, software",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C182",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C221",
      "claim_text": "Python inline comment hint: distributed under the License is distributed on an \"AS IS\" BASIS,",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C183",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C222",
      "claim_text": "Python inline comment hint: WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C184",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C223",
      "claim_text": "Python inline comment hint: See the License for the specific language governing permissions and",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C185",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C224",
      "claim_text": "Python inline comment hint: limitations under the License.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C186",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C225",
      "claim_text": "Python inline comment hint: Initialize weights and apply final processing",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C187",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C226",
      "claim_text": "Python inline comment hint: Modified from LLaVA: https://github.com/haotian-liu/LLaVA.git",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C188",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C227",
      "claim_text": "Python inline comment hint: Copyright 2023 Haotian Liu",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C189",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C228",
      "claim_text": "Python inline comment hint: Licensed under the Apache License, Version 2.0 (the \"License\");",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C190",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C229",
      "claim_text": "Python inline comment hint: you may not use this file except in compliance with the License.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C191",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C230",
      "claim_text": "Python inline comment hint: You may obtain a copy of the License at",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C192",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C231",
      "claim_text": "Python inline comment hint: http://www.apache.org/licenses/LICENSE-2.0",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C193",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C232",
      "claim_text": "Python inline comment hint: Unless required by applicable law or agreed to in writing, software",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C194",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C233",
      "claim_text": "Python inline comment hint: distributed under the License is distributed on an \"AS IS\" BASIS,",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C195",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C234",
      "claim_text": "Python inline comment hint: WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C196",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C235",
      "claim_text": "Python inline comment hint: See the License for the specific language governing permissions and",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C197",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C236",
      "claim_text": "Python inline comment hint: limitations under the License.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C198",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C237",
      "claim_text": "Python inline comment hint: Initialize weights and apply final processing",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C199",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C238",
      "claim_text": "Python inline comment hint: Copyright 2023 Haotian Liu",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C200",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C239",
      "claim_text": "Python inline comment hint: Licensed under the Apache License, Version 2.0 (the \"License\");",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C201",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C240",
      "claim_text": "Python inline comment hint: you may not use this file except in compliance with the License.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C202",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C241",
      "claim_text": "Python inline comment hint: You may obtain a copy of the License at",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C203",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C242",
      "claim_text": "Python inline comment hint: http://www.apache.org/licenses/LICENSE-2.0",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C204",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C243",
      "claim_text": "Python inline comment hint: Unless required by applicable law or agreed to in writing, software",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C205",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C244",
      "claim_text": "Python inline comment hint: distributed under the License is distributed on an \"AS IS\" BASIS,",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C206",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C245",
      "claim_text": "Python inline comment hint: WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C207",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C246",
      "claim_text": "Python inline comment hint: See the License for the specific language governing permissions and",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C208",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C247",
      "claim_text": "Python inline comment hint: limitations under the License.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C209",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C248",
      "claim_text": "Python inline comment hint: 从这初始化的encoder 和 projector",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C210",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C249",
      "claim_text": "Docstring hint for LlavaMetaModel.random_initialize_model: 随机初始化给定模型的所有参数。 参数: - model (nn.Module): 要初始化的PyTorch模型实例。 - mean (float): 权重初始化的均值，默认为0.0。 - std (float): 权重初始化的标准差，默认为0.02。",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C211",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C250",
      "claim_text": "Docstring hint for unpad_image: Unpads a PyTorch tensor of a padded and resized image. Args: tensor (torch.Tensor): The image tensor, assumed to be in CxHxW format. original_size (tuple): The original size of PIL image (width, height). Returns: torch.Tensor: The unpadded image tensor.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C212",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C251",
      "claim_text": "Module docstring hint: Usage: python3 -m llava.model.make_delta --base ~/model_weights/llama-7b --target ~/model_weights/llava-7b --delta ~/model_weights/llava-7b-delta --hub-repo-id liuhaotian/llava-7b-delta",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C213",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C252",
      "claim_text": "Python inline comment hint: create transformer blocks for point cloud via timm",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C214",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C253",
      "claim_text": "Python inline comment hint: create whole point cloud encoder",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C215",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C254",
      "claim_text": "Python inline comment hint: change resize/crop size in preprocessing to the largest image size in s2_scale",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C216",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C255",
      "claim_text": "Python inline comment hint: https://github.com/Strawberry-Eat-Mango/PCT_Pytorch/blob/main/util.py",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C217",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C256",
      "claim_text": "Python inline comment hint: exclude CLS token",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C218",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C257",
      "claim_text": "Python inline comment hint: if not self.training or self.prob == 0.:",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C219",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C258",
      "claim_text": "Python inline comment hint: return x",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C220",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C259",
      "claim_text": "Python inline comment hint: fps the centers out",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C221",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C260",
      "claim_text": "Python inline comment hint: B G 3",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C222",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C261",
      "claim_text": "Python inline comment hint: knn to get the neighborhood",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C223",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C262",
      "claim_text": "Python inline comment hint: _, idx = self.knn(xyz, center) # B G M",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C224",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C263",
      "claim_text": "Python inline comment hint: B G M",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C225",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C264",
      "claim_text": "Python inline comment hint: normalize",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C226",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C265",
      "claim_text": "Python inline comment hint: encoder",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C227",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C266",
      "claim_text": "Python inline comment hint: ModuleList not support forward",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C228",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C267",
      "claim_text": "Docstring hint for fps: data B N 3 number int",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C229",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C268",
      "claim_text": "Docstring hint for index_points: Input: points: input points data, [B, N, C] idx: sample index data, [B, S] Return: new_points:, indexed points data, [B, S, C]",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C230",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C269",
      "claim_text": "Docstring hint for knn_point: Input: nsample: max sample number in local region xyz: all points, [B, N, C] new_xyz: query points, [B, S, C] Return: group_idx: grouped points index, [B, S, nsample]",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C231",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C270",
      "claim_text": "Docstring hint for square_distance: Calculate Euclid distance between each two points. src^T * dst = xn * xm + yn * ym + zn * zm; sum(src^2, dim=-1) = xn*xn + yn*yn + zn*zn; sum(dst^2, dim=-1) = xm*xm + ym*ym + zm*zm; dist = (xn - xm)^2 + (yn - ym)^2 + (zn - zm)^2 = sum(src**2,dim=-1)+sum(dst**2,dim=-1)-2*src^T*dst Input: src: source points, [B, N, C] dst: target points, [B, M, C] Output: dist: per-point square distance, [B, N, M]",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C232",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C271",
      "claim_text": "Docstring hint for PatchDropout: https://arxiv.org/abs/2212.00794",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C233",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C272",
      "claim_text": "Docstring hint for Group.forward: input: B N 3 --------------------------- output: B G M 3 center : B G 3",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C234",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C273",
      "claim_text": "Docstring hint for Encoder.forward: point_groups : B G N 3 ----------------- feature_global : B G C",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C235",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C274",
      "claim_text": "Docstring hint for skeleton_Group.forward: xyz: 所有token的xyz input: B N 3 --------------------------- output: B G M 3 center : B G 3",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C236",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C275",
      "claim_text": "Python inline comment hint: Set the format of root handlers",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C237",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C276",
      "claim_text": "Python inline comment hint: Redirect stdout and stderr to loggers",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C238",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C277",
      "claim_text": "Python inline comment hint: Get logger",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C239",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C278",
      "claim_text": "Python inline comment hint: Add a file handler for all loggers",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C240",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C279",
      "claim_text": "Python inline comment hint: From the io.TextIOWrapper docs:",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C241",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C280",
      "claim_text": "Python inline comment hint: On output, if newline is None, any '\\n' characters written",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C242",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C281",
      "claim_text": "Python inline comment hint: are translated to the system default line separator.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C243",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C282",
      "claim_text": "Python inline comment hint: By default sys.stdout.write() expects '\\n' newlines and then",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C244",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C283",
      "claim_text": "Python inline comment hint: translates them so this is still cross platform.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C245",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C284",
      "claim_text": "Python inline comment hint: Modified from github.com/openai/CLIP",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C246",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C285",
      "claim_text": "Docstring hint for StreamToLogger: Fake file-like stream object that redirects writes to a logger instance.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C247",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C286",
      "claim_text": "Docstring hint for disable_torch_init: Disable the redundant torch default initialization to accelerate model creation.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C248",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C287",
      "claim_text": "Docstring hint for violates_moderation: Check whether the text violates OpenAI moderation API.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C249",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C288",
      "claim_text": "Docstring hint for bytes_to_unicode: Returns list of utf-8 byte and a corresponding list of unicode strings. The reversible bpe codes work on unicode strings. This means you need a large # of unicode characters in your vocab if you want to avoid UNKs. When you're at something like a 10B token dataset you end up needing around 5K for decent coverage. This is a signficant percentage of your normal, say, 32K bpe vocab. To avoid that, we want lookup tables between utf-8 bytes and unicode strings. And avoids mapping to whitespace/control characters the bpe code barfs on.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C250",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C289",
      "claim_text": "Docstring hint for get_pairs: Return set of symbol pairs in a word. Word is represented as tuple of symbols (symbols being variable-length strings).",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C251",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C290",
      "claim_text": "Module docstring hint: A model worker executes the model.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C252",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C291",
      "claim_text": "Python inline comment hint: stopping_criteria = KeywordsStoppingCriteria(keywords, tokenizer, input_ids)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C253",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C292",
      "claim_text": "Python inline comment hint: shape: (b, num_heads, s, head_dim)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C254",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C293",
      "claim_text": "Python inline comment hint: reuse k, v",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C255",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C294",
      "claim_text": "Python inline comment hint: repeat k/v heads if n_kv_heads < n_heads",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C256",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C295",
      "claim_text": "Python inline comment hint: Transform the data into the format required by flash attention",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C257",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C296",
      "claim_text": "Python inline comment hint: shape: [b, s, 3, num_heads, head_dim]",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C258",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C297",
      "claim_text": "Python inline comment hint: Disable the transformation of the attention mask in LlamaModel as the flash attention",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C259",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C298",
      "claim_text": "Python inline comment hint: requires the attention mask to be the same as the key_padding_mask",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C260",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C299",
      "claim_text": "Python inline comment hint: [bsz, seq_len]",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C261",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C300",
      "claim_text": "Module docstring hint: Directly copied the code from https://raw.githubusercontent.com/oobabooga/text-generation-webui/main/modules/llama_attn_hijack.py and made some adjustments",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C262",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C301",
      "claim_text": "Python inline comment hint: pylint: disable=duplicate-code",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C263",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C302",
      "claim_text": "Python inline comment hint: [bsz, nh, t, hd]",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C264",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C303",
      "claim_text": "Python inline comment hint: reuse k, v, self_attention",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C265",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C304",
      "claim_text": "Python inline comment hint: We only apply xformers optimizations if we don't need to output the whole attention matrix",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C266",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C305",
      "claim_text": "Python inline comment hint: We therefore check if one element in the upper triangular portion is zero. If it is, then the mask is all zeros.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C267",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C306",
      "claim_text": "Python inline comment hint: input and output should be of form (bsz, q_len, num_heads, head_dim)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C268",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C307",
      "claim_text": "Python inline comment hint: input and output should be of form (bsz, q_len, num_heads, head_dim)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C269",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C308",
      "claim_text": "Python inline comment hint: upcast attention to fp32",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C270",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C309",
      "claim_text": "Python inline comment hint: Borrowed from peft.utils.get_peft_model_state_dict",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C271",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C310",
      "claim_text": "Python inline comment hint: all samples are in the same modality",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C272",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C311",
      "claim_text": "Python inline comment hint: Only save Adapter",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C273",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C312",
      "claim_text": "Python inline comment hint: self.model.save_pretrained(output_dir, state_dict=state_dict)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C274",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C313",
      "claim_text": "Docstring hint for split_to_even_chunks: Split a list of indices into `chunks` chunks of roughly equal lengths.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C275",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C314",
      "claim_text": "Docstring hint for LengthGroupedSampler: Sampler that samples indices in a way that groups together features of the dataset of roughly the same length while keeping a bit of randomness.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C276",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C315",
      "claim_text": "Docstring hint for LLaVATrainer.create_optimizer: Setup the optimizer. We provide a reasonable default that works well. If you want to use something else, you can pass a tuple in the Trainer's init through `optimizers`, or subclass and override this method in a subclass.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C277",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C316",
      "claim_text": "Python inline comment hint: Modified from LLaVA: https://github.com/haotian-liu/LLaVA.git",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C278",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C317",
      "claim_text": "Python inline comment hint: Adopted from https://github.com/lm-sys/FastChat. Below is the original copyright:",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C279",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C318",
      "claim_text": "Python inline comment hint: Adopted from tatsu-lab@stanford_alpaca. Below is the original copyright:",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C280",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C319",
      "claim_text": "Python inline comment hint: Copyright 2023 Rohan Taori, Ishaan Gulrajani, Tianyi Zhang, Yann Dubois, Xuechen Li",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C281",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C320",
      "claim_text": "Python inline comment hint: Licensed under the Apache License, Version 2.0 (the \"License\");",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C282",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C321",
      "claim_text": "Python inline comment hint: you may not use this file except in compliance with the License.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C283",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C322",
      "claim_text": "Python inline comment hint: You may obtain a copy of the License at",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C284",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C323",
      "claim_text": "Python inline comment hint: http://www.apache.org/licenses/LICENSE-2.0",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C285",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C324",
      "claim_text": "Python inline comment hint: Unless required by applicable law or agreed to in writing, software",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C286",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C325",
      "claim_text": "Python inline comment hint: \"CLS\": inference of stage 1, 2",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C287",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C326",
      "claim_text": "Python inline comment hint: \"OM_Pooling\":  training and inference of  stage 3",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C288",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C327",
      "claim_text": "Python inline comment hint: stage 2 or stage 3",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C289",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C328",
      "claim_text": "Docstring hint for pc_norm: pc: NxC, return NxC",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C290",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C329",
      "claim_text": "Docstring hint for safe_save_model_for_hf_trainer: Collects the state dict and dump to disk.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C291",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C330",
      "claim_text": "Docstring hint for smart_tokenizer_and_embedding_resize: Resize tokenizer and embedding. Note: This is the unoptimized version that may make your embedding size not be divisible by 64.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C292",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C331",
      "claim_text": "Docstring hint for _tokenize_fn: Tokenize a list of strings.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C293",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C332",
      "claim_text": "Docstring hint for _add_speaker_and_signal: Add speaker and start/end signal on each round.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C294",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C333",
      "claim_text": "Docstring hint for preprocess: Given a list of sources, each is a conversation list. This transform: 1. Add signal '### ' at the beginning each sentence, with end signal ' '; 2. Concatenate conversations together; 3. Tokenize the concatenated conversation; 4. Make a deepcopy as the target. Mask human words with IGNORE_INDEX.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C295",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C334",
      "claim_text": "Docstring hint for LazySupervisedDataset: Dataset for supervised fine-tuning.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C296",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C335",
      "claim_text": "Docstring hint for DataCollatorForSupervisedDataset: Collate examples for supervised fine-tuning.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C297",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C336",
      "claim_text": "Docstring hint for make_supervised_data_module: Make dataset and collator for supervised fine-tuning.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C298",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C337",
      "claim_text": "Python inline comment hint: Make it more memory efficient by monkey patching the LLaMA model with xformers attention.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C299",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C338",
      "claim_text": "Python inline comment hint: Need to call this before importing transformers.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C300",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C339",
      "claim_text": "Python inline comment hint: * use the default config file in the same dir",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C301",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C340",
      "claim_text": "Python inline comment hint: * check data path",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C302",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C341",
      "claim_text": "Python inline comment hint: * should be 40",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C303",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C342",
      "claim_text": "Python inline comment hint: \"tv_stand\" -> \"tv stand\"",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C304",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C343",
      "claim_text": "Python inline comment hint: * list of category names",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C305",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C344",
      "claim_text": "Python inline comment hint: * ndarray of N, C: (8192, 6) (xyz and normals)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C306",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C345",
      "claim_text": "Python inline comment hint: * set random seed",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C307",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C346",
      "claim_text": "Python inline comment hint: * random choose subset_nums",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C308",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C347",
      "claim_text": "Python inline comment hint: * print len",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C309",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C348",
      "claim_text": "Python inline comment hint: * random sample",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C310",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C349",
      "claim_text": "Python inline comment hint: point_set = np.concatenate((point_set, np.zeros_like(point_set)), axis=-1) if self.use_color else point_set",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C311",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C350",
      "claim_text": "Python inline comment hint: point_set = np.concatenate((point_set, np.ones_like(point_set)*0.4), axis=-1) if self.use_color else point_set",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C312",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C351",
      "claim_text": "Docstring hint for ModelNet.__init__: Args: data_args: split: train or test",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C313",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C352",
      "claim_text": "Docstring hint for ModelNet.pc_norm: pc: NxC, return NxC",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C314",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C353",
      "claim_text": "Python inline comment hint: * use the default config file in the same dir",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C315",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C354",
      "claim_text": "Python inline comment hint: * check data path",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C316",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C355",
      "claim_text": "Python inline comment hint: * should be 40",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C317",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C356",
      "claim_text": "Python inline comment hint: \"tv_stand\" -> \"tv stand\"",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C318",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C357",
      "claim_text": "Python inline comment hint: * list of category names",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C319",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C358",
      "claim_text": "Python inline comment hint: * ndarray of N, C: (8192, 6) (xyz and normals)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C320",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C359",
      "claim_text": "Python inline comment hint: * set random seed",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C321",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C360",
      "claim_text": "Python inline comment hint: * random choose subset_nums",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C322",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C361",
      "claim_text": "Python inline comment hint: * print len",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C323",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C362",
      "claim_text": "Python inline comment hint: * random sample",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C324",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C363",
      "claim_text": "Python inline comment hint: * ndarray, int",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C325",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C364",
      "claim_text": "Python inline comment hint: * random sample",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C326",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C365",
      "claim_text": "Docstring hint for ModelNet.__init__: Args: data_args: split: train or test",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C327",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C366",
      "claim_text": "Docstring hint for ModelNet.pc_norm: pc: NxC, return NxC",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C328",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C367",
      "claim_text": "Python inline comment hint: from .pointllm import PointLLMLlamaForCausalLM, PointLLMConfig",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C329",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C368",
      "claim_text": "Python inline comment hint: from .pointbert.point_encoder import PointTransformer",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C330",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C369",
      "claim_text": "Python inline comment hint: Copyright 2023 Runsen Xu",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C331",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C370",
      "claim_text": "Python inline comment hint: * add logger",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C332",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C371",
      "claim_text": "Python inline comment hint: address of config file, in the same dir of this file",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C333",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C372",
      "claim_text": "Python inline comment hint: * default for v1.1, v1.2 uses PointTransformer_8192point_2layer.yaml",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C334",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C373",
      "claim_text": "Python inline comment hint: * default is false",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C335",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C374",
      "claim_text": "Python inline comment hint: * number of output features, with cls token",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C336",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C375",
      "claim_text": "Python inline comment hint: a list",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C337",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C376",
      "claim_text": "Python inline comment hint: * print relevant info with projection layers",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C338",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C377",
      "claim_text": "Python inline comment hint: Add projection layer with linear layers and GELU activation",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C339",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C378",
      "claim_text": "Python inline comment hint: Single layer",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C340",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C379",
      "claim_text": "Python inline comment hint: Enable model/pipeline parallelism",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C341",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C380",
      "claim_text": "Python inline comment hint: * called when stage2 or inference or inference without pre-training, assume tokenizer has point tokens",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C342",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C381",
      "claim_text": "Python inline comment hint: Adopted from https://github.com/lm-sys/FastChat. Below is the original copyright:",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C343",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C382",
      "claim_text": "Python inline comment hint: * some version is changed to flash_attn_varlen_qkvpacked_func, so need to check",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C344",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C383",
      "claim_text": "Python inline comment hint: [bsz, q_len, nh, hd]",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C345",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C384",
      "claim_text": "Python inline comment hint: [bsz, nh, q_len, hd]",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C346",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C385",
      "claim_text": "Python inline comment hint: [bsz, nh, t, hd]",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C347",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C386",
      "claim_text": "Python inline comment hint: Flash attention codes from",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C348",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C387",
      "claim_text": "Python inline comment hint: https://github.com/HazyResearch/flash-attention/blob/main/flash_attn/flash_attention.py",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C349",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C388",
      "claim_text": "Python inline comment hint: transform the data into the format required by flash attention",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C350",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C389",
      "claim_text": "Python inline comment hint: We have disabled _prepare_decoder_attention_mask in LlamaModel",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C351",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C390",
      "claim_text": "Python inline comment hint: the attention_mask should be the same as the key_padding_mask",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C352",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C391",
      "claim_text": "Python inline comment hint: Disable the transformation of the attention mask in LlamaModel as the flash attention",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C353",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C392",
      "claim_text": "Python inline comment hint: requires the attention mask to be the same as the key_padding_mask",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C354",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C393",
      "claim_text": "Docstring hint for forward: Input shape: Batch x Time x Channel attention_mask: [bsz, q_len]",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C355",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C394",
      "claim_text": "Python inline comment hint: since there could be multiple levels of wrapping, unwrap recursively",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C356",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C395",
      "claim_text": "Python inline comment hint: Save the model",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C357",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C396",
      "claim_text": "Python inline comment hint: Only save the model itself if we are using distributed training",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C358",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C397",
      "claim_text": "Docstring hint for unwrap_model: Recursively unwraps a model from potential containers (as used in distributed training). Args: model (`torch.nn.Module`): The model to unwrap.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C359",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C398",
      "claim_text": "Python inline comment hint: Adopted from https://github.com/lm-sys/FastChat. Below is the original copyright:",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C360",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C399",
      "claim_text": "Python inline comment hint: Adopted from tatsu-lab@stanford_alpaca. Below is the original copyright:",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C361",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C400",
      "claim_text": "Python inline comment hint: Copyright 2023 Rohan Taori, Ishaan Gulrajani, Tianyi Zhang, Yann Dubois, Xuechen Li",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C362",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C401",
      "claim_text": "Python inline comment hint: Licensed under the Apache License, Version 2.0 (the \"License\");",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C363",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C402",
      "claim_text": "Python inline comment hint: you may not use this file except in compliance with the License.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C364",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C403",
      "claim_text": "Python inline comment hint: You may obtain a copy of the License at",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C365",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C404",
      "claim_text": "Python inline comment hint: * for two stage training",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C366",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C405",
      "claim_text": "Python inline comment hint: * use with torch.inference_mode to control, not requires_grad for fsdp for second stage",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C367",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C406",
      "claim_text": "Python inline comment hint: * fix pointnet for first stage, need for fsdp in stage2",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C368",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C407",
      "claim_text": "Python inline comment hint: * we assume in stage2, llm, point_backbone, and projection layer can be loaded from the model checkpoint",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C369",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C408",
      "claim_text": "Python inline comment hint: * stage2",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C370",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C409",
      "claim_text": "Python inline comment hint: layer.register_forward_hook(print_layer_output)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C371",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C410",
      "claim_text": "Docstring hint for safe_save_model_for_hf_trainer: Collects the state dict and dump to disk.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C372",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C411",
      "claim_text": "Python inline comment hint: Adopted from https://github.com/lm-sys/FastChat. Below is the original copyright:",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C373",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C412",
      "claim_text": "Python inline comment hint: Adopted from tatsu-lab@stanford_alpaca. Below is the original copyright:",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C374",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C413",
      "claim_text": "Python inline comment hint: Make it more memory efficient by monkey patching the LLaMA model with FlashAttn.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C375",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C414",
      "claim_text": "Python inline comment hint: Need to call this before importing transformers.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C376",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C415",
      "claim_text": "Python inline comment hint: from pointllm.train.llama_flash_attn_monkey_patch import replace_llama_attn_with_flash_attn",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C377",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C416",
      "claim_text": "Python inline comment hint: replace_llama_attn_with_flash_attn()",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C378",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C417",
      "claim_text": "Python inline comment hint: list of (shape_name, shape_txt_file_path) tuple",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C379",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C418",
      "claim_text": "Docstring hint for PointNet2ClassificationSSG.forward: Forward pass of the network Parameters ---------- pointcloud: Variable(torch.cuda.FloatTensor) (B, N, 3 + input_channels) tensor Point cloud to run predicts on Each point in the point-cloud MUST be formated as (x, y, z, features...)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C380",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C419",
      "claim_text": "Docstring hint for PointNet2SemSegSSG.forward: Forward pass of the network Parameters ---------- pointcloud: Variable(torch.cuda.FloatTensor) (B, N, 3 + input_channels) tensor Point cloud to run predicts on Each point in the point-cloud MUST be formated as (x, y, z, features...)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C381",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C420",
      "claim_text": "Module docstring hint: Phi-3 model configuration",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C382",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C421",
      "claim_text": "Python inline comment hint: coding=utf-8",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C383",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C422",
      "claim_text": "Python inline comment hint: Copyright 2024 Microsoft and the HuggingFace Inc. team. All rights reserved.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C384",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C423",
      "claim_text": "Python inline comment hint: Licensed under the Apache License, Version 2.0 (the \"License\");",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C385",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C424",
      "claim_text": "Python inline comment hint: you may not use this file except in compliance with the License.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C386",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C425",
      "claim_text": "Python inline comment hint: You may obtain a copy of the License at",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C387",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C426",
      "claim_text": "Python inline comment hint: http://www.apache.org/licenses/LICENSE-2.0",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C388",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C427",
      "claim_text": "Python inline comment hint: Unless required by applicable law or agreed to in writing, software",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C389",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C428",
      "claim_text": "Python inline comment hint: distributed under the License is distributed on an \"AS IS\" BASIS,",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C390",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C429",
      "claim_text": "Python inline comment hint: WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C391",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C430",
      "claim_text": "Python inline comment hint: See the License for the specific language governing permissions and",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C392",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C431",
      "claim_text": "Python inline comment hint: limitations under the License.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C393",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C432",
      "claim_text": "Docstring hint for Phi3Config: This is the configuration class to store the configuration of a [`Phi3Model`]. It is used to instantiate a Phi-3 model according to the specified arguments, defining the model architecture. Instantiating a configuration with the defaults will yield a similar configuration to that of the [microsoft/Phi-3-mini-4k-instruct](https://huggingface.co/microsoft/Phi-3-mini-4k-instruct). Configuration objects inherit from [`PretrainedConfig`] and can be used to control the model outputs. Read the documentation from [`PretrainedConfig`] for more information. Args: vocab_size (`int`, *optional*, defaults to 32064): Vocabulary size of the Phi-3 model. Defines the number of different tokens that can be represented by the `inputs_ids` passed when calling [`Phi3Model`]. hidden_size (`int`, *optional*, defaults to 3072): Dimension of the hidden representations. intermediate_size (`int`, *optional*, defaults to 8192): Dimension of the MLP representations. num_hidden_layers (`int`, *optional*, defaults to 32): Number of hidden layers in the Transformer decoder. num_attention_heads (`int`, *optional*, defaults to 32): Number of attention heads for each attention layer in the Transformer decoder. num_key_value_heads (`int`, *optional*): This is the number of key_value heads that should be used to implement Grouped Query Attention. If `num_key_value_heads=num_attention_heads`, the model will use Multi Head Attention (MHA), if `num_key_value_heads=1 the model will use Multi Query Attention (MQA) otherwise GQA is used. When converting a multi-head checkpoint to a GQA checkpoint, each group key and value head should be constructed by meanpooling all the original heads within that group. For more details checkout [this paper](https://arxiv.org/pdf/2305.13245.pdf). If it is not specified, will default to `num_attention_heads`. resid_pdrop (`float`, *optional*, defaults to 0.0): Dropout probability for mlp outputs. embd_pdrop (`int`, *optional*, defaults to 0.0): The dropout ratio for the embeddings. attention_dropout (`float`, *optional*, defaults to 0.0): The dropout ratio after computing the attention scores. hidden_act (`str` or `function`, *optional*, defaults to `\"silu\"`): The non-linear activation function (function or string) in the decoder. max_position_embeddings (`int`, *optional*, defaults to 4096): The maximum sequence length that this model might ever be used with. original_max_position_embeddings (`int`, *optional*, defaults to 4096): The maximum sequence length that this model was trained with. This is used to determine the size of the original RoPE embeddings when using long scaling. initializer_range (`float`, *optional*, defaults to 0.02): The standard deviation of the truncated_normal_initializer for initializing all weight matrices. rms_norm_eps (`float`, *optional*, defaults to 1e-05): The epsilon value used for the RMSNorm. use_cache (`bool`, *optional*, defaults to `True`): Whether or not the model should return the last key/values attentions (not used by all models). Only relevant if `config.is_decoder=True`. Whether to tie weight embeddings or not. tie_word_embeddings (`bool`, *optional*, defaults to `False`): Whether to tie weight embeddings rope_theta (`float`, *optional*, defaults to 10000.0): The base period of the RoPE embeddings. rope_scaling (`dict`, *optional*): The scaling strategy for the RoPE embeddings. If `None`, no scaling is applied. If a dictionary, it must contain the following keys: `type`, `short_factor` and `long_factor`. The `type` must be either `su` or `yarn` and the `short_factor` and `long_factor` must be lists of numbers with the same length as the hidden size divided by the number of attention heads divided by 2. bos_token_id (`int`, *optional*, defaults to 1): The id of the \"beginning-of-sequence\" token. eos_token_id (`int`, *optional*, defaults to 32000): The id of the \"end-of-sequence\" token. pad_token_id (`int`, *optional*, defaults to 32000): The id of the padding token. sliding_window (`int`, *optional*): Sliding window attention window size. If `None`, no sliding window is applied. Example: ```python >>> from transformers import Phi3Model, Phi3Config >>> # Initializing a Phi-3 style configuration >>> configuration = Phi3Config.from_pretrained(\"microsoft/Phi-3-mini-4k-instruct\") >>> # Initializing a model from the configuration >>> model = Phi3Model(configuration) >>> # Accessing the model configuration >>> configuration = model.config ```",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C394",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C433",
      "claim_text": "Docstring hint for Phi3Config._rope_scaling_validation: Validate the `rope_scaling` configuration.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C395",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C434",
      "claim_text": "Python inline comment hint: Hyper-parameters",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C396",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C435",
      "claim_text": "Python inline comment hint: Log on each process a small summary",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C397",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C436",
      "claim_text": "Python inline comment hint: Modle Loading",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C398",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C437",
      "claim_text": "Python inline comment hint: loading the model with flash-attenstion support",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C399",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C438",
      "claim_text": "Python inline comment hint: use unk rather than eos token to prevent endless generation",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C400",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C439",
      "claim_text": "Python inline comment hint: Data Processing",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C401",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C440",
      "claim_text": "Python inline comment hint: Add an empty system message if there is none",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C402",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C441",
      "claim_text": "Python inline comment hint: Training",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C403",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C442",
      "claim_text": "Python inline comment hint: Evaluation",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C404",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C443",
      "claim_text": "Python inline comment hint: ############",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C405",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C444",
      "claim_text": "Python inline comment hint: Model Constants",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C406",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C445",
      "claim_text": "Python inline comment hint: Modified from LLaVA: https://github.com/haotian-liu/LLaVA.git",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C407",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C446",
      "claim_text": "Docstring hint for SeparatorStyle: Different separator style.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C408",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C447",
      "claim_text": "Docstring hint for Conversation: A class that keeps all conversation history.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C409",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C448",
      "claim_text": "Python inline comment hint: Resize the image",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C410",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C449",
      "claim_text": "Docstring hint for select_best_resolution: Selects the best resolution from a list of possible resolutions based on the original size. Args: original_size (tuple): The original size of the image in the format (width, height). possible_resolutions (list): A list of possible resolutions in the format [(width1, height1), (width2, height2), ...]. Returns: tuple: The best fit resolution in the format (width, height).",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C411",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C450",
      "claim_text": "Docstring hint for resize_and_pad_image: Resize and pad an image to a target resolution while maintaining aspect ratio. Args: image (PIL.Image.Image): The input image. target_resolution (tuple): The target resolution (width, height) of the image. Returns: PIL.Image.Image: The resized and padded image.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C412",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C451",
      "claim_text": "Docstring hint for divide_to_patches: Divides an image into patches of a specified size. Args: image (PIL.Image.Image): The input image. patch_size (int): The size of each patch. Returns: list: A list of PIL.Image.Image objects representing the patches.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C413",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C452",
      "claim_text": "Docstring hint for get_anyres_image_grid_shape: Calculate the shape of the image patch grid after the preprocessing for images of any resolution. Args: image_size (tuple): The size of the input image in the format (width, height). grid_pinpoints (str): A string representation of a list of possible resolutions. patch_size (int): The size of each image patch. Returns: tuple: The shape of the image patch grid in the format (width, height).",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C414",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C453",
      "claim_text": "Docstring hint for process_anyres_image: Process an image with variable resolutions. Args: image (PIL.Image.Image): The input image to be processed. processor: The image processor object. grid_pinpoints (str): A string representation of a list of possible resolutions. Returns: torch.Tensor: A tensor containing the processed image patches.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C415",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C454",
      "claim_text": "Module docstring hint: A controller manages distributed workers. It sends worker addresses to clients.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C416",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C455",
      "claim_text": "Python inline comment hint: Dict[str -> WorkerInfo]",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C417",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C456",
      "claim_text": "Python inline comment hint: Directly return address",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C418",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C457",
      "claim_text": "Python inline comment hint: Check status before returning",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C419",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C458",
      "claim_text": "Python inline comment hint: Let the controller act as a worker to achieve hierarchical",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C420",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C459",
      "claim_text": "Python inline comment hint: management. This can be used to connect isolated sub networks.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C421",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C460",
      "claim_text": "Python inline comment hint: Hard cut-off",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C422",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C461",
      "claim_text": "Python inline comment hint: Hard cut-off for images",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C423",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C462",
      "claim_text": "Python inline comment hint: text = '<Image><image></Image>' + text",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C424",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C463",
      "claim_text": "Python inline comment hint: This generate call is skipped due to invalid inputs",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C425",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C464",
      "claim_text": "Python inline comment hint: First round of conversation",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C426",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C465",
      "claim_text": "Python inline comment hint: Query worker address",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C427",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C466",
      "claim_text": "Python inline comment hint: No available worker",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C428",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C467",
      "claim_text": "Python inline comment hint: Construct prompt",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C429",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C468",
      "claim_text": "Python inline comment hint: Make requests",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C430",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C469",
      "claim_text": "Python inline comment hint: Stream output",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C431",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C470",
      "claim_text": "Python inline comment hint: stop_btn = gr.Button(value=\"⏹️  Stop Generation\", interactive=False)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C432",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C471",
      "claim_text": "Python inline comment hint: Register listeners",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C433",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C472",
      "claim_text": "Module docstring hint: Manually register workers. Usage: python3 -m fastchat.serve.register_worker --controller http://localhost:21001 --worker-name http://localhost:21002",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C434",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C473",
      "claim_text": "Module docstring hint: A model worker executes the model.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C435",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C474",
      "claim_text": "Python inline comment hint: Select backend",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C436",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C475",
      "claim_text": "Python inline comment hint: replace_token = DEFAULT_IMAGE_TOKEN",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C437",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C476",
      "claim_text": "Python inline comment hint: if getattr(self.model.config, 'mm_use_im_start_end', False):",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C438",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C477",
      "claim_text": "Python inline comment hint: replace_token = DEFAULT_IM_START_TOKEN + replace_token + DEFAULT_IM_END_TOKEN",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C439",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C478",
      "claim_text": "Python inline comment hint: prompt = prompt.replace(DEFAULT_IMAGE_TOKEN, replace_token)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C440",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C479",
      "claim_text": "Python inline comment hint: max_context_length = getattr(model.config, 'max_position_embeddings', 2048)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C441",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C480",
      "claim_text": "Python inline comment hint: Set the format of root handlers",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C442",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C481",
      "claim_text": "Python inline comment hint: Redirect stdout and stderr to loggers",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C443",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C482",
      "claim_text": "Python inline comment hint: Get logger",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C444",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C483",
      "claim_text": "Python inline comment hint: Add a file handler for all loggers",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C445",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C484",
      "claim_text": "Python inline comment hint: From the io.TextIOWrapper docs:",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C446",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C485",
      "claim_text": "Python inline comment hint: On output, if newline is None, any '\\n' characters written",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C447",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C486",
      "claim_text": "Python inline comment hint: are translated to the system default line separator.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C448",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C487",
      "claim_text": "Python inline comment hint: By default sys.stdout.write() expects '\\n' newlines and then",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C449",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C488",
      "claim_text": "Python inline comment hint: translates them so this is still cross platform.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C450",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C489",
      "claim_text": "Python inline comment hint: Modified from github.com/openai/CLIP",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C451",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C490",
      "claim_text": "Docstring hint for StreamToLogger: Fake file-like stream object that redirects writes to a logger instance.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C452",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C491",
      "claim_text": "Docstring hint for disable_torch_init: Disable the redundant torch default initialization to accelerate model creation.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C453",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C492",
      "claim_text": "Docstring hint for violates_moderation: Check whether the text violates OpenAI moderation API.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C454",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C493",
      "claim_text": "Docstring hint for bytes_to_unicode: Returns list of utf-8 byte and a corresponding list of unicode strings. The reversible bpe codes work on unicode strings. This means you need a large # of unicode characters in your vocab if you want to avoid UNKs. When you're at something like a 10B token dataset you end up needing around 5K for decent coverage. This is a signficant percentage of your normal, say, 32K bpe vocab. To avoid that, we want lookup tables between utf-8 bytes and unicode strings. And avoids mapping to whitespace/control characters the bpe code barfs on.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C455",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C494",
      "claim_text": "Docstring hint for get_pairs: Return set of symbol pairs in a word. Word is represented as tuple of symbols (symbols being variable-length strings).",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C456",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C495",
      "claim_text": "Python inline comment hint: from .model import PointLLMLlamaForCausalLM",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C457",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C496",
      "claim_text": "Python inline comment hint: * pop the last message if it's None, this is used for multi-round dialogue",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C458",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C497",
      "claim_text": "Python inline comment hint: image = image.resize((224, 224))",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C459",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C498",
      "claim_text": "Python inline comment hint: fastchat",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C460",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C499",
      "claim_text": "Docstring hint for SeparatorStyle: Different separator style.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C461",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C500",
      "claim_text": "Docstring hint for Conversation: A class that keeps all conversation history.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C462",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C501",
      "claim_text": "Python inline comment hint: from .scanobjectNN import ScanObjectNN",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C463",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C502",
      "claim_text": "Python inline comment hint: * make a val dataset",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C464",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C503",
      "claim_text": "Python inline comment hint: * load train split",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C465",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C504",
      "claim_text": "Python inline comment hint: * use all data as training data",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C466",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C505",
      "claim_text": "Python inline comment hint: * default is simple_des, used for stage1 pre-train",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C467",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C506",
      "claim_text": "Python inline comment hint: Load the data list from JSON",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C468",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C507",
      "claim_text": "Python inline comment hint: * print the conversations_type",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C469",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C508",
      "claim_text": "Python inline comment hint: * print before filtering",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C470",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C509",
      "claim_text": "Python inline comment hint: * iterate the list and filter",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C471",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C510",
      "claim_text": "Python inline comment hint: * these two ids have corrupted colored point files, so filter them when use_color is True",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C472",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C511",
      "claim_text": "Python inline comment hint: Iterate the list, filter those \"conversation_type\" not in self.conversation_types",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C473",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C512",
      "claim_text": "Python inline comment hint: * print after filtering",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C474",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C513",
      "claim_text": "Python inline comment hint: * print the size of different conversation_type",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C475",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C514",
      "claim_text": "Docstring hint for make_object_point_data_module: Make dataset and collator for Joint3Ddataset with text and point cloud data.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C476",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C515",
      "claim_text": "Docstring hint for ObjectPointCloudDataset: Dataset utilities for objaverse.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C477",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C516",
      "claim_text": "Docstring hint for ObjectPointCloudDataset.__init__: split: only considered when data_args.split_train_val is True. conversation_types: tuple, used to filter the data, default is ('simple_description'), other types is: \"detailed_description\", \"single_round\", \"multi_round\". tokenizer: load point clouds only if None",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C478",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C517",
      "claim_text": "Docstring hint for ObjectPointCloudDataset.pc_norm: pc: NxC, return NxC",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C479",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C518",
      "claim_text": "Docstring hint for ObjectPointCloudDataset.__len__: Return number of utterances.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C480",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C519",
      "claim_text": "Python inline comment hint: * Sample Usage:",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C481",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C520",
      "claim_text": "Python inline comment hint: * from utils import LRUCache",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C482",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C521",
      "claim_text": "Python inline comment hint: * cache = LRUCache(capacity, max_access_count)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C483",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C522",
      "claim_text": "Python inline comment hint: if self.cache is None:",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C484",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C523",
      "claim_text": "Python inline comment hint: info_data = self.multiview_scannet[info_index]",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C485",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C524",
      "claim_text": "Python inline comment hint: else:",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C486",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C525",
      "claim_text": "Python inline comment hint: info_data = self.cache.get(info_index)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C487",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C526",
      "claim_text": "Python inline comment hint: if info_data is None or self.cache.get_access_count(info_index) >= self.cache.max_access_count:",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C488",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C527",
      "claim_text": "Python inline comment hint: # If not in cache, or accessed max_access_count times, load it and put it in cache",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C489",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C528",
      "claim_text": "Python inline comment hint: info_data = self.multiview_scannet[info_index]",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C490",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C529",
      "claim_text": "Python inline comment hint: self.cache.put(info_index, info_data)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C491",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C530",
      "claim_text": "Python inline comment hint: self.cache.reset_access_count(info_index)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C492",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C531",
      "claim_text": "Docstring hint for pc_norm: pc: NxC, return NxC",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C493",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C532",
      "claim_text": "Docstring hint for DataCollatorForPointTextDataset: Collate examples for mixed dataset with text and point cloud data.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C494",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C533",
      "claim_text": "Docstring hint for farthest_point_sample: Input: xyz: pointcloud data, [N, D] npoint: number of samples Return: centroids: sampled pointcloud index, [npoint, D]",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C495",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C534",
      "claim_text": "Docstring hint for pc_normalize: pc: Nx3 array This functions normalizes a point cloud to fit within a unit sphere. It first calculates the centroid of the point cloud and then subtracts it from all points before scaling all points to fit within a unit sphere.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C496",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C535",
      "claim_text": "Python inline comment hint: * Sample Usage:",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C497",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C536",
      "claim_text": "Python inline comment hint: * from utils import LRUCache",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C498",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C537",
      "claim_text": "Python inline comment hint: * cache = LRUCache(capacity, max_access_count)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C499",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C538",
      "claim_text": "Python inline comment hint: if self.cache is None:",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C500",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C539",
      "claim_text": "Python inline comment hint: info_data = self.multiview_scannet[info_index]",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C501",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C540",
      "claim_text": "Python inline comment hint: else:",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C502",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C541",
      "claim_text": "Python inline comment hint: info_data = self.cache.get(info_index)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C503",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C542",
      "claim_text": "Python inline comment hint: if info_data is None or self.cache.get_access_count(info_index) >= self.cache.max_access_count:",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C504",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C543",
      "claim_text": "Python inline comment hint: # If not in cache, or accessed max_access_count times, load it and put it in cache",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C505",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C544",
      "claim_text": "Python inline comment hint: info_data = self.multiview_scannet[info_index]",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C506",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C545",
      "claim_text": "Python inline comment hint: self.cache.put(info_index, info_data)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C507",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C546",
      "claim_text": "Python inline comment hint: self.cache.reset_access_count(info_index)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C508",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C547",
      "claim_text": "Docstring hint for pc_norm: pc: NxC, return NxC",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C509",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C548",
      "claim_text": "Docstring hint for DataCollatorForPointTextDataset: Collate examples for mixed dataset with text and point cloud data.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C510",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C549",
      "claim_text": "Docstring hint for farthest_point_sample: Input: xyz: pointcloud data, [N, D] npoint: number of samples Return: centroids: sampled pointcloud index, [npoint, D]",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C511",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C550",
      "claim_text": "Docstring hint for pc_normalize: pc: Nx3 array This functions normalizes a point cloud to fit within a unit sphere. It first calculates the centroid of the point cloud and then subtracts it from all points before scaling all points to fit within a unit sphere.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C512",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C551",
      "claim_text": "Python inline comment hint: Set the format of root handlers",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C513",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C552",
      "claim_text": "Python inline comment hint: Redirect stdout and stderr to loggers",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C514",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C553",
      "claim_text": "Python inline comment hint: Get logger",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C515",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C554",
      "claim_text": "Python inline comment hint: Add a file handler for all loggers",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C516",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C555",
      "claim_text": "Python inline comment hint: * get the logger_file's directory, and create it if not exist",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C517",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C556",
      "claim_text": "Python inline comment hint: From the io.TextIOWrapper docs:",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C518",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C557",
      "claim_text": "Python inline comment hint: On output, if newline is None, any '\\n' characters written",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C519",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C558",
      "claim_text": "Python inline comment hint: are translated to the system default line separator.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C520",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C559",
      "claim_text": "Python inline comment hint: By default sys.stdout.write() expects '\\n' newlines and then",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C521",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C560",
      "claim_text": "Python inline comment hint: translates them so this is still cross platform.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C522",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C561",
      "claim_text": "Python inline comment hint: url = \"https://api.chatanywhere.tech/v1/moderations\"",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C523",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C562",
      "claim_text": "Docstring hint for StreamToLogger: Fake file-like stream object that redirects writes to a logger instance.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C524",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C563",
      "claim_text": "Docstring hint for disable_torch_init: Disable the redundant torch default initialization to accelerate model creation.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C525",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C564",
      "claim_text": "Docstring hint for violates_moderation: Check whether the text violates OpenAI moderation API.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C526",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C565",
      "claim_text": "Python inline comment hint: yapf: disable",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C527",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C566",
      "claim_text": "Python inline comment hint: yapf: enable",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C528",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C567",
      "claim_text": "Python inline comment hint: 0~0.875",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C529",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C568",
      "claim_text": "Python inline comment hint: set to the first point",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C530",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C569",
      "claim_text": "Docstring hint for angle_axis: Returns a 4x4 rotation matrix that performs a rotation around axis by angle Parameters ---------- angle : float Angle to rotate by axis: np.ndarray Axis to rotate about Returns ------- torch.Tensor 3x3 rotation matrix",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C531",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C570",
      "claim_text": "Python inline comment hint: (B, C, npoint, nsample)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C532",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C571",
      "claim_text": "Python inline comment hint: (B, mlp[-1], npoint, nsample)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C533",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C572",
      "claim_text": "Python inline comment hint: (B, mlp[-1], npoint, 1)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C534",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C573",
      "claim_text": "Python inline comment hint: (B, mlp[-1], npoint)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C535",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C574",
      "claim_text": "Python inline comment hint: (B, C2 + C1, n)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C536",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C575",
      "claim_text": "Docstring hint for _PointnetSAModuleBase.forward: Parameters ---------- xyz : torch.Tensor (B, N, 3) tensor of the xyz coordinates of the features features : torch.Tensor (B, C, N) tensor of the descriptors of the the features Returns ------- new_xyz : torch.Tensor (B, npoint, 3) tensor of the new features' xyz new_features : torch.Tensor (B, \\sum_k(mlps[k][-1]), npoint) tensor of the new_features descriptors",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C537",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C576",
      "claim_text": "Docstring hint for PointnetSAModuleMSG: Pointnet set abstrction layer with multiscale grouping Parameters ---------- npoint : int Number of features radii : list of float32 list of radii to group with nsamples : list of int32 Number of samples in each ball query mlps : list of list of int32 Spec of the pointnet before the global max_pool for each scale bn : bool Use batchnorm",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C538",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C577",
      "claim_text": "Docstring hint for PointnetSAModule: Pointnet set abstrction layer Parameters ---------- npoint : int Number of features radius : float Radius of ball nsample : int Number of samples in the ball query mlp : list Spec of the pointnet before the global max_pool bn : bool Use batchnorm",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C539",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C578",
      "claim_text": "Docstring hint for PointnetFPModule: Propigates the features of one set to another Parameters ---------- mlp : list Pointnet module parameters bn : bool Use batchnorm",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C540",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C579",
      "claim_text": "Docstring hint for PointnetFPModule.forward: Parameters ---------- unknown : torch.Tensor (B, n, 3) tensor of the xyz positions of the unknown features known : torch.Tensor (B, m, 3) tensor of the xyz positions of the known features unknow_feats : torch.Tensor (B, C1, n) tensor of the features to be propigated to known_feats : torch.Tensor (B, C2, m) tensor of features to be propigated Returns ------- new_features : torch.Tensor (B, mlp[-1], n) tensor of the features of the unknown features",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C541",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C580",
      "claim_text": "Python inline comment hint: type(Any, torch.Tensor, torch.Tensor, torch.Tensor) -> Torch.Tensor",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C542",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C581",
      "claim_text": "Python inline comment hint: (B, 3, npoint, nsample)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C543",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C582",
      "claim_text": "Python inline comment hint: (B, C + 3, npoint, nsample)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C544",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C583",
      "claim_text": "Python inline comment hint: (B, 3 + C, 1, N)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C545",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C584",
      "claim_text": "Docstring hint for FurthestPointSampling.forward: Uses iterative furthest point sampling to select a set of npoint features that have the largest minimum distance Parameters ---------- xyz : torch.Tensor (B, N, 3) tensor where N > npoint npoint : int32 number of features in the sampled set Returns ------- torch.Tensor (B, npoint) tensor containing the set",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C546",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C585",
      "claim_text": "Docstring hint for GatherOperation.forward: Parameters ---------- features : torch.Tensor (B, C, N) tensor idx : torch.Tensor (B, npoint) tensor of the features to gather Returns ------- torch.Tensor (B, C, npoint) tensor",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C547",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C586",
      "claim_text": "Docstring hint for ThreeNN.forward: Find the three nearest neighbors of unknown in known Parameters ---------- unknown : torch.Tensor (B, n, 3) tensor of known features known : torch.Tensor (B, m, 3) tensor of unknown features Returns ------- dist : torch.Tensor (B, n, 3) l2 distance to the three nearest neighbors idx : torch.Tensor (B, n, 3) index of 3 nearest neighbors",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C548",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C587",
      "claim_text": "Docstring hint for ThreeInterpolate.forward: Performs weight linear interpolation on 3 features Parameters ---------- features : torch.Tensor (B, c, m) Features descriptors to be interpolated from idx : torch.Tensor (B, n, 3) three nearest neighbors of the target features in features weight : torch.Tensor (B, n, 3) weights Returns ------- torch.Tensor (B, c, n) tensor of the interpolated features",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C549",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C588",
      "claim_text": "Docstring hint for ThreeInterpolate.backward: Parameters ---------- grad_out : torch.Tensor (B, c, n) tensor with gradients of ouputs Returns ------- grad_features : torch.Tensor (B, c, m) tensor with gradients of features None None",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C550",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C589",
      "claim_text": "Docstring hint for GroupingOperation.forward: Parameters ---------- features : torch.Tensor (B, C, N) tensor of features to group idx : torch.Tensor (B, npoint, nsample) tensor containing the indicies of features to group with Returns ------- torch.Tensor (B, C, npoint, nsample) tensor",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C551",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C590",
      "claim_text": "Docstring hint for GroupingOperation.backward: Parameters ---------- grad_out : torch.Tensor (B, C, npoint, nsample) tensor of the gradients of the output from forward Returns ------- torch.Tensor (B, C, N) gradient of the features None",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C552",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C591",
      "claim_text": "Docstring hint for BallQuery.forward: Parameters ---------- radius : float radius of the balls nsample : int maximum number of features in the balls xyz : torch.Tensor (B, N, 3) xyz coordinates of the features new_xyz : torch.Tensor (B, npoint, 3) centers of the ball query Returns ------- torch.Tensor (B, npoint, nsample) tensor with the indicies of the features that form the query balls",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C553",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C592",
      "claim_text": "Docstring hint for QueryAndGroup: Groups with a ball query of radius Parameters --------- radius : float32 Radius of ball nsample : int32 Maximum number of features to gather in the ball",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C554",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C593",
      "claim_text": "Docstring hint for QueryAndGroup.forward: Parameters ---------- xyz : torch.Tensor xyz coordinates of the features (B, N, 3) new_xyz : torch.Tensor centriods (B, npoint, 3) features : torch.Tensor Descriptors of the features (B, C, N) Returns ------- new_features : torch.Tensor (B, 3 + C, npoint, nsample) tensor",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C555",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C594",
      "claim_text": "Docstring hint for GroupAll: Groups all features Parameters ---------",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C556",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C595",
      "claim_text": "Docstring hint for GroupAll.forward: Parameters ---------- xyz : torch.Tensor xyz coordinates of the features (B, N, 3) new_xyz : torch.Tensor Ignored features : torch.Tensor Descriptors of the features (B, C, N) Returns ------- new_features : torch.Tensor (B, C + 3, 1, N) tensor",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C557",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C596",
      "claim_text": "Python inline comment hint: print(choice_txt)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C558",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C597",
      "claim_text": "Python inline comment hint: \\\\n: GPT-3 can generate the lecture with more tokens.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C559",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C598",
      "claim_text": "Python inline comment hint: \\\\n: GPT-3 can generate the solution with more tokens",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C560",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C599",
      "claim_text": "Python inline comment hint: Inputs",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C561",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C600",
      "claim_text": "Python inline comment hint: upper bound experiment",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C562",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C601",
      "claim_text": "Python inline comment hint: Outputs",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C563",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C602",
      "claim_text": "Python inline comment hint: Inputs",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C564",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C603",
      "claim_text": "Python inline comment hint: upper bound experiment",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C565",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C604",
      "claim_text": "Python inline comment hint: Outputs",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C566",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C605",
      "claim_text": "Python inline comment hint: Inputs",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C567",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C606",
      "claim_text": "Python inline comment hint: upper bound experiment",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C568",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C607",
      "claim_text": "Python inline comment hint: Outputs",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C569",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C608",
      "claim_text": "Module docstring hint: This is just a utility that I use to extract the projector for quantized models. It is NOT necessary at all to train, or run inference/serve demos. Use this script ONLY if you fully understand its implications.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C570",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C609",
      "claim_text": "Python inline comment hint: Smaller models or model checkpoints saved by DeepSpeed.",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C571",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C610",
      "claim_text": "Module docstring hint: Train script for a single file Need to set the TPU address first: export XRT_TPU_CONFIG=\"localservice;0;localhost:51011\"",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C572",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C611",
      "claim_text": "Python inline comment hint: First element of model_output contains all token embeddings",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C573",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C612",
      "claim_text": "Python inline comment hint: Train Loop",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C574",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C613",
      "claim_text": "Python inline comment hint: Instantiate optimizer",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C575",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C614",
      "claim_text": "Python inline comment hint: Now we train the model",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C576",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C615",
      "claim_text": "Python inline comment hint: Get the batch data",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C577",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C616",
      "claim_text": "Python inline comment hint: print(index, \"batch {}x{}\".format(len(batch), \",\".join([str(len(b)) for b in batch])))",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C578",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C617",
      "claim_text": "Python inline comment hint: (anchor, positive)",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C579",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C618",
      "claim_text": "Python inline comment hint: Compute embeddings",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C580",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C619",
      "claim_text": "Python inline comment hint: Compute cross-entropy loss",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C581",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C620",
      "claim_text": "Python inline comment hint: Symmetric loss as in CLIP",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C582",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C621",
      "claim_text": "Python inline comment hint: Compute cross-entropy loss",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C583",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C622",
      "claim_text": "Python inline comment hint: One-way loss",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C584",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C623",
      "claim_text": "Docstring hint for RedditDataset: A class that handles the reddit data files",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C585",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C624",
      "claim_text": "Docstring hint for Dataset: A class that handles one dataset",
      "support_status": "partial",
      "evidence_ids": [
        "E1011",
        "E1012",
        "E1014",
        "E1015",
        "E1017"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C586",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    }
  ]
}
```