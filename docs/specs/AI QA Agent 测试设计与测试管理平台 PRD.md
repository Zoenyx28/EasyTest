# AI QA Agent 测试设计与测试管理平台 PRD

> 版本：V2.0  
> 定位：AI 原生测试设计与质量工程平台  
> 核心模式：AI Generation + AI Review + Human-in-the-loop + Quality Gate  
> 核心目标：从“AI生成测试用例”升级为“AI持续进行测试设计与质量优化”

---

# 1. 产品定位

本系统是一套面向测试工程师、产品经理和研发团队的 AI 原生测试设计与测试管理平台。

系统不以“一次性生成测试用例”为核心，而是将需求逐层转换为结构化测试资产：

```text
Requirement
    ↓
Requirement Analysis
    ↓
Story
    ↓
Story Review
    ↓
Human Confirmation
    ↓
TestPoint
    ↓
TestPoint Review
    ↓
Human Confirmation
    ↓
TestScenario
    ↓
GeneratedCase
    ↓
Case Review
    ↓
TestStrategy
    ↓
Automation
    ↓
Execution
    ↓
Coverage / Risk
    ↓
Test Gap
    ↓
AI补测
```

核心理念：

> **AI负责理解、拆解、评估、建议和生成；产品负责业务事实确认；测试工程师负责测试质量确认。**

---

# 2. 产品核心目标

## 2.1 需求可理解

AI能够从原始需求中识别：

- 业务目标
- 业务角色
- 业务实体
- 业务流程
- 业务规则
- 状态变化
- 输入输出
- 异常条件
- 权限
- 外部依赖
- 数据约束

---

## 2.2 需求可拆解

将复杂 Requirement 拆解为多个独立 Story。

例如：

```text
需求：
用户申请订单退款

↓

Story 1：用户申请退款
Story 2：退款资格校验
Story 3：退款金额校验
Story 4：管理员审核退款
Story 5：退款结果更新订单状态
```

---

## 2.3 Story 可评审

AI不仅生成 Story，还必须判断：

> Story 是否足够准确、完整、独立、可测试？

输出：

```text
Score
Issue
Suggestion
InformationGap
QualityGate
```

---

## 2.4 测试点可验证

Story 确认后生成 TestPoint。

AI再次进行测试设计质量评审：

```text
覆盖度
完整性
风险覆盖
测试维度
重复性
可测试性
```

---

## 2.5 测试用例可追溯

任何测试用例都能够追溯到：

```text
Requirement
 ↓
Story
 ↓
TestPoint
 ↓
TestScenario
 ↓
GeneratedCase
```

---

# 3. 核心设计原则

## 3.1 行业知识驱动领域模型

系统遵循：

```text
测试领域知识
      ↓
DDD领域模型
      ↓
AI Agent
      ↓
技术框架
```

而不是：

```text
LLM
 ↓
Prompt
 ↓
测试用例
```

---

# 4. 核心领域模型

```text
Project
Branch

Requirement
RequirementSource
RequirementAnalysis
InformationGap

Story
StoryReview

TestPoint
TestPointReview

TestScenario
ScenarioReview

GeneratedCase
CaseReview

TestStrategy
CaseBinding
TestCaseDefinition

TestTask
Execution
ExecutionResult

Coverage
Risk
TestGap
```

---

# 5. 核心领域关系

```text
Requirement
    │
    ├── RequirementSource
    │
    ├── RequirementAnalysis
    │
    ├── InformationGap
    │
    └── Story[]
             │
             └── StoryReview
                     │
                     ↓
                 TestPoint[]
                     │
                     └── TestPointReview
                             │
                             ↓
                         TestScenario[]
                             │
                             ↓
                        GeneratedCase[]
                             │
                             └── CaseReview
                                     │
                                     ↓
                               TestStrategy
                                     │
                                     ↓
                                CaseBinding
                                     │
                                     ↓
                           TestCaseDefinition
                                     │
                                     ↓
                                  Execution
                                     │
                                     ↓
                            Coverage / Risk
                                     │
                                     ↓
                                  TestGap
```

