# Method: LinearRAG (blind code-to-method baseline)

This candidate is reconstructed only from the supplied author-intent YAML and
the LinearRAG source tree. The intent supplies the requested scope and story
order; executable behavior is described from the source. Claims about
scalability, retrieval quality, robustness, multi-hop performance, or
superiority are not treated as implementation facts.

## 1. Corpus representation and offline indexing

The provided run entry point reads pre-existing chunks from
`dataset/<dataset_name>/chunks.json` and prefixes each chunk with its numeric
index. It passes these strings to the indexing method as passages. The code
does not implement a token-based passage splitter; the `chunk_token_size` and
overlap fields in the configuration are not used by this path.

For each passage, `EmbeddingStore` computes and persists a content hash,
stores the original text, and obtains a normalized embedding from the
configured sentence-transformer model. The same store mechanism is used for
entities and sentence strings. The indexer invokes spaCy NER on new passages in
parallel. It ignores entities labelled `ORDINAL` or `CARDINAL`, records the
unique retained entities for each passage, and records each retained entity
under the text of the sentence span in which it occurs. Existing NER results
may be loaded from the configured working directory and merged with new
results.

The resulting data therefore preserves passage text and creates embeddings for
passages, entities, and entity-containing sentence strings. The indexing path
contains no call to the configured answer-generation LLM; the LLM is used later
by `qa()` after retrieval.

## 2. Relation-free graph data structures

The author intent names the desired organization a Tri-Graph. The executable
representation is more limited. The in-memory `igraph` object receives
vertices for entity hash IDs and passage hash IDs only. Sentence hash IDs are
stored in the sentence embedding store and in the two Python mappings
`entity -> sentences` and `sentence -> entities`; they are not added as
vertices to the `igraph` object.

For every passage/entity pair, the indexer counts case-sensitive occurrences
of the entity string in the passage. If `c(p,e)` is that count and
`C(p) = sum_e c(p,e)`, the edge weight inserted from passage `p` to entity `e`
is

`w(p,e) = c(p,e) / C(p)`.

The graph is undirected. In addition, passages whose stored text begins with
an integer followed by `:` are connected to the next passage in numeric order
with weight 1. The graph consequently contains weighted passage-entity edges
and adjacent-passage edges. The sentence/entity associations used for local
propagation are auxiliary mappings and sparse matrices, not sentence vertices
or mention edges in the PageRank graph. The indexer writes the resulting
entity/passage graph to `LinearRAG.graphml`.

This construction uses NER and occurrence/containment statistics rather than
an explicit relation-extraction or relation-triple module. That is a
code-level description of the shown index path; it does not by itself prove
linear scaling or a zero-cost deployment outcome.

## 3. Query seeds and local entity activation

For a question `q`, the retriever computes a normalized question embedding.
spaCy processes the question using the same filtering of ordinal and cardinal
entities, lowercases the retained query-entity strings, and returns them as a
set. For each query entity, the retriever computes dot products against all
stored entity embeddings and selects the maximum-scoring entity as a seed. If
`z` is a query-entity embedding and `u_e` is a stored entity embedding, the
seed is

`e* = argmax_e u_e dot z`, with seed score `a_0(e*) = u_e* dot z`.

When no query entity is extracted, the code bypasses graph search and uses
dense passage retrieval. Otherwise, the seed entities initialize the local
entity stage. In the default non-vectorized path, each active entity has a
score and a tier. At each iteration, entities below the configured relevance
threshold are skipped. For each remaining entity, already-used linked
sentences are removed, sentence embeddings are compared with the question,
and the top configured number of sentences are selected by similarity. A
selected sentence is marked used and propagates its signal to every entity
recorded for that sentence.

For an active entity `e` with score `a_i(e)` and a selected sentence `s`, the
propagated score used by the code is

`a_(i+1)(e') = a_i(e) * sim(s,q)`

