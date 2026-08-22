import { Component, ReactNode } from 'react';

export class AppErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error) {
    console.error('Data-Berge render error', error);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="empty-app" style={{ display: 'grid', placeItems: 'center', minHeight: '100vh', padding: 24 }}>
          <div className="error-banner" style={{ maxWidth: 720 }}>
            Something on this page could not render: {this.state.error.message || 'Unexpected UI payload.'}
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
