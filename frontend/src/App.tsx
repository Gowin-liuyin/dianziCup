/**
 * 工作台外壳组件（开发骨架阶段）。
 *
 * 后端 API 尚未接入，页面必须显式呈现「未连接」状态；
 * 不渲染任何业务统计或示例数据，避免被误读为真实能力。
 */
export function App() {
  return (
    <main>
      <h1>AI 安全知识情报工作台</h1>
      <p data-testid="connection-status">后端 API 未连接（开发骨架阶段）</p>
    </main>
  );
}
