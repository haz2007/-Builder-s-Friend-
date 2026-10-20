import { useEffect, useRef, useState } from "react";

type Props = {
  value: number;
  /** Длительность отсчёта, мс */
  duration?: number;
};

/** Число «досчитывается» от нуля, когда появляется на экране. */
export default function CountUp({ value, duration = 1200 }: Props) {
  const ref = useRef<HTMLSpanElement>(null);
  const [current, setCurrent] = useState(0);

  useEffect(() => {
    const element = ref.current;
    if (!element || value <= 0) return;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let frame = 0;

    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      observer.disconnect();

      if (reduceMotion) {
        setCurrent(value);
        return;
      }

      const start = performance.now();
      const tick = (now: number) => {
        const progress = Math.min(1, (now - start) / duration);
        // ease-out: быстро в начале, плавно в конце
        const eased = 1 - Math.pow(1 - progress, 3);
        setCurrent(Math.round(value * eased));
        if (progress < 1) frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
    });

    observer.observe(element);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [value, duration]);

  return <span ref={ref}>{current}</span>;
}
