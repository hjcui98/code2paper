# LinearRAG blind-baseline audit

## Provenance boundary

- Allowed inputs: the supplied author-intent YAML and the supplied LinearRAG
  source tree.
- Not inspected or used: original paper, true answer, `paper_final`, existing
  candidate/verified products, OpenCode documents, `.agent` documents,
  external models, and external execution artifacts.
- This is a manually authored comparison baseline. No Code2Paper writer,
  structural gate, publication gate, or LLM runtime was invoked.

## Requested status fields

- `writer_status`: `manual_baseline_generated`
- `structural_exit`: `not_applicable_no_Code2Paper_writer`
- `publication_ready`: `false`
- `final_text_validation`: `pass_with_pending_and_explicit_trigraph_gap`
- `unsupported_positive_claims`: `0 unmarked`; unsupported or contradicted
  intent claims are explicitly labelled pending, incomplete, or code-mismatched.

## Coverage accounting

The denominators are declared for this audit and are not borrowed from a
Code2Paper schema.

- Paragraph/story coverage: `7/7`. The candidate covers corpus/indexing,
  graph representation, query seeds, local activation, hybrid initialization
  and PageRank, answer/evaluation surface, and evidence limits.
- Building-block slots: `6/6 represented`; `5 direct`, `1 partial`. NER,
  activation, dynamic thresholding, PageRank, and hybrid initialization are
  directly represented. Tri-Graph is partial because sentence nodes and their
  PageRank edges are absent from the executable graph.
- Pipeline edges: `3/3 represented`; `2 direct`, `1 partial`. Local activation
  and passage ranking are direct. Offline Tri-Graph construction is partial
  because the implementation stores sentence mappings but adds only entity and
  passage vertices to the graph.
- Formula coverage: `9/9 addressed`; all nine are code-derived. The candidate
  states occurrence-normalized edge weights, nearest-entity seed selection,
  iterative propagation, threshold predicate, entity contribution, final
  hybrid passage score, reset sanitization, PageRank invocation/ranking, and
  dense fallback ranking. The
  intent-level claims about complexity, robustness, zero cost, and performance
  are qualitative claims and are marked pending rather than converted into
  unsupported formulas.

## Direct code support

- Passage loading, hashing, normalized embeddings, and persisted stores:
  `run.py:32-40`, `src/embedding_store.py:7-67`.
- spaCy passage/query NER, filtering, sentence associations, and entity sets:
  `src/ner.py:6-49`.
- Entity/sentence auxiliary maps and index flow:
  `src/LinearRAG.py:555-582`, `src/LinearRAG.py:648-672`.
- Actual igraph vertices and weighted edges:
  `src/LinearRAG.py:584-646`.
- Query embedding, seed matching, and no-entity dense fallback:
  `src/LinearRAG.py:84-129`, `src/LinearRAG.py:515-553`.
- BFS propagation, threshold pruning, sentence de-duplication, and optional
  sparse implementation:
  `src/LinearRAG.py:218-479`.
- Hybrid passage score, optional attribute term, reset sanitization, and PPR:
  `src/LinearRAG.py:186-216`, `src/LinearRAG.py:481-513`.
- QA prompt, LLM call, answer parsing, and evaluator metrics:
  `src/LinearRAG.py:53-82`, `src/evaluate.py:19-103`.
- Configuration and command-line overrides:
  `src/config.py:4-27`, `run.py:17-29`, `run.py:46-73`.

## Incomplete or pending items

1. Sentence vertices and sentence mention/contain edges are not added to the
   PageRank graph; only auxiliary sparse/mapping structures use them.
2. Passage splitting is external to the shown code; `chunks.json` supplies the
   passage units and `chunk_token_size` is unused.
3. Pruning, PageRank, and two-stage retrieval effects on noise, recall,
   precision, and multi-hop reasoning are not established by static code.
4. Linear scalability and zero indexing-token-cost outcomes require complexity,
   cost, or runtime evidence. The index method itself contains no LLM call.
5. No comparative or numerical retrieval/generation result was produced in
   this blind baseline.

## Final judgment

The candidate is an evidence-bounded method reconstruction, but it is not
publication-ready. The intended Tri-Graph is only partially realized in the
executable graph, and effect, cost, scalability, and comparison claims have
no authorized evidence here.
