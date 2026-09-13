import { useEffect, useRef } from "react"
import { TopBar } from "@/components/layout/TopBar"
import { RightPanel } from "@/components/layout/RightPanel"
import { ViewPage } from "@/components/views/ViewPage"
import { ChatPanel } from "@/components/chat/ChatPanel"
import { SettingsDialog } from "@/components/settings/SettingsDialog"
import { useAppStore } from "@/store/app"
import { endpoints } from "@/lib/api"

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(((reader.result as string) || "").split(",")[1] || "")
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

export default function App() {
  const showChat = useAppStore((s) => s.showChat)
  const setBom = useAppStore((s) => s.setBom)
  const setReport = useAppStore((s) => s.setReport)
  const setActivePanelTab = useAppStore((s) => s.setActivePanelTab)
  const setPanelOpen = useAppStore((s) => s.setPanelOpen)

  const bomRef = useRef<HTMLInputElement>(null)
  const pcbRef = useRef<HTMLInputElement>(null)
  const posRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail
      if (detail === "import-bom") bomRef.current?.click()
      else if (detail === "import-data") pcbRef.current?.click()
    }
    window.addEventListener("eda:import", handler)
    return () => window.removeEventListener("eda:import", handler)
  }, [])

  async function onBomFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (!f) return
    const b64 = await fileToBase64(f)
    const r = await endpoints.importBom(f.name, b64)
    if (r.ok && r.items) {
      setBom(r.items)
      setActivePanelTab("bom")
      setPanelOpen(true)
    }
    if (e.target) e.target.value = ""
  }

  async function onPcbFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (!f) return
    const b64 = await fileToBase64(f)
    const r = await endpoints.importPcb(f.name, b64)
    if (r.ok) {
      setReport(r.msg || "PCB 已导入")
      setActivePanelTab("report")
      setPanelOpen(true)
    }
    if (e.target) e.target.value = ""
  }

  async function onPosFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (!f) return
    const b64 = await fileToBase64(f)
    await endpoints.importPos(f.name, b64)
    if (e.target) e.target.value = ""
  }

  return (
    <div className="flex h-screen flex-col bg-muted/40">
      <TopBar />
      <div className="flex min-h-0 flex-1 gap-3 p-3">
        <main className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl border bg-card shadow-sm">
          {showChat ? <ChatPanel /> : <ViewPage />}
        </main>
        <RightPanel />
      </div>
      <SettingsDialog />

      <input ref={bomRef} type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={onBomFile} />
      <input ref={pcbRef} type="file" accept=".json,.epro" className="hidden" onChange={onPcbFile} />
      <input ref={posRef} type="file" accept=".csv" className="hidden" onChange={onPosFile} />
    </div>
  )
}
