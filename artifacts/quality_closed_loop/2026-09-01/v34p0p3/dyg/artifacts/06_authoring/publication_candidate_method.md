## Dynamic graph encoding: how interaction sequences are represented with heterogeneous features and aligned

First-hop interaction sequences for source and destination nodes are extracted and encoded using node, edge, absolute temporal, and co-occurrence signals, transforming raw interaction records into a unified feature representation that captures temporal and structural context. The sequences are padded to a maximum length $L_{max}$ using a specified patch size $p$, after which the heterogeneous features (node, edge, temporal, co-occurrence) are stacked along dimension 2 to form a unified tensor. $$
\begin{aligned} \mathbf{S}_{src} &= \text{Pad}(\mathbf{N}_{src}, \mathbf{T}_{int}, \mathbf{N}_{nbr}, \mathbf{E}_{nbr}, \mathbf{T}_{nbr}; p, L_{max}) \\ \mathbf{S}_{dst} &= \text{Pad}(\mathbf{N}_{dst}, \mathbf{T}_{int}, \mathbf{N}_{nbr}, \mathbf{E}_{nbr}, \mathbf{T}_{nbr}; p, L_{max}) \\ \mathbf{X}_{src} &= \text{Stack}(\mathbf{S}_{src}; \text{dim}=2) \in \mathbb{R}^{B \times L_{src} \times (C \times d_c)} \\ \mathbf{X}_{dst} &= \text{Stack}(\mathbf{S}_{dst}; \text{dim}=2) \in \mathbb{R}^{B \times L_{dst} \times (C \times d_c)} \end{aligned}
$$ In this expression, $B$ denotes the batch size, $L_{src}$ and $L_{dst}$ the source and destination sequence lengths, $C$ the number of channels, and $d_c$ the channel embedding dimension; the stacked tensors $X_{src}$ and $X_{dst}$ each have shape $(B, L, C, d_c)$. All encoding types are projected to a common dimension and concatenated to yield aligned node embeddings for downstream use.

## Motivation: limitations of vanilla SSMs – they ignore irregular timespans and are vulnerable to input noise

Vanilla SSMs assume inputs are sampled on a uniform temporal grid, leaving them unable to account for irregular timespans between consecutive observations. This uniform-sampling assumption further renders them vulnerable to input noise, as perturbations in the input sequence propagate directly through the recurrent dynamics.

## Redesign: timespan-informed Δt and A for temporally aware forgetting

The discrete-time step is reformulated as a function of the absolute timespan, decoupling the forgetting rate from the input sequence length so that older states are attenuated more aggressively as the elapsed interval grows. The state-transition matrix is initialized as a diagonal matrix whose eigenvalues have strictly negative real parts, guaranteeing exponential decay of the hidden state without divergence. The input and output projection matrices are redefined under a spectral-norm constraint that renders the selective read–write mechanism invariant to the scale of the projected features, thereby supporting robust selective reviewing of historical data. $$
\Delta t = f_{\text{time}}(\tau), \quad A = A_0, \quad B = B_{\text{spec}}, \quad C = C_{\text{spec}}
$$

Structural similarity between the target node and each historical neighbor is captured through a co-occurrence frequency encoding that counts shared neighbors, providing a scale-free measure of how strongly two nodes are embedded in the same local subgraph. The timespan-informed step and the diagonal initialization with strictly negative real-part eigenvalues together realize temporally aware forgetting: the decay rate of the hidden state is modulated by the elapsed timespan, so that older observations are progressively suppressed. The spectral-norm redefinition of the input and output projection matrices constrains the selective mechanism so that the amount of input written to state and the amount of state read out remain invariant to feature scale, enabling stable and robust selective reviewing across heterogeneous historical sequences. $$
\begin{aligned} \Delta t_i &= \sigma\left( w_{\Delta t} \cdot \phi(\tau_i) \right), \quad \tau_i = t_{\text{pred}} - t_i \\ A &= \text{diag}(\lambda_1, \dots, \lambda_n), \quad \text{Re}(\lambda_j) < 0 \forall j \\ B_i &= \frac{B_i^{\text{raw}}}{\|B_i^{\text{raw}}\|_2}, \quad C_i = \frac{C_i^{\text{raw}}}{\|C_i^{\text{raw}}\|_2} \end{aligned}
$$