---

# 6. AI QA Agent总体架构

AI Agent 不采用单一超级 Agent。

采用：

```text
QA Orchestrator
        │
        ├── Requirement Analyzer
        ├── Story Designer
        ├── Story Reviewer
        ├── TestPoint Designer
        ├── TestPoint Reviewer
        ├── Scenario Designer
        ├── TestCase Generator
        ├── TestCase Reviewer
        ├── Strategy Advisor
        ├── Automation Advisor
        ├── Execution Analyzer
        └── Coverage Analyzer
```

---

# 7. QA Orchestrator

Orchestrator负责整个测试设计生命周期。

核心任务：

```text
1. 接收任务
2. 判断当前阶段
3. 调度Agent
4. 管理上下文
5. 保存中间产物
6. 触发Review
7. 判断Quality Gate
8. 决定是否进入下一阶段
9. 处理人工反馈
10. 重新触发AI
```

---

# 8. AI任务状态

所有AI任务统一采用：

```text
PENDING
 ↓
RUNNING
 ↓
REVIEW
 ↓
WAITING_HUMAN
 ↓
CONFIRMED
 ↓
NEXT_STAGE
```

异常：

```text
RUNNING
 ↓
FAILED
 ↓
RETRY
```

---

# 9. Requirement阶段

## 9.1 Requirement

Requirement是整个测试设计流程的原始业务输入。

来源：

```text
手工输入
文件
飞书文档
项目代码 / Git
```

---

# 10. Requirement Analysis

AI首先不直接生成测试点。

第一步是：

> **理解需求。**

输出：

```text
业务目标
业务角色
业务实体
业务流程
业务规则
状态
输入
输出
异常
权限
依赖
风险
```

---

# 11. InformationGap

如果AI判断需求信息不足，则创建：

```text
InformationGap
```

示例：

```text
问题：

“退款失败”的具体业务条件未定义。

需要产品确认：

□ 第三方支付失败
□ 订单状态不允许退款
□ 退款金额超限
□ 网络超时
□ 其他
```

---

# 12. InformationGap类型

```text
BUSINESS_RULE_MISSING
ACCEPTANCE_CRITERIA_MISSING
DATA_RULE_MISSING
STATE_TRANSITION_MISSING
PERMISSION_RULE_MISSING
ERROR_RULE_MISSING
DEPENDENCY_MISSING
```

严重等级：

```text
CRITICAL
HIGH
MEDIUM
LOW
```

---

# 13. Story设计

## 13.1 Story定义

Story是：

> **从业务角度描述一个独立、可验证的业务能力。**

Story不是测试用例。

Story也不是简单复制需求标题。

---

# 14. Story生成

输入：

```text
Requirement
RequirementAnalysis
InformationGap
```

输出：

```text
Story[]
```

每个Story至少包含：

```text
Story ID
标题
业务目标
业务角色
业务行为
业务规则
前置条件
业务结果
异常条件
依赖Story
来源Requirement
```

---

# 15. Story拆解原则

AI必须遵循：

### 独立性

一个Story尽可能表达一个独立业务能力。

### 完整性

不能遗漏原始需求中的业务能力。

### 可测试性

Story必须能够进一步转换成TestPoint。

### 合理粒度

避免：

```text
过粗
```

也避免：

```text
过细
```

---

# 16. Story Review

Story生成后，不直接进入TestPoint。

首先进入：

> **Story Quality Gate**

---

# 17. Story评分模型

Story评分采用多维评分，而不是单一总分。

建议：

| 评分维度 | 权重 |
|---|---:|
| 需求覆盖度 | 25% |
| 业务完整性 | 20% |
| 独立性 | 15% |
| 可测试性 | 15% |
| 粒度合理性 | 10% |
| 业务规则完整性 | 10% |
| 依赖完整性 | 5% |

