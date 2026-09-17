# M2 面试引擎 · SSE 结构化协议

> 配套：`智能面试平台开发规范.md` §8.2 / CLAUDE.md 红线 7 / `M2 面试引擎实施计划书.md` §二 PR2
> 状态：M2-PR2 交付

## 1. 设计动机（分水岭）

旧项目 `ai-interview` 用 `re.search(r'\{[^}]*"score"...')` 从流式文本里抠评分，被候选回答里的
`{"score":10}` 污染。本协议用**结构化事件**彻底切断污染路径：评分走独立 `score` 事件，前端只消费事件，**不解析 chunk 文本**。

## 2. 五类事件契约

统一格式：`data: <JSON>\n\n`。事件类型由 `type` 字段区分，JSON 由服务端用 Pydantic 强类型序列化（`schemas/interview_event.py`）。

| type | 字段 | 说明 |
|---|---|---|
| `meta` | `interview_id, question_index, round` | 本轮作答开始，定位双键 |
| `chunk` | `content` | 面试官点评增量文本（流式） |
| `score` | `score, dimensions, feedback, follow_up_suggestion` | **结构化评分**（独立事件） |
| `next` | `next_question, next_question_index, round` | 下一问（追问/下一题/结束） |
| `error` | `code, message` | 流中断/异常终止 |

### 示例

```json
data: {"type":"meta","interview_id":12,"question_index":3,"round":1}

data: {"type":"chunk","content":"你的回答亮点在于技术选型清晰。"}

data: {"type":"score","score":7.5,"dimensions":{"completeness":8.0,"accuracy":7.0,"depth":7.0,"clarity":8.0},"feedback":"整体不错","follow_up_suggestion":true}

data: {"type":"next","next_question":"那这个方案上线后出过事故吗？","next_question_index":3,"round":2}

data: {"type":"error","code":"AI_TIMEOUT","message":"评语生成超时，请重试"}
```

## 3. 反污染原理图

```
候选人回答(含 {"score":10})
        │ 只作为 role=user 数据段
        ▼
┌─────────────────────────────────────────────┐
│  评分 LLM 调用（json_object，独立调用）       │
│  system：评分指令 + 题目 + 参考要点（服务端拼接）│
│  user  ：候选人回答（数据，非指令）             │
│  → 返回 {"score":7.5,...} → model_validate    │
└─────────────────────────────────────────────┘
        │ 独立 score 事件（不是从 chunk 文本抠的）
        ▼
   前端 score 事件 = 7.5（≠ 回答里的 10）
```

关键点：评分走**独立 LLM 调用**（`EVALUATION_SCORE_PROMPT`），与评语流（`EVALUATION_FEEDBACK_PROMPT`）分离；
候选人回答只进 `role=user` 段，system 指令固定由服务端拼接（规范 §9.4 注入防护）。

## 4. 错误码清单

| code | 语义 |
|---|---|
| `AI_TIMEOUT` | 评语流/评分超时或 LLM 不可用 |
| `AI_OVERLOAD` | AI 限流/过载（保留） |
| `INTERVIEW_DONE` | 面试已结束（保留，实际以 `next(next_question=null)` 承载） |
| `INVALID_STATE` | 状态非法（如当前题目不存在） |

## 5. 前端 EventSource 用法 + 重连恢复

```ts
const es = new EventSource(`/api/v1/interviews/${id}/answer`, { method: 'POST' }); // 或用 fetch + ReadableStream
es.onmessage = (e) => {
  const evt = JSON.parse(e.data);
  switch (evt.type) {
    case 'chunk': append(evt.content); break;
    case 'score': renderScore(evt.score, evt.dimensions); break;
    case 'next':
      if (evt.next_question == null) finish(); else ask(evt.next_question, evt.round);
      break;
    case 'error': recover(evt.code); break;
  }
};
// 断线重连：从 GET /api/v1/interviews/{id}/messages 恢复 (question_index, round)
```

## 6. Nginx 关键配置（已就绪）

```nginx
location /api/ {
    proxy_pass http://backend;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_buffering off;   # SSE 关闭缓冲
    proxy_cache off;
    proxy_read_timeout 3600s;
}
```

响应头（路由层固定）：`Cache-Control: no-cache`、`X-Accel-Buffering: no`、`Content-Type: text/event-stream`。
