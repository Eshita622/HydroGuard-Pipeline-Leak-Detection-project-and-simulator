import { createRoot } from 'react-dom/client';
import { App as CapacitorApp } from '@capacitor/app';

import App from './App';
import { ErrorBoundary } from '@/components/error-boundary';

import './index.css';

if (typeof window !== 'undefined' && (window as any).Capacitor?.isNativePlatform?.()) {
  CapacitorApp.addListener('backButton', ({ canGoBack }) => {
    if (canGoBack) window.history.back();
    else void CapacitorApp.exitApp();
  });
}

createRoot(document.getElementById('root')!, {
  // Keeps caught errors off reportError(), which would raise the dev overlay.
  onCaughtError: (error, errorInfo) => {
    console.error(error, errorInfo.componentStack);
  },
}).render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>,
);
