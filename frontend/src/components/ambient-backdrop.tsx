import { useEffect, useState } from "react";

/** 装饰性拓扑缓慢漂移，与业务进度无关；隐藏页面暂停，减少动画由 CSS 控制。 */
export function AmbientBackdrop() {
  const [paused, setPaused] = useState(() => document.hidden);
  useEffect(() => {
    const updateVisibility = () => setPaused(document.hidden);
    document.addEventListener("visibilitychange", updateVisibility);
    return () => document.removeEventListener("visibilitychange", updateVisibility);
  }, []);

  return <div className="ambient-backdrop" aria-hidden="true" data-paused={paused} data-testid="ambient-backdrop">
    <div className="ambient-light" />
    <svg viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMid slice" focusable="false">
      <g className="ambient-topology" data-testid="ambient-motion">
        <path d="M680 0 840 125 1050 125 1190 265 1430 265 1600 95 M925 0 1100 175 1310 175 1440 45 1600 45 M1080 0 1220 110 1375 110 1490 225 1600 225 M0 890 260 890 380 770 605 770 715 880 910 880 1030 1000 M410 1000 550 860 780 860 910 730 1190 730 1410 950 1600 950" />
        <circle cx="840" cy="125" r="3" /><circle cx="1190" cy="265" r="3" /><circle cx="1310" cy="175" r="3" /><circle cx="1375" cy="110" r="3" /><circle cx="380" cy="770" r="3" /><circle cx="715" cy="880" r="3" /><circle cx="910" cy="730" r="3" />
      </g>
      <g className="ambient-orbit"><path d="M1160 25 1250 115 1510 115 M590 955 675 870 820 870" /><circle cx="1250" cy="115" r="2" /><circle cx="675" cy="870" r="2" /></g>
    </svg>
  </div>;
}
