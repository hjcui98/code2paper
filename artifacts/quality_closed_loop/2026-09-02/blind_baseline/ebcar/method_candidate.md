# EBCAR: Embedding-Based Context-Aware Reranking

## 1. Scope and input representation

This candidate describes the EBCAR implementation visible in the supplied
repository. The author intent positions EBCAR as an embedding-only reranker
for retrieved passages, with structural document cues and two complementary
attention patterns. The code supports the data path and neural computation
below; it does not, by itself, establish latency improvements, competitiveness
with text-based LLM rerankers, or gains on cross-passage reasoning tasks.

The retrieval configuration selects the Hugging Face embedding wrapper for
`nishimoto/contriever-sentencetransformer` and requests normalized embeddings.
For each query, the data preparation code invokes a Chroma retriever with
`k=20`, embeds the query and the retrieved passage texts, and records a binary
label by exact `chunk_id` equality with the query's target chunk. The chunk
identifier is split into a document identifier and a passage identifier. The
reranker itself receives a query vector q in R^768, passage
vectors p_1, ..., p_K in R^768, labels, document identifiers,
passage positions, and passage text. The forward computations use the vectors,
labels, and identifiers; passage text is carried through the batch and is used
only when the ranked text list is reconstructed.

## 2. Structural augmentation

When `add_positional_encoding` is enabled, each passage vector is augmented by
two vectors. First, the dataset adapter converts the document identifiers in
each retrieved set to relative indices in order of first occurrence. The model
then looks up an entry in a K x d document-ID embedding table using

\[
g(d_i)=(d_i\bmod K)+\left\lfloor d_i/K\right\rfloor,
\qquad K=20,
\]

where d_i is the identifier presented to the model. The table is initialized
with a normal distribution of mean zero and standard deviation (0.02). The
repository comment says that this embedding should not be updated, but the
shown code assigns `requires_grad=False` to the module object rather than
calling it on the embedding weight; whether the table is actually frozen is
therefore an implementation point requiring verification.

Second, a frozen table of 5,000 passage-position vectors is constructed from a
sinusoidal encoding. For position t and dimension index j, the code
uses

\[
P_{t,2j}=\sin\!\left(t\exp\left(-\frac{2j\log 10000}{d}\right)\right),
\qquad
P_{t,2j+1}=\cos\!\left(t\exp\left(-\frac{2j\log 10000}{d}\right)\right),
\]

and then applies L2 normalization across the embedding dimension. The
augmented passage representation is consequently

\[
\widetilde p_i=p_i+E_{\mathrm{doc}}[g(d_i)]+P_{r_i},
\]

where r_i is the passage position extracted from the chunk identifier.
The query vector is not augmented at this stage.

## 3. Hybrid-attention encoder

The model prepends the query to the augmented passage sequence,

\[
X^{(0)}=[q;\widetilde p_1;\ldots;\widetilde p_K].
\]

The configured encoder contains 16 layers with embedding width 768 and eight
heads; the implementation default for the feed-forward hidden width is 2,048.
Each layer first applies layer normalization and sends the normalized sequence
through two independent multi-head attention modules. In either module the
code forms learned linear projections (Q=XW_Q), (K=XW_K), and
(V=XW_V), computes scaled logits

\[
A=\operatorname{softmax}\!\left(\frac{QK^{\mathsf T}}
{\sqrt{d_h}}+M\right)V,
\]

and applies an output projection. Dropout with probability 0.1 is applied to
the attention weights and to the residual branches.

The shared module receives no attention mask, so it can connect every sequence
position. The dedicated module receives an additive mask. In the separate
`rerank` path, a passage row is allowed to attend to the query and to passage
rows carrying the same relative document identifier; all other logits for that
row are set to (-\infty). Thus, for passage rows in the inference path,

\[
M_{ij}=\begin{cases}
0,&j=0\ \text{or}\ d_j=d_i,\\
-\infty,&\text{otherwise}.
\end{cases}
\]

The two attention outputs are added and placed in a residual connection. A
second normalized residual branch applies a linear map to width 2,048, ReLU,
dropout, and a linear map back to width 768. Repeating this block produces
contextualized sequence states, from which the passage states are selected.

The training `forward` path constructs the dedicated mask with row indices
starting at zero, although the query occupies sequence position zero and the
passages occupy positions one through (K). The `rerank` path explicitly adds
the one-position offset. Consequently, the same-document mask equation is
directly supported for inference, while equivalence between training and
inference masks is pending verification.

## 4. Contrastive training objective

For each sample, the code computes a dot product between the original query
vector and every contextualized passage state, then divides the resulting
scores by the configured temperature (tau = 1.0):

\[
s_i=\frac{q^{\mathsf T}h_i}{\tau}.
\]

The training data contract requires exactly one label-1 passage per sample.
With positive index + and negative set N, the per-sample loss
implemented with `logsumexp` is

\[
\mathcal L_i=-s_++\log\left(\exp(s_+)+
\sum_{j\in\mathcal N}\exp(s_j)\right).
\]

The batch loss is the arithmetic mean of these per-sample losses. No query
encoder is defined in the supplied model, and the loss uses the original
input query rather than the encoder's output at the prepended query position;
this is the code-level basis for treating q as the scoring anchor.

The training wrapper uses Adam with learning rate 1e-3 and weight decay
zero. The configured maximum is 20 epochs, with batch size 256 and patience
five for stopping after validation loss ceases to improve. A checkpoint is
written whenever the mean validation loss improves, using a run-name-and-epoch
filename. The training wrapper also reports validation MRR at 10, but no
numeric result is asserted by this code-only candidate.

## 5. Inference and ranking

At inference, the model repeats structural augmentation and the hybrid encoder,
retaining the original query vector for scoring. It divides each query–passage
dot product by the same temperature, sorts the scores in descending order, and
uses the resulting indices to reorder the supplied passage-text list. The
returned object is therefore a ranked list of the retrieved texts together
with their scaled scores. The implementation does not generate text or run a
language-model encoder over the passages during this reranking call.

## 6. Data mixture and evaluation surface

The training preprocessing script constructs training and validation lists by
loading MLDR, SQuAD, and NarrativeQA sources, attaching source labels and
integer IDs. The Chroma construction code stores passage text with chunk
metadata and builds the vector store in batches of 1,000 documents. During
dataset access, the mixed examples are shuffled; when positional augmentation
is enabled, the retrieved passage order is randomly permuted before being
returned to the model while labels, document IDs, passage IDs, and text are
permuted consistently.

The test preprocessing script defines eight named ConTEB data configurations,
including the three training-related domains and five additional domains.
The evaluation wrapper is intended to retrieve passages, embed the query and
documents with the same embedding wrapper, call `rerank`, and report MRR@10
and nDCG@10. However, the shown evaluation function references an undefined
`working_dir` variable when constructing the test vector-store path, and it
expects a checkpoint named `conteb_train_ebcar_best.pt` although the training
wrapper writes improving checkpoints with a different run-name-and-epoch
pattern. A successful end-to-end test evaluation and all numerical quality or
throughput claims therefore remain incomplete from the supplied code.

## 7. Explicitly pending author-intent claims

The following statements are retained as author-intent targets rather than
implementation facts: substantial speedup over text-based LLM rerankers;
competitiveness on cross-passage inference; improved coreference resolution or
local coherence; scalability to unseen documents; stabilization caused by a
fixed query anchor; and superiority of the combined attention pattern over
either attention alone. The code exposes the mechanisms that could be used to
test these hypotheses, but contains no evidence establishing them.
