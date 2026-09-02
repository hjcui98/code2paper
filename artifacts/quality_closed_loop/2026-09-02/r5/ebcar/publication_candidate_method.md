## Motivation: efficiency and cross‑passage inference challenges in existing rerankers.

ConTEB is an evaluation suite that tests rerankers on challenging tasks requiring cross-passage inference, document-wide context, and structural reasoning. The suite targets the efficiency and cross-passage inference limitations of existing rerankers by constructing tasks in which correct rankings depend on integrating evidence across multiple passages rather than on any single passage in isolation.

## Embedding‑based reranking formulation and overall framework.


The framework formulates reranking through an embedding-based ranking mechanism, in which candidate items are scored and ordered according to a learned representation, and couples this scoring stage with the surrounding retrieval pipeline to produce a final ranked output.

## Architecture details: enriching embeddings with document ID and position

The pipeline begins with a dense retrieval stage in which a Contriever-based retriever fetches the top-$k$ candidate passages together with their pre-computed embeddings, and the query is encoded with the same model to produce a compatible representation. The encoder forward pass branches on whether dedicated attention is enabled: when the flag is set, a dedicated masked attention module is activated alongside the shared full attention; when it is not set, the encoder relies solely on shared full attention. The encoder output is combined through a dropout-gated fusion of the shared and dedicated attention outputs, and the positional encoding is returned as part of the forward pass.

Each retrieved passage is enriched with two structural signals before encoding: a sinusoidal positional encoding that captures the position of the passage within its original document, providing structural order cues that complement content-level information. These augmented embeddings are processed by a Transformer encoder in which each layer applies a shared full attention module, allowing the query and all passages to attend to one another for global relevance and cross-document relationships, and a dedicated masked attention module that restricts each passage to attend only to the query and to other passages from the same document. This hybrid attention design jointly models inter-document and intra-document dependencies within a single encoder stack.

The dedicated masked attention module restricts each passage to attend only to the query and to other passages from the same document, enabling fine-grained coreference resolution and local coherence. Formally, the augmented passage embedding is computed as $$
\mathbf{p}' = \mathbf{p} + \mathbf{e}_{\text{doc}} + \mathbf{e}_{\text{pos}} \quad \text{and} \quad \mathbf{h} = \text{Concat}(\mathbf{q}, \mathbf{p}')
$$, where $p$ is the original passage embedding, $e_{\text{doc}}$ is the learned document ID embedding, $e_{\text{pos}}$ is the sinusoidal passage-position encoding, $p'$ is the resulting augmented embedding, $q$ is the query embedding, and $h$ is the concatenated sequence fed into the Transformer encoder. The dedicated attention and positional encoding are each active when their respective configuration flags are enabled; otherwise the encoder operates with shared full attention alone.

## Training objective:

InfoNCE loss with fixed query anchor.


The training objective realizes contrastive learning through an InfoNCE loss that treats the query embedding as a fixed anchor: the loss pulls the updated positive passage embedding toward the query while pushing negative passage embeddings away. For each sample, the per-sample loss is computed as the negative of the positive similarity score minus the log-sum-exp of all candidate similarity scores along the candidate dimension. Per-sample losses are stacked and averaged to yield the batch-level objective; when the candidate set for a sample is empty, that sample contributes no loss term to the batch mean. $$
\mathcal{L}_{\text{InfoNCE}} = \frac{1}{B} \sum_{i=1}^{B} \left( -s_{i}^{+} + \log \sum_{j \in \mathcal{N}_i \cup \{i\}} e^{s_{ij}} \right)
$$ Here $B$ denotes the batch size, $s_{i}^{+}$ is the similarity between the query and the positive passage for sample $i$, $s_{ij}$ is the similarity between the query and candidate passage $j$, $N_i$ is the set of negative passages for sample $i$, and $L_{\text{InfoNCE}}$ is the resulting contrastive loss. The training data comprises three ConTEB datasets—MLDR, SQuAD, and NarrativeQA—covering entity disambiguation, span matching, and narrative comprehension, respectively.

## Inference procedure.

Each candidate passage embedding $${mathbf{p}_i}$$ is contextualized by adding document and position embeddings to yield $${mathbf{p}_i^{\text{ctx}}}$, and the unchanged query embedding $${mathbf{q}}$$ is concatenated with these contextualized passages to form a sequence $${mathbf{h}}$$ that is processed by an attention mechanism to produce a vector of relevance scores $${mathbf{s}}$$ over the $N$ candidate passages. $$
\begin{align}
\mathbf{p}_i^{\text{ctx}} &= \mathbf{p}_i + \mathbf{e}_{\text{doc}}(i) + \mathbf{e}_{\text{pos}}(i) \\
\mathbf{h} &= [\mathbf{q}; \mathbf{p}_1^{\text{ctx}}, \dots, \mathbf{p}_N^{\text{ctx}}] \\
\mathbf{s} &= \text{Attn}(\mathbf{h}) \in \mathbb{R}^{N} \\
\text{rank} &= \text{argsort}(\mathbf{s}, \text{descending})
\end{align}
$$ Passages are ranked by sorting the scores in descending order to obtain the final indices.