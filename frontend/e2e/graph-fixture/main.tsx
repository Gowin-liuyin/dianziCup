import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { AuthProvider, useAuthSession } from "../../src/app/auth-session";
import { AmbientBackdrop } from "../../src/components/ambient-backdrop";
import { EventWorkspace } from "../../src/features/events/event-workspace";
import { GraphExplorerView } from "../../src/features/graph/graph-explorer-view";
import { graphFixtureEventId } from "../../src/features/graph/graph.fixture";
import "../../src/styles.css";

function FixtureHarness() {
  const [hash, setHash] = useState(window.location.hash);
  const { refreshSession } = useAuthSession();
  useEffect(() => { const update = () => setHash(window.location.hash); window.addEventListener("hashchange", update); return () => window.removeEventListener("hashchange", update); }, []);
  return <><AmbientBackdrop /><main style={{ position: "relative", padding: "16px", maxWidth: "1440px", margin: "auto" }}><p>R17 隔离合成 Fixture · 不连接真实情报服务</p><button className="button secondary" onClick={() => void refreshSession()}>测试重新验证会话</button><div style={{ marginTop: "16px" }}>{hash.startsWith("#events/") ? <EventWorkspace /> : <GraphExplorerView eventId={graphFixtureEventId} dataMode="fixture" />}</div></main></>;
}
const root = document.getElementById("root");
if (root === null) throw new Error("Fixture root missing");
createRoot(root).render(<AuthProvider><FixtureHarness /></AuthProvider>);
