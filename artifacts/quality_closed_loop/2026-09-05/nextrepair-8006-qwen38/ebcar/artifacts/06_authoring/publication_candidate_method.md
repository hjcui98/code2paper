## Motivation: efficiency and cross‑passage inference challenges in existing rerankers.

Existing rerankers face efficiency constraints and limited capacity for cross-passage inference, document-wide context, and structural reasoning. To address these challenges, the ConTEB benchmark is introduced as an evaluation suite that isolates these demanding inference requirements, thereby exposing the specific limitations of current systems.

## Embedding‑based reranking formulation and overall framework.

Embedding-based reranking maps candidate items into a shared representational space, where a learned scoring function assigns a relevance score by comparing the query embedding against each candidate embedding. Within the overall framework, this reranking stage is positioned between an upstream retrieval component and a downstream consumer, with the embedding model serving as the central mechanism that determines which candidates advance to subsequent processing stages.

## Architecture details: enriching embeddings with document ID and position

The system retrieves top-k candidate passages and their pre-computed embeddings using a dense retriever, and encodes the query with the same model. A configuration flag enables a dedicated attention pathway; when active, the encoder combines the shared full-attention output and the dedicated masked-attention output through a residual connection after a dropout step. A sinusoidal positional encoding is computed from the sequence length and returned as part of the embedding preparation.

Each retrieved passage embedding is augmented with a dynamic document-ID embedding and a sinusoidal passage-position encoding, injecting document-identity and ordering signals into the representation. The Transformer encoder then applies a hybrid attention mechanism in every layer: a shared full multi-head attention module allows the query and all passages to attend to one another, capturing global relevance and cross-document relationships, while a dedicated masked attention module restricts each passage to attend only to the query and to other passages from the same document, jointly modelling inter- and intra-document dependencies.

The dedicated masked attention module computes multi-head attention in which each passage is restricted to attend only to the query and to other passages originating from the same document, enabling fine-grained coreference resolution and local coherence within document boundaries.

## Training objective:

InfoNCE loss with fixed query anchor.

The training objective employs a contrastive InfoNCE loss that pulls the updated positive passage embedding toward the fixed query embedding while pushing negative passage embeddings away. For each sample $i$ in a batch of size $B$, the per-sample loss is the negative similarity score $-s_{q_i, p_i^+}$ between the fixed query embedding $q_i$ and the updated positive passage embedding $p_i^+$, normalized by the log-sum-exp of similarity scores over the negative set $N_i$. $$
\mathcal{L}_{\text{InfoNCE}} = \frac{1}{B} \sum_{i=1}^{B} \left( -s_{q_i, p_i^+} + \log \sum_{j \in \mathcal{N}_i} e^{s_{q_i, p_j}} \right)
$$ The scalar training signal is the mean of these per-sample losses across the batch, encouraging alignment between each query and its designated positive passage while enforcing separation from all other passage embeddings in the batch.

## Inference procedure.

At inference time, the scoring function computes the dot product between the unchanged query embedding $q$ and each contextualized passage embedding $p_i$, yielding a scalar relevance score $s_i$ for every passage in the candidate set. Passages are then ranked by a descending sort over these scores, producing a permutation $π$ that orders passages from most to least relevant. This procedure avoids full-text processing and autoregressive generation to reduce inference latency. The scoring and ranking operations are formalized as follows: $$s_i = q^T p_i, π = argsort_i(s_i, descending)$$