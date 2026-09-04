## Motivation: revisit GraphRAG shortcomings from relation extraction errors

The retrieval pipeline is anchored by a hierarchical Tri-Graph structure that organizes entity, sentence, and passage nodes through sparse contain and message adjacencies. This design avoids explicit relation extraction entirely by relying on the intrinsic structural connectivity to guide vectorized retrieval operations.

## LinearRAG overview: Tri‑Graph concept and two‑stage retrieval philosophy

The framework constructs an offline tri-graph that organizes knowledge across entities, sentences, and passages. Adjacency matrices capture the containment and message relationships between these structural elements to support downstream retrieval.

## Offline Tri‑Graph construction

The offline construction mechanism builds a hierarchical tri-graph by segmenting corpus passages into discrete sentences and extracting named entities to populate two sparse adjacency structures: a contain matrix mapping passages to their constituent entities and a mention matrix linking sentences to referenced entities. This representation preserves the original textual hierarchy while enabling structured relational queries across passages, sentences, and extracted entities.

## First retrieval stage: relevant entity activation via local semantic bridging

The first retrieval stage activates relevant entities via local semantic bridging by initializing activation scores from matched entities and computing query–sentence similarities. Relevance is then iteratively propagated through the sentence–entity subgraph to identify latent intermediate entities that facilitate multi-hop connections. Dynamic pruning applies threshold-based filtering during propagation to retain only strongly relevant entities, thereby preventing combinatorial expansion and mitigating noise accumulation.

## Second retrieval stage: passage retrieval via global importance aggregation

Passage retrieval retrieves top candidates via global importance aggregation by using activated entities as seeds for personalized PageRank on the passage–entity subgraph, initializing nodes with a hybrid score. The method propagates influence from the activated entities to rank passages according to their aggregated importance. Hybrid passage initialization combines direct query similarity with entity-based statistics to set the initial scores for the personalized PageRank computation. This configuration enables vectorized retrieval when the system is configured to use vectorized retrieval, returning the sorted passage indices and scores. The retrieval mechanism remains unresolved when the configuration state is unresolved, limiting the availability of the vectorized retrieval path.