## Motivation: revisit GraphRAG shortcomings from relation extraction errors

The Tri-Graph is a hierarchical graph that organizes entity, sentence, and passage nodes connected by sparse contain and message adjacency relations, anchoring the entire retrieval pipeline without requiring explicit relation extraction. When vectorized retrieval is enabled, the pipeline branches on this configuration, computes the sparse entity-to-sentence adjacency structure, and returns retrieval results over the resulting graph.

## LinearRAG overview: Tri‑Graph concept and two‑stage retrieval philosophy

Offline Tri‑Graph construction assembles a three‑layer graph whose nodes are entities, sentences, and passages, and whose edges are captured by two adjacency matrices: a containment matrix encoding hierarchical nesting relations and a message matrix encoding semantic co‑occurrence between entities. The resulting static graph is produced entirely offline, providing a fixed topological substrate for the two‑stage retrieval process described subsequently.

## Offline Tri‑Graph construction

Offline Tri-Graph construction proceeds by splitting each corpus passage into constituent sentences, extracting named entities from every sentence via spaCy, and assembling two sparse binary adjacency matrices: a contain matrix linking passages to the entities they host and a mention matrix linking sentences to the entities they reference. This two-level incidence structure preserves the original textual hierarchy—passages and sentences remain first-class nodes—so that downstream retrieval can operate at either granularity without losing provenance to the source text.

## First retrieval stage: relevant entity activation via local semantic bridging

Entity activation in the first retrieval stage proceeds through three coordinated sub-steps: initialization, iterative propagation, and dynamic pruning. During initialization, seed entities receive scores proportional to their similarity to the query embedding; the propagation step then iteratively redistributes relevance mass through the sentence–entity subgraph via personalized PageRank with a configurable damping coefficient and undirected weighted edges; dynamic pruning filters nodes whose scores fall below a retention threshold, preventing combinatorial expansion and retaining only strongly relevant entities. The propagation and pruning dynamics are governed by $$
\begin{aligned}
&\text{Initialization:} \quad \mathbf{r}^{(0)}_v = \begin{cases} \text{sim}(\mathbf{q}, \mathbf{s}_v) & \text{if } v \in \mathcal{V}_{\text{seed}} \\ 0 & \text{otherwise} \end{cases} \\
&\text{Propagation:} \quad \mathbf{r}^{(t+1)}_v = \alpha \sum_{u \in \mathcal{N}(v)} \frac{w_{uv}}{\sum_{z \in \mathcal{N}(u)} w_{uz}} \mathbf{r}^{(t)}_u + (1-\alpha) \mathbf{r}^{(0)}_v \\
&\text{Pruning:} \quad \mathcal{V}^{(t+1)} = \{ v \in \mathcal{V}^{(t)} \mid \mathbf{r}^{(t+1)}_v \ge \tau \}
\end{aligned}
$$, where the initialization assigns each seed entity a score proportional to its similarity to the query, the propagation step iteratively redistributes mass through the subgraph, and a threshold $τ$ prunes nodes whose scores fall below the retention boundary. Entity weights computed over the activated subgraph are combined with passage weights to yield node weights over the full graph; propagation is executed over the vertex set, and the resulting document scores are sorted to produce ranked passage indices and scores. This activation path applies to entities whose text does not appear in the pre-mapped sentence-to-entity index and that carry an ordinal or cardinal label; for these entities, the vectorized scoring and PageRank propagation identify latent intermediate entities that enable multi-hop connections across the graph.

## Second retrieval stage: passage retrieval via global importance aggregation

When vectorized retrieval is enabled, passage retrieval operates by propagating importance through the passage–entity subgraph via personalized PageRank, using the activated entities as seeds and initializing passage nodes with a hybrid score that combines direct query–passage similarity with entity-based statistics (occurrence and level) to form the initial ranking vector $$
\mathbf{r}^{(0)} = \alpha \mathbf{h} + (1-\alpha)\mathbf{1}, \quad \mathbf{r}^{(k+1)} = \alpha \left( \mathbf{r}^{(k)} \mathbf{W} + \mathbf{v} \right) + (1-\alpha)\mathbf{1}
$$. The iterative PPR update rule, governed by a damping parameter and a personalization vector derived from the activated entity seeds, yields a globally ranked list of passages by sorting the converged node scores.