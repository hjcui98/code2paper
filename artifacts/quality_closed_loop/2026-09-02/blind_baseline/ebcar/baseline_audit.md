# EBCAR blind baseline audit

## Provenance boundary

Generation inputs were limited to:

1. `/data1/users/cuihengjia/code2paper/paperyaml3/EBCAR - Embedding-Based Context-Aware Reranker.yaml`
2. The EBCAR research-code tree at `/data1/users/cuihengjia/code2paper/code_final/EBCAR - Embedding-Based Context-Aware Reranker`

The repository's draft/paper and generated-output surfaces were not used. No
original paper, answer oracle, `paper_final`, candidate, or verified artifact
was consulted. No Code2Paper Agent or external model was invoked for this
baseline.

## Result fields

- `writer_status`: `manual_baseline_generated`
- `structural_exit`: `not_applicable_no_Code2Paper_writer`; the text is structurally complete as a candidate, with explicit caveats.
- `publication_ready`: `false`
- `final_text_validation`: `pass_with_pending`; a manual provenance pass found no unmarked unsupported positive claim. This is not a Code2Paper validator result.

## Direct code support

- Contriever configuration and normalized query/passage embeddings: `conf/retrieval_model/contriever.yaml`; `src/dataset/__init__.py`.
- Chroma retrieval with `top_k=20`, exact `chunk_id` labeling, document/passage ID extraction, and serialized tensors/metadata: `src/dataset/__init__.py`; `src/build_vector_database.py`.
- Relative document-ID remapping, per-example permutation, and the model input contract: `src/dataset/ebcar_dataset.py`.
- A 20-entry document-ID embedding table, 5,000-entry normalized sinusoidal passage-position table, and additive augmentation: `src/model/ebcar_dedicated_attention_model.py:32-133`.
- Separate shared and masked multi-head attention, pre-normalization, residual addition, feed-forward block, and dropout: `src/model/transformer_encoder_hybrid_attention.py:12-164`.
- Original-query dot products, temperature scaling, exactly-one-positive assertion, log-sum-exp loss, descending sort, and text reconstruction: `src/model/ebcar_dedicated_attention_model.py:192-344`.
- MLDR/SQuAD/NarrativeQA train/validation mixture, Adam settings, validation-loss checkpointing, and MRR@10 logging: `data/real/ConTEB_train/preprocess.py`; `src/train_ebcar.py`; `conf/config.yaml`.
- The intended test metrics and their implementation defects: `src/evaluate.py`; `src/utils.py`.

## Pending or unverified content

The candidate explicitly labels these author-intent targets as pending rather
than implementation facts: (i) speedup over text-based LLM rerankers, (ii)
competitiveness on cross-passage tasks, (iii) improved coreference/local
coherence, (iv) scalability to unseen documents, (v) stabilization from a
fixed query anchor, and (vi) superiority of the combined attention pattern.

Two code-level uncertainties are also retained: the document-ID embedding's
module-level `requires_grad=False` assignment does not visibly freeze its
weight, and the training mask uses row indices without the query-position
offset used by `rerank`. The test wrapper's undefined `working_dir` and
checkpoint-name mismatch make end-to-end evaluation incomplete.

## Coverage

Coverage denominators are defined from the supplied intent, not from any
unseen reference. A slot is one of the 12 listed `key_building_blocks`; an
edge is one of the six data/control transitions described in the candidate;
and a formula is one of the five equations needed to express augmentation,
position encoding, attention masking, scoring, and InfoNCE.

- Paragraph/story coverage: `7/7` story blocks represented (motivation/scope, input and retrieval, structural augmentation, hybrid encoder, training objective, inference ranking, data/evaluation boundary).
- Slot coverage: `12/12` represented. `8/12` are directly code-supported; `4/12` are partial because they include either an intent-only effect claim, the training-mask discrepancy, or the document-ID freeze ambiguity.
- Edge coverage: `6/6` represented. `5/6` are directly code-supported end to end; `1/6` (the intended training-time local-attention edge) is partial because of the row-offset defect.
- Formula coverage: `5/5` represented. `4/5` are directly code-supported; `1/5` (the clean same-document mask equation for training) is only fully supported by the inference path.
