# 测试执行页面修改计划

## 需求分析

用户需要对测试执行页面进行以下修改：

1. **中文本地化**：将页面上的按钮和文字描述改成必要的中文
2. **任务管理模式**：从单任务执行改为多任务管理模式

   * 支持创建测试任务

   * 支持单个任务执行/停止

   * 支持全部任务执行

   * 点击任务展示任务中的测试用例及其执行状态

## 当前代码分析

### 文件结构

| 文件                                     | 说明                                             |
| -------------------------------------- | ---------------------------------------------- |
| `src/components/TestExecutionView.vue` | 当前测试执行页面（单任务模式）                                |
| `src/components/TestOverviewView.vue`  | 用例总览页面，通过 `runSelected`/`runAll` 事件传递选中的用例 UID |
| `src/App.vue`                          | 主应用组件，处理跨页面状态传递                                |
| `src/types.ts`                         | 类型定义                                           |
| `src/composables/useApi.ts`            | API 请求封装                                       |
| `src/composables/useWebSocket.ts`      | WebSocket 连接封装                                 |

### 当前数据流

```
TestOverviewView (选中用例) -> App.vue (selectedUids) -> TestExecutionView (接收并执行)
```

### 存在的问题

1. 当前只能执行一次测试，不支持任务管理
2. 页面文字大部分是英文，需要中文本地化
3. 缺少任务列表和任务状态管理

## 实现方案

### 1. 类型扩展

在 `src/types.ts` 中添加任务相关类型定义：

```typescript
export interface TestTask {
  id: string;
  name: string;
  status: 'idle' | 'running' | 'done' | 'stopped' | 'error';
  uids: string[];
  total: number;
  passed: number;
  failed: number;
  broken: number;
  skipped: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}
```

### 2. 页面结构重构

修改 `TestExecutionView.vue`，采用类似 `TestReportsView.vue` 的左右布局：

* **左侧**：任务列表

  * 显示所有创建的测试任务

  * 支持筛选（全部/运行中/已完成）

  * 支持操作按钮（执行/停止）

* **右侧**：任务详情

  * 显示选中任务的基本信息和统计

  * 显示任务中的测试用例列表及其执行状态

  * 支持查看单个用例的日志详情

### 3. 中文本地化

将以下内容改为中文：

| 英文原文                                                   | 中文翻译                          |
| ------------------------------------------------------ | ----------------------------- |
| SELECTED CASES                                         | 已选用例                          |
| PENDING                                                | 待执行                           |
| Sequential                                             | 串行                            |
| Parallel                                               | 并行                            |
| Concurrency                                            | 并发数                           |
| Stop                                                   | 停止                            |
| Start Execution                                        | 开始执行                          |
| Executing...                                           | 执行中...                        |
| Execution Progress                                     | 执行进度                          |
| Pass Rate                                              | 通过率                           |
| Elapsed Time                                           | 耗时                            |
| Total                                                  | 总数                            |
| Passed                                                 | 通过                            |
| Failed                                                 | 失败                            |
| Broken                                                 | 异常                            |
| Skipped                                                | 跳过                            |
| Execution Queue                                        | 执行队列                          |
| All / Running / Failed / Passed / Pending              | 全部 / 运行中 / 失败 / 通过 / 待执行      |
| Description                                            | 描述                            |
| Error Message                                          | 错误信息                          |
| Stack Trace                                            | 堆栈信息                          |
| Execution Logs                                         | 执行日志                          |
| Duration                                               | 耗时                            |
| PENDING / RUNNING / PASSED / FAILED / BROKEN / SKIPPED | 待执行 / 运行中 / 通过 / 失败 / 异常 / 跳过 |

### 4. 数据流调整

```
TestOverviewView (选中用例) -> App.vue (selectedUids) -> TestExecutionView (创建新任务)
```

修改 `TestExecutionView.vue`：

* 接收 `selectedUids` 时，自动创建一个新任务

* 任务存储在本地状态中，支持多任务管理

### 5. 关键功能实现

#### 5.1 任务创建

