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
        "caption/description-style text supervision"
      ],
      "outputs": [
        "stable projector initialization for language conditioning"
      ],
      "modules": [
        {
          "path": "pointllm/train/train.py",
          "symbols": [
            "train"
          ],
          "role": "training-stage orchestration via argument combinations",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/model/pointllm.py",
          "symbols": [
            "PointLLMLlamaModel.forward"
          ],
          "role": "inject projected point features into language token stream",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/data/object_point_dataset.py",
          "symbols": [
            "ObjectPointCloudDataset"
          ],
          "role": "load/filter conversation supervision and point samples",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_projector/builder.py",
          "symbols": [
            "build_vision_projector"
          ],
          "role": "shared projector from encoder space to LLM hidden space",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/train/pointllm_trainer.py",
          "symbols": [
            "PointLLMTrainer"
          ],
          "role": "trainer-side save/checkpoint behavior",
          "category": "experiment-support",
          "is_novel": false
        }
      ],
      "mechanisms": [
        {
          "mechanism_id": "MECH-001",
          "description": "Establish projector-language coupling under mostly frozen backbone settings.",
          "support_status": "supported",
          "evidence_ids": [
            "E77",
            "E80",
            "E85",
            "E86",
            "E87",
            "E88",
            "E89",
            "E90",
            "E91",
            "E92",
            "E93",
            "E94",
            "E95",
            "E96",
            "E537",
            "E538",
            "E539",
            "E540",
            "E548",
            "E549",
            "E78",
            "E81",
            "E82",
            "E83",
            "E84",
            "E541",
            "E542",
            "E543",
            "E550",
            "E551",
            "E552",
            "E553",
            "E554",
            "E555",
            "E556",
            "E557",
            "E544",
            "E545",
            "E546",
            "E558",
            "E559",
            "E560",
            "E561",
            "E562",
            "E563",
            "E564",
            "E565",
            "E566",
            "E567",
            "E568",
            "E547",
            "E569",
            "E570",
            "E571",
            "E572",
            "E573",
            "E75",
            "E76",
            "E595",
            "E596",
            "E597",
            "E2412",
            "E228",
            "E230",
            "E236",
            "E234",
            "E233",
            "E232",
            "E237",
            "E243",
            "E244",
            "E245",
            "E246",
            "E247",
            "E248",
            "E249",
            "E250",
            "E251",
            "E136",
            "E139",
            "E137",
            "E148",
            "E149",
            "E150",
            "E151",
            "E152",
            "E153",
            "E154",
            "E155",
            "E156",
            "E157",
            "E140",
            "E144",
            "E147",
            "E146",
            "E145"
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
            }
          ]
        }
      ]
    },
    {
      "stage_id": "S2",
      "name": "Stage II: Rich Instruction Alignment",
      "purpose": "Expand from simple descriptions to richer instruction/dialog patterns while preserving projector continuity.",
      "inputs": [
        "detailed_description",
        "single_round",
        "multi_round"
      ],
      "outputs": [
        "improved instruction-following alignment before 3D transfer"
      ],
      "modules": [
        {
          "path": "pointllm/train/train.py",
          "symbols": [
            "train"
          ],
          "role": "training-stage orchestration via argument combinations",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/data/object_point_dataset.py",
          "symbols": [
            "ObjectPointCloudDataset"
          ],
          "role": "load/filter conversation supervision and point samples",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/data/utils.py",
          "symbols": [
            "preprocess_multimodal_point_cloud"
          ],
          "role": "convert point placeholders into multimodal training tokens",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/train/pointllm_trainer.py",
          "symbols": [
            "PointLLMTrainer"
          ],
          "role": "trainer-side save/checkpoint behavior",
          "category": "experiment-support",
          "is_novel": false
        }
      ],
      "mechanisms": [
        {
          "mechanism_id": "MECH-002",
          "description": "Expand from simple descriptions to richer instruction/dialog patterns while preserving projector continuity.",
          "support_status": "supported",
          "evidence_ids": [
            "E228",
            "E230",
            "E236",
            "E234",
            "E233",
            "E232",
            "E237",
            "E243",
            "E244",
            "E245",
            "E246",
            "E247",
            "E248",
            "E249",
            "E250",
            "E251",
            "E76",
            "E311",
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
            "E80",
            "E85",
            "E86",
            "E87",
            "E88",
            "E89",
            "E90",
            "E91",
            "E92",
            "E93",
            "E94",
            "E95",
            "E96",
            "E77",
            "E321",
            "E366",
            "E367",
            "E368",
            "E369",
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
            "E75",
            "E226",
            "E239",
            "E240",
            "E241",
            "E242",
            "E252",
            "E253",
            "E254",
            "E255",
            "E256",
            "E257",
            "E258",
            "E259",
            "E78",
            "E81",
            "E82",
            "E83",
            "E84",
            "E270",
            "E305",
            "E308",
            "E307",
            "E306",
            "E323",
            "E324",
            "E325",
            "E326",
            "E327",
            "E328",
            "E329",
            "E330",
            "E309",
            "E331",
            "E310",
            "E312",
            "E344"
          ],
          "confidence": "high",
          "submechanisms": []
        }
      ]
    },
    {
      "stage_id": "S3",
      "name": "Stage III: Point-Language Transfer",
      "purpose": "Use point-cloud token features and compact token aggregation to transfer prior alignment to 3D inputs.",
      "inputs": [
        "point cloud + conversation supervision pairs"
      ],
      "outputs": [
        "3D-grounded language responses"
      ],
      "modules": [
        {
          "path": "pointllm/train/train.py",
          "symbols": [
            "train"
          ],
          "role": "training-stage orchestration via argument combinations",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/model/pointllm.py",
          "symbols": [
            "PointLLMLlamaModel.forward"
          ],
          "role": "inject projected point features into language token stream",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/data/object_point_dataset.py",
          "symbols": [
            "ObjectPointCloudDataset"
          ],
          "role": "load/filter conversation supervision and point samples",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_encoder/point_encoder.py",
          "symbols": [
            "skeleton_Group"
          ],
          "role": "compact point-token aggregation with neighborhood routing",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_projector/builder.py",
          "symbols": [
            "build_vision_projector"
          ],
          "role": "shared projector from encoder space to LLM hidden space",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/train/pointllm_trainer.py",
          "symbols": [
            "PointLLMTrainer"
          ],
          "role": "trainer-side save/checkpoint behavior",
          "category": "experiment-support",
          "is_novel": false
        }
      ],
      "mechanisms": [
        {
          "mechanism_id": "MECH-003",
          "description": "Use point-cloud token features and compact token aggregation to transfer prior alignment to 3D inputs.",
          "support_status": "supported",
          "evidence_ids": [
            "E140",
            "E144",
            "E147",
            "E146",
            "E145",
            "E143",
            "E141",
            "E172",
            "E173",
            "E174",
            "E175",
            "E176",
            "E177",
            "E136",
            "E139",
            "E137",
            "E148",
            "E149",
            "E150",
            "E151",
            "E152",
            "E153",
            "E154",
            "E155",
            "E156",
            "E157",
            "E160",
            "E161",
            "E162",
            "E163",
            "E164",
            "E165",
            "E166",
            "E167",
            "E168",
            "E169",
            "E170",
            "E158",
            "E80",
            "E85",
            "E86",
            "E87",
            "E88",
            "E89",
            "E90",
            "E91",
            "E92",
            "E93",
            "E94",
            "E95",
            "E96",
            "E180",
            "E181",
            "E182",
            "E183",
            "E184",
            "E185",
            "E186",
            "E187",
            "E445",
            "E447",
            "E446",
            "E513",
            "E514",
            "E515",
            "E516",
            "E517",
            "E518",
            "E519",
            "E520",
            "E521",
            "E522",
            "E77",
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
            "E523",
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
            "E198"
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
            }
          ]
        }
      ]
    },
    {
      "stage_id": "S4",
      "name": "Runtime and saving behavior",
      "purpose": "Control runtime mechanics (trainer save behavior/logging/checkpoint flow).",
      "inputs": [
        "training arguments"
      ],
      "outputs": [
        "checkpoints/log artifacts"
      ],
      "modules": [
        {
          "path": "pointllm/train/train.py",
          "symbols": [
            "train"
          ],
          "role": "training-stage orchestration via argument combinations",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/model/pointllm.py",
          "symbols": [
            "PointLLMLlamaModel.forward"
          ],
          "role": "inject projected point features into language token stream",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/data/object_point_dataset.py",
          "symbols": [
            "ObjectPointCloudDataset"
          ],
          "role": "load/filter conversation supervision and point samples",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "llava/model/multimodal_projector/builder.py",
          "symbols": [
            "build_vision_projector"
          ],
          "role": "shared projector from encoder space to LLM hidden space",
          "category": "method-core",
          "is_novel": false
        },
        {
          "path": "pointllm/train/pointllm_trainer.py",
          "symbols": [
            "PointLLMTrainer"
          ],
          "role": "trainer-side save/checkpoint behavior",
          "category": "experiment-support",
          "is_novel": false
        }
      ],
      "mechanisms": [
        {
          "mechanism_id": "MECH-004",
          "description": "Control runtime mechanics (trainer save behavior/logging/checkpoint flow).",
          "support_status": "supported",
          "evidence_ids": [
            "E579",
            "E580",
            "E583",
            "E584",
            "E585",
            "E586",
            "E587",
            "E588",
            "E589",
            "E590",
            "E591",
            "E592",
            "E593",
            "E577",
            "E581",
            "E582",
            "E80",
            "E85",
            "E86",
            "E87",
            "E88",
            "E89",
            "E90",
            "E91",
            "E92",
            "E93",
            "E94",
            "E95",
            "E96",
            "E77",
            "E429",
            "E432",
            "E431",
            "E464",
            "E465",
            "E466",
            "E467",
            "E468",
            "E469",
            "E470",
            "E471",
            "E472",
            "E473",
            "E136",
            "E139",
            "E137",
            "E148",
            "E149",
            "E150",
            "E151",
            "E152",
            "E153",
            "E154",
            "E155",
            "E156",
            "E157",
            "E140",
            "E144",
            "E147",
            "E146",
            "E145",
            "E143",
            "E141",
            "E172",
            "E173",
            "E174",
            "E175",
            "E176",
            "E177",
            "E76",
            "E78",
            "E81",
            "E82",
            "E83",
            "E84",
            "E2410",
            "E2617",
            "E2616",
            "E2638",
            "E2639",
            "E2640",
            "E2641",
            "E2619",
            "E2646",
            "E2647",
            "E2648",
            "E2624",
            "E2632",
            "E2669",
            "E2670",
            "E474",
            "E475",
            "E226",
            "E239",
            "E240",
            "E241"
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
            }
          ]
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
    "Excluded source: lava-vicuna_2024_4_Phi-3-mini-4k-instruct/README.md (excluded from main evidence chain).",
    "Excluded source: pretrained_weight/clip_used_in_Uni3D/README.md (excluded from main evidence chain).",
    "Excluded source: pretrained_weight/eval_model_weight/sup-simcse-roberta-large/README.md (excluded from main evidence chain).",
    "Excluded source: pretrained_weight/eval_model_weight/all-mpnet-base-v2/README.md (excluded from main evidence chain).",
    "Excluded source: release/5M_data_seting/weight/stage_2/5M_low_lr_1e5/README.md (excluded from main evidence chain).",
    "Excluded source: release/5M_data_seting/weight/stage_3/use_stage_5M_data_lr_1e5/README.md (excluded from main evidence chain).",
    "Excluded source: release/paper/weight/stage_3/README.md (excluded from main evidence chain).",
    "Excluded source: release/paper/weight/stage_2/README.md (excluded from main evidence chain).",
    "Excluded source: pointnet++/Pointnet2_PyTorch/README.rst (excluded from main evidence chain)."
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
      "path": "lava-vicuna_2024_4_Phi-3-mini-4k-instruct/README.md",
      "reason": "excluded from main evidence chain"
    },
    {
      "path": "pretrained_weight/clip_used_in_Uni3D/README.md",
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
      "path": "release/5M_data_seting/weight/stage_2/5M_low_lr_1e5/README.md",
      "reason": "excluded from main evidence chain"
    },
    {
      "path": "release/5M_data_seting/weight/stage_3/use_stage_5M_data_lr_1e5/README.md",
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
      "path": "pointnet++/Pointnet2_PyTorch/README.rst",
      "reason": "excluded from main evidence chain"
    }
  ],
  "author_logic_priority": true,
  "frozen_mechanisms": [
    {
      "mechanism_id": "MECH-001",
      "mechanism_name": "Stage I: Text-First Interface Warmup",
      "mechanism_description": "Establish projector-language coupling under mostly frozen backbone settings.",
      "parent_stage_id": "S1",
      "inputs": [
        "caption/description-style text supervision"
      ],
      "outputs": [
        "stable projector initialization for language conditioning"
      ],
      "implementation_anchor": {
        "path": "pointllm/train/pointllm_trainer.py",
        "symbols": [
          "PointLLMTrainer"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E77",
        "E80",
        "E85",
        "E86",
        "E87",
        "E88",
        "E89",
        "E90",
        "E91",
        "E92",
        "E93",
        "E94",
        "E95",
        "E96",
        "E537",
        "E538",
        "E539",
        "E540",
        "E548",
        "E549",
        "E78",
        "E81",
        "E82",
        "E83",
        "E84",
        "E541",
        "E542",
        "E543",
        "E550",
        "E551",
        "E552",
        "E553",
        "E554",
        "E555",
        "E556",
        "E557",
        "E544",
        "E545",
        "E546",
        "E558",
        "E559",
        "E560",
        "E561",
        "E562",
        "E563",
        "E564",
        "E565",
        "E566",
        "E567",
        "E568",
        "E547",
        "E569",
        "E570",
        "E571",
        "E572",
        "E573",
        "E75",
        "E76",
        "E595",
        "E596",
        "E597",
        "E2412",
        "E228",
        "E230",
        "E236",
        "E234",
        "E233",
        "E232",
        "E237",
        "E243",
        "E244",
        "E245",
        "E246",
        "E247",
        "E248",
        "E249",
        "E250",
        "E251",
        "E136",
        "E139",
        "E137",
        "E148",
        "E149",
        "E150",
        "E151",
        "E152",
        "E153",
        "E154",
        "E155",
        "E156",
        "E157",
        "E140",
        "E144",
        "E147",
        "E146",
        "E145"
      ]
    },
    {
      "mechanism_id": "MECH-002",
      "mechanism_name": "Stage II: Rich Instruction Alignment",
      "mechanism_description": "Expand from simple descriptions to richer instruction/dialog patterns while preserving projector continuity.",
      "parent_stage_id": "S2",
      "inputs": [
        "detailed_description",
        "single_round",
        "multi_round"
      ],
      "outputs": [
        "improved instruction-following alignment before 3D transfer"
      ],
      "implementation_anchor": {
        "path": "pointllm/data/object_point_dataset.py",
        "symbols": [
          "ObjectPointCloudDataset"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E228",
        "E230",
        "E236",
        "E234",
        "E233",
        "E232",
        "E237",
        "E243",
        "E244",
        "E245",
        "E246",
        "E247",
        "E248",
        "E249",
        "E250",
        "E251",
        "E76",
        "E311",
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
        "E80",
        "E85",
        "E86",
        "E87",
        "E88",
        "E89",
        "E90",
        "E91",
        "E92",
        "E93",
        "E94",
        "E95",
        "E96",
        "E77",
        "E321",
        "E366",
        "E367",
        "E368",
        "E369",
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
        "E75",
        "E226",
        "E239",
        "E240",
        "E241",
        "E242",
        "E252",
        "E253",
        "E254",
        "E255",
        "E256",
        "E257",
        "E258",
        "E259",
        "E78",
        "E81",
        "E82",
        "E83",
        "E84",
        "E270",
        "E305",
        "E308",
        "E307",
        "E306",
        "E323",
        "E324",
        "E325",
        "E326",
        "E327",
        "E328",
        "E329",
        "E330",
        "E309",
        "E331",
        "E310",
        "E312",
        "E344"
      ]
    },
    {
      "mechanism_id": "MECH-003",
      "mechanism_name": "Stage III: Point-Language Transfer",
      "mechanism_description": "Use point-cloud token features and compact token aggregation to transfer prior alignment to 3D inputs.",
      "parent_stage_id": "S3",
      "inputs": [
        "point cloud + conversation supervision pairs"
      ],
      "outputs": [
        "3D-grounded language responses"
      ],
      "implementation_anchor": {
        "path": "pointllm/model/pointllm.py",
        "symbols": [
          "PointLLMLlamaModel.forward"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E140",
        "E144",
        "E147",
        "E146",
        "E145",
        "E143",
        "E141",
        "E172",
        "E173",
        "E174",
        "E175",
        "E176",
        "E177",
        "E136",
        "E139",
        "E137",
        "E148",
        "E149",
        "E150",
        "E151",
        "E152",
        "E153",
        "E154",
        "E155",
        "E156",
        "E157",
        "E160",
        "E161",
        "E162",
        "E163",
        "E164",
        "E165",
        "E166",
        "E167",
        "E168",
        "E169",
        "E170",
        "E158",
        "E80",
        "E85",
        "E86",
        "E87",
        "E88",
        "E89",
        "E90",
        "E91",
        "E92",
        "E93",
        "E94",
        "E95",
        "E96",
        "E180",
        "E181",
        "E182",
        "E183",
        "E184",
        "E185",
        "E186",
        "E187",
        "E445",
        "E447",
        "E446",
        "E513",
        "E514",
        "E515",
        "E516",
        "E517",
        "E518",
        "E519",
        "E520",
        "E521",
        "E522",
        "E77",
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
        "E523",
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
        "E198"
      ]
    },
    {
      "mechanism_id": "MECH-004",
      "mechanism_name": "Runtime and saving behavior",
      "mechanism_description": "Control runtime mechanics (trainer save behavior/logging/checkpoint flow).",
      "parent_stage_id": "S4",
      "inputs": [
        "training arguments"
      ],
      "outputs": [
        "checkpoints/log artifacts"
      ],
      "implementation_anchor": {
        "path": "pointllm/train/pointllm_trainer.py",
        "symbols": [
          "PointLLMTrainer"
        ]
      },
      "distinguishing_level": "none",
      "author_claim_relation": "supported",
      "evidence_span_ids": [
        "E579",
        "E580",
        "E583",
        "E584",
        "E585",
        "E586",
        "E587",
        "E588",
        "E589",
        "E590",
        "E591",
        "E592",
        "E593",
        "E577",
        "E581",
        "E582",
        "E80",
        "E85",
        "E86",
        "E87",
        "E88",
        "E89",
        "E90",
        "E91",
        "E92",
        "E93",
        "E94",
        "E95",
        "E96",
        "E77",
        "E429",
        "E432",
        "E431",
        "E464",
        "E465",
        "E466",
        "E467",
        "E468",
        "E469",
        "E470",
        "E471",
        "E472",
        "E473",
        "E136",
        "E139",
        "E137",
        "E148",
        "E149",
        "E150",
        "E151",
        "E152",
        "E153",
        "E154",
        "E155",
        "E156",
        "E157",
        "E140",
        "E144",
        "E147",
        "E146",
        "E145",
        "E143",
        "E141",
        "E172",
        "E173",
        "E174",
        "E175",
        "E176",
        "E177",
        "E76",
        "E78",
        "E81",
        "E82",
        "E83",
        "E84",
        "E2410",
        "E2617",
        "E2616",
        "E2638",
        "E2639",
        "E2640",
        "E2641",
        "E2619",
        "E2646",
        "E2647",
        "E2648",
        "E2624",
        "E2632",
        "E2669",
        "E2670",
        "E474",
        "E475",
        "E226",
        "E239",
        "E240",
        "E241"
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
      "Stage II: Rich Instruction Alignment",
      "Stage III: Point-Language Transfer",
      "Runtime and saving behavior"
    ],
    "author_unsupported_parts": []
  },
  "unsupported_author_parts": [],
  "claim_contracts": [
    {
      "claim_id": "C1",
      "claim_intent": "The method contains a paper-facing stage named Stage I: Text-First Interface Warmup.",
      "support_status": "supported",
      "evidence_span_ids": [
        "E77",
        "E80",
        "E85",
        "E86",
        "E87",
        "E88",
        "E89",
        "E90",
        "E91",
        "E92",
        "E93",
        "E94",
        "E95",
        "E96",
        "E537",
        "E538",
        "E539",
        "E540",
        "E548",
        "E549",
        "E78",
        "E81",
        "E82",
        "E83",
        "E84",
        "E541",
        "E542",
        "E543",
        "E550",
        "E551",
        "E552",
        "E553",
        "E554",
        "E555",
        "E556",
        "E557",
        "E544",
        "E545",
        "E546",
        "E558",
        "E559",
        "E560",
        "E561",
        "E562",
        "E563",
        "E564",
        "E565",
        "E566",
        "E567",
        "E568",
        "E547",
        "E569",
        "E570",
        "E571",
        "E572",
        "E573",
        "E75",
        "E76",
        "E595",
        "E596",
        "E597",
        "E2412",
        "E228",
        "E230",
        "E236",
        "E234",
        "E233",
        "E232",
        "E237",
        "E243",
        "E244",
        "E245",
        "E246",
        "E247",
        "E248",
        "E249",
        "E250",
        "E251",
        "E136",
        "E139",
        "E137",
        "E148",
        "E149",
        "E150",
        "E151",
        "E152",
        "E153",
        "E154",
        "E155",
        "E156",
        "E157",
        "E140",
        "E144",
        "E147",
        "E146",
        "E145"
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
        "E228",
        "E230",
        "E236",
        "E234",
        "E233",
        "E232",
        "E237",
        "E243",
        "E244",
        "E245",
        "E246",
        "E247",
        "E248",
        "E249",
        "E250",
        "E251",
        "E76",
        "E311",
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
        "E80",
        "E85",
        "E86",
        "E87",
        "E88",
        "E89",
        "E90",
        "E91",
        "E92",
        "E93",
        "E94",
        "E95",
        "E96",
        "E77",
        "E321",
        "E366",
        "E367",
        "E368",
        "E369",
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
        "E75",
        "E226",
        "E239",
        "E240",
        "E241",
        "E242",
        "E252",
        "E253",
        "E254",
        "E255",
        "E256",
        "E257",
        "E258",
        "E259",
        "E78",
        "E81",
        "E82",
        "E83",
        "E84",
        "E270",
        "E305",
        "E308",
        "E307",
        "E306",
        "E323",
        "E324",
        "E325",
        "E326",
        "E327",
        "E328",
        "E329",
        "E330",
        "E309",
        "E331",
        "E310",
        "E312",
        "E344"
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
        "E140",
        "E144",
        "E147",
        "E146",
        "E145",
        "E143",
        "E141",
        "E172",
        "E173",
        "E174",
        "E175",
        "E176",
        "E177",
        "E136",
        "E139",
        "E137",
        "E148",
        "E149",
        "E150",
        "E151",
        "E152",
        "E153",
        "E154",
        "E155",
        "E156",
        "E157",
        "E160",
        "E161",
        "E162",
        "E163",
        "E164",
        "E165",
        "E166",
        "E167",
        "E168",
        "E169",
        "E170",
        "E158",
        "E80",
        "E85",
        "E86",
        "E87",
        "E88",
        "E89",
        "E90",
        "E91",
        "E92",
        "E93",
        "E94",
        "E95",
        "E96",
        "E180",
        "E181",
        "E182",
        "E183",
        "E184",
        "E185",
        "E186",
        "E187",
        "E445",
        "E447",
        "E446",
        "E513",
        "E514",
        "E515",
        "E516",
        "E517",
        "E518",
        "E519",
        "E520",
        "E521",
        "E522",
        "E77",
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
        "E523",
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
        "E198"
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
        "E579",
        "E580",
        "E583",
        "E584",
        "E585",
        "E586",
        "E587",
        "E588",
        "E589",
        "E590",
        "E591",
        "E592",
        "E593",
        "E577",
        "E581",
        "E582",
        "E80",
        "E85",
        "E86",
        "E87",
        "E88",
        "E89",
        "E90",
        "E91",
        "E92",
        "E93",
        "E94",
        "E95",
        "E96",
        "E77",
        "E429",
        "E432",
        "E431",
        "E464",
        "E465",
        "E466",
        "E467",
        "E468",
        "E469",
        "E470",
        "E471",
        "E472",
        "E473",
        "E136",
        "E139",
        "E137",
        "E148",
        "E149",
        "E150",
        "E151",
        "E152",
        "E153",
        "E154",
        "E155",
        "E156",
        "E157",
        "E140",
        "E144",
        "E147",
        "E146",
        "E145",
        "E143",
        "E141",
        "E172",
        "E173",
        "E174",
        "E175",
        "E176",
        "E177",
        "E76",
        "E78",
        "E81",
        "E82",
        "E83",
        "E84",
        "E2410",
        "E2617",
        "E2616",
        "E2638",
        "E2639",
        "E2640",
        "E2641",
        "E2619",
        "E2646",
        "E2647",
        "E2648",
        "E2624",
        "E2632",
        "E2669",
        "E2670",
        "E474",
        "E475",
        "E226",
        "E239",
        "E240",
        "E241"
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
        "E77",
        "E80",
        "E85",
        "E86",
        "E87",
        "E88",
        "E89",
        "E90",
        "E91",
        "E92",
        "E93",
        "E94",
        "E95",
        "E96",
        "E537",
        "E538",
        "E539",
        "E540",
        "E548",
        "E549",
        "E78",
        "E81",
        "E82",
        "E83",
        "E84",
        "E541",
        "E542",
        "E543",
        "E550",
        "E551",
        "E552",
        "E553",
        "E554",
        "E555",
        "E556",
        "E557",
        "E544",
        "E545",
        "E546",
        "E558",
        "E559",
        "E560",
        "E561",
        "E562",
        "E563",
        "E564",
        "E565",
        "E566",
        "E567",
        "E568",
        "E547",
        "E569",
        "E570",
        "E571",
        "E572",
        "E573",
        "E75",
        "E76",
        "E595",
        "E596",
        "E597",
        "E2412",
        "E228",
        "E230",
        "E236",
        "E234",
        "E233",
        "E232",
        "E237",
        "E243",
        "E244",
        "E245",
        "E246",
        "E247",
        "E248",
        "E249",
        "E250",
        "E251",
        "E136",
        "E139",
        "E137",
        "E148",
        "E149",
        "E150",
        "E151",
        "E152",
        "E153",
        "E154",
        "E155",
        "E156",
        "E157",
        "E140",
        "E144",
        "E147",
        "E146",
        "E145"
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
        "E228",
        "E230",
        "E236",
        "E234",
        "E233",
        "E232",
        "E237",
        "E243",
        "E244",
        "E245",
        "E246",
        "E247",
        "E248",
        "E249",
        "E250",
        "E251",
        "E76",
        "E311",
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
        "E80",
        "E85",
        "E86",
        "E87",
        "E88",
        "E89",
        "E90",
        "E91",
        "E92",
        "E93",
        "E94",
        "E95",
        "E96",
        "E77",
        "E321",
        "E366",
        "E367",
        "E368",
        "E369",
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
        "E75",
        "E226",
        "E239",
        "E240",
        "E241",
        "E242",
        "E252",
        "E253",
        "E254",
        "E255",
        "E256",
        "E257",
        "E258",
        "E259",
        "E78",
        "E81",
        "E82",
        "E83",
        "E84",
        "E270",
        "E305",
        "E308",
        "E307",
        "E306",
        "E323",
        "E324",
        "E325",
        "E326",
        "E327",
        "E328",
        "E329",
        "E330",
        "E309",
        "E331",
        "E310",
        "E312",
        "E344"
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
        "E140",
        "E144",
        "E147",
        "E146",
        "E145",
        "E143",
        "E141",
        "E172",
        "E173",
        "E174",
        "E175",
        "E176",
        "E177",
        "E136",
        "E139",
        "E137",
        "E148",
        "E149",
        "E150",
        "E151",
        "E152",
        "E153",
        "E154",
        "E155",
        "E156",
        "E157",
        "E160",
        "E161",
        "E162",
        "E163",
        "E164",
        "E165",
        "E166",
        "E167",
        "E168",
        "E169",
        "E170",
        "E158",
        "E80",
        "E85",
        "E86",
        "E87",
        "E88",
        "E89",
        "E90",
        "E91",
        "E92",
        "E93",
        "E94",
        "E95",
        "E96",
        "E180",
        "E181",
        "E182",
        "E183",
        "E184",
        "E185",
        "E186",
        "E187",
        "E445",
        "E447",
        "E446",
        "E513",
        "E514",
        "E515",
        "E516",
        "E517",
        "E518",
        "E519",
        "E520",
        "E521",
        "E522",
        "E77",
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
        "E523",
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
        "E198"
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
        "E579",
        "E580",
        "E583",
        "E584",
        "E585",
        "E586",
        "E587",
        "E588",
        "E589",
        "E590",
        "E591",
        "E592",
        "E593",
        "E577",
        "E581",
        "E582",
        "E80",
        "E85",
        "E86",
        "E87",
        "E88",
        "E89",
        "E90",
        "E91",
        "E92",
        "E93",
        "E94",
        "E95",
        "E96",
        "E77",
        "E429",
        "E432",
        "E431",
        "E464",
        "E465",
        "E466",
        "E467",
        "E468",
        "E469",
        "E470",
        "E471",
        "E472",
        "E473",
        "E136",
        "E139",
        "E137",
        "E148",
        "E149",
        "E150",
        "E151",
        "E152",
        "E153",
        "E154",
        "E155",
        "E156",
        "E157",
        "E140",
        "E144",
        "E147",
        "E146",
        "E145",
        "E143",
        "E141",
        "E172",
        "E173",
        "E174",
        "E175",
        "E176",
        "E177",
        "E76",
        "E78",
        "E81",
        "E82",
        "E83",
        "E84",
        "E2410",
        "E2617",
        "E2616",
        "E2638",
        "E2639",
        "E2640",
        "E2641",
        "E2619",
        "E2646",
        "E2647",
        "E2648",
        "E2624",
        "E2632",
        "E2669",
        "E2670",
        "E474",
        "E475",
        "E226",
        "E239",
        "E240",
        "E241"
      ],
      "allowed_wording_boundary": "Do not add behavior beyond the cited implementation anchors and evidence spans.",
      "required_qualifiers": [],
      "review_question_id": ""
    },
    {
      "claim_id": "C9",
      "claim_intent": "Python inline comment hint: you may not use this file except in compliance with the License.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-9"
    },
    {
      "claim_id": "C10",
      "claim_intent": "Python inline comment hint: * for two stage training",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-10"
    },
    {
      "claim_id": "C11",
      "claim_intent": "Python inline comment hint: * use with torch.inference_mode to control, not requires_grad for fsdp for second stage",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-11"
    },
    {
      "claim_id": "C12",
      "claim_intent": "Python inline comment hint: * fix pointnet for first stage, need for fsdp in stage2",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-12"
    },
    {
      "claim_id": "C13",
      "claim_intent": "Python inline comment hint: * we assume in stage2, llm, point_backbone, and projection layer can be loaded from the model checkpoint",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-13"
    },
    {
      "claim_id": "C14",
      "claim_intent": "Python inline comment hint: * stage2",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-14"
    },
    {
      "claim_id": "C15",
      "claim_intent": "Python inline comment hint: layer.register_forward_hook(print_layer_output)",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-15"
    },
    {
      "claim_id": "C16",
      "claim_intent": "Docstring hint for safe_save_model_for_hf_trainer: Collects the state dict and dump to disk.",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-16"
    },
    {
      "claim_id": "C17",
      "claim_intent": "Python inline comment hint: * add logger",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-17"
    },
    {
      "claim_id": "C18",
      "claim_intent": "Python inline comment hint: address of config file, in the same dir of this file",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-18"
    },
    {
      "claim_id": "C19",
      "claim_intent": "Python inline comment hint: * default for v1.1, v1.2 uses PointTransformer_8192point_2layer.yaml",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-19"
    },
    {
      "claim_id": "C20",
      "claim_intent": "Python inline comment hint: * default is false",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-20"
    },
    {
      "claim_id": "C21",
      "claim_intent": "Python inline comment hint: * number of output features, with cls token",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-21"
    },
    {
      "claim_id": "C22",
      "claim_intent": "Python inline comment hint: a list",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-22"
    },
    {
      "claim_id": "C23",
      "claim_intent": "Python inline comment hint: * print relevant info with projection layers",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-23"
    },
    {
      "claim_id": "C24",
      "claim_intent": "Python inline comment hint: Add projection layer with linear layers and GELU activation",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-24"
    },
    {
      "claim_id": "C25",
      "claim_intent": "Python inline comment hint: Single layer",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-25"
    },
    {
      "claim_id": "C26",
      "claim_intent": "Python inline comment hint: Enable model/pipeline parallelism",
      "support_status": "partially_supported",
      "evidence_span_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "allowed_wording_boundary": "Use only if hard evidence spans verify the comment-driven insight.",
      "required_qualifiers": [
        "partially supported by implementation evidence"
      ],
      "review_question_id": "RQ-26"
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
      "claim_text": "Establish projector-language coupling under mostly frozen backbone settings.",
      "support_status": "supported",
      "evidence_ids": [
        "E77",
        "E80",
        "E85",
        "E86",
        "E87",
        "E88",
        "E89",
        "E90",
        "E91",
        "E92",
        "E93",
        "E94",
        "E95",
        "E96",
        "E537",
        "E538",
        "E539",
        "E540",
        "E548",
        "E549",
        "E78",
        "E81",
        "E82",
        "E83",
        "E84",
        "E541",
        "E542",
        "E543",
        "E550",
        "E551",
        "E552",
        "E553",
        "E554",
        "E555",
        "E556",
        "E557",
        "E544",
        "E545",
        "E546",
        "E558",
        "E559",
        "E560",
        "E561",
        "E562",
        "E563",
        "E564",
        "E565",
        "E566",
        "E567",
        "E568",
        "E547",
        "E569",
        "E570",
        "E571",
        "E572",
        "E573",
        "E75",
        "E76",
        "E595",
        "E596",
        "E597",
        "E2412",
        "E228",
        "E230",
        "E236",
        "E234",
        "E233",
        "E232",
        "E237",
        "E243",
        "E244",
        "E245",
        "E246",
        "E247",
        "E248",
        "E249",
        "E250",
        "E251",
        "E136",
        "E139",
        "E137",
        "E148",
        "E149",
        "E150",
        "E151",
        "E152",
        "E153",
        "E154",
        "E155",
        "E156",
        "E157",
        "E140",
        "E144",
        "E147",
        "E146",
        "E145"
      ],
      "mechanism_ids": [
        "MECH-001"
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
        "MECH-001"
      ],
      "source": "submechanism:SUBMECH1",
      "caveats": []
    },
    {
      "claim_id": "C3",
      "claim_text": "SimpleResBlock exposes generic code behaviors: pointwise transformation, normalization. Detected implementation patterns include positionwise feed forward, layer normalization.",
      "support_status": "supported",
      "evidence_ids": [
        "E541"
      ],
      "mechanism_ids": [
        "MECH-001"
      ],
      "source": "submechanism:SUBMECH4",
      "caveats": []
    },
    {
      "claim_id": "C4",
      "claim_text": "Mlp exposes generic code behaviors: pointwise transformation, normalization, regularization. Detected implementation patterns include positionwise feed forward, layer normalization, dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E544"
      ],
      "mechanism_ids": [
        "MECH-001"
      ],
      "source": "submechanism:SUBMECH5",
      "caveats": []
    },
    {
      "claim_id": "C5",
      "claim_text": "build_vision_projector exposes generic code behaviors: pointwise transformation. Detected implementation patterns include positionwise feed forward.",
      "support_status": "supported",
      "evidence_ids": [
        "E547"
      ],
      "mechanism_ids": [
        "MECH-001"
      ],
      "source": "submechanism:SUBMECH6",
      "caveats": []
    },
    {
      "claim_id": "C6",
      "claim_text": "Expand from simple descriptions to richer instruction/dialog patterns while preserving projector continuity.",
      "support_status": "supported",
      "evidence_ids": [
        "E228",
        "E230",
        "E236",
        "E234",
        "E233",
        "E232",
        "E237",
        "E243",
        "E244",
        "E245",
        "E246",
        "E247",
        "E248",
        "E249",
        "E250",
        "E251",
        "E76",
        "E311",
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
        "E80",
        "E85",
        "E86",
        "E87",
        "E88",
        "E89",
        "E90",
        "E91",
        "E92",
        "E93",
        "E94",
        "E95",
        "E96",
        "E77",
        "E321",
        "E366",
        "E367",
        "E368",
        "E369",
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
        "E75",
        "E226",
        "E239",
        "E240",
        "E241",
        "E242",
        "E252",
        "E253",
        "E254",
        "E255",
        "E256",
        "E257",
        "E258",
        "E259",
        "E78",
        "E81",
        "E82",
        "E83",
        "E84",
        "E270",
        "E305",
        "E308",
        "E307",
        "E306",
        "E323",
        "E324",
        "E325",
        "E326",
        "E327",
        "E328",
        "E329",
        "E330",
        "E309",
        "E331",
        "E310",
        "E312",
        "E344"
      ],
      "mechanism_ids": [
        "MECH-002"
      ],
      "source": "method_mechanism",
      "caveats": []
    },
    {
      "claim_id": "C7",
      "claim_text": "Use point-cloud token features and compact token aggregation to transfer prior alignment to 3D inputs.",
      "support_status": "supported",
      "evidence_ids": [
        "E140",
        "E144",
        "E147",
        "E146",
        "E145",
        "E143",
        "E141",
        "E172",
        "E173",
        "E174",
        "E175",
        "E176",
        "E177",
        "E136",
        "E139",
        "E137",
        "E148",
        "E149",
        "E150",
        "E151",
        "E152",
        "E153",
        "E154",
        "E155",
        "E156",
        "E157",
        "E160",
        "E161",
        "E162",
        "E163",
        "E164",
        "E165",
        "E166",
        "E167",
        "E168",
        "E169",
        "E170",
        "E158",
        "E80",
        "E85",
        "E86",
        "E87",
        "E88",
        "E89",
        "E90",
        "E91",
        "E92",
        "E93",
        "E94",
        "E95",
        "E96",
        "E180",
        "E181",
        "E182",
        "E183",
        "E184",
        "E185",
        "E186",
        "E187",
        "E445",
        "E447",
        "E446",
        "E513",
        "E514",
        "E515",
        "E516",
        "E517",
        "E518",
        "E519",
        "E520",
        "E521",
        "E522",
        "E77",
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
        "E523",
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
        "E198"
      ],
      "mechanism_ids": [
        "MECH-003"
      ],
      "source": "method_mechanism",
      "caveats": []
    },
    {
      "claim_id": "C8",
      "claim_text": "PointLLMLlamaModel exposes generic code behaviors: pointwise transformation. Detected implementation patterns include positionwise feed forward.",
      "support_status": "supported",
      "evidence_ids": [
        "E136"
      ],
      "mechanism_ids": [
        "MECH-003"
      ],
      "source": "submechanism:SUBMECH1",
      "caveats": []
    },
    {
      "claim_id": "C9",
      "claim_text": "PointcloudEncoder exposes generic code behaviors: pointwise transformation, regularization. Detected implementation patterns include positionwise feed forward, dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E445"
      ],
      "mechanism_ids": [
        "MECH-003"
      ],
      "source": "submechanism:SUBMECH3",
      "caveats": []
    },
    {
      "claim_id": "C10",
      "claim_text": "Control runtime mechanics (trainer save behavior/logging/checkpoint flow).",
      "support_status": "supported",
      "evidence_ids": [
        "E579",
        "E580",
        "E583",
        "E584",
        "E585",
        "E586",
        "E587",
        "E588",
        "E589",
        "E590",
        "E591",
        "E592",
        "E593",
        "E577",
        "E581",
        "E582",
        "E80",
        "E85",
        "E86",
        "E87",
        "E88",
        "E89",
        "E90",
        "E91",
        "E92",
        "E93",
        "E94",
        "E95",
        "E96",
        "E77",
        "E429",
        "E432",
        "E431",
        "E464",
        "E465",
        "E466",
        "E467",
        "E468",
        "E469",
        "E470",
        "E471",
        "E472",
        "E473",
        "E136",
        "E139",
        "E137",
        "E148",
        "E149",
        "E150",
        "E151",
        "E152",
        "E153",
        "E154",
        "E155",
        "E156",
        "E157",
        "E140",
        "E144",
        "E147",
        "E146",
        "E145",
        "E143",
        "E141",
        "E172",
        "E173",
        "E174",
        "E175",
        "E176",
        "E177",
        "E76",
        "E78",
        "E81",
        "E82",
        "E83",
        "E84",
        "E2410",
        "E2617",
        "E2616",
        "E2638",
        "E2639",
        "E2640",
        "E2641",
        "E2619",
        "E2646",
        "E2647",
        "E2648",
        "E2624",
        "E2632",
        "E2669",
        "E2670",
        "E474",
        "E475",
        "E226",
        "E239",
        "E240",
        "E241"
      ],
      "mechanism_ids": [
        "MECH-004"
      ],
      "source": "method_mechanism",
      "caveats": []
    },
    {
      "claim_id": "C11",
      "claim_text": "PointLLMLlamaModel exposes generic code behaviors: pointwise transformation. Detected implementation patterns include positionwise feed forward.",
      "support_status": "supported",
      "evidence_ids": [
        "E136"
      ],
      "mechanism_ids": [
        "MECH-004"
      ],
      "source": "submechanism:SUBMECH1",
      "caveats": []
    },
    {
      "claim_id": "C12",
      "claim_text": "PatchDropout exposes generic code behaviors: regularization. Detected implementation patterns include dropout.",
      "support_status": "supported",
      "evidence_ids": [
        "E429"
      ],
      "mechanism_ids": [
        "MECH-004"
      ],
      "source": "submechanism:SUBMECH2",
      "caveats": []
    },
    {
      "claim_id": "C13",
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
      "claim_id": "C14",
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
      "claim_id": "C15",
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
      "claim_id": "C16",
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
      "claim_id": "C17",
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
      "claim_id": "C18",
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
      "claim_id": "C19",
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
      "claim_id": "C20",
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
      "claim_id": "C21",
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
      "claim_id": "C22",
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
      "claim_id": "C23",
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
      "claim_id": "C24",
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
      "claim_id": "C25",
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
      "claim_id": "C26",
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
      "claim_id": "C27",
      "claim_text": "The method contains a paper-facing stage named Stage I: Text-First Interface Warmup.",
      "support_status": "supported",
      "evidence_ids": [
        "E77",
        "E80",
        "E85",
        "E86",
        "E87",
        "E88",
        "E89",
        "E90",
        "E91",
        "E92",
        "E93",
        "E94",
        "E95",
        "E96",
        "E537",
        "E538",
        "E539",
        "E540",
        "E548",
        "E549",
        "E78",
        "E81",
        "E82",
        "E83",
        "E84",
        "E541",
        "E542",
        "E543",
        "E550",
        "E551",
        "E552",
        "E553",
        "E554",
        "E555",
        "E556",
        "E557",
        "E544",
        "E545",
        "E546",
        "E558",
        "E559",
        "E560",
        "E561",
        "E562",
        "E563",
        "E564",
        "E565",
        "E566",
        "E567",
        "E568",
        "E547",
        "E569",
        "E570",
        "E571",
        "E572",
        "E573",
        "E75",
        "E76",
        "E595",
        "E596",
        "E597",
        "E2412",
        "E228",
        "E230",
        "E236",
        "E234",
        "E233",
        "E232",
        "E237",
        "E243",
        "E244",
        "E245",
        "E246",
        "E247",
        "E248",
        "E249",
        "E250",
        "E251",
        "E136",
        "E139",
        "E137",
        "E148",
        "E149",
        "E150",
        "E151",
        "E152",
        "E153",
        "E154",
        "E155",
        "E156",
        "E157",
        "E140",
        "E144",
        "E147",
        "E146",
        "E145"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C1",
      "caveats": []
    },
    {
      "claim_id": "C28",
      "claim_text": "The method contains a paper-facing stage named Stage II: Rich Instruction Alignment.",
      "support_status": "supported",
      "evidence_ids": [
        "E228",
        "E230",
        "E236",
        "E234",
        "E233",
        "E232",
        "E237",
        "E243",
        "E244",
        "E245",
        "E246",
        "E247",
        "E248",
        "E249",
        "E250",
        "E251",
        "E76",
        "E311",
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
        "E80",
        "E85",
        "E86",
        "E87",
        "E88",
        "E89",
        "E90",
        "E91",
        "E92",
        "E93",
        "E94",
        "E95",
        "E96",
        "E77",
        "E321",
        "E366",
        "E367",
        "E368",
        "E369",
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
        "E75",
        "E226",
        "E239",
        "E240",
        "E241",
        "E242",
        "E252",
        "E253",
        "E254",
        "E255",
        "E256",
        "E257",
        "E258",
        "E259",
        "E78",
        "E81",
        "E82",
        "E83",
        "E84",
        "E270",
        "E305",
        "E308",
        "E307",
        "E306",
        "E323",
        "E324",
        "E325",
        "E326",
        "E327",
        "E328",
        "E329",
        "E330",
        "E309",
        "E331",
        "E310",
        "E312",
        "E344"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C2",
      "caveats": []
    },
    {
      "claim_id": "C29",
      "claim_text": "The method contains a paper-facing stage named Stage III: Point-Language Transfer.",
      "support_status": "supported",
      "evidence_ids": [
        "E140",
        "E144",
        "E147",
        "E146",
        "E145",
        "E143",
        "E141",
        "E172",
        "E173",
        "E174",
        "E175",
        "E176",
        "E177",
        "E136",
        "E139",
        "E137",
        "E148",
        "E149",
        "E150",
        "E151",
        "E152",
        "E153",
        "E154",
        "E155",
        "E156",
        "E157",
        "E160",
        "E161",
        "E162",
        "E163",
        "E164",
        "E165",
        "E166",
        "E167",
        "E168",
        "E169",
        "E170",
        "E158",
        "E80",
        "E85",
        "E86",
        "E87",
        "E88",
        "E89",
        "E90",
        "E91",
        "E92",
        "E93",
        "E94",
        "E95",
        "E96",
        "E180",
        "E181",
        "E182",
        "E183",
        "E184",
        "E185",
        "E186",
        "E187",
        "E445",
        "E447",
        "E446",
        "E513",
        "E514",
        "E515",
        "E516",
        "E517",
        "E518",
        "E519",
        "E520",
        "E521",
        "E522",
        "E77",
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
        "E523",
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
        "E198"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C3",
      "caveats": []
    },
    {
      "claim_id": "C30",
      "claim_text": "The method contains a paper-facing stage named Runtime and saving behavior.",
      "support_status": "supported",
      "evidence_ids": [
        "E579",
        "E580",
        "E583",
        "E584",
        "E585",
        "E586",
        "E587",
        "E588",
        "E589",
        "E590",
        "E591",
        "E592",
        "E593",
        "E577",
        "E581",
        "E582",
        "E80",
        "E85",
        "E86",
        "E87",
        "E88",
        "E89",
        "E90",
        "E91",
        "E92",
        "E93",
        "E94",
        "E95",
        "E96",
        "E77",
        "E429",
        "E432",
        "E431",
        "E464",
        "E465",
        "E466",
        "E467",
        "E468",
        "E469",
        "E470",
        "E471",
        "E472",
        "E473",
        "E136",
        "E139",
        "E137",
        "E148",
        "E149",
        "E150",
        "E151",
        "E152",
        "E153",
        "E154",
        "E155",
        "E156",
        "E157",
        "E140",
        "E144",
        "E147",
        "E146",
        "E145",
        "E143",
        "E141",
        "E172",
        "E173",
        "E174",
        "E175",
        "E176",
        "E177",
        "E76",
        "E78",
        "E81",
        "E82",
        "E83",
        "E84",
        "E2410",
        "E2617",
        "E2616",
        "E2638",
        "E2639",
        "E2640",
        "E2641",
        "E2619",
        "E2646",
        "E2647",
        "E2648",
        "E2624",
        "E2632",
        "E2669",
        "E2670",
        "E474",
        "E475",
        "E226",
        "E239",
        "E240",
        "E241"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C4",
      "caveats": []
    },
    {
      "claim_id": "C31",
      "claim_text": "Establish projector-language coupling under mostly frozen backbone settings.",
      "support_status": "supported",
      "evidence_ids": [
        "E77",
        "E80",
        "E85",
        "E86",
        "E87",
        "E88",
        "E89",
        "E90",
        "E91",
        "E92",
        "E93",
        "E94",
        "E95",
        "E96",
        "E537",
        "E538",
        "E539",
        "E540",
        "E548",
        "E549",
        "E78",
        "E81",
        "E82",
        "E83",
        "E84",
        "E541",
        "E542",
        "E543",
        "E550",
        "E551",
        "E552",
        "E553",
        "E554",
        "E555",
        "E556",
        "E557",
        "E544",
        "E545",
        "E546",
        "E558",
        "E559",
        "E560",
        "E561",
        "E562",
        "E563",
        "E564",
        "E565",
        "E566",
        "E567",
        "E568",
        "E547",
        "E569",
        "E570",
        "E571",
        "E572",
        "E573",
        "E75",
        "E76",
        "E595",
        "E596",
        "E597",
        "E2412",
        "E228",
        "E230",
        "E236",
        "E234",
        "E233",
        "E232",
        "E237",
        "E243",
        "E244",
        "E245",
        "E246",
        "E247",
        "E248",
        "E249",
        "E250",
        "E251",
        "E136",
        "E139",
        "E137",
        "E148",
        "E149",
        "E150",
        "E151",
        "E152",
        "E153",
        "E154",
        "E155",
        "E156",
        "E157",
        "E140",
        "E144",
        "E147",
        "E146",
        "E145"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C5",
      "caveats": []
    },
    {
      "claim_id": "C32",
      "claim_text": "Expand from simple descriptions to richer instruction/dialog patterns while preserving projector continuity.",
      "support_status": "supported",
      "evidence_ids": [
        "E228",
        "E230",
        "E236",
        "E234",
        "E233",
        "E232",
        "E237",
        "E243",
        "E244",
        "E245",
        "E246",
        "E247",
        "E248",
        "E249",
        "E250",
        "E251",
        "E76",
        "E311",
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
        "E80",
        "E85",
        "E86",
        "E87",
        "E88",
        "E89",
        "E90",
        "E91",
        "E92",
        "E93",
        "E94",
        "E95",
        "E96",
        "E77",
        "E321",
        "E366",
        "E367",
        "E368",
        "E369",
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
        "E75",
        "E226",
        "E239",
        "E240",
        "E241",
        "E242",
        "E252",
        "E253",
        "E254",
        "E255",
        "E256",
        "E257",
        "E258",
        "E259",
        "E78",
        "E81",
        "E82",
        "E83",
        "E84",
        "E270",
        "E305",
        "E308",
        "E307",
        "E306",
        "E323",
        "E324",
        "E325",
        "E326",
        "E327",
        "E328",
        "E329",
        "E330",
        "E309",
        "E331",
        "E310",
        "E312",
        "E344"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C6",
      "caveats": []
    },
    {
      "claim_id": "C33",
      "claim_text": "Use point-cloud token features and compact token aggregation to transfer prior alignment to 3D inputs.",
      "support_status": "supported",
      "evidence_ids": [
        "E140",
        "E144",
        "E147",
        "E146",
        "E145",
        "E143",
        "E141",
        "E172",
        "E173",
        "E174",
        "E175",
        "E176",
        "E177",
        "E136",
        "E139",
        "E137",
        "E148",
        "E149",
        "E150",
        "E151",
        "E152",
        "E153",
        "E154",
        "E155",
        "E156",
        "E157",
        "E160",
        "E161",
        "E162",
        "E163",
        "E164",
        "E165",
        "E166",
        "E167",
        "E168",
        "E169",
        "E170",
        "E158",
        "E80",
        "E85",
        "E86",
        "E87",
        "E88",
        "E89",
        "E90",
        "E91",
        "E92",
        "E93",
        "E94",
        "E95",
        "E96",
        "E180",
        "E181",
        "E182",
        "E183",
        "E184",
        "E185",
        "E186",
        "E187",
        "E445",
        "E447",
        "E446",
        "E513",
        "E514",
        "E515",
        "E516",
        "E517",
        "E518",
        "E519",
        "E520",
        "E521",
        "E522",
        "E77",
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
        "E523",
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
        "E198"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C7",
      "caveats": []
    },
    {
      "claim_id": "C34",
      "claim_text": "Control runtime mechanics (trainer save behavior/logging/checkpoint flow).",
      "support_status": "supported",
      "evidence_ids": [
        "E579",
        "E580",
        "E583",
        "E584",
        "E585",
        "E586",
        "E587",
        "E588",
        "E589",
        "E590",
        "E591",
        "E592",
        "E593",
        "E577",
        "E581",
        "E582",
        "E80",
        "E85",
        "E86",
        "E87",
        "E88",
        "E89",
        "E90",
        "E91",
        "E92",
        "E93",
        "E94",
        "E95",
        "E96",
        "E77",
        "E429",
        "E432",
        "E431",
        "E464",
        "E465",
        "E466",
        "E467",
        "E468",
        "E469",
        "E470",
        "E471",
        "E472",
        "E473",
        "E136",
        "E139",
        "E137",
        "E148",
        "E149",
        "E150",
        "E151",
        "E152",
        "E153",
        "E154",
        "E155",
        "E156",
        "E157",
        "E140",
        "E144",
        "E147",
        "E146",
        "E145",
        "E143",
        "E141",
        "E172",
        "E173",
        "E174",
        "E175",
        "E176",
        "E177",
        "E76",
        "E78",
        "E81",
        "E82",
        "E83",
        "E84",
        "E2410",
        "E2617",
        "E2616",
        "E2638",
        "E2639",
        "E2640",
        "E2641",
        "E2619",
        "E2646",
        "E2647",
        "E2648",
        "E2624",
        "E2632",
        "E2669",
        "E2670",
        "E474",
        "E475",
        "E226",
        "E239",
        "E240",
        "E241"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C8",
      "caveats": []
    },
    {
      "claim_id": "C35",
      "claim_text": "Python inline comment hint: you may not use this file except in compliance with the License.",
      "support_status": "partial",
      "evidence_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C9",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C36",
      "claim_text": "Python inline comment hint: * for two stage training",
      "support_status": "partial",
      "evidence_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C10",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C37",
      "claim_text": "Python inline comment hint: * use with torch.inference_mode to control, not requires_grad for fsdp for second stage",
      "support_status": "partial",
      "evidence_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C11",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C38",
      "claim_text": "Python inline comment hint: * fix pointnet for first stage, need for fsdp in stage2",
      "support_status": "partial",
      "evidence_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C12",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C39",
      "claim_text": "Python inline comment hint: * we assume in stage2, llm, point_backbone, and projection layer can be loaded from the model checkpoint",
      "support_status": "partial",
      "evidence_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C13",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C40",
      "claim_text": "Python inline comment hint: * stage2",
      "support_status": "partial",
      "evidence_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C14",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C41",
      "claim_text": "Python inline comment hint: layer.register_forward_hook(print_layer_output)",
      "support_status": "partial",
      "evidence_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C15",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C42",
      "claim_text": "Docstring hint for safe_save_model_for_hf_trainer: Collects the state dict and dump to disk.",
      "support_status": "partial",
      "evidence_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C16",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C43",
      "claim_text": "Python inline comment hint: * add logger",
      "support_status": "partial",
      "evidence_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C17",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C44",
      "claim_text": "Python inline comment hint: address of config file, in the same dir of this file",
      "support_status": "partial",
      "evidence_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C18",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C45",
      "claim_text": "Python inline comment hint: * default for v1.1, v1.2 uses PointTransformer_8192point_2layer.yaml",
      "support_status": "partial",
      "evidence_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C19",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C46",
      "claim_text": "Python inline comment hint: * default is false",
      "support_status": "partial",
      "evidence_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C20",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C47",
      "claim_text": "Python inline comment hint: * number of output features, with cls token",
      "support_status": "partial",
      "evidence_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C21",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C48",
      "claim_text": "Python inline comment hint: a list",
      "support_status": "partial",
      "evidence_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C22",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C49",
      "claim_text": "Python inline comment hint: * print relevant info with projection layers",
      "support_status": "partial",
      "evidence_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C23",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C50",
      "claim_text": "Python inline comment hint: Add projection layer with linear layers and GELU activation",
      "support_status": "partial",
      "evidence_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C24",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C51",
      "claim_text": "Python inline comment hint: Single layer",
      "support_status": "partial",
      "evidence_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C25",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C52",
      "claim_text": "Python inline comment hint: Enable model/pipeline parallelism",
      "support_status": "partial",
      "evidence_ids": [
        "E1000",
        "E1001",
        "E1002",
        "E1003",
        "E1004"
      ],
      "mechanism_ids": [],
      "source": "claim_contract:C26",
      "caveats": [
        "partially supported by implementation evidence"
      ]
    },
    {
      "claim_id": "C53",
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
      "claim_id": "C54",
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
      "claim_id": "C55",
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
      "claim_id": "C56",
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
      "claim_id": "C57",
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