# Author Review Questions

Project: `attention_transformer_no_author`
Author mode: `none`
Author confirmation required: `true`

This run needs author confirmation before the draft is treated as paper-ready.
Please answer or edit the questions below; unresolved items should keep the method draft conservative.

## Stage And Pipeline Confirmation

- [ ] Is this paper-facing method order correct: `Input Preparation -> Transformer Computation -> Scheduled Optimization`?
- [ ] Should `Input Preparation` be a main method stage? Purpose: Prepare tokenized and serialized data for training. Evidence: `E27, E28, E29, E30, E31, E32, E33, E34, E35, E36, E37, E54, E55`.
- [ ] Should `Transformer Computation` be a main method stage? Purpose: Compute sequence representations through Transformer layers and sublayers. Evidence: `E59, E61, E64, E65, E67, E68, E70, E72, E74, E77, E80, E82, E85, E88`.
- [ ] Should `Scheduled Optimization` be a main method stage? Purpose: Optimize model parameters with loss computation, optional label smoothing, and learning-rate scheduling. Evidence: `E56, E40, E42, E46, E77`.
- [ ] Is execution stage `training_launch` correctly mapped to method stage `scheduled_optimization`? Confidence: 0.78.
- [ ] Is execution stage `training_setup` correctly mapped to method stage `transformer_computation`? Confidence: 0.88.
- [ ] Is execution stage `epoch_update` correctly mapped to method stage `scheduled_optimization`? Confidence: 0.88.
- [ ] Is execution stage `preprocess_data` correctly mapped to method stage `input_preparation`? Confidence: 0.88.

## Module Role Confirmation

- [ ] Should `train.py:cal_performance` be treated as method-core? Current role: loss and accuracy computation. Confidence: 0.90.
- [ ] Should `train.py:cal_loss` be treated as method-core? Current role: loss computation. Confidence: 0.90.
- [ ] Should `train.py:train_epoch` be treated as method-core? Current role: training update loop. Confidence: 0.90.
- [ ] Should `transformer/Layers.py:EncoderLayer` be treated as method-core? Current role: encoder block. Confidence: 0.90.
- [ ] Should `transformer/Layers.py:DecoderLayer` be treated as method-core? Current role: decoder block. Confidence: 0.90.
- [ ] Should `transformer/Models.py:get_pad_mask` be treated as method-core? Current role: Transformer implementation component. Confidence: 0.90.
- [ ] Should `transformer/Models.py:get_subsequent_mask` be treated as method-core? Current role: Transformer implementation component. Confidence: 0.90.
- [ ] Should `transformer/Models.py:PositionalEncoding` be treated as method-core? Current role: Transformer implementation component. Confidence: 0.90.
- [ ] Should `transformer/Models.py:Encoder` be treated as method-core? Current role: encoder stack. Confidence: 0.90.
- [ ] Should `transformer/Models.py:Decoder` be treated as method-core? Current role: decoder stack. Confidence: 0.90.
- [ ] Should `transformer/Models.py:Transformer` be treated as method-core? Current role: sequence-to-sequence model. Confidence: 0.90.
- [ ] Should `transformer/Modules.py:ScaledDotProductAttention` be treated as method-core? Current role: attention kernel. Confidence: 0.90.
- [ ] Should `transformer/Optim.py:ScheduledOptim` be treated as method-core? Current role: warmup optimization. Confidence: 0.90.
- [ ] Should `transformer/SubLayers.py:MultiHeadAttention` be treated as method-core? Current role: attention sublayer. Confidence: 0.90.
- [ ] Should `transformer/SubLayers.py:PositionwiseFeedForward` be treated as method-core? Current role: feed-forward sublayer. Confidence: 0.90.
- [ ] Should `transformer/Translator.py:Translator` be treated as method-core? Current role: Transformer implementation component. Confidence: 0.90.
- [ ] Should `apply_bpe.py:BPE` remain outside the main method? Current category: `infra-utility`.
- [ ] Should `apply_bpe.py:encode` remain outside the main method? Current category: `infra-utility`.
- [ ] Should `apply_bpe.py:recursive_split` remain outside the main method? Current category: `infra-utility`.
- [ ] Should `apply_bpe.py:check_vocab_and_split` remain outside the main method? Current category: `infra-utility`.
- [ ] Should `apply_bpe.py:read_vocabulary` remain outside the main method? Current category: `infra-utility`.
- [ ] Should `apply_bpe.py:isolate_glossary` remain outside the main method? Current category: `infra-utility`.
- [ ] Should `learn_bpe.py:update_vocabulary` remain outside the main method? Current category: `infra-utility`.
- [ ] Should `learn_bpe.py:update_pair_statistics` remain outside the main method? Current category: `infra-utility`.
- [ ] Should `learn_bpe.py:get_pair_statistics` remain outside the main method? Current category: `infra-utility`.
- [ ] Should `learn_bpe.py:replace_pair` remain outside the main method? Current category: `infra-utility`.

