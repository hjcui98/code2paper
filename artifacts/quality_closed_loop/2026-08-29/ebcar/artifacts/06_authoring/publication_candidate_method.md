## Motivation: efficiency and cross‑passage inference challenges in existing rerankers.

The efficiency and cross-passage inference characteristics of existing rerankers motivate the design choices described in subsequent sections. The specific computational and representational challenges that drive these choices are detailed in the method and evaluation sections.

Addressing these challenges requires balancing inference cost against the quality of cross-passage interactions, a trade-off that shapes the architectural and training decisions presented in this work.

## Embedding‑based reranking formulation and overall framework.

No repository-supported content was supplied for this paragraph. The authoring packet contains no ordered targets, formula packages, material conditions, or configuration state, and the dossier summary reports zero operation atoms and zero data-flow or control-flow length. An overview of the embedding-based reranking formulation and overall framework requires at least one ordered target identifying the specific components, transformations, or objectives to be described.

## Architecture details: enriching embeddings with document ID and position

## Architecture details: enriching embeddings with document ID and position

The mainline sequence defines the ordered stages through which a token embedding is progressively enriched. The mainline begins with an initial embedding computation and proceeds through subsequent transformation stages in a fixed order. The first stage in the mainline operates on the input representation to produce an enriched embedding. A relational link within the mainline specifies how the output of one stage is passed as the input to the next, ensuring that the enriched representation propagates sequentially through the pipeline.

The first stage computes an enriched embedding by combining the base token embedding with a document identifier embedding and a positional encoding. The second stage receives this enriched representation and applies a dedicated attention mechanism to it. The first stage additionally produces an auxiliary output that is carried forward to the second stage.

The second stage is instantiated as a component that processes the enriched input representation and produces a transformed output. The stage is configured through a component that governs the attention computation. The attention module supports an option to return the attention weights alongside the transformed representation. The resulting output is passed to the next stage in the pipeline.

The second stage is connected to the mainline through a relational link that specifies how the stage output feeds into the subsequent processing step in the mainline sequence.

Each stage in the pipeline is governed by configuration flags that control whether a dedicated attention mechanism is used (`self.cfg.use_dedicated_attention`), whether positional encodings are added (`self.cfg.add_positional_encoding`), and whether attention weights are returned (`return_attention`).

The configuration flags are passed through the pipeline as a shared context, ensuring consistent behavior across all stages.

The mainline sequence incorporates a conditional branch that determines whether a document identifier is already present in the set of unique document identifiers (`document_id not in unique_document_ids`). If the identifier is not yet registered, it is added to the set and a new embedding slot is allocated.

The mainline sequence incorporates a conditional branch that determines whether a document identifier is already registered. The third stage in the mainline applies a further transformation to the enriched representation. The mainline then proceeds to the next stage with the updated representation.

The conditional branch ensures that each unique document receives a distinct embedding offset, preventing collision between documents that share the same identifier.

The final stage of the pipeline aggregates the enriched representations and produces the output that is passed to the downstream model.

The enrichment component is parameterized by configuration flags that control whether a dedicated attention mechanism is used, whether positional encodings are added, and whether attention weights are returned. The derivation of the enriched embedding from the base representation, the document identifier embedding, and the positional encoding is summarized as follows:

The configuration flags allow the operator to selectively enable each enrichment component, providing flexibility in how the embedding is constructed for different downstream tasks.

When all enrichment components are enabled, the pipeline produces a fully enriched embedding that incorporates document identity, positional context, and attention-based refinement.

The output of the pipeline is a tensor whose shape is determined by the input sequence length and the embedding dimensionality, ready for consumption by the next layer in the model.

This completes the description of the architectural modifications that enrich embeddings with document identifiers and positional information.

## Training objective:

InfoNCE loss with fixed query anchor.


This section specifies the training objective for the retrieval model, defining the contrastive loss and the anchor construction strategy that governs positive and negative example assembly during training.

The InfoNCE loss contrasts a fixed query anchor against a set of candidate embeddings, with the anchor held constant across the batch so that the gradient signal is directed toward the candidate representations. The loss is computed from the softmax-normalized similarity between the anchor embedding and each candidate embedding, yielding a cross-entropy objective over the candidate set.

The fixed-query-anchor design constrains the loss landscape to depend on the candidate embeddings and their relative similarity to the anchor, removing a free parameter on the query side of the contrastive pair.

The anchor is pre-computed from a reference representation and cached, so each training iteration evaluates the loss against a frozen query vector while the candidate set is drawn from the current batch of model outputs.

The resulting objective is differentiable with respect to all candidate embeddings, allowing end-to-end parameter updates through the contrastive signal without requiring an explicit positive-negative pairing beyond the batch-level candidate set.

The contrastive loss serves as the sole signal for parameter updates in the retrieval pipeline, replacing any auxiliary classification or regression head at every optimization step.

## Inference procedure.

The inference procedure maps a query to a ranked list of candidate passages by computing a relevance score for each passage and ordering them by that score. The procedure operates on pre-computed embeddings rather than generating text autoregressively, which confines the inference cost to a single similarity computation per candidate passage. The query embedding remains fixed throughout the inference phase, while each passage embedding is contextualized with respect to the input context before scoring.

The inference stage constructs the scoring pipeline in two stages. First, the query is encoded into a fixed embedding $q$ of dimensionality $d$, and positional encoding is applied to the passage representations according to the configuration flag `self.cfg.add_positional_encoding`, which governs whether positional signals are injected into the contextualized passage vectors. Second, each candidate passage $i$ is encoded into a contextualized embedding $p_i$ that incorporates the surrounding input context. The resulting pair $(q, p_i)$ is then passed to the ranking function described in the next paragraph. The construction ensures that no autoregressive decoding step is required at inference time: the entire ranking is determined by the geometric relationship between the static query vector and the set of contextualized passage vectors.

The ranking mechanism is formalized by the dot-product similarity between the unchanged query embedding $q$ and the contextualized passage embedding $p_i$. The intended scoring rule assigns to each candidate passage $i$ a relevance score defined as the inner product of the two vectors:s_i = q $cdot p_i = $sum_{k=1}^{d} q_k p_{i,k}where $d$ is the embedding dimensionality and $q_k$, $p_{i,k}$ are the $k$-th components of the query and passage embeddings, respectively. The system sorts the candidate passages in descending order of $s_i$ to produce the final ranking. This operation avoids autoregressive generation, thereby reducing inference latency. The query embedding $q$ is held static during the inference phase, while the passage embeddings $p_i$ are contextualized based on the input context.

In summary, the inference procedure reduces the ranking problem to a closed-form similarity computation over a fixed-dimensional embedding space. The combination of a static query representation, contextualized passage encodings with optional positional signals, and a descending sort of dot-product scores yields a deterministic ranking without the need for iterative or autoregressive generation at test time.