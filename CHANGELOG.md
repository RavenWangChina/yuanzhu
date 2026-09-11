# 更新日志 / Changelog

本项目所有显著变更记录于此。格式参照 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.1.1] · 2026-09-11

### Added（打磨版 + 并行 agent，142 测试全绿）
- **T5 引擎并行组**：steps 支持 `{"parallel": [...]}`——组内 asyncio.gather 并发（ai_step 独立 session 计量，AsyncSession 并发安全）；只允许 ai/query 步骤（fail fast）；deep-answer 双盲并行化（视角A/B 同时生成，对抗移到审查步）
- **T7 深度问答页**：`/` 首页直达 /ask——输入框→六步流水线→裁决展示（中间过程折叠）→采纳按钮；导航首项
- **T6 草稿转正**：`POST /api/templates/reload` + Web「重跑评测」按钮——forge 铸坏/evals 不过的 draft，人修目录后一键重跑守门；评测报告存 manifest.last_evals_report（失败原因 Web 可见）
- **T4 枚举值中文化**：labels.ts 显示层映射（major→较重/Open→进行中…；存储值不变——数据契约）
- **T2 估费真值**：YUANZHU_MODEL_PRICES 自定义价目表（JSON）优先 + litellm 本地表 fallback（审查 C2 修正：glm 类网关模型必须走自定义价目）
- **T1 启动提速**：本地价格表（12s→3.1s 实测）
- **T3 evals 副作用清理**：跑完删除 eval- 前缀测试对象（按 created_object_ids 精确删，exec 审计保留）

### Fixed（0.1.1 设计对抗审查，全部 PoC 级验证）
- **C1 evals 幂等键冲突**（第二次跑评测必挂，废掉 reload 场景）：评测运行幂等键追加 run 标识隔离
- **C2 估费永远记 0**：litellm 对网关裸名模型无价目且变量名笔误被 except 静默吞——自定义价目表 + 修正
- **I1-I4**：并行 session 注入点/组内类型约束/异常 fail fast（禁 return_exceptions 防静默降级）/清理误删面（created_ids 为据）

### Added（2026-09-10 深夜二 · metaflow 元流程问答，136 测试全绿）
- **引擎 prompt_vars 多上游绑定**：ai_step 可同时接收多个上游输出（标注块拼接）——视角对抗/综合裁决的地基
- **metaflow 内置模板（装完即用，零开发）**：deep-answer 六步流水线（Insight 反哺→澄清→视角A→质疑者B→独立审查→综合裁决→人审采纳）+ distill-insight 洞见沉淀（知识环外环：采纳答案提炼可复用洞见，后续提问自动引用）
- **同题对垒实证**：同模型裸问 vs 流水线——差距为结构性代差（自我纠错/量化门槛/合规维度/无据断言清除），归档 docs/test-reports/metaflow-duel-2026-09-10/
- 工作流引擎默认模型 glm-5.1（对齐多协议改造）

### Added（2026-09-10 晚 · 冷启动三件套，132 测试全绿）
- **forge 一句话铸模板**（冷启动核心）：`yuanzhu forge "描述"` 或 Web 模板市场铸造框 → AI 生成完整四段式 → 落盘 templates/forge/ → 注册草稿 → **evals 自动守门（全过才上架）**；一致性校验（动作/类型引用 fail-fast）；实测：一句话铸出「部门日报」域（组长提交自动生效/主管汇总人审——AI 正确理解自主性分级），evals 2/2 上架
- **meeting 内置模板**（第二个开箱域）：会议登记（L1）/行动项提炼（AI+人审）/完成行动项（set+语义校验），3 evals 全绿
- **模板开发指南**（docs/模板开发指南.md）：四段式手把手教程（新用户"不知道怎么开发工作流"的入口文档）
- evals 执行器跨域修复（aiqa 硬编码→按域解析）+ draft 模板可跑评测（forge 守门）+ CLI 超时放宽（forge 长操作）

### Added（2026-09-10 · 开源发布准备）
- 使用场景与接入形态文档（三种用户的一天 + Claude Code MCP 接入指南 + 核心概念一分钟版）
- LICENSE 定稿 AGPL-3.0（ADR-009 强保护路线）
- 仓库公开（private → public）

