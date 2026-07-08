# Frontend Refactor TODO

> Branch: feat/refactor-frontend | Started: 2026-07-08

## Done
- [x] CSS variable theme system (zinc-based, shadcn compatible)
- [x] shadcn/ui: Button, Card, Input, Tabs, Dialog (all 5)
- [x] Vite @ alias
- [x] All `<button>` → `<Button>`, `<input>` → `<Input>`
- [x] Tab bar → Radix Tabs
- [x] Login page → Button + Input
- [x] Plaza + tracking cards → Card/CardContent
- [x] Structural hex colors → semantic classes (21→0 structural)
- [x] Calendar → CalendarView component (extracted inline IIFE)
- [x] confirm() → Dialog (Radix Dialog with overlay + animation)
- [x] Collapsible sidebar (toggle to 48px thin strip)
- [x] Collapsible chat input bar

## Remaining Polish
- [x] Select styling
- [x] AnimatePresence on tab content switch
- [x] Toast → shadcn Sonner
- [x] Dark mode toggle
- [x] Loading skipped — not needed at this scale