---

# 18. Story Review输出

例如：

```text
Story-001

用户申请订单退款

综合评分：86

需求覆盖度：95
业务完整性：90
独立性：90
可测试性：80
粒度合理性：85
业务规则完整性：70
依赖完整性：75
```

同时输出：

```text
Issues：

1. 退款资格规则不明确
2. 缺少退款失败状态

Suggestions：

1. 补充订单状态限制
2. 明确第三方退款失败处理
```

---

# 19. Story Quality Gate

不能只使用综合评分判断。

采用：

```text
PASS
WARNING
BLOCKED
```

示例：

```text
Story Quality Gate

需求覆盖度 >= 90%
可测试性 >= 80%
业务规则完整性 >= 80%
无Critical InformationGap
```

满足条件：

```text
PASS
```

存在一般问题：

```text
WARNING
```

存在关键业务信息缺失：

```text
BLOCKED
```

---

# 20. 产品 + 测试人工确认

Story阶段采用双角色Review。

### 产品经理

负责确认：

```text
业务事实
业务规则
业务流程
验收条件
```

### 测试工程师

负责确认：

```text
测试可行性
业务边界
异常流程
风险
Story粒度
```

---

# 21. 人工Review模式

页面提供：

```text
[确认]
[修改]
[补充信息]
[要求AI重新生成]
[忽略问题]
```

推荐流程：

```text
AI生成
 ↓
AI Review
 ↓
产品确认业务事实
 ↓
测试确认测试视角
 ↓
AI重新生成
 ↓
AI重新评分
 ↓
PASS
```

---

# 22. 人工修改原则

对于业务事实：

```text
人确认
```

对于结构化拆解：

```text
AI重新生成
```

例如：

```text
产品补充：

已支付且未完成退款的订单才允许申请退款。

↓

AI重新生成Story

↓

AI重新评分
```

这样可以避免测试人员自行猜测业务规则。

---

# 23. TestPoint设计

Story确认后进入：

```text
Story
 ↓
TestPoint Agent
```

---

# 24. TestPoint定义

TestPoint表示：

> **需要验证的测试关注点。**

例如：

```text
Story：

用户申请订单退款

↓

TestPoint：

退款资格
退款金额
退款原因
退款提交
权限
重复提交
状态
并发
异常
数据一致性
```

---

# 25. TestPoint分类

建议标准化：

```text
Functional
Boundary
Exception
State
Permission
Data
Concurrency
Security
Performance
Compatibility
Dependency
```

---

# 26. TestPoint树

示例：

```text
退款申请

├── 退款资格
│   ├── 可退款订单
│   ├── 不可退款订单
│   └── 已退款订单
│
├── 退款金额
│   ├── 正常金额
│   ├── 0
│   ├── 负数
│   ├── 超额
│   └── 边界值
│
├── 重复提交
│
├── 并发提交
│
└── 异常
    ├── 网络异常
    └── 第三方异常
```

---

# 27. TestPoint Review

测试点生成后进入：

```text
TestPoint Quality Gate
```

---

# 28. TestPoint评分维度

| 维度 | 说明 |
|---|---|
| Story覆盖度 | 是否覆盖Story |
| 业务规则覆盖度 | 是否覆盖业务规则 |
| 正常场景 | Happy Path |
| 异常场景 | Exception |
| 边界场景 | Boundary |
| 状态覆盖 | State |
| 权限覆盖 | Permission |
| 数据覆盖 | Data |
| 并发覆盖 | Concurrency |
| 风险覆盖 | Risk |
| 重复度 | Duplicate |

---

# 29. TestPoint Review示例

```text
TestPoint Coverage：88%

正常流程：100%
异常流程：75%
边界：80%
状态：70%
权限：100%
并发：50%

AI发现：

⚠ 缺少重复提交
⚠ 缺少并发退款
⚠ 缺少第三方退款失败
```

