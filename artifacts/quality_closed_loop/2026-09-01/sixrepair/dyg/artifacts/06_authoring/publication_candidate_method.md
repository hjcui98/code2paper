## Dynamic graph encoding: how interaction sequences are represented with heterogeneous features and aligned

The method extracts first-hop interaction sequences for source and destination nodes, encoding each sequence with heterogeneous signals comprising node identity, edge identity, absolute temporal position, and co-occurrence information. These sequences are padded to a uniform maximum length $L_{max}$ using a specified patch size $p$, and the resulting heterogeneous features are stacked along dimension 2 to form a unified tensor representation that aligns all encoding types into a common dimensional space $$
\begin{aligned} \mathbf{S}_{src} &= \text{Pad}(\mathbf{N}_{src}, \mathbf{T}_{int}, \mathbf{N}_{nbr}, \mathbf{E}_{nbr}, \mathbf{T}_{nbr}; p, L_{max}) \\ \mathbf{S}_{dst} &= \text{Pad}(\mathbf{N}_{dst}, \mathbf{T}_{int}, \mathbf{N}_{nbr}, \mathbf{E}_{nbr}, \mathbf{T}_{nbr}; p, L_{max}) \\ \mathbf{X}_{src} &= \text{Stack}(\mathbf{S}_{src}; \text{dim}=2) \in \mathbb{R}^{B \times L_{src} \times (C \times d_c)} \\ \mathbf{X}_{dst} &= \text{Stack}(\mathbf{S}_{dst}; \text{dim}=2) \in \mathbb{R}^{B \times L_{dst} \times (C \times d_c)} \end{aligned}
$$. The unified tensor is then routed through a continuous-state-space module, with routing weights normalized via softmax and the top-$k$ destination embeddings selected to produce the final source and destination node embeddings.

## Motivation: limitations of vanilla SSMs – they ignore irregular timespans and are vulnerable to input noise

Vanilla SSMs assume inputs are sampled on a uniform temporal grid, leaving them unable to account for irregular timespans between consecutive observations. This uniform-sampling assumption further renders them vulnerable to input noise, as perturbations in the input sequence propagate directly through the recurrent dynamics.

## Redesign: timespan-informed Δt and A for temporally aware forgetting

The state-space model's forgetting mechanism is made temporally aware by expressing the discrete-time step $Δt$ as a function $f_{\text{time}}$ of the elapsed timespan $τ$ between each historical interaction and the prediction time, so that states corresponding to older interactions are attenuated more aggressively. For a target node, the ordered first-hop neighbor events up to the prediction timestamp are extracted as the interaction sequence, and each node is encoded using its raw features, with zero vectors substituted when features are unavailable. Absolute timespans from each interaction to the prediction time are encoded via a trainable cosine-based function, producing the temporal signal that drives the timespan-informed $Δt$. The continuous-time matrix $A_0$ is initialized for stable decay, and the input and output matrices $B_{\text{spec}}$ and $C_{\text{spec}}$ are redefined under spectral norm constraints so that the selective reviewing operation is invariant to the scale of projected features. $$
\Delta t = f_{\text{time}}(\tau), \quad A = A_0, \quad B = B_{\text{spec}}, \quad C = C_{\text{spec}}
$$

Structural similarity between the target node and each historical neighbor is captured by encoding the co-occurrence frequency of shared neighbors, providing a relational signal that complements the temporal encoding. The timespan-informed $Δt$ and the diagonal initialization of $A$ with strictly negative real-part eigenvalues ensure that the hidden state decays exponentially over elapsed time, with the decay rate modulated by $Δt_i$ for each interaction. The redefinition of $B$ and $C$ under spectral norm constraints acts as a robustness mechanism, rendering the selective writing and reading operations invariant to the scale of projected features and thereby enabling stable selective reviewing. $$
\begin{aligned} \Delta t_i &= \sigma\left( w_{\Delta t} \cdot \phi(\tau_i) \right), \quad \tau_i = t_{\text{pred}} - t_i \\ A &= \text{diag}(\lambda_1, \dots, \lambda_n), \quad \text{Re}(\lambda_j) < 0 \forall j \\ B_i &= \frac{B_i^{\text{raw}}}{\|B_i^{\text{raw}}\|_2}, \quad C_i = \frac{C_i^{\text{raw}}}{\|C_i^{\text{raw}}\|_2} \end{aligned}
$$

## Downstream adaptation: link prediction and node classification setups, plus a note on linear computational complexity

For downstream prediction, fixed-size node embeddings are read out from the sequential output and passed to a task-specific predictor. Edge features are encoded as raw feature vectors, with zero vectors substituted when no edge features are available. The readout applies mean pooling over the sequence dimension, followed by a multi-layer perceptron that produces link probabilities or node-classification scores. For link prediction, the predictor consumes edge memories indexed by directed pairs $(src_{node}, dst_{node})$ in edge_memories together with a tuple of positive and negative edges. The SSM step size $t$ is set directly to the irregular timespan between consecutive interactions, preserving linear computational complexity in the sequence length.

## Robust selective reviewing

The DyG-Mamba SSM core implements a continuous state space model in which the step size $Δt$ is redefined as timespan-dependent and the state matrix $A$ is initialized with a stable diagonal structure, enabling input-dependent filtering of historical information so that important interactions are reinforced and noise is suppressed. When the temporal Mamba pathway is active and a non-null timespan is supplied, the input projection weight and bias are applied to the hidden states before routing them through the selective recurrence, and the resulting hidden states are returned as the output of the selective review stage.

To implement timespan-aware forgetting and noise-robust reviewing, the B and C matrices are made input-dependent and the spectral norm constraints $∥W_B∥_2 ≤ 1$ and $∥W_C∥_2 ≤ 1$ are enforced on their respective weight matrices $$
\begin{aligned}
& \text{Input-dependent B/C:} \quad B_t = W_B x_t, \quad C_t = W_C x_t \\
& \text{Spectral Norm Constraints:} \quad \|W_B\|_2 \le 1, \quad \|W_C\|_2 \le 1
\end{aligned}
$$.