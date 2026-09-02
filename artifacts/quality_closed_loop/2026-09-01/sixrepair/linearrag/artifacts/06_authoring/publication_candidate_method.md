## Motivation: revisit GraphRAG shortcomings from relation extraction errors

When vectorized retrieval is enabled, the Tri-Graph—a hierarchical structure over entity, sentence, and passage nodes connected by sparse contain and message adjacency—anchors the retrieval pipeline without requiring explicit relation extraction.

## LinearRAG overview: Tri‑Graph concept and two‑stage retrieval philosophy

Offline Tri‑Graph construction assembles a three‑layer graph whose nodes are entities, sentences, and passages, and whose edges are captured by two adjacency matrices: a containment matrix encoding hierarchical nesting relations and a message matrix encoding semantic co‑occurrence between entities. The resulting static graph is produced entirely offline, providing a fixed topological substrate for the two‑stage retrieval process described subsequently.

## Offline Tri‑Graph construction

Offline Tri-Graph construction proceeds by splitting each corpus passage into constituent sentences, extracting named entities from every sentence via spaCy, and assembling two sparse binary adjacency matrices: a contain matrix linking passages to the entities they host and a mention matrix linking sentences to the entities they reference. This two-level incidence structure preserves the original textual hierarchy—passages and sentences remain first-class nodes—so that downstream retrieval can operate at either granularity without losing provenance to the source text.

## Second retrieval stage: passage retrieval via global importance aggregation

When vectorized retrieval is enabled, passage node weights are initialized by combining direct query–passage similarity with entity-based statistics including occurrence frequency and entity level, producing a hybrid initialization vector for personalized PageRank. Activated entities serve as seeds for personalized PageRank on the passage–entity subgraph, where influence propagates from entity nodes to adjacent passage nodes, yielding a globally ranked list of passages. The resulting PageRank scores are sorted to produce ordered passage indices and their corresponding scores. This retrieval path is active when vectorized retrieval is enabled; the configuration state for this flag is currently unresolved.