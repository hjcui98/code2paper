## Motivation: efficiency and cross‑passage inference challenges in existing rerankers.

Efficiency and cross‑passage inference represent two interrelated limitations in existing reranker architectures: reranking a large candidate pool within tight latency budgets while simultaneously generalizing beyond single‑passage evidence to document‑wide context. The ConTEB benchmark addresses this compound challenge as an evaluation suite that tests rerankers on challenging tasks requiring cross‑passage inference, document‑wide context, and structural reasoning. By separating the demands of cross‑passage reasoning from pure retrieval‑based matching, ConTEB enables researchers to determine whether a reranker's performance derives from genuine multi‑passage integration or from single‑passage heuristics that merely approximate the task. These challenges motivate the need for evaluation protocols that isolate cross‑passage reasoning demands from pure retrieval‑based matching, a gap that the ConTEB suite is designed to fill.

## Embedding‑based reranking formulation and overall framework.

The embedding-based reranking stage scores candidate documents by evaluating their similarity to a query representation in embedding space, operating as a distinct stage within the broader retrieval pipeline. This formulation positions the reranker between the initial retrieval step and the final ranking output, focusing on how document representations are compared against the query vector to determine relevance.

## Architecture details: enriching embeddings with document ID and position

The EB-CAR reranker targets the reranking stage of a retrieval-augmented generation pipeline, addressing cross-passage reasoning when evidence is scattered across multiple passages and requires resolving coreference or structural context (`intended`). The method operates on pre-computed embeddings rather than full text, avoiding autoregressive generation to reduce inference latency . The architecture enriches passage embeddings with document-level structural signals and processes them through a Transformer encoder with a hybrid attention mechanism that jointly models inter- and intra-document dependencies .

The training pipeline in `train_ebcar` branches on `cfg.use_dedicated_attention` to select the dedicated-attention configuration, loads the corresponding weights, and computes validation loss as the mean over the number of validation batches . The reranker is configured by this flag and returned after the training loop completes . A formal expression of the contrastive loss and embedding enrichment mechanism is pending formal derivation.

The pipeline proceeds in two principal phases: input preparation, in which pre-computed dense passage embeddings from a standard retriever are augmented with structural signals, and hybrid-attention encoding, in which the augmented embeddings are processed through a stack of Transformer encoder layers . The output is a set of contextualized passage embeddings used for ranking .

A sinusoidal passage-position encoding is added to each passage embedding to encode the position of that passage within its original document, providing structural order cues . This positional signal complements the document-identity signal by conveying the sequential arrangement of passages within a document .

The shared full attention module implements standard multi-head attention, allowing the query and all passages to attend to each other, thereby capturing global relevance and cross-document relationships . This module operates without document-level masking and models interactions across the entire candidate set .

Document-level structural knowledge is injected into passage embeddings to support cross-passage inference . The enrichment strategy ensures that each passage representation carries both its intrinsic semantic content and its structural position within the source document .

Document IDs are assigned using a relative, dynamic scheme rather than global corpus-level identifiers . Each unique document in the current candidate set receives a distinct ID, so the same document maps to the same ID within a single retrieval context but the ID space is not fixed across different queries .

The query embedding is kept fixed during both training and inference, while passage embeddings are updated through the Transformer encoder . This asymmetry allows the model to refine passage representations without altering the query anchor, simplifying the inference-time scoring computation .

Training is conducted on ConTEB datasets that explicitly require cross-passage reasoning . These datasets provide supervision signals where the correct answer depends on integrating information distributed across multiple passages from the same or different documents .

The training loop computes per-batch loss and averages over the number of batches to obtain epoch-level train and validation loss . The reranker is returned after training completes, with the run identified by a name incorporating the `hybrid_attention` tag and the configuration state .

A dense retriever (Contriever) fetches top-k candidate passages for a given query, and their pre-computed embeddings are retrieved alongside the passages . The query is encoded with the same Contriever model to produce a query embedding in the same vector space, establishing the input vectors for subsequent structural augmentation and encoding stages .

For each retrieved passage, a dynamic document ID embedding and a sinusoidal passage-position encoding are added to its original embedding to inject document-identity and ordering signals . This structural augmentation transforms raw semantic embeddings into enriched representations that carry both content and structural context .

The query embedding and augmented passage embeddings are fed jointly into a Transformer encoder that applies shared full attention for global interactions and dedicated masked attention for intra-document interactions in every layer, producing contextualized passage embeddings . The dedicated module is conditionally active, controlled by ; when disabled, only the shared full-attention path is used .

A learned relative document-identity embedding table assigns embeddings dynamically to unique documents in the candidate set, enabling the model to recognize which passages belong together . The table is indexed by the relative document ID computed for the current retrieval context rather than by a global corpus-level identifier .

The hybrid attention mechanism combines shared full attention (global cross-passage) and dedicated masked attention (intra-document) in each Transformer layer to jointly model inter- and intra-document dependencies . Two complementary attention patterns co-exist in each layer: a global pattern that spans all passages and a document-local pattern restricted to passages sharing the same document ID .

The dedicated masked attention module implements masked multi-head attention that restricts a passage to attend only to the query and to other passages from the same document, enabling fine-grained coreference resolution and local coherence . This masking pattern is applied in addition to the shared full-attention path, so each layer produces a combined representation that reflects both global and document-local context .

At inference, dot-product similarity is computed between the static query embedding and the updated contextualized passage embeddings, and passages are ranked in descending order of these scores . The fixed query embedding serves as the anchor throughout, ensuring that ranking reflects the model's learned contextual refinement of passage representations without altering the query representation itself .

## Training objective:

InfoNCE loss with fixed query anchor.

## Inference procedure.

During inference, the query embedding remains static, retaining its original Contriever representation without undergoing re-encoding by the Transformer. In contrast, candidate passages are processed by the hybrid-attention encoder to produce contextualized passage embeddings. The intended scoring mechanism computes the dot-product similarity between the static query embedding and each contextualized passage embedding, subsequently sorting passages in descending order of these scores to establish the final ranking. This specific inference-time scoring and ranking procedure is currently an author-specified design intent; available repository evidence confirms the training-time reranker invocation and conditional branching logic but does not yet verify the inference-time dot-product scoring formula.