AI建议：

```text
建议新增：

TP-008 并发提交退款
TP-009 重复提交退款
TP-010 第三方退款异常
```

---

# 30. TestPoint迭代机制

```text
AI生成TestPoint
 ↓
AI Review
 ↓
测试工程师修改
 ↓
AI重新Review
 ↓
PASS
```

注意：

> **AI Review不是一次性过程，而是循环过程。**

---

# 31. TestScenario

TestPoint确认后生成TestScenario。

关系：

```text
TestPoint
 ↓
TestScenario
```

定义：

> TestPoint回答“测什么”，TestScenario回答“在什么业务情况下测”。

---

# 32. TestScenario示例

```text
TestPoint：

退款资格

↓

Scenario：

1. 已支付订单正常申请退款
2. 未支付订单申请退款
3. 已完成订单申请退款
4. 已退款订单再次申请退款
5. 已取消订单申请退款
```

---

# 33. Scenario Review

AI检查：

```text
场景覆盖
场景重复
场景完整性
异常覆盖
边界覆盖
状态覆盖
风险覆盖
```

输出：

```text
Coverage
Issues
Suggestions
```

---

# 34. GeneratedCase

TestScenario确认后生成：

```text
GeneratedCase
```

---

# 35. TestCase字段

```text
Case ID
标题
Requirement
Story
TestPoint
TestScenario

前置条件
测试数据
操作步骤
预期结果

测试类型
优先级
风险等级

来源
状态
```

---

# 36. TestCase生成原则

AI生成Case时必须使用：

```text
Requirement
+
Story
+
TestPoint
+
TestScenario
+
Testing Standard
```

而不是只根据Story生成。

---

# 37. TestCase Review

AI检查：

```text
步骤完整性
预期结果完整性
测试数据完整性
业务规则覆盖
测试点覆盖
场景覆盖
重复用例
优先级合理性
自动化可行性
```

---

# 38. 测试类型推荐

AI根据TestCase推荐：

```text
UI
API
Manual
```

例如：

```text
用户输入退款金额
→ UI

退款金额校验
→ API

复杂人工审核流程
→ Manual
```

测试工程师可以修改AI推荐结果。

---

# 39. 自动化绑定

GeneratedCase和TestCaseDefinition保持解耦。

关系：

```text
GeneratedCase
      │
      └── CaseBinding
              │
              ├── API TestCase
              ├── UI TestCase
              └── Other Implementation
```

支持：

```text
一个GeneratedCase
      ↓
多个自动化实现
```

---

# 40. 自动化策略

Automation Advisor根据：

```text
TestCase
TestStrategy
Risk
ExecutionHistory
```

推荐：

```text
自动化
半自动化
人工测试
```

---

# 41. 执行域

测试工程师可以：

```text
选择TestCase
 ↓
创建TestTask
 ↓
选择环境
 ↓
执行
 ↓
Execution
 ↓
ExecutionResult
```

---

# 42. 执行结果

支持：

```text
PASS
FAIL
SKIPPED
ERROR
BLOCKED
```

同时保存：

```text
日志
截图
Trace
错误信息
环境
执行时间
版本
```

---

# 43. Coverage

系统计算：

```text
Requirement Coverage
Story Coverage
TestPoint Coverage
Scenario Coverage
TestCase Coverage
Automation Coverage
Risk Coverage
```

---

# 44. Test Gap

系统发现：

```text
未覆盖Story
未覆盖TestPoint
未覆盖Scenario
未自动化Case
高风险未覆盖
```

例如：

```text
Test Gap：

P0：
并发退款未覆盖

P1：
第三方退款异常未覆盖

P1：
退款状态回调异常未覆盖
```

---

# 45. AI补测

Test Gap进入：

```text
Coverage Analyzer
 ↓
Test Gap
 ↓
AI补测
```

