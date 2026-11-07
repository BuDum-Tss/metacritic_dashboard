import { useCallback, useEffect, useRef, useState } from 'react'

// A horizontally scrolling strip that snaps to its items: swiping and the wheel work natively,
// the hook adds the state the arrows and dots need.
export function useScroller() {
  const ref = useRef<HTMLDivElement>(null)
  const [state, setState] = useState({ index: 0, canPrev: false, canNext: false })

  useEffect(() => {
    const element = ref.current
    if (!element) return
    const update = () => {
      const next = {
        index: element.clientWidth ? Math.round(element.scrollLeft / element.clientWidth) : 0,
        canPrev: element.scrollLeft > 1,
        canNext: element.scrollLeft + element.clientWidth < element.scrollWidth - 1,
      }
      setState((prev) =>
        prev.index === next.index && prev.canPrev === next.canPrev && prev.canNext === next.canNext
          ? prev
          : next,
      )
    }
    update()
    element.addEventListener('scroll', update, { passive: true })
    const observer = new ResizeObserver(update)
    observer.observe(element)
    return () => {
      element.removeEventListener('scroll', update)
      observer.disconnect()
    }
  }, [])

  const scrollPage = useCallback((direction: 1 | -1, fraction = 1) => {
    const element = ref.current
    element?.scrollBy({ left: direction * element.clientWidth * fraction, behavior: 'smooth' })
  }, [])

  const scrollToIndex = useCallback((index: number) => {
    const element = ref.current
    element?.scrollTo({ left: index * element.clientWidth, behavior: 'smooth' })
  }, [])

  return { ref, ...state, scrollPage, scrollToIndex }
}