### Added（2026-09-09）
- 立项文档体系：项目介绍书 v3.7→**v3.8**（商业存档版）、技术验证路线 v2、Palantir 范式学习报告、致谢与引用出处
- 架构决策记录 ADR-001~**013**（总体架构/技术栈/三组件边界/轻量本体/四段式模板/动作自主性分级/对话学习/产品原则/商业挂起/元流程/**双部署形态+插件生态/多形态HMI·IM仅辅助/md→代码载体演进**）
- v0.1 设计文档（spec）：三柱验证范围、本体层 SQLite schema、四段式模板 DSL、三条端到端流程、8 步里程碑；**双部署形态（单机第一验证）+双 HMI（Web+CLI）+两大支柱（AIaaS+DSH）架构总纲**
- **元流程 v2**：六环节×知识环完整规格（工坊内核），全局 CLAUDE.md 宪法同步升级
- 仓库规范化：README、CHANGELOG、ROADMAP、目录结构（server/cli/edge/web/templates/deploy/plugins 骨架）
- 致谢修正：DeepSeek 归属深度求索；战略评审人明确为周志明先生

### Added（2026-09-10 · 后续流程三件套，126 测试全绿）
- **H2 模拟真人测试**（Playwright 按任务卡行为模型全流程模拟，判定通过）+ 卡点修复：待审参数 JSON 原文→中文键名+长文本块（报告全文可读）；动作友好描述（action_description）；去「Report 对象」术语；报告归档 docs/test-reports/h2-2026-09-10-simulated/
- **Bearer 认证中间件**（审查 I5 收口）：YUANZHU_API_TOKEN 非空即启用；/health 与 Web 壳豁免；API/MCP 全拦；CLI 自动携带、Web 401 弹输入存 localStorage；本机模式零摩擦
- **对话学习降级路径**（spec 3.3 预案，企微挂起期数据先行）：聊天记录文本导入（企微/微信导出格式解析+噪音过滤）→ 同一提炼管线 → 草稿区；CLI `yuanzhu import <file> --refine`；**真实链路实证**：11 条记录 → GLM 提炼 2 个精准候选（测试日报汇总/报错排查协助，协同层标注）
- 提炼 job 默认模型 glm-5.1（多协议改造对齐）

### Added（2026-09-10 · 模型网关多协议兼容改造，117 测试全绿；决策记录 ADR-014）
- **Provider 注册表**（gateway/providers.py）：三层配置源——①dsh 配置导入（~/.dsh/settings.yaml 的 providers + credentials refs 解 key，dsh 用户**零配置复用**）②.env 自定义（YUANZHU_PROVIDER_n_{NAME,BASE_URL,API,KEY,MODELS}）③内置兜底（deepseek 等 litellm 原生）
- **多协议映射**：openai-completions → litellm openai/ 前缀+api_base+api_key（一切 OpenAI 兼容端点：天翼云/vLLM/Ollama/one-api）；anthropic-messages 预留
- **/v1/models 动态化**：返回全部已配置模型（本机实测 58 个——dsh 天翼云 provider 全家桶自动导入）
- **全真链路实证**：dsh 天翼云 key 零配置 → GLM-5.1/5.2 真实对话 → AIQA 报告工作流（真实 Bug→GLM 分析→Report 进待审）→ 计量落库（1758 tokens）
- AIQA 工作流默认模型改 glm-5.1（环境实际可用）

### Added（2026-09-10 · CLI 双 HMI 补齐，110 测试全绿）
- **yuanzhu CLI**（ADR-012 开发者第一界面，API 薄壳）：status / query（经 MCP，k=v 过滤）/ pending / approve / reject（拒绝必附理由）/ templates / run（触发工作流）/ mcp tools；argparse 零新依赖，`pip install -e` 后 `yuanzhu` 命令可用；真实运行实证审批闭环

