import { useMemo } from "react";
import type { FinalReportWorkingMissingAxis, FinalReportCapabilityItem } from "../../../types/final-report";
import { STATIC_CAPABILITIES, getCanonicalCapabilityKey, getMaturityScore } from "../../../config/maturityConfig";

function getAngle(index: number, numAxes: number): number {
  return -Math.PI / 2 + (index * 2 * Math.PI) / numAxes;
}

function getCoords(centerX: number, centerY: number, distance: number, angle: number) {
  return {
    x: centerX + distance * Math.cos(angle),
    y: centerY + distance * Math.sin(angle),
  };
}

export default function MaturityRadarChart({
  axes,
  capabilities = [],
  isFrench,
}: {
  axes: FinalReportWorkingMissingAxis[];
  capabilities?: FinalReportCapabilityItem[];
  isFrench: boolean;
}) {
  const allCapabilities = useMemo(() => {
    const scoreMap = new Map<string, number>();
    
    if (capabilities && capabilities.length > 0) {
      capabilities.forEach((cap) => {
        const canonical = getCanonicalCapabilityKey(cap.capability);
        const score = getMaturityScore(cap.maturity_band, cap.maturity_level_number);
        scoreMap.set(canonical, score);
      });
    } else {
      axes.forEach((axisItem) => {
        axisItem.working.forEach((item) => {
          const canonical = getCanonicalCapabilityKey(item.capability);
          const score = getMaturityScore(item.maturity_band);
          scoreMap.set(canonical, score);
        });
        axisItem.missing.forEach((item) => {
          const canonical = getCanonicalCapabilityKey(item.capability);
          const score = getMaturityScore(item.maturity_band);
          scoreMap.set(canonical, score);
        });
      });
    }

    return STATIC_CAPABILITIES.map((staticItem) => {
      const score = scoreMap.get(staticItem.key) || 1;
      return {
        name: isFrench ? staticItem.fr : staticItem.en,
        axis: staticItem.axis,
        score,
        key: staticItem.key
      };
    });
  }, [capabilities, axes, isFrench]);

  const numAxes = allCapabilities.length;
  if (numAxes === 0) return null;

  const width = 480;
  const height = 320;
  const centerX = width / 2;
  const centerY = height / 2;
  const maxRadius = 92;

  const level1Points = allCapabilities.map((_, i) => getCoords(centerX, centerY, maxRadius * 0.33, getAngle(i, numAxes)));
  const level2Points = allCapabilities.map((_, i) => getCoords(centerX, centerY, maxRadius * 0.66, getAngle(i, numAxes)));
  const level3Points = allCapabilities.map((_, i) => getCoords(centerX, centerY, maxRadius, getAngle(i, numAxes)));
  const scorePoints = allCapabilities.map((cap, i) => getCoords(centerX, centerY, maxRadius * (cap.score / 3), getAngle(i, numAxes)));

  const level1String = level1Points.map((p) => `${p.x},${p.y}`).join(" ");
  const level2String = level2Points.map((p) => `${p.x},${p.y}`).join(" ");
  const level3String = level3Points.map((p) => `${p.x},${p.y}`).join(" ");
  const scoreString = scorePoints.map((p) => `${p.x},${p.y}`).join(" ");

  const renderLabelText = (
    label: string,
    x: number,
    y: number,
    textAnchor: "inherit" | "start" | "end" | "middle",
    dx: number,
    dy: number,
    color: string
  ) => {
    const words = label.split(" ");
    
    if (words.length >= 2 && label.length > 12) {
      const midpoint = Math.ceil(words.length / 2);
      const line1 = words.slice(0, midpoint).join(" ");
      const line2 = words.slice(midpoint).join(" ");
      return (
        <text x={x + dx} y={y + dy} textAnchor={textAnchor} fill="#fff" fontSize="11" fontWeight="800" className="font-sans tracking-wide">
          <tspan x={x + dx} dy="-4">{line1.toUpperCase()}</tspan>
          <tspan x={x + dx} dy="12" fill={color}>{line2.toUpperCase()}</tspan>
        </text>
      );
    }
    return (
      <text x={x + dx} y={y + dy} textAnchor={textAnchor} fill="#fff" fontSize="11" fontWeight="800" className="font-sans tracking-wide">
        {label.toUpperCase()}
      </text>
    );
  };

  return (
    <svg width="100%" height="100%" viewBox={`0 0 ${width} ${height}`} fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <filter id="radarGlow" x="-25%" y="-25%" width="150%" height="150%">
          <feGaussianBlur stdDeviation="6" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>

        <linearGradient id="goldFill" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#ffd447" stopOpacity="0.22" />
          <stop offset="100%" stopColor="#c8973f" stopOpacity="0.08" />
        </linearGradient>

        <linearGradient id="goldStroke" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#ffd447" stopOpacity="1" />
          <stop offset="100%" stopColor="#c8973f" stopOpacity="0.75" />
        </linearGradient>
      </defs>

      <polygon points={level3String} fill="rgba(255,255,255,0.01)" stroke="rgba(255,255,255,0.12)" strokeWidth="1" />
      <polygon points={level2String} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="1" />
      <polygon points={level1String} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="1" strokeDasharray="2,2" />

      {level3Points.map((p, i) => (
        <line key={i} x1={centerX} y1={centerY} x2={p.x} y2={p.y} stroke="rgba(255,255,255,0.08)" strokeWidth="1" strokeDasharray="3,3" />
      ))}

      <text x={centerX + 6} y={centerY - maxRadius * 0.33 + 4} fill="rgba(255,255,255,0.28)" fontSize="8.5" fontFamily="monospace" fontWeight="500">1</text>
      <text x={centerX + 6} y={centerY - maxRadius * 0.66 + 4} fill="rgba(255,255,255,0.28)" fontSize="8.5" fontFamily="monospace" fontWeight="500">2</text>
      <text x={centerX + 6} y={centerY - maxRadius + 4} fill="rgba(255,255,255,0.28)" fontSize="8.5" fontFamily="monospace" fontWeight="500">3</text>

      <polygon
        points={scoreString}
        fill="url(#goldFill)"
        stroke="url(#goldStroke)"
        strokeWidth="2.5"
        filter="url(#radarGlow)"
      />

      <circle cx={centerX} cy={centerY} r="3" fill="rgba(255,255,255,0.3)" />

      {scorePoints.map((p, idx) => {
        const cap = allCapabilities[idx];
        let nodeColor = "#ffd447";
        if (cap.axis.toLowerCase() === "analyze" || cap.axis.toLowerCase() === "analyser") nodeColor = "#00d4ff";
        if (cap.axis.toLowerCase() === "improve" || cap.axis.toLowerCase() === "améliorer") nodeColor = "#9f93ff";
        
        return (
          <g key={idx}>
            <circle cx={p.x} cy={p.y} r="7" fill={nodeColor} fillOpacity="0.15" />
            <circle
              cx={p.x}
              cy={p.y}
              r="4"
              fill={nodeColor}
              stroke="#0f121d"
              strokeWidth="2"
            />
          </g>
        );
      })}

      {allCapabilities.map((cap, i) => {
        const angle = getAngle(i, numAxes);
        const cos = Math.cos(angle);
        const sin = Math.sin(angle);
        
        const labelRadius = maxRadius + 14;
        const coords = getCoords(centerX, centerY, labelRadius, angle);
        
        let textAnchor: "inherit" | "start" | "end" | "middle" = "middle";
        let dx = 0;
        let dy = 0;
        
        if (Math.abs(cos) < 0.15) {
          textAnchor = "middle";
          dy = sin < 0 ? -4 : 12;
        } else if (cos > 0) {
          textAnchor = "start";
          dx = 4;
          dy = 3;
        } else {
          textAnchor = "end";
          dx = -4;
          dy = 3;
        }

        let axisColor = "#ffd447";
        if (cap.axis.toLowerCase() === "analyze" || cap.axis.toLowerCase() === "analyser") axisColor = "#00d4ff";
        if (cap.axis.toLowerCase() === "improve" || cap.axis.toLowerCase() === "améliorer") axisColor = "#9f93ff";

        return (
          <g key={i}>
            {renderLabelText(cap.name, coords.x, coords.y, textAnchor, dx, dy, axisColor)}
          </g>
        );
      })}
    </svg>
  );
}
