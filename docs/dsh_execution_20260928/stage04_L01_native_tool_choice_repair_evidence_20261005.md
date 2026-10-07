# L01 packet13 与原生工具选择返修（2026-10-05）

当前 Gate-L FAIL，项目 24 done / 1 in_progress / 24 planned。packet13 的具体一次授权已消耗；下一次模型请求须先封存新完整/cold、独立审查及 fresh packet，并取得该包具体一次授权。M01–M03、P01–P04、G01–G08 按原独立阶段门接续。

## packet13 的实际结果

原始执行根 `/tmp/c2p-dsh-l01-packet-20261005-13`，packet SHA256 `2eb2c5eeeeebbb6a192c8754060c7aec91bed9cc94cd806ec733dff319ad361a`，计划 SHA256 `3d13cc46b66039667cd6456cb36410d8571f87bd9549d000f0a9a53e1170fc97`。原句柄 86098 已回收，exit 1；1 primary、1 非生成 tokenize、0 retry/repair/其他生成。HTTP 200、finish stop、7699 input / 1359 output，原生 tool_calls 为零。普通文本包含 arguments 字符串包装，未提升为工具调用、来源或领域回执。

原 owner 正确报告 `host_single_terminal_required` / `ordinary_model_text`，secondary null、cleanup 空。原任务 cancelled、captured_source 和 receipt 均 null；私有 `DshRejectedTextProviderQuiescenceV1` 已真实登记，费用 spent7699 / pending0，原 owner 正常释放。canonical backend empty，六条严格 history，旧五条不变，无须历史恢复。

独立实际事后裁决 [review.md](/tmp/c2p-dsh-independent-l01-packet13-postlive-20261005-01/review.md)：Gate-L FAIL / lifecycle PASS，382 实际输入，全部实际读集释放。绑定 engine `7f77e169f681d2186ae301c2b2e2bf5811c11018c44f28e1c90162b823ce4d33` / validator `af9fdb96f4a5aa238943f5d7d3733346ce653dc92148bfaba7417e599124cc44`。完整05的1803及fresh cold仅证明这组历史身份，不给新代码换标签。

## 同方向修复

新开发候选 `0.2.0-rc.1+loop-origin.1+tool-choice.2`，runtime tree `b451ebbf551eba55ecb72b1c0bf9aa0f11338418eca51e12558ffcd3c34744b4`，严格审计 PASS。原 pristine、loop-origin.1 与默认运行时不改；最终候选复制原运行时，保留原五处 private-origin 修改，仅另改 PiAi adapter/config 声明两文件。第一原型 tool-choice.1 保留开发证据，不能混用最终候选证书。

profile 明确选择 `c2p_terminal`。其选择策略绑定 frozen effective options / composition / 实际 provider wire；原 DSH loop config 及私有来源 owner 不增权。只支持 OpenAI-completions，校验 required 或精确命名对象、实际 offered tools 与投影；缺工具、错名、额外字段、不支持 API 均发送前拒绝。未设置时保持旧 wire。

最终适配器使用 SDK 公开 `samplingParams.tool_choice` 入口。源码编译先发现中立 SimpleStreamOptions.toolChoice 类型只支持 auto/none，故未采用类型强制转换或 fetch 替代。原 SDK/native decoder/Session/worker/source、usage/finish、费用、formula/witness 门不变。普通文本及 arguments 字符串不修复为终端结果。通用提示说明数学表达式由原占位符承担，不加入本例答案。

物理模型继续使用 loop-origin.1 的原 canonical backend 数据库；候选切换不新建模型占用库，不重复旧费用或历史退役。

## 验证与边界

来源构建证据 [source-build-evidence.json](/tmp/c2p-dsh-tool-choice-source-build-20261005-01/source-build-evidence.json)：原源码只读，隔离副本精确 source patch apply-check 与应用一致；真实 tsc 原句柄84801回收 exit0。原 adapter、最终 runtime adapter、独立编译源码 adapter 的 fake-fetch wire 对照仅新增 tool_choice，其余一致；负例验证12个非法配置及4个工具投影拒绝。该证明限客户端转发与来源编译，不证明当前服务 parser/template 或 whole-package source-build equivalence。

最终候选 setup68617、锁定 wheelhouse pyworker72130、typecheck86332、build42008 均回收 exit0；stage/audit exit0。三项真实 native Host 原句柄72888回收 exit0：合法 draft、错误公式拒绝、普通文本拒绝均通过，并验证真实请求 tool_choice、原费用及正常完成释放、跨进程读回。记录 `/tmp/c2p-dsh-l01-tool-choice-native-regression-20261005-04` 和调查根 `native-regression-candidate2.log`。这些是隔离 fake provider，不访问真实模型。新增13项冻结投影与后端别名反例已注册，完整/core计划版本7；原所有旧 discovery/门保留。

