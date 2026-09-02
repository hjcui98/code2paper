# Method: DyG-Mamba (blind code-to-method baseline)

This candidate is reconstructed from the supplied author-intent YAML and the
DyG-Mamba source tree only. The intent determines the topics and order below;
implementation statements are restricted to operations visible in the code.
No performance, superiority, robustness, or theoretical guarantee is asserted
without an execution artifact or a code-level invariant.

## 1. Problem setting and historical sequence

The implementation operates on timestamped interactions represented by source
node, destination node, edge identifier, interaction time, and raw node and
edge feature arrays. For a target node `v` and prediction time `t`, the
neighbor sampler returns the first-hop interactions whose timestamps are
strictly before `t`. The returned interactions are kept in increasing time
order. In the DyG-Mamba forward path, all such first-hop interactions are
retrieved from the selected graph sampler; if there are more than
`max_input_sequence_length - 1`, the most recent interactions are retained.

The target node is prepended at position zero, with its timestamp set to `t`
and its edge identifier set to zero. The remaining positions contain the
historical neighbors and are zero-padded to the largest sequence length in the
batch. Although a patch-size argument exists in the entry points, the model
constructor assigns `self.patch_size = 1`, so the executable DyG-Mamba path
does not form larger patches. Thus a source and a destination are converted
into two temporally ordered sequences before the neural encoder is called.
During link-prediction training the backbone is
attached to the training-graph sampler; evaluation switches it to the full
graph sampler.

## 2. Four-channel dynamic-graph encoding

For each sequence position, the code gathers a raw node feature and a raw edge
feature by indexing the corresponding feature arrays. Padding uses index zero;
the temporal feature at padded positions is explicitly set to zero. The
feature dimensions are projected independently to a common channel dimension
`c`, and the four resulting channels are stacked and reshaped into a vector
of dimension `D = 4c`.

The first temporal channel encodes the elapsed time from the interaction to the
prediction time. If `delta_i = t - t_i`, the implemented time encoder has the
form

`e_i = cos(W delta_i + b)`.

Its weights are trainable, initialized from inverse powers of ten, and its
bias is initialized to zero. The default command-line time-feature dimension
is 100. This channel is projected with the same type of linear projection as
the node, edge, and co-occurrence channels.

The co-occurrence encoder computes, for every non-padding position, two counts:
the number of appearances of that node in its own sequence and the number of
appearances in the other sequence. Each scalar count is passed through a
linear-ReLU-linear network, and the two encoded values are summed. This gives
the source and destination sequences a lightweight pairwise structural signal
before channel alignment.

In addition to the four input channels, the code constructs a separate control
sequence for the state-space step. Let `s` be the difference between the
current-time entry at position zero and the oldest retained timestamp at
position one, plus `1e-6`. The code forms

`r_j = clip(insert(diff(times), first_value=1), 0, max(s)) / s + 1 / L`.

Here `L` is the padded sequence length used by the implementation. The values
`r_j` are passed through a second trainable cosine time encoder (with beta
equal to 0.9) and a linear projection to dimension `D`. This projected
sequence is supplied to every Mamba layer as `dts`.

## 3. Timespan-conditioned Mamba backbone

The aligned sequence has shape `[batch, length, D]` and is processed by one
`MambaEncoder` object. The training entry points set the Mamba state dimension,
convolution width, and expansion factor from command-line arguments; their
defaults are `d_state = 16`, `d_conv = 4`, and `expand = 2`. The DyG-Mamba
configuration sets two Mamba layers, while the dataset-specific loader may
change the maximum sequence length and number of epochs. With the default
channel size `c = 50`, the model width is `D = 200` and the expanded inner
width is 400.

Each block adds the residual stream, applies LayerNorm (unless the configured
RMS/fused variant is selected), and applies `MambaTimeDelta`. The encoder then
applies a final normalization. Inside the custom mixer, the input is projected
to an inner state and gate, processed by a depthwise causal convolution and a
SiLU activation, and mapped to the state-space parameters. The scan is invoked
as a selective scan with a learned skip parameter `D_skip`.

The transition parameter is computed in the forward pass as

