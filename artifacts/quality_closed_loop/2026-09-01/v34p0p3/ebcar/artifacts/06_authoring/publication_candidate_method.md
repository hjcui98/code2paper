## Motivation: efficiency and cross‑passage inference challenges in existing rerankers.

The ConTEB benchmark is an evaluation suite that tests rerankers on tasks requiring cross-passage inference, document-wide context, and structural reasoning, directly addressing the efficiency and multi-passage inference limitations of existing rerankers.

## Embedding‑based reranking formulation and overall framework.

The framework formulates reranking as a ranking problem in which a learned embedding function maps queries and candidate items into a shared vector space, and a scoring function derives a relevance estimate from the geometric relationship between the query embedding and each candidate embedding. The overall framework couples this embedding-based scoring stage with an upstream retrieval stage, so that the reranker refines an initial candidate set rather than operating over the full corpus.

## Architecture details: enriching embeddings with document ID and position

The retrieval pipeline begins with a dense retriever such as Contriever, which produces pre-computed passage embeddings and a query embedding from the same encoder, fetching the top-𝑘 candidate passages for a given query. Each retrieved passage embedding is augmented with a learned document ID embedding assigned dynamically relative to the unique documents in the current candidate set and with a sinusoidal positional encoding that records the passage's ordinal position within its source document, thereby injecting document-identity and ordering signals into the representation. The query and the augmented passage embeddings are concatenated and processed jointly through a stack of Transformer encoder layers, each of which applies a shared full-attention module for global cross-passage interactions alongside a dedicated masked-attention module that restricts attention to passages originating from the same document. The model is trained with a contrastive InfoNCE loss that anchors on the fixed original query embedding, pulling the contextualized positive passage embedding closer while pushing negative passage embeddings away; at inference, the static query embedding is scored against the updated passage embeddings via dot-product similarity to rank passages in descending order. $$
passages = passages + document_id_embeddings + passage_id_embeddings
$$

Training proceeds with a contrastive InfoNCE objective that pulls the updated positive passage embedding toward the fixed query embedding while pushing negative passage embeddings away, using the dense retriever's initial embeddings as the starting point. The positional encoding component constructs a sinusoidal encoding that encodes the ordinal position of each passage within its original document, providing structural order cues; when positional encoding is enabled, this encoding is added to the passage embeddings before they enter the Transformer encoder. The document ID embedding table assigns learned relative identity vectors to each unique document in the candidate set dynamically, enabling the model to recognize which passages belong to the same document. $$
loss_i = -pos_sim + \operatorname{logsumexp}(all_sims, dim=0)
$$

Each Transformer encoder layer in the hybrid-attention architecture combines two attention sub-layers: a shared full-attention module, which is a standard multi-head attention allowing the query and all passages to attend to one another and thereby capturing global relevance and cross-document relationships, and a dedicated masked-attention module, which restricts each passage to attend only to the query and to other passages from the same document, enabling fine-grained coreference resolution and local intra-document coherence. When dedicated attention is enabled, the outputs of both sub-layers are summed, passed through a dropout layer, and residual-connected back to the input; when positional encoding is enabled, the sinusoidal positional encoding is added to the passage embeddings prior to the attention computation. The layer optionally returns attention weights for inspection when requested.

## Training objective:

InfoNCE loss with fixed query anchor.


The training objective is an InfoNCE contrastive loss that encourages the updated positive passage embedding to align with the fixed query embedding while separating all negative passage embeddings within the batch. The per-example loss is computed as $$
loss_i = -pos_sim + \operatorname{logsumexp}(all_sims, dim=0)
$$ where pos_sim denotes the similarity between the fixed query embedding and its corresponding positive passage embedding, and all_sims collects the similarities between the query embedding and every candidate passage embedding in the current batch. The three ConTEB training sets—MLDR, SQuAD, and NarrativeQA—cover entity disambiguation, span matching, and narrative comprehension, providing diverse supervision signals for the contrastive objective.

## Inference procedure.

The inference procedure computes dot-product similarities between the unchanged query embedding and the contextualized passage embeddings, then sorts passages by descending score to yield ranked relevance scores $$
(relevance_scores, indices) = \operatorname{sort}(similarities, dim=1, descending=True)
$$. When positional encoding is enabled, the contextualized passage embeddings incorporate positional context in the similarity computation; the sorting is applied along the passage dimension to produce the final ranking.