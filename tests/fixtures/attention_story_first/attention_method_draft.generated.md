# Method

## Overview
<!-- c2p: stage=ALL; mechanisms=MECH1,MECH2,MECH3; evidence=E19,E20,E22,E23,E24,E25,E26,E27,E28,E29,E30,E31,E32,E35,E37,E40,E42,E45,E73,E74,E76,E77,E79,E81,E83,E86,E89,E2,E5,E7,E11; confidence=high -->
Transformer Translation Training Pipeline is designed for the following method goal: to train a Transformer sequence-to-sequence model from prepared translation data with architecture-level attention components and scheduled optimization. The paper-facing method is organized into 3 evidence-backed stages: Input Preparation, Transformer Computation, and Scheduled Optimization.

## Evidence-Grounded Pipeline
<!-- c2p: stage=S1; mechanisms=MECH1; evidence=E19,E20,E22,E23,E24,E25,E26,E27,E28,E29,E30,E31,E32; confidence=high -->
**Input Preparation.** The stage purpose is to prepare tokenized and serialized data for training. It consumes raw corpus files, BPE settings, and maximum sequence length and produces serialized data, vocabulary, and filtered train and validation examples. The pipeline prepares translation data by converting raw corpora into tokenized, filtered, vocabulary-backed serialized training artifacts.

<!-- c2p: stage=S2; mechanisms=MECH2; evidence=E35,E37,E40,E42,E45,E73,E74,E76,E77,E79,E81,E83,E86,E89; confidence=high -->
**Transformer Computation.** The stage purpose is to compute sequence representations through Transformer layers and sublayers. It consumes source token sequence, target prefix sequence, and model hyperparameters and produces decoder predictions and attention representations. The method computes sequence representations with Transformer encoder/decoder components built from attention and position-wise feed-forward sublayers. Core implementation symbols include transformer/Layers.py:EncoderLayer, transformer/Layers.py:DecoderLayer, transformer/SubLayers.py:MultiHeadAttention, transformer/SubLayers.py:PositionwiseFeedForward, transformer/Models.py:get_pad_mask, transformer/Models.py:get_subsequent_mask, transformer/Models.py:PositionalEncoding, transformer/Models.py:Encoder, transformer/Models.py:Decoder, transformer/Models.py:Transformer, transformer/Modules.py:ScaledDotProductAttention, and transformer/Translator.py:Translator.

<!-- c2p: stage=S3; mechanisms=MECH3; evidence=E2,E5,E7,E11,E45; confidence=high -->
**Scheduled Optimization.** The stage purpose is to optimize model parameters with loss computation, optional label smoothing, and learning-rate scheduling. It consumes model predictions, target tokens, optimizer settings, and warmup steps and produces updated parameters, training metrics, validation metrics, and checkpoints. Training optimizes model parameters by combining forward prediction, loss computation, backpropagation, and the scheduled learning-rate update. Core implementation symbols include train.py:cal_performance, train.py:cal_loss, train.py:train_epoch, and transformer/Optim.py:ScheduledOptim.

## Core Components
<!-- c2p: stage=ALL; mechanisms=MECH1,MECH2,MECH3; evidence=E19,E20,E22,E23,E24,E25,E26,E27,E28,E29,E30,E31,E32,E35,E37,E40,E42,E45,E73,E74,E76,E77,E79,E81,E83,E86,E89,E2,E5,E7,E11; confidence=high -->
The core method components are the implementation symbols categorized as method-core evidence: transformer/Layers.py:EncoderLayer, transformer/Layers.py:DecoderLayer, transformer/SubLayers.py:MultiHeadAttention, transformer/SubLayers.py:PositionwiseFeedForward, transformer/Models.py:get_pad_mask, transformer/Models.py:get_subsequent_mask, transformer/Models.py:PositionalEncoding, transformer/Models.py:Encoder, transformer/Models.py:Decoder, transformer/Models.py:Transformer, transformer/Modules.py:ScaledDotProductAttention, transformer/Translator.py:Translator, train.py:cal_performance, train.py:cal_loss, train.py:train_epoch, and transformer/Optim.py:ScheduledOptim. Utility and experiment-support modules are not treated as method innovations.

