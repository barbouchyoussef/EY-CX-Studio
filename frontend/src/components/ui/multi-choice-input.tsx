import { useState } from "react";
import { motion } from "framer-motion";

type Props = {
  options: string[];
  disabled: boolean;
  onSelect: (text: string) => void;
};

export default function MultiChoiceOptions({ options, disabled, onSelect }: Props) {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  if (!options || options.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className="w-full"
    >
      <div className="divide-y divide-slate-100">
          {options.map((option, idx) => (
            <button
              key={idx}
              type="button"
              disabled={disabled}
              onClick={() => onSelect(option)}
              onMouseEnter={() => setHoveredIdx(idx)}
              onMouseLeave={() => setHoveredIdx(null)}
              className="group flex w-full items-center gap-4 px-6 py-4 text-left transition-colors duration-150 hover:bg-violet-50/50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <span
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[13px] font-bold transition-all duration-150 ${
                  hoveredIdx === idx
                    ? "bg-violet-500 text-white shadow-md shadow-violet-200"
                    : "bg-violet-50 text-violet-500"
                }`}
              >
                {idx + 1}
              </span>
              <span className="text-[17px] leading-relaxed text-slate-700 group-hover:text-slate-900">
                {option}
              </span>
            </button>
          ))}
      </div>
    </motion.div>
  );
}