AI根据缺口重新生成：

```text
TestPoint
 ↓
Scenario
 ↓
GeneratedCase
```

形成闭环。

---

# 46. 完整AI QA生命周期

最终核心链路：

```text
                    Requirement
                         │
                         ▼
                Requirement Analyzer
                         │
                         ▼
                      Story
                         │
                         ▼
                   Story Reviewer
                         │
              ┌──────────┴──────────┐
              │                     │
             FAIL                  PASS
              │                     │
              ▼                     ▼
       InformationGap          Human Review
              │                     │
              └──────→ AI重新生成 ←─┘
                                    │
                                    ▼
                               TestPoint
                                    │
                                    ▼
                            TestPoint Reviewer
                                    │
                              Human Review
                                    │
                              AI重新评分
                                    │
                                    ▼
                              TestScenario
                                    │
                                    ▼
                             Scenario Review
                                    │
                                    ▼
                              GeneratedCase
                                    │
                                    ▼
                              Case Review
                                    │
                                    ▼
                              TestStrategy
                                    │
                                    ▼
                             Automation
                                    │
                                    ▼
                               Execution
                                    │
                                    ▼
                           Coverage / Risk
                                    │
                                    ▼
                               Test Gap
                                    │
                                    ▼
                              AI补测
                                    │
                                    └──────→ TestPoint
```

---

# 47. AI Agent职责

## Requirement Analyzer

负责：

- 需求理解
- 业务实体识别
- 业务规则识别
- 信息缺口识别

---

## Story Designer

负责：

- 需求拆解
- Story生成
- Story依赖分析
- Story粒度控制

---

## Story Reviewer

负责：

- Story评分
- 完整性检查
- 覆盖率检查
- 业务规则检查
- 问题识别
- 建议生成

---

## TestPoint Designer

负责：

- Story → TestPoint
- 测试点树生成
- 测试维度补充

---

## TestPoint Reviewer

负责：

- 测试点覆盖
- 风险覆盖
- 边界
- 异常
- 状态
- 权限
- 并发
- 数据一致性

---

## Scenario Designer

负责：

```text
TestPoint → TestScenario
```

---

## TestCase Generator

负责：

```text
Scenario → GeneratedCase
```

---

## TestCase Reviewer

负责：

- 用例质量
- 重复检测
- 完整性
- 覆盖率
- 优先级
- 自动化建议

---

# 48. Quality Gate统一模型

所有核心阶段统一采用：

```text
Artifact
 ↓
AI Review
 ↓
Score
 ↓
Issues
 ↓
Suggestions
 ↓
InformationGap
 ↓
QualityGate
```

QualityGate：

```text
PASS
WARNING
BLOCKED
```

---

# 49. AI Review记录

每一次AI Review必须保存：

```text
review_id
artifact_type
artifact_id

score
dimension_scores

issues
suggestions
information_gaps

gate_status

model
prompt_version

created_at
```

这样可以实现：

> **测试设计过程可审计。**

---

# 50. AI版本管理

每一次重新生成都不能直接覆盖历史结果。

建议：

```text
Story v1
Story Review v1

↓

Story v2
Story Review v2

↓

Story v3
Story Review v3
```

最终：

```text
Confirmed Version
```

---

# 51. 前端页面结构

```text
项目

├── 项目概览
│
├── 需求管理
│   ├── 需求列表
│   └── 需求详情
│
├── AI测试设计
│   ├── 需求分析
│   ├── Story
│   ├── 测试点
│   ├── 测试场景
│   └── 测试用例
│
├── 测试用例
│
├── 测试执行
│   ├── 测试任务
│   └── 执行结果
│
└── 质量分析
    ├── 覆盖率
    ├── 风险
    └── 测试缺口
```

---

# 52. 需求详情页

建议采用“测试设计工作台”。