调查根 `/tmp/c2p-dsh-l01-packet13-tool-choice-investigation-20261005-01` 保留每次失败日志。早期 probe 导出、相对测试路径、peer/candidate不符、default sandbox EPERM、首次 pyworker DNS及源码缺依赖/中立类型编译失败均未计通过。candidate1 npm安装14234未显式离线，不能称离线；candidate2启用 offline=true 后安装成功，pyworker仅用原锁哈希六个 wheel。原回归52项和candidate1 native三项保留自己的历史绑定。

当前 source/docs 将统一关闭后冻结完整09 `/tmp/c2p-dsh-l01-admission-20261005-09`，由原 record-offline-receipt dsh-stage04 manager、fresh cold、原两个 reader及独立审查验收。此处记录执行前状态，不预报 passed 数量。未生成下一次 live 授权；8006当前监听进程3597064的启动参数及socket归属现已只读核对：GPU2、qwen3_xml tool parser、qwen3 reasoning parser、模型目录 /data1/users/cuihengjia/qwen3.8-modelopt，无显式 --chat-template；已加载模板字节仍未证实。证据 current-server-process-readback.json；历史GPU6脚本不作为当前身份。无新增真实模型/tokenize请求。

关闭前补充：validator来源清单绑定实际runtime准入脚本、两份原生选择补丁和最终受信candidate合同；Python/Node入口均固定原 canonical admission候选，null/新候选/路径别名拒绝。相关检查默认沙箱39通过、两项EPERM失败保留；仅两个受阻激活场景经原隔离测试重验，88556回收exit0、2通过。原 L01 Qwen profile离线51327回收exit0，真实native blocked局部回执、spent17/pending0、完成登记/backendempty，零实际模型/tokenize；绑定其当时fc116 validator。之后仅严格化Node显式null拒绝和当前记录关闭；最终身份以完整07为准。

完整06中断记录：原37498句柄回收exit143，七个原所属进程均确认absent，输入在执行期间未改，无完整证书/cold。预先只读检查发现原注册 test_serial_writer_e2e.py 硬编码旧candidate，与当前peer冲突；未等失败再消耗完整后续套件。修复仅让原测试使用计划冻结candidate、保留 standalone旧默认及全部原Host/ledger/sentinel/恢复断言。原98919回收exit0、1通过；准确时长见 final-serial-e2e-candidate2.log。随后关闭记录并改用fresh完整07；不复用06、不给历史1803换标签。

完整07实际FAIL：原manager33100回收exit1，engine4590/validator5951执行期间稳定。Python1597通过、56subtests通过、1失败（smoke正例固定旧candidate，严格staging拒绝旧构建），Node/cold未执行；原complete receipt passed=false/offline_required_suite_missing，不改写为成功。原operator reader确认0preparedtask/call/spent/pending，无新增真实模型/tokenize。仅修原smoke测试正例使用进入测试前的计划candidate，所有原冲突/缺环境/证据路由断言保留；70503回收exit0、1通过7.11秒。

完整候选入口扫描还发现 joint-child/cancellation 两份原测试名单仅含old1/old1-built；新增精确final tool-choice.2为受测候选，不接受任意后缀、不加入neutral prototype、不减少任何原来源/取消断言。原断网launcher99157回收exit0：31通过、0失败/skip/cancel，24966.29241ms；当前candidate2最终typecheck40136/audit37857均回收exit0。生产TS输入未变，不重建旧runtime/staging。闭合本批记录后只用fresh完整08，历史07失败完整保留。当前服务安装源码只读八文件绑定已保存 current-installed-vllm-readonly.json：tool_choice不进入build_chat_params，parser调整在render之后；命名流路径及qwen3_xml alias存在，但磁盘源码不构成已加载字节或实际live成功证明。

完整08原manager43570回收exit1，Python1598通过/56subtests、Node220断言通过/0失败；原机器reader因三个新增场景与旧场景名称重复拒绝offline_node_duplicate，原receipt仍false、cold未执行。source-freeze保留45e94/5951身份及失败事实。修复仅在原host-provider场景标题加入named native tool selection区分，原reporter/reader及全部断言不改。六个旧/新场景原2702回收exit0，6通过/0失败skipcancel，484845.683935ms；原validate_node_report实际接受六个独立ID，证据/tmp/c2p-dsh-l01-tool-choice-name-regression-20261005-01/original-reader-result.json。最终typecheck25827回收exit0；生产TS输入未改，无重复build。关闭当前记录后使用fresh完整/cold09；未授权packet14，Gate-L FAIL，24/1/24。
