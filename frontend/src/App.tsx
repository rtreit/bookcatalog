import { useState } from 'react';
import Layout from './components/Layout';
import BookMatcher from './pages/BookMatcher';
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
      {activePage === 'photo-import' && (
        <Placeholder
          icon={'\u{1F4F7}'}
          title="Photo Import"
          description="Take a photo of a bookshelf or a stack of books, and AI will identify each title automatically."
          features={[
            'Vision AI for spine and cover recognition',
            'Batch processing for large collections',
            'Automatic metadata lookup after identification',
          ]}
        />
      )}
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
      {activePage === 'agent-chat' && (
        <Placeholder
          icon={'\u{1F4AC}'}
          title="Agent Chat"
          description="Chat with the AI agent to catalog books, ask questions about your collection, or get recommendations."
          features={[
            'Natural language queries about your catalog',
            'Agent-driven book research and classification',
            'Database operations via conversation',
          ]}
        />
      )}
    </Layout>
  );
}

