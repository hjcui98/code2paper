# K01 · 严格注册读取与完整来源身份（窗口一交付证据）

> 2026-09-29 · owned paths：`src/code2paper/agentic/authoring_artifact_registry.py`、
> `tests/regression_20260917/test_artifact_registry.py`、
> `src/code2paper/agentic/authoring_execution_identity.py`（仅 `VALIDATOR_BUNDLE_SOURCES`）、
> 本文件。阶段命令/日志矩阵见 [kernel_stage_evidence.md](kernel_stage_evidence.md)。

## 1. 修前的两个缺陷（可复核）

1. **加载 validator 会重封摘要。** `load_artifact_registry` 只做
   `ArtifactRegistryV1.model_validate(payload)`，而模型的 `@model_validator(mode="after")`
   会**重算** `content_digest`。于是指针里的注册行被改过（例如 `producer`/`upstream_refs`）
   但声明摘要未改时，加载既不报错也不保留原声明值——损坏值被"重新封印"成合法值。
2. **registration ID 未绑定完整来源。** `registration_id` 的 identity 只含
   role/phase/generation/path/字节与语义摘要，**不含** `producer`/`upstream_refs`/
   `artifact_schema_version`。同一 ID 可以携带不同来源元数据（丢 provenance 也能换来同 ID），
   且没有"同 ID 不同来源"的拒绝路径。

## 2. 修后的合同

| 合同 | 实现 | 具名失败 |
|---|---|---|
| 创建封摘要 / 加载验摘要分离 | 创建时 `ArtifactRegistrationV1` 的 validator 封 `content_digest`；加载时先比较**声明值**与由**声明字段**重算的值，再落到模型（模型的复算值必须等于声明值） | `artifact_registry_unsealed:*`、`artifact_registry_digest_mismatch:*` |
| 加载核对磁盘不可变 record | 按声明摘要定位 `registration.<role>.<phase>.g<N>.<token>.json`，逐条比较逻辑内容；record 自带摘要也必须自洽 | `artifact_registry_record_missing:*`、`..._record_unreadable:*`、`..._record_digest_mismatch:*`、`..._record_mismatch:*`、`..._record_invalid:*` |
| pointer / schema 核对 | 指针 schema 必须是 `2.0`、指针自身封摘要自洽、`active` 不得悬空 | `artifact_registry_schema_version:*`、`artifact_registry_unsealed:pointer`、`artifact_registry_active_dangling:*` |
| 完整来源身份 | identity 覆盖 producer / upstream_refs / 完整逻辑内容（`registration_logical_digest`） | — |
| 同完整内容幂等 | 同逻辑内容重复注册**返回原 record**（不新增 generation、不改写字节），显式 generation 亦然 | `artifact_registration_conflict:*`（同路径不同内容） |
| 同 ID 不同来源拒绝 | 注册时与加载时都拒绝同一 `registration_id` 对应不同逻辑内容 | `artifact_registry_id_conflict:*` |
| 旧记录具名只读 | 旧 `1.0` 指针严格 reader 拒绝；具名 `load_legacy_artifact_registry` 只读打开（校验但不迁移、不重写、不重封） | `artifact_registry_legacy_requires_named_reader:1.0`、`artifact_registry_not_legacy:*` |
| validator 来源清单 | `authoring_artifact_registry.py` 加入 `VALIDATOR_BUNDLE_SOURCES`（仅本任务已落地的裁决文件；共享文件写权按 LEAD 串行分配） | 缺来源 → `validator_source_missing` |

## 3. AT-K01 → 反例 → 节点

| AT 条款 | 反例（构造方式） | 节点 | 结果 |
|---|---|---|---|
| 篡改 upstream/producer 而保留声明摘要 → 失败 | 改指针注册行 `producer`；改磁盘 record 的 `upstream_refs` | `test_k01_tampered_producer_or_upstream_with_kept_digest_is_rejected` | `digest_mismatch` / `record_digest_mismatch`，**不重封** |
| 删 record → 失败 | 删除 `registration.*.json` | `test_k01_deleted_immutable_record_is_rejected` | `record_missing` |
| pointer 替换 → 失败 | 自洽指针：`active` 悬空；追加一条自洽但没有 record 的注册 | `test_k01_replaced_pointer_is_rejected` | `active_dangling`；`record_missing`；替换失败后原指针仍可读 |
| 同 ID 不同来源 → 失败 | 伪造行钉回原 ID、改 producer，并补上自洽 record 以绕过缺失检查 | `test_k01_same_registration_id_with_a_different_source_is_rejected` | `id_conflict` |
| 合法重复保持原 record | 同逻辑内容（含 upstream）重复注册；省略 generation 再注册一次 | `test_registering_a_published_artifact_records_its_identity`、`test_k01_repeat_registration_is_idempotent_without_a_new_generation` | 同 `registration_id`、同 generation、record 字节逐字不变 |
| 丢 provenance 不能换取同 ID | 少传 `upstream_refs` 再注册 | `test_registering_a_published_artifact_records_its_identity`（尾部断言） | 得到**不同** `registration_id` |
| 旧记录具名只读 | 指针改回 `1.0`（自洽） | `test_k01_legacy_registry_is_read_only_and_named` | 严格 reader 拒绝；legacy reader 读取成功且指针字节不变；新格式不得由 legacy reader 冒充 |
| 裁决逻辑进来源清单 + 缺来源拒绝 | 清单成员 + 缺失来源 | `test_k01_registry_is_a_versioned_validator_source`、既有 `test_missing_validator_source_is_reported_not_silently_empty` | 清单含注册表来源；缺失 → `validator_source_missing` |

`test_artifact_index.py::test_k03_legacy_registry_requires_the_named_reader` 另外证明**消费者侧**
的具名只读接线：默认索引把旧指针标 invalid，显式 `allow_legacy_registry=True` 才只读可见。

## 4. 边界与未测

1. 封摘要与 record 定位都用 sha256 前 16 hex 作 token；同 token 不同内容在现实中不可构造，
   代码仍以逻辑内容比较兜底（`record_mismatch`），未做碰撞注入测试。
2. 2026-09-30 返修用冻结 `0918ee76` 的 `register_authoring_artifact` 在隔离子进程生成真实
   `1.0` 指针和 record（依赖 `digest.py`、`tool_runtime.py`，blob 见阶段证据 §9.3）。
   具名 reader 读取后字节不变。把新指针改成 `1.0` 的旧节点仍保留，只证明版本分支。
   字段更少的历史形态本仓库该提交不存在，不臆造。
3. 注册表 active 的 CAS/fence 属 K02（发布事务）；本单元只提供
   `prepare_artifact_registration` / `activate_artifact_registration` 两个可分离入口。
4. 未改 `authoring_artifact_index.py` 的注册表回退语义（属 K03 范围，见阶段证据）。
