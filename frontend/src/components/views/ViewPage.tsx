import { VIEWS } from "@/config/views"
import { dispatchAction } from "@/lib/actions"
import { useAppStore } from "@/store/app"
import { Button } from "@/components/ui/button"

export function ViewPage() {
  const view = useAppStore((s) => s.view)
  const cfg = VIEWS[view]
  if (!cfg) return null

  return (
    <div className="mx-auto max-w-5xl px-10 py-8">
      <div className="mb-7 max-w-2xl">
        <h1 className="text-[28px] font-extrabold leading-tight tracking-tight">
          {cfg.title}
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          {cfg.subtitle}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {cfg.metrics.map((m) => (
          <div
            key={m.label}
            className="flex items-center gap-3 rounded-xl border bg-card p-4 shadow-sm transition-shadow hover:shadow-md"
          >
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent text-primary">
              <m.icon className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <div className="text-2xl font-extrabold leading-none tracking-tight">
                {m.num}
              </div>
              <div className="mt-1 truncate text-xs text-muted-foreground">
                {m.label}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-6 flex gap-2.5">
        {cfg.actions.map((a) => (
          <Button
            key={a.label}
            variant={a.primary ? "default" : "outline"}
            onClick={() => dispatchAction(a.action)}
          >
            {a.label}
          </Button>
        ))}
      </div>

      <div className="mt-7 grid grid-cols-2 gap-3 sm:grid-cols-3">
        {cfg.items.map((it) => (
          <button
            key={it.title}
            onClick={() => dispatchAction(it.action)}
            className="group flex flex-col gap-1.5 rounded-xl border bg-card p-5 text-left shadow-sm transition-all duration-150 hover:-translate-y-0.5 hover:border-primary hover:shadow-md"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
              <it.icon className="h-5 w-5" />
            </div>
            <div className="mt-1.5 text-[15px] font-semibold tracking-tight">
              {it.title}
            </div>
            <div className="text-xs leading-relaxed text-muted-foreground">
              {it.desc}
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