```text
┌─────────────────────────────────────────────┐
│ 需求：订单退款功能              [AI分析]    │
├─────────────────────────────────────────────┤
│                                             │
│ ① 需求分析                                  │
│                                             │
│ 业务目标 / 业务规则 / 风险 / 信息缺口        │
│                                             │
├─────────────────────────────────────────────┤
│ ② Story                                     │
│                                             │
│ Story-001  用户申请退款          96 PASS    │
│ Story-002  管理员审核退款        82 WARNING │
│                                             │
│ [AI重新生成] [人工确认]                      │
│                                             │
├─────────────────────────────────────────────┤
│ ③ TestPoint                                 │
│                                             │
│ 测试点树                                    │
│                                             │
│ 覆盖率：97%                                 │
│                                             │
├─────────────────────────────────────────────┤
│ ④ TestScenario                              │
├─────────────────────────────────────────────┤
│ ⑤ GeneratedCase                             │
├─────────────────────────────────────────────┤
│ ⑥ Coverage                                  │
└─────────────────────────────────────────────┘
```

---

# 53. Story Review页面

建议采用左右布局。

```text
┌──────────────────┬──────────────────────────┐
│ Story列表        │ Story详情                │
│                  │                          │
│ ✓ Story-001 96   │ 用户申请退款             │
│ ⚠ Story-002 82   │                          │
│ ✗ Story-003 61   │ AI评分                   │
│                  │ 完整性 90                │
│                  │ 可测试性 80              │
│                  │ 粒度 85                  │
│                  │                          │
│                  │ 问题                     │
│                  │ ⚠ 缺少退款失败条件        │
│                  │                          │
│                  │ 建议                     │
│                  │ 补充第三方支付异常        │
│                  │                          │
│                  │ [确认] [修改] [重新生成]  │
└──────────────────┴──────────────────────────┘
```

---

# 54. 测试点Review页面

```text
┌──────────────────┬──────────────────────────┐
│ 测试点树         │ AI Review                │
│                  │                          │
│ 退款资格         │ 覆盖率 97%               │
│ 退款金额         │ 异常 90%                 │
│ 权限             │ 边界 95%                 │
│ 并发             │ 状态 80%                 │
│ 异常             │ 并发 60% ⚠              │
│                  │                          │
│                  │ AI建议：                 │
│                  │ 增加并发退款测试点        │
│                  │                          │
│                  │ [添加] [重新评分]         │
└──────────────────┴──────────────────────────┘
```

---

# 55. 前后端职责边界

## 前端

负责：

```text
展示AI结果
Review交互
人工修改
质量评分展示
状态展示
测试点树编辑
版本切换
```

## 后端

负责：

```text
领域模型
业务规则
AI任务编排
Quality Gate
权限
版本
审计
数据持久化
```

---

# 56. 后端架构

推荐：

```text
API
 │
 ▼
Application
 │
 ▼
Domain
 │
 ▼
Infrastructure
```

---

# 57. Domain

核心：

```text
Requirement
Story
TestPoint
TestScenario
GeneratedCase
Review
QualityGate
InformationGap
Coverage
TestGap
```

---

# 58. Application

核心服务：

```text
RequirementService
StoryService
TestPointService
ScenarioService
TestCaseService
ReviewService
CoverageService
ExecutionService
```

---

# 59. Infrastructure

负责：

```text
PostgreSQL
LLM
Lark
Git
File Storage
Pytest
Playwright
CI/CD
```

---

# 60. API设计

API围绕业务能力设计。

例如：

```http
POST /requirements/{id}/analyze

POST /requirements/{id}/stories/generate

POST /stories/{id}/review

POST /stories/{id}/confirm

POST /stories/{id}/regenerate

POST /stories/{id}/test-points/generate

POST /test-points/{id}/review

POST /test-points/{id}/confirm

POST /test-points/{id}/regenerate

POST /test-points/{id}/scenarios/generate

POST /scenarios/{id}/cases/generate

POST /generated-cases/{id}/review

POST /generated-cases/{id}/bindings

POST /tasks/{id}/execute

POST /requirements/{id}/coverage/analyze

POST /test-gaps/{id}/generate
```

