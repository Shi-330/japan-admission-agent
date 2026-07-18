import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"
import { toast } from "sonner"

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

/** Clipboard copy with toast feedback. */
export function copyText(text, label) {
  navigator.clipboard.writeText(text).then(() => {
    toast.success('已复制 ' + label)
  }).catch(() => {
    toast.error('复制失败，请手动复制')
  })
}
