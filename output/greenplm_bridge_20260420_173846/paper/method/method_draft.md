# Method

## Overview
<!-- c2p: stage=ALL; mechanisms=MECH1,MECH2,MECH3,MECH4; evidence=E5,E4,E6,E7,E8,E9,E10; confidence=high -->
Author-Marker Grounded Method Pipeline is designed to coordinate a method pipeline that establishes projector-language coupling under mostly frozen backbone settings; then expands from simple descriptions to richer instruction/dialog patterns while preserving projector continuity; then uses point-cloud token features and compact token aggregation to transfer prior alignment to 3D inputs; then controls runtime mechanics (trainer save behavior/logging/checkpoint flow). Three-stage training pipeline: Stage I establishes projector-language coupling with frozen backbones using DataCollatorForPointTextDataset; Stage II expands to rich instruction/dialog patterns (evidence missing); Stage III performs point-language transfer using ObjectPointCloudDataset and PointcloudEncoder. Training utilizes Adam optimization with learning rate scheduling, custom training loops (training_step), and LLaVATrainer for checkpoint/saving behavior. Point cloud preprocessing includes fps sampling and knn grouping. The paper-facing method is organized into 4 evidence-backed stages: Stage I: Text-First Interface Warmup, Stage II: Rich Instruction Alignment, Stage III: Point-Language Transfer, and Runtime and saving behavior.

## Evidence-Grounded Pipeline
<!-- c2p: stage=S1; mechanisms=MECH1; evidence=E5; confidence=high -->
**Stage I: Text-First Interface Warmup.** This stage is designed to establish projector-language coupling under mostly frozen backbone settings. It consumes raw point cloud and produces the next stage inputs. The stage uses DataCollatorForPointTextDataset. The data flow links input to DataCollatorForPointTextDataset via forward and DataCollatorForPointTextDataset to output via output.

<!-- c2p: stage=S2; mechanisms=MECH2; evidence=E5; confidence=high -->
**Stage II: Rich Instruction Alignment.** This stage is designed to expand from simple descriptions to richer instruction/dialog patterns while preserving projector continuity. It consumes the previous stage outputs and produces the next stage inputs.

<!-- c2p: stage=S3; mechanisms=MECH3; evidence=E5,E4,E6,E7,E8,E9,E10; confidence=high -->
**Stage III: Point-Language Transfer.** This stage is designed to use point-cloud token features and compact token aggregation to transfer prior alignment to 3D inputs. It consumes the previous stage outputs and produces the next stage inputs. The stage uses PointcloudEncoder for injecting projected point features into language token stream, ObjectPointCloudDataset, and PointNet2ClassificationSSG for compacting point-token aggregation with neighborhood routing. PointcloudEncoder encodes point clouds using transformer-based architecture with grouping and patch dropout, projecting features into the LLM token space and PointNet2ClassificationSSG performs local-to-global aggregation of point features through hierarchical SA modules with neighborhood grouping before LLM conditioning. The data flow links input to PointcloudEncoder via forward, PointcloudEncoder to ObjectPointCloudDataset via forward, and ObjectPointCloudDataset to PointNet2ClassificationSSG via forward.

<!-- c2p: stage=S4; mechanisms=MECH4; evidence=E5; confidence=high -->
**Runtime and saving behavior.** This stage is designed to control runtime mechanics (trainer save behavior/logging/checkpoint flow). It consumes the previous stage outputs and produces the next stage inputs. The stage uses QueryAndGroup and LLaVATrainer. The data flow links input to QueryAndGroup via forward, QueryAndGroup to LLaVATrainer via forward, and LLaVATrainer to output via output.

## Core Components
<!-- c2p: stage=ALL; mechanisms=MECH1,MECH2,MECH3,MECH4; evidence=E5,E4,E6,E7,E8,E9,E10; confidence=high -->
The core method components support the following paper-facing roles: DataCollatorForPointTextDataset, inject projected point features into language token stream, ObjectPointCloudDataset, compact point-token aggregation with neighborhood routing, QueryAndGroup, and LLaVATrainer. Utility and experiment-support modules are not treated as method innovations.

## Method Procedure
<!-- c2p: stage=ALL; mechanisms=MECH1,MECH2,MECH3,MECH4; evidence=E5,E4,E6,E7,E8,E9,E10; confidence=high -->
The method procedure follows the paper-level stage order rather than the raw execution order: Stage I: Text-First Interface Warmup -> Stage II: Rich Instruction Alignment -> Stage III: Point-Language Transfer -> Runtime and saving behavior. This ordering keeps orchestration, setup, and utility behavior separate from the method mechanisms.

## Implementation Notes and Configurable Behavior
<!-- c2p: stage=ALL; mechanisms=MECH1,MECH2,MECH3,MECH4; evidence=E4,E5,E6,E7,E8,E9,E10; confidence=medium -->
An author-highlighted distinguishing mechanism is retained only as an evidence-backed implementation claim: A compact local-to-global aggregation path is used before point features are conditioned into the LLM.

<!-- c2p: stage=ALL; mechanisms=MECH1,MECH2,MECH3,MECH4; evidence=E4,E5,E6,E7,E8,E9,E10; confidence=medium -->
An author-highlighted distinguishing mechanism is retained only as an evidence-backed implementation claim: Compress point-token sequences before LLM fusion to keep useful structure with manageable token cost.