---

# 61. 数据隔离

需求域继续采用：

```text
project_id
branch_id
```

作为核心隔离维度。

所有核心领域对象必须校验：

```text
project_id
branch_id
```

禁止跨项目、跨分支读取需求测试设计数据。

---

# 62. 数据追溯

必须支持：

```text
Requirement
 ↓
Story
 ↓
TestPoint
 ↓
Scenario
 ↓
GeneratedCase
 ↓
TestCaseDefinition
 ↓
Execution
 ↓
Result
```

任何执行结果均可以反向追溯到原始需求。

---

# 63. AI上下文设计

每个Agent必须获取正确层级上下文。

### Story Agent

```text
Requirement
RequirementAnalysis
InformationGap
```

### TestPoint Agent

```text
Requirement
Story
StoryReview
Testing Standards
```

### Scenario Agent

```text
Story
TestPoint
TestPointReview
```

### Case Agent

```text
Story
TestPoint
TestScenario
Testing Standards
```

### Case Reviewer

```text
Requirement
Story
TestPoint
Scenario
GeneratedCase
```

---

# 64. Shared Testing Knowledge

建立统一测试知识层：

```text
testing-standard
testcase-template
priority-rule
automation-rule
coverage-rule
risk-rule
glossary
```

用于约束不同Agent的输出。

---

# 65. 测试标准

AI测试设计必须覆盖常见测试维度：

```text
Functional
Boundary
Exception
State
Permission
Security
Data
Concurrency
Performance
Compatibility
Dependency
```

不同业务领域可以增加领域专属规则。

---

# 66. 去重机制

AI需要在多个阶段进行去重。

### Story

防止：

```text
Story A
Story B
```

表达同一业务能力。

### TestPoint

防止：

```text
退款金额校验
金额合法性校验
```

重复。

### TestCase

防止：

```text
相同前置
相同步骤
相同预期
```

产生重复用例。

---

# 67. 覆盖率体系

最终覆盖：

```text
Requirement Coverage
Story Coverage
TestPoint Coverage
Scenario Coverage
Case Coverage
Automation Coverage
Risk Coverage
```

---

# 68. AI测试设计质量指标

平台核心指标不应该只是：

```text
AI生成用例数量
```

而应该是：

```text
Story质量
TestPoint覆盖率
TestScenario覆盖率
Case质量
需求覆盖率
风险覆盖率
自动化覆盖率
AI建议采纳率
人工修改率
AI重新生成次数
测试缺口关闭率
```

---

# 69. 人机协同指标

重点统计：

```text
AI首次通过率
AI Review发现问题数量
人工修改率
AI建议采纳率
人工驳回率
AI重新生成次数
Quality Gate通过率
```

这些数据最终可以反向优化Prompt和Agent。

---

# 70. TDD设计

核心领域逻辑采用TDD。

重点测试：

```text
Requirement生命周期
Story拆解状态
Story Review状态
Quality Gate
InformationGap
TestPoint层级
TestPoint Review
Scenario关联
GeneratedCase
CaseBinding
Coverage计算
TestGap
```

例如：

```text
Given Story存在Critical InformationGap

When 提交确认

Then QualityGate必须为BLOCKED
```

---

# 71. DDD设计

核心领域采用：

```text
Controller
 ↓
Application Service
 ↓
Domain
 ↓
Repository
```

Controller禁止直接操作数据库。

---

# 72. MVP规划

## MVP-1：测试设计基础

实现：

```text
Project
Branch
Requirement
RequirementSource
RequirementAnalysis
Story
StoryReview
InformationGap
```

目标：

> 打通 Requirement → Story → Review → Human Confirm。

---

## MVP-2：测试点设计

实现：

