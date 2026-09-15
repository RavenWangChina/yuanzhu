# 社媒宣传交接文档

> 交接日期：2026年09月15日 · 交接目的：本对话回归元铸工坊产品开发，社媒宣传由独立对话接手
> 工作目录：`D:\tangoWord\默认工作空间\SOSOFAST`

## 一、产品（一段话认知）

**元铸工坊 SOSOFAST**（GitHub: `RavenWangChina/yuanzhu`，PyPI 包名 `yuanzhu`）——企业 AI 人效平台，开源（AGPL-3.0），当前 v0.1.11。

核心叙事一句话：**AI 提议，人拍板。**

三个卖点（宣传素材永远从这三个里选钩子）：
1. **Staged writes**——AI 的每个写操作先暂存等人批准，审批权永不回流给 AI（切企业对 agent 失控的焦虑）
2. **一句话铸造工作流**——描述日常工作 → AI 生成四段式模板（对象模型+动作库+工作流+评测集）→ 三道质量门守门（结构校验/冒烟测试/评测）
3. **三记忆推衍**——行为日志+知识库+模板库交叉分析，主动提议工作流

自举故事（差异化钩子）：用元铸工坊开发元铸工坊——它成了自己的第一个用户。

诚实约束（所有文案必须保留）：**0.1.x 技术验证期**、161 测试、AGPL-3.0。不夸大。

## 二、当前发布状态（截至交接时）

### 已上线（渠道资产）

| 渠道 | 状态 | 链接/标识 |
|------|------|----------|
| MCP 官方 Registry | ✅ 已收录 | `io.github.RavenWangChina/yuanzhu` v0.1.11（API 确认） |
| PyPI | ✅ v0.1.11 | pypi.org/project/yuanzhu（README 含所有权标记） |
| npm（dsh 生态） | ✅ | `dsh-plugin-yuanzhu@0.1.0` |
| Claude 插件市场（自建） | ✅ | `claude plugin marketplace add RavenWangChina/yuanzhu` |
| GitHub 仓门面 | ✅ | 双语 description、14 个 topics、徽章+GIF README、social preview 已生效 |
| awesome-mcp-servers PR | ⏳ 待合并 | PR #14425（带 🤖🤖🤖 快速通道标记） |
| awesome-claude-code PR | ⏸️ 差临门一脚 | fork 分支 `add-yuanzhu` 已建好+条目已算好，卡在网络对大 POST 的间歇性掐断；网络好时重跑 contents API PUT + 建 PR 即可 |
| mcpservers.org | ⏳ 审核中 | 免费提交成功，12h 内审核，通过邮件通知 451294972@qq.com |
| Glama（8.7万收录） | ⏳ 自动抓取 | 每日 09:00 更新轮，Registry 已发大概率自动进，次日验证 `glama.ai/mcp/servers?query=yuanzhu` |
| dsh-plugin.org | ⏳ 爬虫排队 | 仓已加 `dsh-plugin` topic（GitHub topic 页已归类），等爬虫下轮抓取 |
| Smithery | ❌ 未提交 | 需注册账号（浏览器登录后提交） |
| Anthropic 官方/社区市场表单 | ❌ 地区封锁 | platform.claude.com 对大陆不可达+本机无代理，长期挂账 |

### 已发布内容（A/B 测试进行中）

| 平台 | 版本 | 链接 | 发布时间 |
|------|------|------|---------|
| 掘金 | A（治理钩） | https://juejin.cn/spost/7685291727632482338 | 09-15 10:59 |
| 知乎 | B（自举故事） | https://zhuanlan.zhihu.com/p/2083151088031641874 | 09-15 11:16 |

两篇同一产品的两种钩子（A=痛点干货 / B=自举故事），观察 72 小时数据定胜出版。

## 三、账号与凭据

| 平台 | 状态 | 说明 |
|------|------|------|
| 掘金 | 浏览器已登录（playwright 会话） | 账号已绑定手机，可发文 |
| 知乎 | 浏览器已登录 | 用户名"王睿文" |
| GitHub | PAT 在旧会话 jsonl 里（见下） | 只需 read_api+repo 权限用途 |
| npm | token 在 `D:/tmp/npm-token.txt` | 7 天有效期（09-21 过期），发布权限+bypass 2FA |
| 即刻 | 未登录 | 用户叫停，二维码流程在 playwright 浏览器试过两次未完成 |

**凭据红线**：token/密码存 `D:/tmp/`（GitHub 恢复码 `github-recovery-codes.txt`、TOTP 密钥 `github-totp-secret.txt`、PyPI token、npm token）。**凭据值永远不写进对话/文档/公开仓**，只引用路径。建议引导用户迁密码管理器。

**网络事实**：github.com 网页时通时断（api.github.com 稳定）；V2EX / linux.do / Reddit / HN 直连全封；掘金/知乎/即刻/少数派/bing 可达。github.com 对大 POST 请求体有间歇性掐断（enable/文件上传类操作会随机失败，重试或多等是常态）。

## 四、素材库（现成可用）

