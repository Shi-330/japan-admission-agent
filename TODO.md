# Frontend Refactor TODO

> Branch: feat/refactor-frontend | Started: 2026-07-08

## Done
- [x] CSS variable theme system (zinc-based, shadcn compatible)
- [x] shadcn/ui components: Button, Card, Input, Tabs
- [x] Vite @ alias
- [x] All `<button>` → `<Button>`
- [x] Tab bar → Radix Tabs
- [x] Login page → Button + Input

## Component Migration
- [x] Plaza cards → Card/CardContent
- [x] Per-school tracking cards → Card/CardContent
- [x] All `<input>` → `<Input>`
- [ ] All `<select>` → styled select or shadcn Select
- [ ] `<textarea>` where applicable → Input

## Dialogs & Overlays
- [ ] confirm() → Dialog component (delete confirmation, etc.)
- [ ] Add school form → Dialog/Sheet
- [ ] Profile edit → Sheet (slide-out)

## Polish
- [ ] Remove all hardcoded hex colors → semantic classes
- [ ] Calendar → date-fns + hand-written grid (remove inline IIFE)
- [ ] AnimatePresence on tab content switch
- [ ] Card hover → Framer Motion spring
- [ ] Toast → shadcn Sonner or custom toast component
- [ ] Stage tag colors → CSS variable-based variants
- [ ] Chat bubbles → variant styling

## Later
- [ ] Dark mode toggle
- [ ] Responsive sidebar
- [ ] Loading skeletons
