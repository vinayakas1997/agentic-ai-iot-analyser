import { useEffect } from "react";
import Navbar from "./components/Navbar";
import WorkspacePage from "./pages/WorkspacePage";
import { useSessionStore } from "./stores/sessionStore";
import { useWorkspaceSocket } from "./hooks/useWorkspaceSocket";

export default function App() {
  const bootstrap = useSessionStore((s) => s.bootstrap);
  const startPoller = useSessionStore((s) => s.startPoller);
  const stopPoller = useSessionStore((s) => s.stopPoller);

  useWorkspaceSocket();

  useEffect(() => {
    bootstrap();
    startPoller();
    return () => stopPoller();
  }, [bootstrap, startPoller, stopPoller]);

  return (
    <div className="flex flex-col h-screen bg-bg-deep text-text">
      <Navbar />
      <WorkspacePage />
    </div>
  );
}