| 素材 | 位置 | 说明 |
|------|------|------|
| A/B 发帖文案 | `docs/launch-posts.md` | 含 V2EX 版（网络通了可发）+ 即刻版 + 数据记录表 |
| Demo GIF（16 秒） | `docs/demo.gif`（README 已引用） | 6 帧：对话入口→一句话铸造→staged 待审→能力地图→知识库→slogan，每帧中文标注 |
| GIF 源帧 | `docs/demo-frames/` | PNG 序列 |
| Social preview 图 | `docs/social-preview.png`（已上传生效） | 1200×640 |
| 提交材料（英文） | `SUBMISSION.md` | 官方目录+MCP 目录站的英文模板 |
| 知乎 md 原稿 | `D:/tangoWord/默认工作空间/aiac-psc-project/yuanzhu-zhihu.md` | playwright 允许根目录（沙箱要求） |

## 五、待办清单（按优先级）

1. **72 小时互动期（正在进行）**：盯掘金/知乎两篇的评论与私信，**10 分钟内回复**（算法吃互动）。回复口径：诚实、克制、不吹。评论钩"你们团队不敢让 AI 碰什么"要接住每个回答
2. **数据记录**：明晚看两篇浏览/互动/star 增量，填 `docs/launch-posts.md` 记录表，**定 A/B 胜出版**
3. **胜出版 → 投阮一峰《科技爱好者周刊》**（最高优先单点，实测案例一期 +300 star）：
   - 方式：GitHub issue 提交到 `ruanyf/weekly`（周五发布）
   - 文案约束：**150 字内**、用户视角、1-2 个差异点、链接；叙事与已投的"MOVO：DeepSeek Harness 企业级 Agent 平台"**错位**（我们谈"治理层"不谈"Agent 平台"）
   - **投前自检**（元铸工坊 deep-answer 工作流的裁决，勿跳过）：翻近 5 期确认①自荐通道活跃②无同质化项目；门面达标线=一句话定位+GIF+一行命令可跑（已全部达成）
4. **补发渠道**（素材全复用）：V2EX 分享创造（网络恢复后）、即刻（用户扫码）、少数派（可达未投）、掘金沸点（短内容二次曝光）
5. **awesome-claude-code PR 补完**：fork `RavenWangChina/awesome-claude-code` 分支 `add-yuanzhu` 就绪，contents API PUT README（~195KB，base64）+ 建 PR 到 `hesreallyhim/awesome-claude-code`，标题带 🤖🤖🤖
6. **验证轮**：次日验证 Glama 收录、mcpservers.org 审核邮件、awesome-mcp-servers PR #14425 合并状态
7. **每周一篇内容**（2-4 周）：launch 复盘（带真实数据）/ "How I built" 技术文 / 对比文
8. Show HN（机会性）：周二-四 8-10AM PT（北京晚 23 点），发后 5 分钟内跟创始人评论（动机/技术栈/局限/求反馈）

## 六、增长策略结论（两轮调研浓缩，勿重新调研）

- **国内平台是冷启动地狱**：知乎/掘金/CSDN 推广文实测几十浏览、1-2 star——预期放平
- **真实爆发点排序**：阮一峰周刊（+300/期）> Reddit r/mcp（+10/帖，标题要技术钩）> L站 Linux.do（被封，可让用户手机发）> HN（难上，机会性）
- **叙事框架**："I built X to solve Y"，绝不产品宣传腔；诚实标注早期状态反而加分
- **GitHub Trending 算法**：短期 star 增速>fork>新 Release；周二三发布、多渠道同刻集中推、README 英文
- **视频被低估**：部署教学视频能带来 PR 贡献者（B 站可选）
- 指标校准：此阶段看**第一个陌生 star / 第一条非亲友 issue**，不看下载量

## 七、红线与约束（必读）

1. **脱敏红线**：任何公开内容不得出现——惠威/qw-message/天翼云网关域名/公司内部信息/于淼等真实同事姓名
2. **版本号纪律**：产品版本递进由用户裁决，宣传对话不碰产品代码
3. **不可逆动作先问**：付费推广、批量群发、删除内容、绑定新账号——先经用户确认
4. **单点账号安全**：知乎/掘金是用户实名账号，发文前内容可让用户扫一眼（尤其标题）
5. **AGPL 合规**：引用项目内容需保留许可声明
6. **两篇已发文章不重复发**同平台（社区规则）

## 八、元铸工坊怎么用（宣传对话也能用它）

服务启动：`cd SOSOFAST/server && ./.venv/Scripts/python -X utf8 -m uvicorn yuanzhu.main:app --port 8600`

- **深度思考**：`POST /api/workflows/run-async {"domain":"metaflow","workflow":"deep-answer","params":{"question":"..."},"run_by":"..."}` 然后 `GET /api/workflows/status/{task_id}` 轮询——六步流水线（澄清→双视角对抗→审计→裁决），写文案/做决策前跑一遍，质量显著提升（本次投稿决策即它的裁决："先修门面再投"被数据验证正确）
- 知识库已有本次宣传的洞见沉淀，deep-answer 会自动检索

## 九、回归点（产品线备忘）

宣传对话与开发对话的交汇点只有一个：**产品数据**。star/issue/下载量数字由宣传对话记录，产品迭代由开发对话处理。用户提过 H2 真人测试（于淼机服务在跑等数据）、v0.2 候选（VS Code 插件/桌面壳/实时流式推衍）——这些归开发线。