`A = -exp(A_log)`.

`A_log` is initialized with `log(1), ..., log(d_state)` for each inner channel
and remains a trainable parameter. Consequently, the initialization produces
negative diagonal entries in the implemented parameterization. The code does
not impose a post-update projection or other check that would establish a
strictly negative spectrum after training.

The time-control path is also narrower than the intent description. The
training scripts pass only `d_state`, `d_conv`, and `expand` in `ssm_cfg`; they
do not enable the optional `time_mamba` flag, whose default is false. In this
configuration, `B` and `C` are obtained from the current convolved hidden
input through `x_proj`, whereas the scan step `dt` is generated from the
projected `dts` sequence through `dt_generate_layer` and `dt_proj`, followed by
the scan's softplus handling. The source tree contains no spectral-normalization
operation or explicit constraints of the form `||W_B||_2 <= 1` or
`||W_C||_2 <= 1`. It therefore implements a time-conditioned step input, but
does not establish the intended monotonicity, Ebbinghaus law, Lipschitz bound,
or noise-robustness guarantee.

## 4. Pair interaction and readout

The same `MambaEncoder` object is applied to the source and destination
sequences. After the two sequential outputs are produced, a cross-linear
attention layer is applied in both directions: the source queries the
destination output, and the destination then queries the updated source
output. The attention uses softmax-normalized queries and keys, an einsum
context contraction, an output projection, dropout, and a residual LayerNorm.

The sequence readout is a learned router rather than mean pooling. Separate
source and destination linear gates produce one logit per position. Softmax
weights are computed over the sequence, the largest at most 64 positions are
selected, their weights are renormalized, and the weighted sums are passed
through a shared linear output layer to return node embeddings. Noise-logit
layers are declared in the class, but their use is commented out in the
forward path. Thus the executable link-prediction path uses one shared
backbone, cross-sequence mixing, and gated top-k pooling.

## 5. Downstream tasks and optimization

For link prediction, the two output embeddings are concatenated and passed to
`MergeLayer`: a linear layer, ReLU, and a second linear layer produce one logit.
The training loop computes a sigmoid probability for one positive and one
sampled negative pair per batch item, concatenates their labels, and optimizes
binary cross-entropy. The evaluation helper reports average precision and
ROC-AUC for the concatenated positive/negative predictions. Negative sampling can
be random, historical, or inductive according to the command-line setting.

For node classification, the script wraps the same dynamic backbone with an
MLP classifier whose dimensions are `input_dim -> 80 -> 10 -> 1`, with ReLU
and dropout between the hidden layers. The backbone is placed in evaluation
mode and called under `no_grad`; only the classifier is passed to the
optimizer. The script uses the source embedding returned by the pair-embedding
function, applies a sigmoid, and trains with binary cross-entropy. The visible
node-classification path therefore does not implement a separate
single-sequence, no-co-occurrence variant: it calls the same source/destination
embedding routine, which includes co-occurrence encoding and cross attention.

The data loader pads raw node and edge features to dimension 172. The default
split ratios are 0.15 for validation and 0.15 for testing. Link prediction
also constructs an inductive split by removing edges involving a randomly
selected set of test-time nodes from the training graph. The training scripts
use Adam by default with learning rate `1e-4`, zero weight decay, and an
early-stopping checkpoint mechanism. These code paths define an experimental
procedure, but this blind run produced no metric artifact, so no numerical
effect or comparison is claimed here.

## 6. Author-intent items that remain unverified

The supplied intent proposes a monotonic, forgetting-curve-inspired mapping
from elapsed time to `Delta t`, a stability guarantee from a negative spectrum,
spectral-norm constraints on `B` and `C`, selective historical review with
noise suppression, independent source and destination encoders, mean pooling,
linear-complexity justification, and improvements over standard SSMs. The
code directly supports neither the corresponding guarantees nor the claimed
effects. In particular, the executable configuration contradicts independent
encoders and mean pooling, and it does not contain the proposed spectral-norm
constraints. These statements must remain pending or incomplete until a
separate, authorized execution artifact or an implementation change supplies
the missing evidence.
