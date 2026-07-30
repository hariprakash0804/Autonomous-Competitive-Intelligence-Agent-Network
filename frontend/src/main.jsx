import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.jsx';

// ── Self-XSS Console Security Warning ──────────────────────────────────────────
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'production') {
  console.log(
    '%cSTOP! %cThis browser feature is intended for developers.\nIf someone told you to copy and paste code here to unlock features or modify notes, it is a Self-XSS attack and a scam.',
    'color: #ef4444; font-size: 26px; font-weight: bold;',
    'color: #cbd5e1; font-size: 13px; font-weight: 500;'
  );
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>
);
