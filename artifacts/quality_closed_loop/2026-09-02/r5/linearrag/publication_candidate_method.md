## Motivation: revisit GraphRAG shortcomings from relation extraction errors

Tri-Graph is a hierarchical graph whose node types span entities, sentences, and passages, connected by sparse contain and message adjacency relations; by grounding the retrieval pipeline in this structure, the system avoids explicit relation extraction entirely.

## LinearRAG overview: Tri‑Graph concept and two‑stage retrieval philosophy

LinearRAG constructs an offline Tri‑Graph whose node set comprises entities, sentences, and passages, connected by contain and message adjacency matrices that encode structural containment and semantic messaging relations across the three granularities.

## Offline Tri‑Graph construction

The Tri-Graph is constructed offline from the corpus by splitting each passage into constituent sentences and extracting entities from both passages and sentences using spaCy. Two sparse adjacency matrices are then formed—a contain matrix linking passages to their entities and a mention matrix linking sentences to their entities—yielding a three-tier hierarchy in which original text units and extracted entities coexist as distinct node sets.

## First retrieval stage: relevant entity activation via local semantic bridging

Entity activation proceeds through three coupled operations. Entity weights $w_{entity}$ and passage weights $w_{passage}$ are computed from query–entity matching and query–sentence similarity, respectively, and combined into a node weight vector $w_{node}$ that serves as the reset distribution for Personalized PageRank (PPR) on the sentence–entity subgraph $G$. PPR is then iteratively propagated with a damping factor $α$ that controls the decay of relevance across entity–sentence edges, allowing the algorithm to surface latent bridging entities that connect the query to distant passages and thereby support multi-hop retrieval. A threshold-based dynamic pruning step retains only entities whose propagated relevance scores $r$ exceed a cutoff, preventing combinatorial expansion and noise accumulation in subsequent retrieval stages. $$
\mathbf{w}_{node} = \mathbf{w}_{entity} + \mathbf{w}_{passage}, \quad \mathbf{r} = \text{PPR}(\mathcal{G}, \mathbf{w}_{node}, \alpha)
$$ This propagation operates on an undirected weighted graph whose edge weights are derived from the similarity scores, and the entire activation is gated by a configuration flag that enables or disables vectorized retrieval.

## Second retrieval stage: passage retrieval via global importance aggregation

Passage retrieval operates by seeding personalized PageRank on the passage–entity subgraph $G$ with the activated entities, initializing each passage node with a hybrid weight $w_{text{node}} = w_{text{entity}} + w_{text{passage}}$ that combines entity-based scores with direct query–passage similarity. Influence then propagates through the undirected, weighted edges of $G$ under damping factor $	heta$ and reset vector $r_0$, yielding a PageRank score vector $r$ that is sorted in descending order to produce the ranked permutation $	heta$ of passage indices. $$
\begin{aligned} \mathbf{w}_{\text{node}} &= \mathbf{w}_{\text{entity}} + \mathbf{w}_{\text{passage}} \\ \mathbf{r} &= \text{PPR}\left(G, \mathbf{w}_{\text{node}}, \alpha, \mathbf{r}_0\right) \\ \pi &= \text{argsort}(\mathbf{r}) \end{aligned}
$$ This retrieval path is active when the vectorized-retrieval configuration flag is enabled, which triggers precomputation of sparse adjacency matrices for the subgraph.