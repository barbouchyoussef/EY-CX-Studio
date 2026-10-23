'use client';

import { useEffect, useRef, useState } from "react";
import { motion, useSpring, useTransform, type SpringOptions } from "framer-motion";
import clsx from "clsx";

type SpotlightProps = {
  className?: string;
  size?: number;
  springOptions?: SpringOptions;
};

export function Spotlight({
  className,
  size = 240,
  springOptions = { bounce: 0, stiffness: 120, damping: 18 },
}: SpotlightProps) {
  const markerRef = useRef<HTMLDivElement>(null);
  const [isHovered, setIsHovered] = useState(false);
  const [parentElement, setParentElement] = useState<HTMLElement | null>(null);

  const mouseX = useSpring(0, springOptions);
  const mouseY = useSpring(0, springOptions);

  const spotlightLeft = useTransform(mouseX, (x) => `${x - size / 2}px`);
  const spotlightTop = useTransform(mouseY, (y) => `${y - size / 2}px`);

  useEffect(() => {
    const parent = markerRef.current?.parentElement ?? null;
    if (!parent) return;
    parent.style.position = parent.style.position || "relative";
    parent.style.overflow = "hidden";
    setParentElement(parent);
  }, []);

  useEffect(() => {
    if (!parentElement) return;

    const handleMouseMove = (event: MouseEvent) => {
      const { left, top } = parentElement.getBoundingClientRect();
      mouseX.set(event.clientX - left);
      mouseY.set(event.clientY - top);
    };
    const handleMouseEnter = () => setIsHovered(true);
    const handleMouseLeave = () => setIsHovered(false);

    parentElement.addEventListener("mousemove", handleMouseMove);
    parentElement.addEventListener("mouseenter", handleMouseEnter);
    parentElement.addEventListener("mouseleave", handleMouseLeave);

    return () => {
      parentElement.removeEventListener("mousemove", handleMouseMove);
      parentElement.removeEventListener("mouseenter", handleMouseEnter);
      parentElement.removeEventListener("mouseleave", handleMouseLeave);
    };
  }, [mouseX, mouseY, parentElement]);

  return (
    <motion.div
      ref={markerRef}
      className={clsx(
        "pointer-events-none absolute rounded-full bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.92),rgba(241,245,249,0.88),rgba(191,219,254,0.38),transparent_78%)] blur-2xl transition-opacity duration-300",
        isHovered ? "opacity-100" : "opacity-0",
        className
      )}
      style={{
        width: size,
        height: size,
        left: spotlightLeft,
        top: spotlightTop,
      }}
    />
  );
}