### Added（2026-09-10 · v0.1 全部代码交付，104 测试全绿）
- **本体层（H7 基座）**：六表 schema（对象/链接/动作类型+实例+执行记录）；三类 DSL 解析器（YAML→注册）；staged writes 状态机（staged→approved→applied/rejected/reverted）——transform 规则引擎（set 改属性 / create_object 建对象，from:/literal: 值解析，数据驱动无硬编码动作名）；submission_criteria 语义校验；autonomy L1 自动/L2+ 人审；幂等键；补偿事务（快照恢复+建对象删除）
- **MCP 暴露**：/mcp 端点（tools/list + tools/call）；exposed 对象类型与动作类型自动生成 agent 工具（query_/execute_ 命名，大小写不敏感回查）；审批三工具
- **中控骨架**：节点管理（注册 upsert/心跳/能力标签/超时下线）；任务编排（状态机+在线节点分发+pull 模式+结果回报）；模板库（四段式目录解析→本体层注册①②+Template 登记③④，幂等 upsert）；LiteLLM 网关（/v1/chat/completions+models，用量计量 ModelUsage 落库）
- **Web 控制台（Vite+Vue3，4 页）**：待审中心（批准/拒绝带理由+before 快照上下文）、模板市场（工作流「使用」按钮+参数弹窗+常驻错误框）、节点拓扑、用量审计；FastAPI 托管静态文件+SPA fallback
- **AIQA 四段式首发模板**：5 对象/4 链接/6 动作（RegisterModule L1+五写操作 L2）/2 工作流（考古=双 AI 步骤+迭代提交用例；报告=查询+AI 总结+建报告）/3 评测用例
- **工作流执行引擎**：ai_step（提示词分区：稳定前缀+可变段，expect_json 宽容解析）/query_step/action_step（iterate_over 逐项 staged）；变量绑定 $params/$item/$output
- **evals 执行器**：模板自带评测可跑（action/approve 步骤+跨用例 $last_<type> 引用链+object_exists/error_contains 断言）——硬化清单 evals 项
- **对话学习采集（服务端）**：企微回调端点（GET 验证回显+POST 收消息）；内存环形缓冲 2000 条（**原文不落库**，有测试看守）；提炼 job（提示词分区）→工作流候选落模板草稿区（draft 徽章+协同层诚实标注）；授权群白名单
- **H2 真人测试场景包**：任务卡/观察记录表/通过判定/种子脚本（seed_h2.py 实测通过）
- 元流程执行：方案对抗审查（5 项关键意见采纳）+ 环节 4 代码审查（10 项修复）+ 真实运行实证（H7 全链路/H2 关键路径 Playwright 实测）

### Fixed（2026-09-10 · 代码审查修复，全部 PoC 实锤后修复）
- **C1** SQLAlchemy JSON 列同引用赋值不持久化 → exec_log（before/transform_log/created_object_ids）丢失 → revert 泄漏对象：deepcopy 修复
- **C2** SPA fallback 路径穿越（%2e%2e 读任意文件含 .env）：resolve+is_relative_to
- **C3** 并发审批竞态（动作重复执行产生双对象）：approve/apply 改 DB 层乐观锁
- **I1** criteria 仅 stage 校验（TOCTOU）：apply 前复查；**I2** revert 恢复 stage 时快照吞中间修改：生效点快照
- **I3** 模板注册 path 无约束（任意目录→动作注入）：templates/ 根白名单
- **I4** workflow/对话学习模型调用绕过计量：call_model 提取 usage 落库
- **I5** limit 无上限（DoS 面）：钳制（Bearer 认证挂账：非本机部署前必加）
- **M1** 企微配 AES key 后验签不生效（fail-open）：改 fail-closed；**M2** 前端三页加载失败静默：错误文案显示
- 途中实证抓修：get_db async generator 形态（测试 override 曾掩盖）；litellm 裸模型名需 provider 前缀（加映射表）；幂等键 {name} 与参数名冲突；多条 set 规则互相覆盖

### Fixed（2026-09-10 凌晨）
- PDF 二进制污染：.gitattributes 声明 *.pdf binary（CRLF 转换曾损坏文件流）
- 全文档一致性：三年画面 IM 表述→多形态 HMI；路线图/技术验证路线/ROADMAP 的 v0.1 描述同步双形态
