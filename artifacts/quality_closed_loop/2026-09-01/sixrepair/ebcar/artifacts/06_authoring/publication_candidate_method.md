## Motivation: efficiency and cross‑passage inference challenges in existing rerankers.

The ConTEB benchmark is an evaluation suite that tests rerankers on tasks requiring cross-passage inference, document-wide context, and structural reasoning, directly addressing the efficiency and multi-passage inference limitations of existing rerankers.

## Embedding‑based reranking formulation and overall framework.

The framework formulates reranking as a ranking problem in which a learned embedding function maps queries and candidate items into a shared vector space, and a scoring function derives a relevance estimate from the geometric relationship between the query embedding and each candidate embedding. The overall framework couples this embedding-based scoring stage with an upstream retrieval stage, so that the reranker refines an initial candidate set rather than operating over the full corpus.

## Architecture details: enriching embeddings with document ID and position

A dense retriever (Contriever) fetches the top-$k$ candidate passages and their pre-computed embeddings, and the query is encoded with the same model to obtain a fixed query representation. Each retrieved passage embedding $e_i^{(0)}$ is then structurally augmented with a learned document-ID embedding $e_{d(i)}$ and a sinusoidal passage-position encoding $p_i$, injecting document-identity and ordering signals into the static retriever output. The augmented passage embeddings together with the query are fed into a Transformer encoder in which every layer applies a shared full multi-head attention module $A_{\text{full}}$ that captures global cross-passage interactions, and a dedicated masked multi-head attention module $A_{\text{mask}}$ that enforces intra-document coherence by restricting attention to passages from the same document via a document-specific mask matrix $M_{d}$, allowing the model to consolidate local document-level context while maintaining global relevance signals. The layer-$l$ hidden state is computed as $H^{(l)} = A_{\text{full}}(H^{(l-1)}) + A_{\text{mask}}(H^{(l-1)}, M_{d})$, where $H^{(l)}$ denotes the hidden state at layer $l$ of the encoder. $$
\begin{aligned} \\mathbf{e}_{i}^{\text{aug}} &= \\mathbf{e}_{i}^{\text{base}} + \\mathbf{E}_{\text{doc}}[\text{doc}(i)] + \\mathbf{P}_{\text{pos}}(i) \\\ \\mathbf{H}^{(0)} &= [\\mathbf{q}; \\mathbf{e}_{1}^{\text{aug}}, \\dots, \\mathbf{e}_{K}^{\text{aug}}] \\\ \\mathbf{H}^{(\\ell+1)} &= \\mathbf{H}^{(\\ell)} + \text{Dropout}\\left( \text{Attn}_{\text{full}}(\\mathbf{H}^{(\\ell)}) + \text{Attn}_{\text{mask}}(\\mathbf{H}^{(\\ell)}, \\mathbf{M}_{\text{doc}}) \right) \\end{aligned}
$$

The model is trained with a contrastive InfoNCE loss that pulls the updated positive passage embedding $p^{+}$ toward the fixed query embedding $q$ while repelling negative passage embeddings $p^{j}$ from the candidate set. The document-ID embedding table is learned jointly, assigning relative identity embeddings dynamically to unique documents so that the model recognizes which passages belong together; the sinusoidal positional encoding further encodes each passage's position within its original document, providing structural order cues. The loss is defined as $L_{\text{InfoNCE}} = -\text{log} 
rac{\text{exp}(q^{\text{T}} p^{+} / au)}{\text{exp}(q^{\text{T}} p^{+} / au) + \text{exp}(q^{\text{T}} p^{j} / au)}$, where $	au$ is a temperature scaling factor. $$
\mathcal{L}_{\text{InfoNCE}} = -\log \frac{\exp(\mathbf{q}^{\top}\mathbf{p}^{+}/\tau)}{\sum_{j=0}^{K} \exp(\mathbf{q}^{\top}\mathbf{p}^{j}/\tau)}
$$

At each Transformer encoder layer, the hybrid attention mechanism combines a shared full multi-head attention module, which allows the query and all passages to attend to one another and thereby captures global relevance and cross-document relationships, with a dedicated masked multi-head attention module, which restricts each passage to attend only to the query and to other passages from the same document, enabling fine-grained coreference resolution and local coherence. When dedicated attention is enabled, the two attention outputs are summed and passed through a dropout-residual connection; when positional encoding is enabled, sinusoidal position encodings are added to the input embeddings before the encoder. When $return_{\text{attention}}$ is set, the shared attention module additionally returns its attention weights for downstream inspection.

## Training objective:

InfoNCE loss with fixed query anchor.


The training objective employs an InfoNCE contrastive loss that encourages the updated positive passage embedding to align with a fixed query anchor while separating it from negative candidates. The per-sample loss $L_i$ is computed by subtracting the positive similarity $pos_sim$ from the log-sum-exp $logsumexp$ of the full similarity vector $all_sims$ over all candidate passages: $$
\mathcal{L}_i = -\text{pos\_sim} + \text{logsumexp}(\text{all\_sims}, \text{dim}=0)
$$ This objective is instantiated across three ConTEB training sets—MLDR, SQuAD, and NarrativeQA—covering entity disambiguation, span matching, and narrative comprehension. The contrastive signal is defined relative to the in-batch candidate set, so the loss magnitude depends on the composition of negatives present in each mini-batch.

## Inference procedure.

The inference procedure contextualizes base passage embeddings with document and passage ID embeddings, then computes dot-product similarities between the static query embedding and the resulting contextualized passage embeddings. These similarities are sorted in descending order to produce relevance scores and ranked passage indices $$
\begin{align}
&\mathbf{q} \in \mathbb{R}^{d}, \quad \mathbf{p}_i \in \mathbb{R}^{d}, \quad i \in \{1, \dots, N\} \\
&\mathbf{p}_i^{ctx} = \mathbf{p}_i + \mathbf{e}_{doc(i)} + \mathbf{e}_{pass(i)} \\
&\mathbf{X} = [\mathbf{q} \oplus \mathbf{p}_1^{ctx} \oplus \dots \oplus \mathbf{p}_N^{ctx}] \in \mathbb{R}^{(1+N) \times d} \\
&s_i = \mathbf{q}^\top \mathbf{p}_i^{ctx} \\
&\pi = \operatorname{argsort}_{i}(-s_i)
\end{align}
$$ when positional encoding is enabled.