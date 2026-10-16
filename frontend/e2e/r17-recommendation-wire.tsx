import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { AuthProvider } from "../src/app/auth-session";
import { AmbientBackdrop } from "../src/components/ambient-backdrop";
import { RecommendationWorkspace, ReportWorkspace } from "../src/features/recommendations/recommendation-workspace";
import "../src/styles.css";

/** 产品组件的隔离浏览器入口；API只能由测试显式拦截，不含业务样本或失败回填。 */
function IsolatedWorkspace() {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => { const changed = () => setHash(window.location.hash); window.addEventListener("hashchange", changed); return () => window.removeEventListener("hashchange", changed); }, []);
  return <div style={{ position: "relative", isolation: "isolate", minHeight: "100dvh" }}><AmbientBackdrop /><main><header className="page-heading"><div><p className="eyebrow">ISOLATED API FIXTURE / 非 LIVE</p><h1>本人关注与证据报告</h1><p>显式隔离测试环境，页面不提供模拟成功替代路径。</p></div></header><nav className="panel-actions" aria-label="隔离工作区导航"><a className="button secondary" href="#changes">本人推荐</a><a className="button secondary" href="#reports">日周报告</a></nav><AuthProvider>{hash === "#reports" ? <ReportWorkspace /> : <RecommendationWorkspace />}</AuthProvider></main></div>;
}
const root = document.getElementById("root"); if (root !== null) createRoot(root).render(<IsolatedWorkspace />);
