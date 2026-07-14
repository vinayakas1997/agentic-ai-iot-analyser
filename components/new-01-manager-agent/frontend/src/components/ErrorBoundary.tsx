import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
  info: ErrorInfo | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, info: null };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    this.setState({ error, info });
    console.error("Uncaught render error:", error, info.componentStack);
  }

  render() {
    const { error, info } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="flex flex-col items-center justify-center h-screen bg-bg-deep text-text p-6">
        <div className="max-w-2xl w-full rounded-xl border-2 border-red-500/30 bg-surface-1 p-5">
          <h1 className="text-base font-semibold text-red-400 mb-1">Something went wrong</h1>
          <p className="text-sm text-muted mb-3">
            The UI hit an unexpected error and stopped rendering. Details below can help track down the cause.
          </p>
          <pre className="bg-black/30 rounded-lg p-3 text-xs text-red-300 overflow-auto max-h-40 mb-3 whitespace-pre-wrap">
            {error.message}
          </pre>
          {info?.componentStack && (
            <pre className="bg-black/30 rounded-lg p-3 text-[11px] text-muted overflow-auto max-h-52 mb-4 whitespace-pre-wrap">
              {info.componentStack}
            </pre>
          )}
          <button
            type="button"
            className="text-sm px-3.5 py-1.5 rounded-lg bg-accent hover:bg-[#1d8cf0] text-white font-medium"
            onClick={() => window.location.reload()}
          >
            Reload
          </button>
        </div>
      </div>
    );
  }
}
