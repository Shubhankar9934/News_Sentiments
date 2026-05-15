## WebSocket testing (Postman)

Postman supports WebSocket requests (New → WebSocket Request).

1. URL: `ws://localhost:8000/api/v1/ws/research-progress`
2. Connect, then send text payload:

```json
{ "action": "run", "ticker": "NVDA", "days": 7 }
```

3. You should receive JSON messages with `type: "progress"` and a final `type: "result"` containing the report.
