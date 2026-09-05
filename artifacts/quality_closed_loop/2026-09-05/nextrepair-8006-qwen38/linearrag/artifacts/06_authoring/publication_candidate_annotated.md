## Motivation: revisit GraphRAG shortcomings from relation extraction errors

The Tri-Graph is a hierarchical graph whose entity, sentence, and passage nodes are connected through sparse contain and message adjacency. By anchoring retrieval to these structural links rather than to individually extracted relation triples, the design sidesteps the error accumulation that arises when explicit relation extraction misidentifies or omits semantic connections between entities.

## LinearRAG overview: Tri‑Graph concept and two‑stage retrieval philosophy

LinearRAG builds an offline tri‑graph whose nodes represent entities, sentences, and passages and whose edges encode containment (passage-to-sentence, sentence-to-entity) and message-adjacency relations among entities. This pre-computed structure serves as the knowledge substrate that the subsequent retrieval stages query.

## Offline Tri‑Graph construction

The offline Tri-Graph is constructed from the corpus by splitting each passage into constituent sentences and extracting named entities with spaCy, from which two sparse adjacency matrices are derived: a contain matrix linking passages to their entities and a mention matrix linking sentences to their entities. When no new passage identifiers are present, the graph is populated by extracting node and edge sets from the existing passage hashes, entities, and sentences, ensuring that the hierarchical structure preserves original text alongside entity nodes.

## First retrieval stage: relevant entity activation via local semantic bridging

Given an input query $q$, the activation procedure initializes a seed set of matched entities $E_{seed}$ and computes query–sentence similarities, then iteratively propagates relevance scores through the sentence–entity subgraph $G_{SE}$. The propagation step corresponds to a personalized PageRank operation with damping factor $E$ that updates the relevance vector $r^{(t)}$ at each iteration $t$, and the pruning step applies a threshold $E$ to retain only entities whose propagated scores exceed the threshold, limiting combinatorial expansion during multi-hop discovery. The full mechanism is formalized as $$
r^{(0)} = \text{Init}(q, \mathcal{E}_{\text{seed}}), \quad r^{(t+1)} = \text{Prune}\left( \text{PPR}(G_{SE}, r^{(t)}, \alpha), \tau \right)
$$ where $q$ is the input query, $E_{seed}$ is the set of seed entities matched to the query, $r^{(t)}$ is the vector of entity relevance scores at iteration $t$, $G_{SE}$ is the sentence–entity subgraph, $E$ is the damping factor, and $E$ is the relevance threshold for pruning. The resulting passage scores are sorted to yield a ranked list of relevant passages. The activation path is gated by a vectorized-retrieval configuration flag whose activation condition is not yet resolved.

## Second retrieval stage: passage retrieval via global importance aggregation

The second retrieval stage ranks passages through global importance aggregation: activated entities serve as seeds for a Personalized PageRank walk over the passage–entity subgraph $G$, with passage nodes initialized by a hybrid score $r^{(0)}$ that combines entity-based weights $w_{ent}$ (derived from the activated entities) and passage-based weights $w_{pass}$ (derived from direct query–passage similarity). The PPR algorithm, parameterized by a damping factor $a$ governing influence decay per propagation step, produces a final score vector $r$ from which the globally ordered list of top passages is obtained by sorting in descending order. $$
r^{(0)} = \mathbf{w}_{\text{ent}} + \mathbf{w}_{\text{pass}}, \quad \mathbf{r} = \text{PPR}(\mathcal{G}, \mathbf{r}^{(0)}, \alpha)
$$ This retrieval path is activated when vectorized retrieval is enabled in the system configuration; the precise activation condition remains to be confirmed.

<!-- code2paper-annotation {"annotation_id":"annotation:pkg:MA-S4:author_intent:001","claim_strength":"structural","derivation_kind":"formal_derived","enters_verified":false,"paragraph_id":"paragraph:MA-S4:method-unit-1","section_id":"MA-S4","surface_mode":"omit_and_review","target_id":"pkg:MA-S4:author_intent:001","target_kind":"formula","verified_eligible":false} -->
<!-- code2paper-annotation {"annotation_id":"annotation:pkg:MA-S5:author_intent:0","claim_strength":"structural","derivation_kind":"formal_derived","enters_verified":false,"paragraph_id":"paragraph:MA-S5:method-unit-1","section_id":"MA-S5","surface_mode":"omit_and_review","target_id":"pkg:MA-S5:author_intent:0","target_kind":"formula","verified_eligible":false} -->
