import { MATURITY_CARDS } from "../../../config/maturityConfig";

type Props = {
  currentStep: number;
  isFrench: boolean;
};

export default function MaturityStepper({ currentStep, isFrench }: Props) {
  const labels = isFrench ? MATURITY_CARDS.fr : MATURITY_CARDS.en;

  return (
    <div className="panel-inner print:hidden">
      <div className="relative flex items-start gap-3 pt-20 pb-4 px-2 md:px-4">
        
        {/* Connected horizontal track line behind the nodes */}
        <div className="absolute left-[calc(16.6%+3.5rem)] right-[calc(16.6%)] top-[46px] h-[3px] bg-white/10 select-none pointer-events-none rounded-full print:hidden">
          {/* Active progress line fill */}
          <div 
            className="h-full bg-gradient-to-r from-ey-yellow-soft via-[#00d4ff] to-[#7c5cff] rounded-full transition-all duration-1000 ease-out" 
            style={{
              width: currentStep === 1 ? "0%" : currentStep === 2 ? "50%" : "100%"
            }}
          />
        </div>

        {/* The Connected Maturity Flow Grid */}
        <div className="flex-1 grid grid-cols-3 gap-6 items-start pl-14 md:pl-16 relative z-10">
          {[1, 2, 3].map((stage) => {
            const isSelected = currentStep === stage;
            const isPassed = currentStep >= stage;
            const stageData = labels[stage as 1 | 2 | 3];
            
            // Color configuration matching stage
            let accentColor = "rgba(255, 255, 255, 0.4)";
            let gradientText = "from-white to-white/70";
            let borderClass = "border-white/10 bg-white/[0.01]";
            let badgeBg = "bg-white/20";
            let badgeTextColor = "text-white";
            
            if (stage === 1) {
              accentColor = "#ffd447";
              gradientText = "from-ey-yellow-soft to-[#c8973f]";
              badgeBg = "bg-[linear-gradient(135deg,#ffd447_0%,#c8973f_100%)]";
              badgeTextColor = "text-[#111318]";
              if (isSelected) {
                borderClass = "border-ey-yellow-soft/45 bg-[linear-gradient(180deg,rgba(255,212,71,0.06),rgba(255,255,255,0.01))] shadow-[0_16px_36px_rgba(255,212,71,0.12)] print:border-black/15";
              }
            } else if (stage === 2) {
              accentColor = "#00d4ff";
              gradientText = "from-[#85eaff] to-[#00d4ff]";
              badgeBg = "bg-[linear-gradient(135deg,#85eaff_0%,#00d4ff_100%)]";
              badgeTextColor = "text-[#111318]";
              if (isSelected) {
                borderClass = "border-[#00d4ff]/45 bg-[linear-gradient(180deg,rgba(0,212,255,0.06),rgba(255,255,255,0.01))] shadow-[0_16px_36px_rgba(0,212,255,0.12)] print:border-black/15";
              }
            } else {
              accentColor = "#7c5cff";
              gradientText = "from-[#9f93ff] to-[#7c5cff]";
              badgeBg = "bg-[linear-gradient(135deg,#9f93ff_0%,#7c5cff_100%)]";
              badgeTextColor = "text-white";
              if (isSelected) {
                borderClass = "border-[#7c5cff]/45 bg-[linear-gradient(180deg,rgba(124,92,255,0.06),rgba(255,255,255,0.01))] shadow-[0_16px_36px_rgba(124,92,255,0.12)] print:border-black/15";
              }
            }

            return (
              <div key={stage} className="flex flex-col items-center group relative print:text-black">
                
                {/* Interactive Step Node on the Line */}
                <div className="relative flex items-center justify-center h-[54px] w-full mb-6 print:hidden">
                  <div 
                    className={`h-11 w-11 rounded-full border-2 flex items-center justify-center font-bold font-mono text-sm transition-all duration-500 ${
                      isSelected 
                        ? "bg-[#111318] scale-110" 
                        : isPassed 
                        ? "bg-white/5 text-white/90" 
                        : "bg-[#111318] text-white/30 border-white/10"
                    }`}
                    style={{ 
                      borderColor: isPassed ? accentColor : "rgba(255,255,255,0.1)",
                      color: isPassed ? accentColor : undefined,
                      boxShadow: isSelected ? `0 0 20px ${accentColor}44` : undefined
                    }}
                  >
                    {stage}
                  </div>

                  {/* Your Position floating label above the active node */}
                  {isSelected && (
                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-3.5 z-10 flex flex-col items-center select-none pointer-events-none animate-bounce">
                      <div className={`px-3.5 py-1.5 rounded-full ${badgeBg} ${badgeTextColor} font-sans text-[0.68rem] font-bold uppercase tracking-[0.15em] shadow-[0_8px_20px_rgba(0,0,0,0.3)]`}>
                        {labels.yourPosition}
                      </div>
                      <div className="w-1.5 h-1.5 rotate-45 -mt-0.5" style={{ backgroundColor: accentColor }} />
                    </div>
                  )}
                </div>

                {/* Card describing the level */}
                <div className={`w-full rounded-2xl border p-5.5 backdrop-blur-[10px] min-h-[195px] transition-all duration-300 ${borderClass} hover:border-white/20 hover:bg-white/[0.02] flex flex-col items-center text-center print:bg-white print:border-black/10 print:text-black print:min-h-0`}>
                  <h3 className={`font-sans text-[1.25rem] font-extrabold tracking-tight m-0 bg-clip-text text-transparent bg-gradient-to-r ${gradientText} print:text-black print:bg-none print:bg-clip-border`}>
                    {stageData.title}
                  </h3>
                  <p className="font-mono text-[0.72rem] m-0 mt-1 uppercase tracking-[0.15em] text-white/50 print:text-black/50">
                    {isFrench ? `Niveau ${stage}` : `Level ${stage}`}
                  </p>
                  <p className="font-sans text-[0.92rem] leading-relaxed m-0 mt-3 text-white/78 group-hover:text-white transition-colors duration-200 max-w-[210px] print:text-black/85">
                    {stageData.desc}
                  </p>
                </div>

              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
