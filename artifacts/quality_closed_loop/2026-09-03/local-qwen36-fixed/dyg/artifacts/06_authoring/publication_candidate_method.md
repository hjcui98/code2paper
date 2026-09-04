## Motivation: limitations of vanilla SSMs – they ignore irregular timespans and are vulnerable to input noise

The transformation applies fused add norm hidden states with weight bias eps to process the input sequence. Subsequently, the method uses step hidden states conv state ssm out to generate the final output representation.

## Dynamic graph encoding: how interaction sequences are represented with heterogeneous features and aligned

Dynamic graph encoding transforms raw interaction sequences into a unified, aligned feature representation that captures temporal and structural context. This mechanism normalizes softmax dst router logits across dimension 1 to yield floating-point routing weights, and it computes the product of the number of channels and the channel embedding dimension. The process selects the top-k dst routing weights, bounded by the minimum of the top sequence length and the selected embedding size, to aggregate contextual signals. Finally, the procedure returns the source node embedding alongside the destination representation, though the precise initialization of the diagonal matrix with strictly negative real-part eigenvalues remains to be formally established.

## Redesign: timespan-informed Δt and A for temporally aware forgetting

The first-hop interaction sequence of a node is extracted and encoded using node, edge, absolute temporal, and co-occurrence signals. A timespan-aware state-space model is introduced to allow the system to forget historical states proportionally to the elapsed time. This behavior is realized by formulating the discrete-time step Δt as a function of the timespan and initializing the transition matrix A to ensure stable decay. The projection and output matrices are redefined with spectral norm constraints to support robust selective reviewing. Because the precise mathematical formulation of the timespan-informed Δt and A remains under formalization, the exact decay dynamics are currently specified through these structural redesign principles rather than closed-form expressions.

## Downstream adaptation: link prediction and node classification setups

For downstream adaptation, the framework reads fixed-size node embeddings from the sequential output to generate task-specific predictions for link prediction and node classification. Interaction sequences are constructed by extracting ordered first-hop neighbor events for each target node up to the prediction timestamp. Node and edge encodings rely on raw feature representations, substituting zero vectors when specific attributes are unavailable. This extraction process maintains linear computational complexity with respect to the number of interactions, enabling efficient scaling across large dynamic graphs.

Absolute temporal encoding captures the timespan between each historical interaction and the prediction time through a trainable cosine-based function. Concurrently, co-occurrence frequency encoding models structural similarity by quantifying the frequency of shared neighbors between the target node and each historical neighbor. These encoding mechanisms integrate temporal dynamics and topological context to refine the downstream prediction signals.

## Robust selective reviewing

Robust selective reviewing enables input-dependent filtering of historical information, reinforcing important interactions while suppressing noise. This mechanism maintains stability through spectral norm constraints, ensuring that the model focuses on relevant contextual signals without overfitting to irrelevant historical data.