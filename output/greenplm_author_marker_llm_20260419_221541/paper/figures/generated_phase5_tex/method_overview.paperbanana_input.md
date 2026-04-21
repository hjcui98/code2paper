Create a paper-ready method overview figure from the following method draft.

Figure requirements:
- Use the method draft as the primary source.
- Show the paper-level method stages and the main mechanism flow.
- Prefer a left-to-right or top-to-bottom pipeline with concise node labels.
- Do not add claims that are not present in the draft.
- Keep utility or experiment-support details out of the main visual flow.
- Include only labels that can be traced to the draft text.

Detected draft sections:
- Stage I: Text-First Interface Warmup
- Stage II: Rich Instruction Alignment
- Stage III: Point-Language Transfer
- Mechanism Design
- Runtime and Saving Behavior

Optional audit context:
method_evidence={"method_name": "Author-Marker Grounded Method Pipeline", "stage_names": ["Stage I: Text-First Interface Warmup", "Stage Ii: Rich Instruction Alignment", "Stage Iii: Point-Language Transfer", "Runtime And Saving Behavior"], "mechanism_count": 4}
claim_map={"claims": 57, "supported_or_partial": 57}

Method draft:
\section{Method}\label{sec:method}

Our approach implements a progressive three-stage alignment pipeline---\textbf{Stage~I: Text-First Interface Warmup}, \textbf{Stage~II: Rich Instruction Alignment}, and \textbf{Stage~III: Point-Language Transfer}---designed to ground a frozen large language model (LLM) in 3D point-cloud understanding while minimizing reliance on scarce 3D-text paired data. A unified projection interface bridges the modality gap throughout all stages, with training orchestration handled by a custom trainer to ensure stable stage transitions and reproducible checkpointing.

\subsection{Stage I: Text-First Interface Warmup}\label{subsec:stage1}

Stage~I establishes the initial coupling between the multimodal projector and the LLM using caption-style text supervision while maintaining both the vision and language backbones in a frozen state. The \texttt{build\_vision\_projector} module (\texttt{llava/model/multimodal\_projector/builder.py}) implements a position-wise feed-forward transformation $\mathrm{FFN}(x)=\sigma(xW_1+b_1)W_2+b_2$ with nonlinear activation and layer normalization (via \texttt{SimpleResBlock} and \texttt{Mlp} sub-mechanisms) to map inputs into the LLM's hidden space. By consuming description-style annotations through the \texttt{ObjectPointCloudDataset} loader, this stage yields a stable projector initialization that aligns the token distribution with the language model's embedding space prior to introducing any 3D data.

\subsection{Stage II: Rich Instruction Alignment}\label{subsec:stage2}

Stage~II expands the supervision signal from simple captions to richer instruction-following and multi-turn dialog patterns, preserving the projector's continuity with the text-conditioned interface established in Stage~I. The dataset layer provides diverse conversation formats---including \texttt{detailed\_description}, \texttt{single\_round}, and \texttt{multi\_round} exchanges---while the training loop maintains frozen backbone constraints. This progression refines the projector's capacity to handle complex linguistic structures without disrupting the initial alignment, effectively preparing the interface for multimodal inputs while keeping the core LLM parameters static.

\subsection{Stage III: Point-Language Transfer}\label{subsec:stage3}

Stage~III activates the 3D pathway by ingesting point-cloud samples alongside conversational supervision pairs, leveraging compact token aggregation to manage computational costs within the LLM context window. Raw point clouds are processed by the \texttt{PointcloudEncoder} (\texttt{llava/model/multimodal\_encoder/point\_encoder.py}), which applies position-wise transformations with dropout regularization. The \texttt{skeleton\_Group} aggregation module compresses the point set into a compact token sequence via local-to-global neighborhood routing (configured with \texttt{num\_group=32} and \texttt{group\_size=8}). These aggregated features are projected through the shared \texttt{build\_vision\_projector} and injected into the LLM's token stream via \texttt{PointLLMLlamaModel.forward}, enabling the generation of 3D-grounded language responses while the LLM backbone remains frozen.

\subsection{Mechanism Design}\label{subsec:mechanism}

The architectural approach centers on a \textbf{persistent projection bottleneck} that remains consistent across all training stages, ensuring stable modality transfer without requiring backbone fine-tuning. The projector comprises feed-forward blocks with layer normalization, specifically utilizing \texttt{SimpleResBlock} and \texttt{Mlp} components that implement the transformation $\mathrm{FFN}(x)=\sigma(xW_1+b_1)W_2+b_2$. For 3D inputs, the method employs parameter-efficient aggregation: the \texttt{skeleton\_Group} operator partitions point clouds into 32 local neighborhoods (group size 8) before encoding, significantly compressing the spatial input dimensionality. This compact representation is mapped to the LLM's embedding space through the pre-aligned projector, allowing the frozen language model to interpret 3D structural information through a text-aligned interface.

\subsection{Runtime and Saving Behavior}\label{subsec:runtime}

Training mechanics are managed by the \texttt{PointLLMTrainer} class, which orchestrates distributed training state, checkpoint serialization, and logging across all stages. The trainer implements custom save logic that collects model state dictionaries and persists them to disk, handling mixed-precision states and FSDP constraints. This infrastructure ensures reproducible stage transitions and reliable artifact generation throughout the progressive alignment pipeline.
