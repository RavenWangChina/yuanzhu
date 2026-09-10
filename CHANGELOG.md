# 更新日志 / Changelog

本项目所有显著变更记录于此。格式参照 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added（2026-09-09）
- 立项文档体系：项目介绍书 v3.7→**v3.8**（商业存档版）、技术验证路线 v2、Palantir 范式学习报告、致谢与引用出处
- 架构决策记录 ADR-001~**013**（总体架构/技术栈/三组件边界/轻量本体/四段式模板/动作自主性分级/对话学习/产品原则/商业挂起/元流程/**双部署形态+插件生态/多形态HMI·IM仅辅助/md→代码载体演进**）
- v0.1 设计文档（spec）：三柱验证范围、本体层 SQLite schema、四段式模板 DSL、三条端到端流程、8 步里程碑；**双部署形态（单机第一验证）+双 HMI（Web+CLI）+两大支柱（AIaaS+DSH）架构总纲**
- **元流程 v2**：六环节×知识环完整规格（工坊内核），全局 CLAUDE.md 宪法同步升级
- 仓库规范化：README、CHANGELOG、ROADMAP、目录结构（server/cli/edge/web/templates/deploy/plugins 骨架）
- 致谢修正：DeepSeek 归属深度求索；战略评审人明确为周志明先生

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