## Mechanism Confirmation

- [ ] In `Input Preparation`, is this mechanism description accurate? `The pipeline prepares translation data by converting raw corpora into tokenized, filtered, vocabulary-backed serialized training artifacts.`
- [ ] In `Transformer Computation`, is this mechanism description accurate? `The method computes sequence representations with Transformer encoder/decoder components built from attention and position-wise feed-forward sublayers.`
- [ ] In `Scheduled Optimization`, is this mechanism description accurate? `Training optimizes model parameters by combining forward prediction, loss computation, backpropagation, and the scheduled learning-rate update.`
- [ ] Should detected behavior `regularization` in `transformer/Layers.py:EncoderLayer` be mentioned in the main method, appendix, or omitted?
- [ ] Should detected behavior `regularization` in `transformer/Layers.py:DecoderLayer` be mentioned in the main method, appendix, or omitted?
- [ ] Should detected behavior `regularization` in `transformer/Models.py:Encoder` be mentioned in the main method, appendix, or omitted?
- [ ] Should detected behavior `regularization` in `transformer/Models.py:Decoder` be mentioned in the main method, appendix, or omitted?
- [ ] Should detected behavior `regularization` in `transformer/Models.py:Transformer` be mentioned in the main method, appendix, or omitted?
- [ ] Should detected behavior `regularization` in `transformer/Modules.py:ScaledDotProductAttention` be mentioned in the main method, appendix, or omitted?
- [ ] Should detected behavior `regularization` in `transformer/SubLayers.py:MultiHeadAttention` be mentioned in the main method, appendix, or omitted?
- [ ] Should detected behavior `regularization` in `transformer/SubLayers.py:PositionwiseFeedForward` be mentioned in the main method, appendix, or omitted?

## Quantitative Parameter Confirmation

- [ ] Is `smoothing=False` in `train.py:cal_performance` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?
- [ ] Is `smoothing=False` in `train.py:cal_loss` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?
- [ ] Is `dropout=0.1` in `transformer/Layers.py:EncoderLayer` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?
- [ ] Is `dropout=0.1` in `transformer/Layers.py:DecoderLayer` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?
- [ ] Is `n_position=200` in `transformer/Models.py:PositionalEncoding` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?
- [ ] Is `dropout=0.1` in `transformer/Models.py:Encoder` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?
- [ ] Is `n_position=200` in `transformer/Models.py:Encoder` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?
- [ ] Is `scale_emb=False` in `transformer/Models.py:Encoder` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?
- [ ] Is `n_position=200` in `transformer/Models.py:Decoder` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?
- [ ] Is `dropout=0.1` in `transformer/Models.py:Decoder` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?
- [ ] Is `scale_emb=False` in `transformer/Models.py:Decoder` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?
- [ ] Is `d_word_vec=512` in `transformer/Models.py:Transformer` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?
- [ ] Is `d_model=512` in `transformer/Models.py:Transformer` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?
- [ ] Is `d_inner=2048` in `transformer/Models.py:Transformer` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?
- [ ] Is `n_layers=6` in `transformer/Models.py:Transformer` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?
- [ ] Is `n_head=8` in `transformer/Models.py:Transformer` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?
- [ ] Is `d_k=64` in `transformer/Models.py:Transformer` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?
- [ ] Is `d_v=64` in `transformer/Models.py:Transformer` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?
- [ ] Is `dropout=0.1` in `transformer/Models.py:Transformer` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?
- [ ] Is `n_position=200` in `transformer/Models.py:Transformer` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?
- [ ] Is `trg_emb_prj_weight_sharing=True` in `transformer/Models.py:Transformer` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?
- [ ] Is `emb_src_trg_weight_sharing=True` in `transformer/Models.py:Transformer` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?
- [ ] Is `scale_emb_or_prj=prj` in `transformer/Models.py:Transformer` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?
- [ ] Is `attn_dropout=0.1` in `transformer/Modules.py:ScaledDotProductAttention` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?
- [ ] Is `dropout=0.1` in `transformer/SubLayers.py:MultiHeadAttention` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?
- [ ] Is `dropout=0.1` in `transformer/SubLayers.py:PositionwiseFeedForward` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?

## Claim And Novelty Boundary Confirmation

- [ ] Which statements, if any, are true novelty claims rather than ordinary implementation descriptions?

## Source Boundary Confirmation

- [ ] `README.md` is excluded from the main evidence chain because: excluded from main evidence chain. Is this correct?
