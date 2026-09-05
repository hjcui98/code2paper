## Motivation: limitations of vanilla SSMs – they ignore irregular timespans and are vulnerable to input noise

Standard SSM step operations—fused add and norm applied to hidden states with learned weight, bias, and epsilon parameters, followed by convolutional state and SSM output computation—assume a uniform sampling grid over the input sequence. This assumption renders them insensitive to irregular timespans between observations, and the absence of an explicit noise-robustness mechanism makes the hidden-state trajectory vulnerable to input perturbation.

## Dynamic graph encoding: how interaction sequences are represented with heterogeneous features and aligned

The dynamic graph encoder transforms raw interaction sequences into a unified, aligned feature representation that captures temporal and structural context. Router logits are normalized via softmax to produce routing weights, from which a top-k subset is selected to form the selected embeddings; the number of channels is computed from the channel embedding dimension. The encoder returns source and destination node embeddings as its output.

## Redesign: timespan-informed Δt and A for temporally aware forgetting

The redesigned SSM encodes a node's first-hop interaction sequence by passing aligned node, edge, absolute temporal, and co-occurrence signals through a continuous-state recurrence whose step size $Δt_i$ is a learnable, monotonically increasing function of the inter-event time gap $τ_i$ and whose state-transition matrix $A$ is initialized as a diagonal matrix with negative real-part eigenvalues to ensure stable decay. $$
h_{i} = \exp(\Delta t_i A) h_{i-1} + \Delta t_i B_i x_i, \quad y_i = C_i h_i + D x_i
$$ In this expression, $h_i$ is the hidden state at step $i$, $x_i$ is the input element, $y_i$ is the output, $B_i$ and $C_i$ are input-dependent matrices redefined with spectral norm constraints, and $D$ is the skip-connection matrix. The term $e^{Δt_i A}$ governs the forgetting of historical states proportionally to the elapsed time, while $Δt_i B_i x_i$ represents the input-dependent update that enables temporally aware selective reviewing.

## Downstream adaptation: link prediction and node classification setups

Downstream tasks consume fixed-size node embeddings produced by a readout function applied to the sequential output of the encoder. For a target node, the interaction sequence is extracted as the ordered list of first-hop neighbor events up to a prediction timestamp, with each event carrying raw node and edge features; when a feature vector is unavailable, a zero vector is substituted. In the case-study protocol, a neighbor sampler retrieves all first-hop neighbors for the destination node set, and an edge bank with unlimited memory stores historical source-node records so that a query pair is resolved by checking whether the pair appears in the stored edge memories. The readout function maps the encoded sequence to a fixed-size embedding suitable for link prediction (by comparing embeddings of two candidate nodes) or node classification (by applying a classifier to a single embedding); in the case-study protocol the procedure returns both the source and destination node embeddings for downstream scoring.

The node embedding $h_u^t$ at prediction time $t$ is obtained by applying a readout function to the sequential encoding of the interaction history: $$
\mathbf{h}_{u}^{t} = \text{ReadOut}\left( \text{SeqEnc}\left( \{ (\mathbf{x}_{v}, \mathbf{e}_{uv}, \Delta t_{uv}) \}_{v \in \mathcal{N}_{u}^{t}} \right) \right)
$$ Here $h_u^t$ denotes the fixed-size embedding for node $u$ at time $t$, $N_u^t$ is the set of first-hop neighbors of $u$ up to time $t$, $x_v$ and $e_{uv}$ are the raw node and edge features, and $t_{uv}$ is the timespan from the interaction to the prediction time. The timespan is encoded via a trainable cosine-based function that captures the absolute temporal offset between each historical interaction and the query time. In addition, a co-occurrence frequency encoding captures structural similarity by representing the number of shared neighbors between the target node and each historical neighbor; in the case-study protocol this feature is concatenated with the source-node embedding when the interaction index is zero.

## Robust selective reviewing

The selective reviewing mechanism performs input-dependent filtering over historical information, reinforcing salient interactions while suppressing noise. Stability of this filtering is maintained by constraining the spectral norm of the reviewing transformation $W_{\text{review}}$ so that it does not exceed a positive scalar bound $\text{rho}$, where $\text{W}_{\text{review}}$ denotes the weight matrix or transformation operator associated with the selective reviewing module, $|\text{cdot}|_2$ denotes the spectral norm (maximum singular value), and $\text{rho}$ is the stability threshold. $$
\|W_{\text{review}}\|_2 \le \rho
$$ This constraint ensures that the selective review process does not amplify errors or signals beyond a stable range.