## Code-Backed Mechanism Details
<!-- c2p: stage=S2; mechanisms=MECH2; evidence=E35; confidence=high -->
**SUBMECH2.** EncoderLayer exposes generic code behaviors: sequential composition, regularization. Detected implementation patterns include encoder layer composition, dropout. It composes a block from a self-transformation sublayer followed by a point-wise transformation sublayer and applies dropout inside module computation. Detected structural parameters include dropout=0.1.

<!-- c2p: stage=S2; mechanisms=MECH2; evidence=E37; confidence=high -->
**SUBMECH3.** DecoderLayer exposes generic code behaviors: sequential composition, regularization. Detected implementation patterns include decoder layer composition, dropout. It composes a block from self-transformation, cross-context transformation, and point-wise transformation sublayers and applies dropout inside module computation. Detected structural parameters include dropout=0.1. Detected tensor roles include enc_output (encoder output representation).

<!-- c2p: stage=S2; mechanisms=MECH2; evidence=E40; confidence=high -->
**SUBMECH4.** MultiHeadAttention exposes generic code behaviors: parallel projection, skip connection, normalization, regularization. Detected implementation patterns include multi head projection, residual connection, layer normalization, dropout. It projects inputs into multiple parallel branches, applies a transformation in parallel, and merges the branches, adds a residual connection around a sub-computation, applies layer normalization around module computation, and applies dropout inside module computation. Detected structural parameters include dropout=0.1. Detected tensor roles include q (query representation), k (key representation), v (value representation), and mask (attention or validity mask).

<!-- c2p: stage=S2; mechanisms=MECH2; evidence=E40; confidence=medium -->
Equation candidate **Multi-Branch Projection** is supported by the detected code pattern:
$$
\mathrm{MultiBranch}(X)=\mathrm{Merge}(f_1(XW_1),\ldots,f_h(XW_h))W^O
$$

<!-- c2p: stage=S2; mechanisms=MECH2; evidence=E42; confidence=high -->
**SUBMECH5.** PositionwiseFeedForward exposes generic code behaviors: pointwise transformation, skip connection, normalization, regularization. Detected implementation patterns include positionwise feed forward, residual connection, layer normalization, dropout. It applies two point-wise linear transformations with a nonlinear activation between them, adds a residual connection around a sub-computation, applies layer normalization around module computation, and applies dropout inside module computation. Detected structural parameters include dropout=0.1. Detected tensor roles include x (layer input representation).

<!-- c2p: stage=S2; mechanisms=MECH2; evidence=E42; confidence=medium -->
Equation candidate **Point-wise Feed-Forward Transformation** is supported by the detected code pattern:
$$
\mathrm{FFN}(x)=\sigma(xW_1+b_1)W_2+b_2
$$

<!-- c2p: stage=S2; mechanisms=MECH2; evidence=E74; confidence=high -->
**SUBMECH6.** get_subsequent_mask exposes generic code behaviors: constraint application. Detected implementation patterns include autoregressive subsequent mask. It builds a structural mask to block disallowed future-position access.

<!-- c2p: stage=S2; mechanisms=MECH2; evidence=E76; confidence=high -->
**SUBMECH7.** PositionalEncoding exposes generic code behaviors: representation injection. Detected implementation patterns include sinusoidal positional encoding. It constructs periodic position encodings and injects them into learned representations. Detected structural parameters include n_position=200. Detected tensor roles include x (layer input representation).

<!-- c2p: stage=S2; mechanisms=MECH2; evidence=E76; confidence=medium -->
Equation candidate **Periodic Positional Encoding** is supported by the detected code pattern:
$$
\mathrm{PE}_{(pos,2i)}=\sin(pos/10000^{2i/d}),\quad \mathrm{PE}_{(pos,2i+1)}=\cos(pos/10000^{2i/d})
$$