for each entity `e'` occurring in `s`. Scores below the same threshold are not
added to the next active set. Entity weights accumulate the seed and propagated
scores, while the tier records the propagation depth. Iteration stops when no
new active entity remains or the configured maximum number of iterations is
reached. An optional vectorized branch performs analogous operations with
PyTorch sparse entity-sentence matrices, sentence de-duplication, per-entity
top-k selection, and thresholding; the run entry point leaves this option off
by default. In both descriptions, the active-set predicate is
`retain(e) iff a_i(e) >= iteration_threshold`.

## 4. Hybrid passage initialization and global ranking

After local activation, the retriever computes dense dot-product similarities
between the question and every passage and min-max normalizes the resulting
passage scores. For each passage, it also counts case-insensitive occurrences
of each activated entity. If `d(p)` is the normalized dense score, `a(e)` is
the active entity score, `l(e)` is its recorded tier, and `o(p,e)` is the text
occurrence count, the entity contribution used in the code is

`b(p) = sum_e a(e) * log(1 + o(p,e)) / max(l(e), 1)`.

The passage initialization weight is then

`h(p) = passage_ratio * d(p) + log(1 + b(p))`,

followed by multiplication by `passage_node_weight` when the weight is placed
on the graph vertex. If the optional attribute-query fallback is enabled, a
keyword-overlap term can additionally be added before that final scaling; the
run entry point disables it by default. The entity weights from the local
stage and the passage weights are added into one graph reset vector. NaN and
negative reset values are replaced with zero, i.e. the reset value for a graph
vertex `v` is `g(v) = 0` when its weight is NaN or negative, and `g(v) = w(v)`
otherwise.

The retriever calls igraph personalized PageRank on the undirected weighted
entity/passage graph, using the reset vector and the configured damping factor.
It extracts the PageRank values at passage vertices, sorts them in descending
order, and returns the top `retrieval_top_k` passage texts and scores. In
compact notation, this is `pi = PPR(G, g, damping)` followed by descending
sorting of `pi` restricted to passage vertices. The
configuration dataclass defaults are `retrieval_top_k = 5`, `max_iterations = 3`,
`top_k_sentence = 1`, `passage_ratio = 1.5`, `passage_node_weight = 0.05`,
`damping = 0.5`, and `iteration_threshold = 0.5`; the `run.py` command-line
defaults override the threshold to 0.4, `top_k_sentence` to 3, and
`passage_ratio` to 2.

If the query has no extracted seed entity, the fallback score is simply
`d(p) = q dot v_p` for each passage embedding, and the passages are ranked by
descending `d(p)` without the graph/PageRank stage.

## 5. Answer generation and evaluation surface

The `qa()` method calls retrieval for each question, concatenates the ranked
passage texts, and sends a system/user message to the configured LLM. The
prompt requests a reasoning section beginning after `Thought:` and an answer
after `Answer:`; the returned text is parsed at `Answer:` when that marker is
present. The run entry point then stores predictions and the evaluator computes
an LLM-judged correctness score and a normalized-answer containment score.
Those generation and evaluation paths depend on an external LLM call and were
not executed for this blind baseline, so no answer accuracy is reported.

## 6. Evidence boundary and unresolved intent claims

The source directly supports NER-based entity indexing, normalized embeddings,
auxiliary sentence/entity associations, weighted entity/passage graph edges,
local thresholded propagation, hybrid passage weights, personalized PageRank,
dense fallback retrieval, and top-k passage output. It does not support the
following statements as unqualified method facts:

- A complete three-vertex-type Tri-Graph with sentence vertices and mention or
  contain adjacency in the PageRank graph: sentence information is auxiliary,
  and `add_nodes()` adds only entities and passages.
- In-code passage-to-sentence splitting or a lossless, fully represented
  sentence hierarchy: the input chunks are supplied by the dataset and only
  entity-containing sentence spans are recorded.
- That fixed-threshold pruning prevents exponential growth, controls noise,
  or adapts optimally to query complexity.
- That PageRank or the two-stage design produces robust multi-hop retrieval,
  better precision/recall, or superiority over other graph-RAG systems.
- Linear scalability or a measured zero-LLM-token indexing cost. The shown
  indexing path makes no LLM call, but neither complexity nor cost is measured
  by this code-only reconstruction.

These items remain `pending` or `incomplete`; no numerical or comparative
positive claim is made in this candidate.
