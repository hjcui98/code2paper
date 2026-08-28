## Motivation: efficiency and cross‑passage inference challenges in existing rerankers.

Existing dense and listwise rerankers face two coupled pressures: inference efficiency at scale and the need to perform cross‑passage inference when a query's answer requires integrating evidence distributed across multiple passages. These pressures motivate the design of evaluation tasks that isolate cross‑passage reasoning from single‑passage retrieval.

The ConTEB benchmark is an evaluation suite that tests rerankers on tasks requiring cross‑passage inference, document‑wide context, and structural reasoning, thereby exposing the limits of existing rerankers on precisely the inference patterns that efficiency‑constrained architectures struggle to model.

## Embedding‑based reranking formulation and overall framework.

This section formulates the embedding‑based reranking objective and situates it within the overall framework, defining how candidate representations are scored and reordered to produce a final ranking.

## Architecture details: enriching embeddings with document ID and position

The architecture under consideration enriches pre-computed dense passage embeddings with two structural signals—a document-identity embedding and a sinusoidal passage-position encoding—and processes the augmented vectors jointly with the query embedding through a stack of Transformer encoder layers equipped with a hybrid attention mechanism comprising a shared full-attention module and a dedicated masked-attention module. The intended design goal is to support cross-passage reasoning in retrieval-augmented generation by injecting document-level structural knowledge into the embedding space while avoiding full-text processing and autoregressive generation to reduce inference latency.

The core transformation maps the augmented passage embeddings and the fixed query embedding through the hybrid-attention encoder to produce contextualized passage embeddings; the closed-form expression for this layer-wise mapping is pending formal derivation. The input to each layer is the set of augmented passage embeddings concatenated with the query embedding, the transformation applies the shared full-attention module followed by the dedicated masked-attention module with residual connections and layer normalization, and the output is the set of contextualized passage embeddings that encode both cross-passage and intra-document structural information.

The pipeline proceeds in three operational phases: input preparation, structural augmentation, and hybrid-attention encoding. Each phase is described in turn below, with the configuration-dependent branching that governs the dedicated attention path made explicit at each decision point.

A sinusoidal passage-position encoding is intended to encode the ordinal position of a passage within its source document, providing structural order cues that distinguish passages sharing identical content but appearing at different locations in the original document.

The shared full-attention module is a standard multi-head attention layer in which the query token and all passage tokens attend to one another without restriction, capturing global relevance signals and cross-document relationships across the entire candidate set.

In each Transformer encoder layer, the shared full-attention module and the dedicated masked-attention module operate in sequence, with residual connections and layer normalization applied after each sub-layer, so that the output of a layer is a function of both global and document-local interaction patterns.

The dedicated masked-attention module is conditionally active, governed by the configuration flag `cfg.use_dedicated_attention`; when this flag is set to false, the layer reduces to the shared full-attention path alone, and the document-local coherence signal is not modeled.

The attention mask applied by the dedicated module is intended to restrict each passage token's attention to the query token and to other passage tokens that share the same document identifier, thereby isolating intra-document interactions from inter-document interactions within the same layer.

The output of the final Transformer layer is a set of contextualized passage embeddings, each of which has been updated by both the global full-attention path and, when is enabled, the document-local masked-attention path, producing representations that encode both cross-passage and intra-document structural information.

The query embedding is held fixed throughout both training and inference; only the passage embeddings are updated by the encoder, so that the final ranking score is computed as the dot-product similarity between the static query vector and the contextualized passage vectors.

In the retrieval and embedding preparation phase, a dense retriever (Contriever) is intended to fetch top-𝑘 candidate passages for a given query, retrieving their pre-computed embeddings from the retriever's index; the query is encoded with the same Contriever model to produce a query embedding in the shared vector space.

In the structural augmentation phase, each retrieved passage embedding is augmented with a dynamic document-identity embedding and a sinusoidal passage-position encoding, injecting document-identity and ordering signals into the vector representation before it enters the hybrid-attention encoder.

In the hybrid-attention encoding phase, the query embedding and the augmented passage embeddings are fed jointly into the stack of Transformer encoder layers, where each layer applies the shared full-attention module and, when is enabled, the dedicated masked-attention module, producing contextualized passage embeddings as output.

The document-identity embedding table is a learned lookup of relative document-identity vectors, assigned dynamically to the unique documents present in the current candidate set rather than using global corpus-level identifiers, enabling the model to recognize which passages belong to the same source document.

The hybrid attention mechanism combines the shared full-attention module (modeling global cross-passage interactions) and the dedicated masked-attention module (modeling intra-document interactions) within each Transformer layer, so that inter-document and intra-document dependencies are jointly represented in the contextualized output.

The dedicated masked-attention module restricts each passage token's attention to the query token and to other passage tokens from the same document, enabling fine-grained coreference resolution and local coherence modeling that the unrestricted full-attention path alone cannot capture.

The complete architecture thus realizes the stated goal of enriching embeddings with document-identity and position signals and processing them through a hybrid-attention Transformer encoder, with the dedicated document-local attention path activated conditionally via .

## Inference procedure.

At inference time the query embedding is held static as the original Contriever embedding, while the contextualized passage embeddings are produced by the hybrid-attention encoder. These two sets of vectors constitute the inputs to the subsequent scoring and ranking stage.

In the intended scoring and ranking step, dot-product similarities are computed between the unchanged query embedding and each contextualized passage embedding, and passages are sorted in descending order of these scores to produce the final ranking.