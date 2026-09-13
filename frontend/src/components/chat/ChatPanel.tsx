import { useEffect, useRef, useState } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import rehypeSanitize from "rehype-sanitize"
import { ImagePlus, Send, Wrench } from "lucide-react"
import { cn } from "@/lib/utils"
import { loadDemo, sendChatText, sendImage } from "@/lib/actions"
import { useAppStore } from "@/store/app"
import type { ChatMessage } from "@/lib/types"

function Bubble({ msg }: { msg: ChatMessage }) {
  if (msg.role === "system") {
    return (
      <div className="flex justify-center">
        <div className="rounded-md bg-muted px-3 py-1 text-xs text-muted-foreground">
          {msg.content}
        </div>
      </div>
    )
  }

  const isUser = msg.role === "user"
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[78%] rounded-xl px-4 py-3 text-sm leading-relaxed shadow-sm",
          isUser
            ? "bg-primary text-primary-foreground"
            : "border bg-card",
        )}
      >
        {msg.image && (
          <img
            src={msg.image}
            alt=""
            className="mb-2 block max-h-48 rounded-md"
          />
        )}

        {msg.toolCalls && msg.toolCalls.length > 0 && (
          <div className="mb-2 flex flex-col gap-1">
            {msg.toolCalls.map((t, i) => (
              <div
                key={i}
                className="flex items-center gap-2 rounded-md border border-primary/20 bg-accent/40 px-2.5 py-1.5 text-xs text-muted-foreground"
              >
                <Wrench className="h-3.5 w-3.5 text-primary" />
                <span className="font-mono text-primary">{t.name}</span>
                <span className="ml-auto text-[10px]">
                  {t.status === "running" ? "执行中…" : "完成"}
                </span>
              </div>
            ))}
          </div>
        )}

        {isUser ? (
          <div className="whitespace-pre-wrap break-words">{msg.content}</div>
        ) : (
          <div className="prose prose-sm max-w-none prose-p:my-1 prose-pre:bg-muted prose-pre:text-foreground prose-code:text-primary">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeSanitize]}
            >
              {msg.content || (msg.streaming ? "▍" : "")}
            </ReactMarkdown>
            {msg.streaming && msg.content && (
              <span className="animate-pulse text-primary">▍</span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function EmptyState() {
  const setView = useAppStore((s) => s.setView)
  return (
    <div className="flex h-full flex-col items-center justify-center text-center">
      <div className="relative flex h-24 w-24 items-center justify-center rounded-3xl bg-gradient-to-br from-primary to-[#5b8def] text-white shadow-lg shadow-primary/25">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.2"
          className="h-11 w-11"
        >
          <rect x="3" y="4" width="18" height="14" rx="2" />
          <path d="M3 9h18M8 20h8M12 18v2" />
        </svg>
      </div>
      <div className="mt-5 text-[28px] font-extrabold tracking-tight">
        开始你的 <span className="text-primary">EDA</span> 审查
      </div>
      <div className="mt-2 text-sm text-muted-foreground">
        输入指令，或从功能卡片选择一项开始
      </div>
      <div className="mt-6 flex gap-2">
        <button
          onClick={() => loadDemo()}
          className="rounded-full bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/80"
        >
          一键演示
        </button>
        <button
          onClick={() => setView("bom")}
          className="rounded-full border px-4 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:border-primary hover:text-primary"
        >
          导入 BOM
        </button>
      </div>
    </div>
  )
}

export function ChatPanel() {
  const messages = useAppStore((s) => s.messages)
  const isStreaming = useAppStore((s) => s.isStreaming)
  const [input, setInput] = useState("")
  const [image, setImage] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  function send() {
    const text = input.trim()
    if (!text && !image) return
    if (image) sendImage(text || "分析这张图片", image)
    else sendChatText(text)
    setInput("")
    setImage(null)
    if (fileRef.current) fileRef.current.value = ""
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (!f) return
    const reader = new FileReader()
    reader.onload = () => setImage(reader.result as string)
    reader.readAsDataURL(f)
  }

  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto px-8 py-6">
        {messages.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="mx-auto max-w-3xl space-y-4">
            {messages.map((m) => (
              <Bubble key={m.id} msg={m} />
            ))}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="shrink-0 border-t bg-background px-8 py-4">
        {image && (
          <div className="mb-2 flex items-center gap-2">
            <img src={image} alt="预览" className="h-14 rounded-md border object-contain" />
            <button
              onClick={() => setImage(null)}
              className="flex h-5 w-5 items-center justify-center rounded-full bg-destructive text-white"
            >
              ✕
            </button>
          </div>
        )}
        <div className="flex items-end gap-2">
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={onFile}
          />
          <button
            onClick={() => fileRef.current?.click()}
            title="添加图片"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border text-muted-foreground transition-colors hover:border-primary hover:text-primary"
          >
            <ImagePlus className="h-4 w-4" />
          </button>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            placeholder="输入审查指令或问题… (Enter 发送, Shift+Enter 换行)"
            className="max-h-40 min-h-10 flex-1 resize-none rounded-xl border bg-background px-3.5 py-2.5 text-sm leading-relaxed outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/20"
          />
          <button
            onClick={send}
            disabled={isStreaming}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-colors hover:bg-primary/80 disabled:opacity-40"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
