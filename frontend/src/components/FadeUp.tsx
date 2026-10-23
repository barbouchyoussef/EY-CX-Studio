import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

type FadeUpProps = {
  children: ReactNode;
  delay?: string;
  className?: string;
};

export default function FadeUp({ children, delay = "", className = "" }: FadeUpProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    const observer = new IntersectionObserver(
      entries => {
        if (entries[0]?.isIntersecting) {
          setInView(true);
          observer.disconnect();
        }
      },
      { threshold: 0.16 }
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={ref} className={`fade-up ${delay} ${inView ? "fade-up--in" : ""} ${className}`.trim()}>
      {children}
    </div>
  );
}

