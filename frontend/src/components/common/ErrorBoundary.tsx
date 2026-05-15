import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="mx-auto max-w-xl p-6 text-sm">
          <h2 className="text-lg font-semibold">Something went wrong</h2>
          <p className="mt-2 text-muted-foreground">Please refresh the page.</p>
        </div>
      );
    }
    return this.props.children;
  }
}
