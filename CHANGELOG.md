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

### Fixed（2026-09-10 凌晨）
- PDF 二进制污染：.gitattributes 声明 *.pdf binary（CRLF 转换曾损坏文件流）
- 全文档一致性：三年画面 IM 表述→多形态 HMI；路线图/技术验证路线/ROADMAP 的 v0.1 描述同步双形态
