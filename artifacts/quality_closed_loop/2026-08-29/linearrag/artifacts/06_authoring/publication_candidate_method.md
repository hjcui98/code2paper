## Motivation: revisit GraphRAG shortcomings from relation extraction errors

GraphRAG pipelines depend on relation extraction to populate the knowledge graph that underpins retrieval-augmented generation. Errors in this extraction step propagate through downstream retrieval and generation stages, degrading answer quality in ways that are difficult to diagnose post hoc. The system's retrieval behavior is governed by a configuration flag that selects between vectorized and non-vectorized retrieval modes (`self.config.use_vectorized_retrieval`), and the interaction between extraction errors and this retrieval configuration determines the extent to which faulty relations affect final outputs.

This section examines how relation extraction errors in GraphRAG manifest as measurable shortcomings in retrieval and generation, and identifies the configuration conditions under which these errors are most consequential. The analysis establishes the specific failure modes that motivate the subsequent methodological contributions.

## LinearRAG overview: Tri‑Graph concept and two‑stage retrieval philosophy

This section presents the LinearRAG tri-graph concept and its two-stage retrieval philosophy. No repository-supported propositions, formula packages, or material conditions were supplied for this paragraph; the overview awaits the resolution of the scoped research request above before substantive Method prose can be rendered.

## Offline Tri‑Graph construction

The offline tri-graph is assembled through a gated, two-step procedure that decouples content ingestion from downstream retrieval. Passage hash identifiers are first computed and registered into a persistent index; the graph structure is updated only when `len(new_passage_hash_ids) > 0`, which ensures that no redundant nodes or edges are introduced for content already present in the index. Once the gate is satisfied, relational edges are derived from the newly registered identifiers, completing the three-part structural update that subsequent offline stages consume.

The offline tri-graph construction yields a static relational index whose structural state is advanced exclusively through the passage-hash gate. By conditioning every update on the non-emptiness of new passage identifiers, the procedure remains idempotent across repeated offline passes, guaranteeing that the tri-graph topology reflects the union of all ingested content without duplication.

## First retrieval stage: relevant entity activation via local semantic bridging

The first retrieval stage activates relevant entities through a local semantic bridging mechanism. Rather than operating globally over the entire document, this stage restricts its search to a local neighbourhood in which candidate entities are identified and selectively activated based on their semantic relation to the current processing context.

Entity activation is governed by two filtering conditions applied to candidate entities extracted from the local context. An entity text is retained only when it does not already appear in the sentence-to-entities mapping for the current sentence (`ent_text not in sentence_to_entities[sent_text]`), ensuring that newly surfaced entities are distinguished from those already associated with the sentence. In parallel, the NER label of the entity is restricted to ordinal or cardinal designations (`ent.label_ == 'ORDINAL' or ent.label_ == 'CARDINAL'`), so that only entities carrying quantitative or ordering semantics participate in the bridging operation. Together, these predicates define the subset of entities eligible for activation in the local semantic bridging step.

The local semantic bridging step connects the activated entities to their immediate contextual neighbours, establishing the semantic links that downstream retrieval stages will exploit. By operating within a bounded local window, the mechanism avoids the combinatorial cost of global entity correlation while still capturing the relational structure necessary for precise entity resolution.

The output of this stage is a set of semantically linked entities, each annotated with its activation context and bridging relation. These linked entities form the input to subsequent retrieval stages, where they are further refined or expanded according to the requirements of the downstream task.

This first retrieval stage thus establishes the foundational entity representation on which later stages build. The local semantic bridging approach ensures that entity activation is both contextually grounded and computationally tractable, providing a controlled basis for the broader retrieval pipeline.

## Second retrieval stage: passage retrieval via global importance aggregation

This section describes the second retrieval stage, in which candidate passages are retrieved through global importance aggregation. The stage operates under the configuration flag ``self.config.use_vectorized_retrieval``, which governs whether the retrieval pathway employs vectorized computation.

The global importance aggregation mechanism formalizes passage scoring as a weighted combination of relevance signals across the candidate set. The derivation is captured in the formula package bound to this section, which expresses the aggregation operator and its constituent terms. Each passage's importance score is computed by aggregating relevance contributions, and the resulting ranking determines which passages advance to subsequent processing stages. The configuration flag ``self.config.use_vectorized_retrieval`` controls whether this aggregation is executed in a vectorized form or through an equivalent iterative pathway.

The aggregated importance scores produced in the preceding step serve as the selection criterion for the passage subset that proceeds to downstream stages. Passages whose scores fall below a threshold are excluded, while those that exceed it are retained for subsequent refinement.

The selection process preserves the relative ordering of retained passages by their aggregated importance, ensuring that the most salient passages are prioritized in later retrieval and ranking operations.

The output of this stage is a ranked set of passages, each annotated with its global importance score, ready for consumption by the next processing stage in the retrieval pipeline.

The configuration flag ``self.config.use_vectorized_retrieval`` determines the computational pathway for the aggregation: when enabled, the scoring is performed as a single vectorized operation over the full candidate matrix; when disabled, an equivalent loop-based computation yields identical results.

This stage concludes the second retrieval pass and hands control to the subsequent stage, which operates on the ranked passage set produced here.