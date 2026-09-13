// SSE 流式客户端 — POST /api/v1/chat/stream，逐事件解析

export interface StreamEvent {
  event: string // "token" | "tool_call" | "done" | "error"
  data: string
}

export async function* streamChat(
  text: string,
  agentMode: boolean,
): AsyncGenerator<StreamEvent> {
  const res = await fetch("/api/v1/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, agent_mode: agentMode }),
  })

  if (!res.ok || !res.body) {
    throw new Error(`HTTP ${res.status}`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const lines = buffer.split("\n")
    buffer = lines.pop() ?? ""

    let event = "message"
    let dataLines: string[] = []

    for (const line of lines) {
      if (line.startsWith("event:")) {
        event = line.slice(6).trim()
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim())
      } else if (line === "") {
        if (dataLines.length > 0) {
          yield { event, data: dataLines.join("\n") }
        }
        event = "message"
        dataLines = []
      }
    }
  }
}
