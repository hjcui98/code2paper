## Motivation: efficiency and cross‑passage inference challenges in existing rerankers.

The ConTEB benchmark is an evaluation suite that tests rerankers on challenging tasks requiring cross-passage inference, document-wide context, and structural reasoning. These task characteristics target the efficiency and cross-passage inference challenges that existing rerankers face when reasoning beyond a single passage.

## Embedding‑based reranking formulation and overall framework.

The reranking stage formulates candidate reordering as a similarity computation between query and document embeddings, assigning each candidate a ranking score derived from the geometric alignment of its embedding with the query embedding in a shared representation space. This embedding-based formulation defines the overall framework, in which retrieval candidates are re-ordered by embedding-derived relevance scores rather than by lexical or statistical overlap.

## Architecture details: enriching embeddings with document ID and position

The retrieval stage begins with pre-computed dense passage embeddings obtained from a standard dense retriever such as Contriever, which returns the top-*k* candidate passages together with their pre-computed embeddings; the query is encoded with the same model to produce a static query embedding. For each retrieved passage, a dynamic document-ID embedding (assigned relative to the unique documents in the current candidate set) and a sinusoidal passage-position encoding are added to the original passage embedding, injecting document-identity and intra-document ordering signals into the representation. The query and the enriched passage embeddings are then fed jointly into a stack of Transformer encoder layers that apply a hybrid attention mechanism: a shared full-attention module captures global cross-passage interactions, while a dedicated masked-attention module restricts each passage's attention to the query and to other passages from the same document, consolidating intra-document coherence.
passages = passages + document_id_embeddings + passage_id_embeddings
 At inference, dot-product similarity between the static query embedding and the updated passage embeddings is computed, and passages are ranked in descending order of these scores.

Training employs a contrastive InfoNCE objective that pulls the contextualized positive passage embedding toward the fixed query embedding and pushes negative passage embeddings away, with the loss computed as the negative of the positive similarity minus the log-sum-exp over all similarity scores. The dense retriever (Contriever) supplies the initial passage embeddings and top-*k* retrieval results that serve as the input to the contrastive stage. A learned document-ID embedding table assigns a relative identity embedding to each unique document in the candidate set, enabling the model to recognize which passages belong to the same document. When positional encoding is enabled, a sinusoidal position vector is computed for each passage's position within its original document and L2-normalized before being added to the passage embedding, providing structural order cues.
loss_i = -pos_sim + \operatorname{logsumexp}(all_sims, dim=0)


Within each Transformer layer, the hybrid attention mechanism combines a shared full-attention module and a dedicated masked-attention module to jointly model inter- and intra-document dependencies. The shared full-attention module is a standard multi-head attention layer that allows the query and all passages to attend to one another, capturing global relevance and cross-document relationships. The dedicated masked-attention module is a masked multi-head attention layer that restricts each passage to attend only to the query and to other passages from the same document, enabling fine-grained coreference resolution and local coherence. The outputs of both attention modules are summed, passed through dropout, and added residually to the input; when the dedicated attention branch is active, its output is combined with the shared output before the residual connection. The shared attention module optionally returns attention weights for downstream inspection.

## Training objective:

InfoNCE loss with fixed query anchor.


The training objective employs an InfoNCE contrastive loss with a fixed query anchor, which encourages the updated positive passage embedding to align with the query while separating negative passages. The per-example loss is computed as the negative positive similarity offset by the log-sum-exp of all pairwise similarities, yielding the recorded result
loss_i = -pos_sim + \operatorname{logsumexp}(all_sims, dim=0)
. EBCAR is trained on three ConTEB datasets—MLDR, SQuAD, and NarrativeQA—covering entity disambiguation, span matching, and narrative comprehension.

## Inference procedure.

The inference procedure computes dot-product similarities between the unchanged query embedding and the contextualized passage embeddings (`self.cfg.add_positional_encoding`), producing a similarity tensor that is sorted along the passage dimension in descending order to yield relevance scores and ranked indices.
(relevance_scores, indices) = \operatorname{sort}(similarities, dim=1, descending=True)