```text
TestPoint
TestPointReview
QualityGate
```

目标：

> 打通 Story → TestPoint → Review → 迭代确认。

---

## MVP-3：测试用例

实现：

```text
TestScenario
GeneratedCase
CaseReview
TestStrategy
```

目标：

> 打通 TestPoint → Scenario → Case。

---

## MVP-4：自动化

实现：

```text
CaseBinding
TestCaseDefinition
TestTask
Execution
ExecutionResult
```

目标：

> 打通测试设计 → 自动化执行。

---

## MVP-5：质量闭环

实现：

```text
Coverage
Risk
TestGap
AI补测
```

最终形成：

```text
需求
 ↓
测试设计
 ↓
自动化
 ↓
执行
 ↓
覆盖率
 ↓
缺口
 ↓
AI补测
```

---

# 73. 最终产品形态

最终系统不是：

> AI测试用例生成器

而是：

> **AI QA Agent 测试设计与质量决策平台。**

核心能力：

```text
Understand
理解需求

Decompose
拆解Story

Evaluate
评估测试设计质量

Collaborate
与产品/测试协同

Generate
生成测试资产

Execute
执行自动化测试

Analyze
分析质量数据

Improve
持续补充测试
```

最终形成：

```text
                    AI QA Agent

                       需求
                        ↓
                    AI理解
                        ↓
                    Story拆解
                        ↓
                 ┌── Story Review
                 │
                 ↓
              人工确认
                 │
                 ↓
               TestPoint
                 ↓
             TestPoint Review
                 ↓
              人工确认
                 ↓
             TestScenario
                 ↓
              TestCase
                 ↓
             Case Review
                 ↓
             Automation
                 ↓
              Execution
                 ↓
          Coverage / Risk
                 ↓
              Test Gap
                 ↓
              AI补测
                 │
                 └────────────→ TestPoint
```

---

# 74. 核心产品原则总结

整个系统遵循五个原则：

### 原则一：先理解，再测试

```text
Requirement
 ↓
Story
 ↓
TestPoint
```

---

### 原则二：AI生成不是终点

```text
Generate
 ↓
Review
 ↓
Improve
```

---

### 原则三：业务事实由人确认

```text
AI推测
 ↓
提出问题
 ↓
产品确认
 ↓
AI重新生成
```

---

### 原则四：测试质量逐层建立

```text
Story Quality
 ↓
TestPoint Quality
 ↓
Scenario Quality
 ↓
Case Quality
```

---

### 原则五：执行结果反哺测试设计

```text
Execution
 ↓
Coverage
 ↓
Gap
 ↓
AI补测
 ↓
TestPoint
```

---

# 75. 最终核心闭环

```text
             ┌──────────────────────────┐
             │       Requirement        │
             └────────────┬─────────────┘
                          ↓
                   AI Requirement
                     Analysis
                          ↓
                     Story生成
                          ↓
                   Story AI Review
                          ↓
                产品 + 测试人工确认
                          ↓
                     Story确认
                          ↓
                  TestPoint生成
                          ↓
                 TestPoint AI Review
                          ↓
                    测试工程师确认
                          ↓
                  TestScenario生成
                          ↓
                  GeneratedCase生成
                          ↓
                    Case AI Review
                          ↓
                    测试策略决策
                          ↓
                    自动化实现
                          ↓
                      执行
                          ↓
               ┌──────────┴──────────┐
               ↓                     ↓
            Coverage                Risk
               │                     │
               └──────────┬──────────┘
                          ↓
                       TestGap
                          ↓
                       AI补测
                          ↓
                     TestPoint
                          │
                          └───────────────┐
                                          ↓
                                  持续质量闭环
```

**最终目标不是让 AI 一次生成“正确答案”，而是让 AI、产品经理、测试工程师共同经过多个质量门，把一个模糊需求逐步加工成可信、可追溯、可执行、可度量的测试资产。**