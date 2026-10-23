'use client';

import { Suspense, lazy, useEffect, useRef, useState } from "react";

const Spline = lazy(() => import("@splinetool/react-spline"));

interface SplineSceneProps {
  scene: string;
  className?: string;
}

function SplineLoader() {
  return (
    <div className="flex h-full w-full items-center justify-center">
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="h-18 w-18 animate-pulse rounded-full bg-[radial-gradient(circle_at_30%_30%,rgba(255,255,255,0.96),rgba(219,234,254,0.82),rgba(255,255,255,0.18))] shadow-[0_18px_40px_rgba(148,163,184,0.25)]" />
        <div className="text-[11px] font-medium uppercase tracking-[0.22em] text-slate-500">Loading robot</div>
      </div>
    </div>
  );
}

export function SplineScene({ scene, className }: SplineSceneProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isIntersecting, setIsIntersecting] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsIntersecting(entry.isIntersecting);
      },
      {
        root: null, // viewport
        rootMargin: "300px", // load 300px before it enters the viewport
        threshold: 0.01,
      }
    );

    if (containerRef.current) {
      observer.observe(containerRef.current);
    }

    return () => {
      observer.disconnect();
    };
  }, []);

  return (
    <div ref={containerRef} className={className} style={{ width: "100%", height: "100%" }}>
      {isIntersecting ? (
        <Suspense fallback={<SplineLoader />}>
          <Spline scene={scene} className="h-full w-full" />
        </Suspense>
      ) : (
        <SplineLoader />
      )}
    </div>
  );
}
