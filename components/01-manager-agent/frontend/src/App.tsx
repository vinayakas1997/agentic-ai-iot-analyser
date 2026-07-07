import { useEffect } from "react";
import Navbar from "./components/Navbar";
import WorkspacePage from "./pages/WorkspacePage";
import { useSessionStore } from "./stores/sessionStore";
import { useWorkspaceSocket } from "./hooks/useWorkspaceSocket";

export default function App() {
  const bootstrap = useSessionStore((s) => s.bootstrap);

  useWorkspaceSocket();

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  return (
    <div className="flex flex-col h-screen bg-bg-deep text-text">
      <Navbar />
      <WorkspacePage />
    </div>
  );
}