```typescript
function createTask(uids: string[]) {
  const task: TestTask = {
    id: Date.now().toString(),
    name: `测试任务 ${Date.now()}`,
    status: 'idle',
    uids,
    total: uids.length,
    passed: 0,
    failed: 0,
    broken: 0,
    skipped: 0,
    created_at: new Date().toISOString(),
  };
  tasks.value.push(task);
  selectedTaskId.value = task.id;
}
```

#### 5.2 任务执行

```typescript
async function executeTask(taskId: string) {
  const task = tasks.value.find(t => t.id === taskId);
  if (!task || task.status === 'running') return;
  
  task.status = 'running';
  task.started_at = new Date().toISOString();
  
  // 初始化用例状态
  const caseStates: Record<string, TestCaseState> = {};
  for (const uid of task.uids) {
    caseStates[uid] = { uid, status: 'pending', ... };
  }
  taskCaseStates[taskId] = caseStates;
  
  // 调用后端 API
  const data = await post('/run', { uids: task.uids, ... });
  
  // 连接 WebSocket 监听进度
  connect(data.run_id);
  
  // 更新任务关联的 run_id
  task.run_id = data.run_id;
}
```

#### 5.3 WebSocket 消息处理

修改 WebSocket 消息处理逻辑，根据 run\_id 分发到对应的任务和用例：

```typescript
onMessage((msg: any) => {
  if (msg.type === 'test_result') {
    // 找到对应的任务
    const task = tasks.value.find(t => t.run_id === msg.run_id);
    if (task && taskCaseStates[task.id]) {
      const caseState = taskCaseStates[task.id][msg.uid];
      if (caseState) {
        caseState.status = msg.status;
      }
    }
  } else if (msg.type === 'suite_progress') {
    const task = tasks.value.find(t => t.run_id === msg.run_id);
    if (task) {
      task.passed = msg.passed;
      task.failed = msg.failed;
      task.broken = msg.broken;
      task.skipped = msg.skipped;
      task.completed = msg.completed;
    }
  } else if (msg.type === 'run_complete') {
    const task = tasks.value.find(t => t.run_id === msg.run_id);
    if (task) {
      task.status = 'done';
      task.completed_at = new Date().toISOString();
    }
  }
});
```

#### 5.4 停止任务

```typescript
async function stopTask(taskId: string) {
  const task = tasks.value.find(t => t.id === taskId);
  if (!task || task.status !== 'running') return;
  
  closeWs();
  if (task.run_id) {
    await post(`/run/${task.run_id}/stop`);
  }
  
  task.status = 'stopped';
  task.completed_at = new Date().toISOString();
  
  // 重置该任务下所有用例状态
  if (taskCaseStates[taskId]) {
    for (const uid in taskCaseStates[taskId]) {
      if (taskCaseStates[taskId][uid].status === 'running') {
        taskCaseStates[taskId][uid].status = 'pending';
      }
    }
  }
}
```

#### 5.5 执行全部任务

```typescript
async function executeAllTasks() {
  const idleTasks = tasks.value.filter(t => t.status === 'idle');
  for (const task of idleTasks) {
    await executeTask(task.id);
  }
}
```

## 文件修改清单

| 文件                                     | 修改类型 | 说明                 |
| -------------------------------------- | ---- | ------------------ |
| `src/types.ts`                         | 添加   | 添加 `TestTask` 接口定义 |
| `src/components/TestExecutionView.vue` | 重写   | 重构为多任务管理模式，添加中文本地化 |
| `src/App.vue`                          | 修改   | 可能需要调整状态传递逻辑       |

## 潜在风险与注意事项

1. **WebSocket 并发问题**：当前 WebSocket 只支持单个连接，多任务并发执行时需要考虑连接管理
2. **内存管理**：任务列表和用例状态会占用内存，需要考虑清理机制
3. **后端 API 支持**：当前后端 `/run` 接口只支持单次执行，需要确认是否支持多任务并发
4. **状态同步**：任务状态和用例状态需要正确同步，避免数据不一致

## 测试验证

1. 从用例总览选择用例后，点击"执行选中"或"执行全部"，验证测试执行页面是否自动创建新任务
2. 验证任务列表显示正确，支持筛选
3. 验证单个任务执行/停止功能正常
4. 验证全部任务执行功能正常
5. 验证点击任务后，右侧显示任务中的测试用例及其执行状态
6. 验证中文显示正确

