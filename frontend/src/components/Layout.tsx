import type { ReactNode } from 'react';
import Sidebar from './Sidebar';
import './Layout.css';

interface LayoutProps {
  activePage: string;
  onNavigate: (page: string) => void;
  title: string;
  subtitle?: string;
  children: ReactNode;
}

export default function Layout({ activePage, onNavigate, title, subtitle, children }: LayoutProps) {
  return (
    <div className="layout">
      <Sidebar activePage={activePage} onNavigate={onNavigate} />
      <div className="layout-content">
        <header className="layout-header">
          <h1>{title}</h1>
          {subtitle && <p>{subtitle}</p>}
        </header>
        <main className="layout-main">
          {children}
        </main>
      </div>
    </div>
  );
}
