"use client"

// Adapted from 21st.dev "modern-animated-hero-section" (RainingLetters + ScrambledTitle).
// Vite/Dolos changes: glyph and .dud styles live in index.css (no styled-jsx), phrases and
// children are props, the rain moves through refs instead of per-frame React state, every
// loop is cleaned up on unmount, and prefers-reduced-motion freezes both effects.

import { useEffect, useRef, type ReactNode } from "react"
import { useReducedMotion } from "framer-motion"

const GLYPHS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-=[]{}|;:,.<>?ΔΘΛΞΠΣΦΨΩ"
const pick = () => GLYPHS[Math.floor(Math.random() * GLYPHS.length)]
const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")

interface QueueItem { from: string; to: string; start: number; end: number; char?: string }

export class TextScramble {
  el: HTMLElement
  chars = "!<>-_\\/[]{}—=+*^?#ΔΛΞΣΨΩ"
  queue: QueueItem[] = []
  frame = 0
  frameRequest = 0
  resolve: () => void = () => {}

  constructor(el: HTMLElement) {
    this.el = el
    this.update = this.update.bind(this)
  }

  setText(newText: string) {
    const oldText = this.el.innerText
    const length = Math.max(oldText.length, newText.length)
    const promise = new Promise<void>((resolve) => (this.resolve = resolve))
    this.queue = []
    for (let i = 0; i < length; i++) {
      const start = Math.floor(Math.random() * 40)
      this.queue.push({ from: oldText[i] || "", to: newText[i] || "", start, end: start + Math.floor(Math.random() * 40) })
    }
    cancelAnimationFrame(this.frameRequest)
    this.frame = 0
    this.update()
    return promise
  }

  cancel() {
    cancelAnimationFrame(this.frameRequest)
  }

  update() {
    let output = ""
    let complete = 0
    for (const q of this.queue) {
      if (this.frame >= q.end) {
        complete++
        output += esc(q.to)
      } else if (this.frame >= q.start) {
        if (!q.char || Math.random() < 0.28) q.char = this.chars[Math.floor(Math.random() * this.chars.length)]
        output += `<span class="dud">${esc(q.char)}</span>`
      } else {
        output += esc(q.from)
      }
    }
    this.el.innerHTML = output
    if (complete === this.queue.length) {
      this.resolve()
    } else {
      this.frameRequest = requestAnimationFrame(this.update)
      this.frame++
    }
  }
}

function ScrambledTitle({ phrases, label, still }: { phrases: string[]; label: string; still: boolean }) {
  const ref = useRef<HTMLHeadingElement>(null)
  const key = phrases.join("\u0000")

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const list = key.split("\u0000")
    if (still || list.length < 2) {
      el.textContent = list[0]
      return
    }
    const fx = new TextScramble(el)
    let i = 0
    let timer = 0
    let alive = true
    const next = () => {
      fx.setText(list[i]).then(() => {
        if (alive) timer = window.setTimeout(next, 2200)
      })
      i = (i + 1) % list.length
    }
    next()
    return () => {
      alive = false
      window.clearTimeout(timer)
      fx.cancel()
    }
  }, [key, still])

  return (
    <h1
      ref={ref}
      aria-label={label}
      className="font-mono font-extrabold text-text tracking-[0.14em] leading-none whitespace-nowrap text-[clamp(3.25rem,12vw,6rem)]"
    >
      {phrases[0]}
    </h1>
  )
}

function Rain({ still }: { still: boolean }) {
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = box.current
    if (!el) return
    let W = el.clientWidth
    let H = el.clientHeight
    const count = Math.max(40, Math.min(300, Math.round((W * H) / 4300)))
    const nodes: HTMLSpanElement[] = []
    const drops = Array.from({ length: count }, () => ({ x: Math.random() * 100, y: Math.random() * 100, speed: 0.1 + Math.random() * 0.3 }))
    const frag = document.createDocumentFragment()
    for (let i = 0; i < count; i++) {
      const span = document.createElement("span")
      span.className = "rain-glyph"
      span.textContent = pick()
      nodes.push(span)
      frag.appendChild(span)
    }
    el.appendChild(frag)

    const place = (i: number) => {
      const d = drops[i]
      nodes[i].style.transform = `translate3d(${(d.x / 100) * W}px, ${(d.y / 100) * H}px, 0) translate(-50%, -50%)`
    }
    for (let i = 0; i < count; i++) place(i)

    const ro = new ResizeObserver(() => {
      W = el.clientWidth
      H = el.clientHeight
      for (let i = 0; i < count; i++) place(i)
    })
    ro.observe(el)
    if (still) {
      return () => {
        ro.disconnect()
        nodes.forEach((n) => n.remove())
      }
    }

    // Fall only while the hero is on screen.
    let raf = 0
    let last = 0
    let visible = true
    const tick = (now: number) => {
      if (!visible) {
        raf = 0
        return
      }
      const step = last ? Math.min(3, (now - last) / 16.67) : 1
      last = now
      for (let i = 0; i < count; i++) {
        const d = drops[i]
        d.y += d.speed * step
        if (d.y >= 100) {
          d.y = -5
          d.x = Math.random() * 100
          nodes[i].textContent = pick()
        }
        place(i)
      }
      raf = requestAnimationFrame(tick)
    }
    const io = new IntersectionObserver(([e]) => {
      visible = e.isIntersecting
      if (visible && !raf) {
        last = 0
        raf = requestAnimationFrame(tick)
      }
    })
    io.observe(el)
    raf = requestAnimationFrame(tick)

    let lit: number[] = []
    const flicker = window.setInterval(() => {
      if (!visible) return
      lit.forEach((i) => nodes[i].classList.remove("on"))
      lit = Array.from({ length: 3 + Math.floor(Math.random() * 3) }, () => Math.floor(Math.random() * count))
      lit.forEach((i) => nodes[i].classList.add("on"))
    }, 50)

    return () => {
      cancelAnimationFrame(raf)
      window.clearInterval(flicker)
      io.disconnect()
      ro.disconnect()
      nodes.forEach((n) => n.remove())
    }
  }, [still])

  return <div ref={box} aria-hidden className="absolute inset-0 overflow-hidden pointer-events-none select-none" />
}

const DEFAULT_PHRASES = ["DOLOS", "ΔΟΛΟΣ"]

export default function RainingLetters({
  phrases = DEFAULT_PHRASES,
  label = "Dolos",
  children,
  className = "",
}: {
  phrases?: string[]
  label?: string
  children?: ReactNode
  className?: string
}) {
  const still = !!useReducedMotion()
  return (
    <div className={`relative w-full min-h-[100svh] bg-bg overflow-hidden ${className}`}>
      <Rain still={still} />
      {/* Readability scrim behind the copy, and a fade into the next section. */}
      <div aria-hidden className="absolute inset-0 z-10 bg-[radial-gradient(ellipse_at_center,rgba(3,6,4,.94)_0%,rgba(3,6,4,.72)_38%,rgba(3,6,4,0)_72%)]" />
      <div aria-hidden className="absolute inset-x-0 bottom-0 z-10 h-40 bg-gradient-to-b from-transparent to-bg" />
      <div className="relative z-20 min-h-[100svh] flex flex-col items-center justify-center px-4 py-24">
        <ScrambledTitle phrases={phrases} label={label} still={still} />
        {children}
      </div>
    </div>
  )
}
