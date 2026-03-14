import { useState } from 'react';
import Layout from './components/Layout';
import BookMatcher from './pages/BookMatcher';
import AgentChat from './pages/AgentChat';
import PhotoImport from './pages/PhotoImport';
import DebugDashboard from './pages/DebugDashboard';
import Placeholder from './pages/Placeholder';

const pages: Record<string, { title: string; subtitle: string }> = {
  'book-matcher': {
    title: 'Book Matcher',
    subtitle: 'Match strings to real books using Open Library',
  },
  'photo-import': {
    title: 'Photo Import',
    subtitle: 'Identify books from photos of shelves and stacks',
  },
  'debug-dashboard': {
    title: 'Debug Dashboard',
    subtitle: 'Inspect the full matching pipeline for test orders',
  },
  'database': {
    title: 'Database',
    subtitle: 'Browse and manage your book catalog',
  },
  'agent-chat': {
    title: 'Agent Chat',
    subtitle: 'Chat with the AI book cataloging agent',
  },
};

export default function App() {
  const [activePage, setActivePage] = useState('book-matcher');
  const page = pages[activePage] ?? pages['book-matcher'];

  return (
    <Layout
      activePage={activePage}
      onNavigate={setActivePage}
      title={page.title}
      subtitle={page.subtitle}
    >
      {activePage === 'book-matcher' && <BookMatcher />}
      {activePage === 'photo-import' && <PhotoImport />}
      {activePage === 'debug-dashboard' && <DebugDashboard />}
      {activePage === 'database' && (
        <Placeholder
          icon={'\u{1F4BE}'}
          title="Database Browser"
          description="Browse, search, and manage your cataloged books. Export to Access, SQLite, or Excel."
          features={[
            'Full-text search across all book metadata',
            'Export to multiple storage backends',
            'Edit and merge duplicate entries',
          ]}
        />
      )}
      {activePage === 'agent-chat' && <AgentChat />}
    </Layout>
  );
}