<!-- c2p: stage=S2; mechanisms=MECH2; evidence=E77; confidence=high -->
**SUBMECH8.** Encoder exposes generic code behaviors: repeated composition, normalization, regularization. Detected implementation patterns include encoder stack, layer normalization, dropout. It builds a representation stack from repeated encoder-like layers, applies layer normalization around module computation, and applies dropout inside module computation. Detected structural parameters include dropout=0.1, n_position=200, and scale_emb=False. Detected tensor roles include src_seq (source token sequence) and src_mask (source padding mask).

<!-- c2p: stage=S2; mechanisms=MECH2; evidence=E79; confidence=high -->
**SUBMECH9.** Decoder exposes generic code behaviors: repeated composition, normalization, regularization. Detected implementation patterns include decoder stack, layer normalization, dropout. It builds a representation stack from repeated decoder-like layers, applies layer normalization around module computation, and applies dropout inside module computation. Detected structural parameters include n_position=200, dropout=0.1, and scale_emb=False. Detected tensor roles include trg_seq (target token sequence), trg_mask (target autoregressive/padding mask), enc_output (encoder output representation), and src_mask (source padding mask).

<!-- c2p: stage=S2; mechanisms=MECH2; evidence=E81; confidence=high -->
**SUBMECH10.** Transformer exposes generic code behaviors: parameter sharing, regularization. Detected implementation patterns include embedding projection weight sharing, dropout. It shares parameters between representation and projection components when configured and applies dropout inside module computation. Detected structural parameters include d_word_vec=512, d_model=512, d_inner=2048, n_layers=6, n_head=8, d_k=64, d_v=64, dropout=0.1, n_position=200, trg_emb_prj_weight_sharing=True, emb_src_trg_weight_sharing=True, and scale_emb_or_prj=prj. Detected tensor roles include src_seq (source token sequence) and trg_seq (target token sequence).

<!-- c2p: stage=S2; mechanisms=MECH2; evidence=E83; confidence=high -->
**SUBMECH11.** ScaledDotProductAttention exposes generic code behaviors: weighted aggregation, regularization. Detected implementation patterns include scaled dot product attention, dropout. It computes attention weights from scaled query-key compatibility scores and applies them to values and applies dropout inside module computation. Detected structural parameters include attn_dropout=0.1. Detected tensor roles include q (query representation), k (key representation), v (value representation), and mask (attention or validity mask).

<!-- c2p: stage=S2; mechanisms=MECH2; evidence=E83; confidence=medium -->
Equation candidate **Scaled Dot-Product Attention** is supported by the detected code pattern:
$$
\mathrm{Attention}(Q,K,V)=\mathrm{softmax}(QK^T/\sqrt{d_k})V
$$

<!-- c2p: stage=S3; mechanisms=MECH3; evidence=E7; confidence=high -->
**SUBMECH1.** cal_loss exposes generic code behaviors: objective shaping. Detected implementation patterns include label smoothing loss. It computes smoothed target distributions for a shaped loss objective. Detected structural parameters include smoothing=False.

## Training Procedure
<!-- c2p: stage=ALL; mechanisms=MECH1,MECH2,MECH3; evidence=E19,E20,E22,E23,E24,E25,E26,E27,E28,E29,E30,E31,E32,E35,E37,E40,E42,E45,E73,E74,E76,E77,E79,E81,E83,E86,E89,E2,E5,E7,E11; confidence=high -->
The method procedure follows the paper-level stage order rather than the raw execution order: Input Preparation -> Transformer Computation -> Scheduled Optimization. This ordering keeps orchestration, setup, and utility behavior separate from the method mechanisms.

## Implementation Notes and Configurable Behavior
<!-- c2p: stage=ALL; mechanisms=MECH1,MECH2,MECH3; evidence=E35,E37,E40,E45; confidence=high -->
An author-highlighted distinguishing mechanism is retained only as an evidence-backed implementation claim: The implementation follows the Transformer architecture and warmup optimization schedule.