## Downstream adaptation: link prediction and node classification setups, plus a note on linear computational complexity

Downstream adaptation reads out fixed-size node embeddings from the sequential output and produces task-specific predictions for link prediction or node classification. Edge encoding uses raw edge features, substituting zero vectors when unavailable, and the readout applies mean pooling over the sequence dimension followed by a multi-layer perceptron. The SSM step size is directly coupled to the irregular timespans between interactions, so that temporal irregularity is absorbed into the recurrent dynamics rather than handled by a separate temporal encoder. The model maintains an edge memory that records an unlimited-memory history of source and destination node identifiers; when (src_node_id, dst_node_id) in edge_memories, the predictor returns a probability array over the edge tuple, whereas absent pairs fall through to the standard link-prediction path. The resulting per-interaction cost is linear in the sequence length, preserving the linear computational complexity of the underlying SSM recurrence.

## Robust selective reviewing

The DyG-Mamba selective review mechanism operates on a continuous state space model whose discretization step size Δt is redefined as a function of the timespan between consecutive interactions, replacing the uniform-step assumption of standard Mamba. The system matrix A is initialized as a stable diagonal, and the hidden state is computed from the input tensor through a linear projection whose weights mediate selective filtering of historical information. ### DyG-Mamba SSM Core: Continuous State Space Model with Redefined $\Delta t$ and Stable Diagonal Initialization

The DyG-Mamba architecture realizes a continuous state space model (SSM) by discretizing the continuous-time dynamics using a timespan-dependent step size $\Delta t_k$. The core mechanism is defined by the following equations:

$$
\begin{aligned}
&\text{Continuous SSM:} \quad \dot{h}(t) = A h(t) + B(t) x(t), \quad y(t) = C(t) h(t) \\
&\text{Discretization:} \quad h_{k+1} = \bar{A} h_k + \bar{B} x_k, \quad \bar{A} = e^{A \Delta t_k}, \quad \bar{B} = \left( \int_0^{\Delta t_k} e^{A \tau} d\tau \right) B(t_k) \\
&\text{Timespan-dependent step:} \quad \Delta t_k = f(\Delta t_{\text{span}, k}) \\
&\text{Stable diagonal init:} \quad A = \text{diag}(a_1, \dots, a_N), \quad a_i \le 0 \\
&\text{Spectral norm constraint:} \quad \|W_B\|_2 \le 1, \quad \|W_C\|_2 \le 1
\end{aligned}
$$

**Symbol Definitions:**
* $h(t)$: Continuous hidden state.
* $A$: State transition matrix, initialized as a stable diagonal matrix with non-positive eigenvalues ($a_i \le 0$) to ensure decay.
* $B(t), C(t)$: Input and output matrices, which are input-dependent in the selective SSM variant.
* $\Delta t_k$: Discrete step size, redefined as a function $f$ of the timespan $\Delta t_{\text{span}, k}$ to account for temporal gaps in dynamic graphs.
* $\bar{A}, \bar{B}$: Discretized state transition and input matrices.
* $W_B, W_C$: Weight matrices associated with the input-dependent generation of $B$ and $C$.

**Assumptions:**
1. The system is linear time-invariant in the continuous domain but time-varying in the discrete selective domain.
2. Stability is maintained by constraining the spectral norms of the input-dependent weight matrices $W_B$ and $W_C$ to be less than or equal to 1.
3. The diagonal initialization of $A$ ensures that the base system is stable before input-dependent modulation. The input-dependent matrices B and C are constrained by spectral norm bounds to ensure that reinforced interactions remain numerically stable while noise is suppressed.

The input-dependent matrices B and C implement timespan-aware forgetting and noise-robust reviewing by making the state transition and output projection functions of the input, with their weight matrices constrained so that ∥W_B∥₂ ≤ 1 and ∥W_C∥₂ ≤ 1. $$
\begin{aligned}
& \text{Input-dependent B/C:} \quad B_t = W_B x_t, \quad C_t = W_C x_t \\
& \text{Spectral Norm Constraints:} \quad \|W_B\|_2 \le 1, \quad \|W_C\|_2 \le 1
\end{aligned}
$$