import './Sidebar.css';

interface SidebarProps {
  activePage: string;
  onNavigate: (page: string) => void;
}

interface NavItem {
  id: string;
  label: string;
  icon: string;
  badge?: string;
}

const toolsNav: NavItem[] = [
  { id: 'book-matcher', label: 'Book Matcher', icon: '\u{1F50D}' },
  { id: 'photo-import', label: 'Photo Import', icon: '\u{1F4F7}', badge: 'Soon' },
];

const dataNav: NavItem[] = [
  { id: 'database', label: 'Database', icon: '\u{1F4BE}', badge: 'Soon' },
];

const aiNav: NavItem[] = [
  { id: 'agent-chat', label: 'Agent Chat', icon: '\u{1F4AC}', badge: 'Soon' },
];

export default function Sidebar({ activePage, onNavigate }: SidebarProps) {
  const renderItem = (item: NavItem) => (
    <button
      key={item.id}
      className={`sidebar-item ${activePage === item.id ? 'active' : ''}`}
      onClick={() => onNavigate(item.id)}
    >
      <span className="sidebar-icon">{item.icon}</span>
      {item.label}
      {item.badge && <span className="sidebar-badge">{item.badge}</span>}
    </button>
  );

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">B</div>
          <div>
            <div className="sidebar-logo-text">BookCatalog</div>
            <div className="sidebar-version">v0.1.0</div>
          </div>
        </div>
      </div>
      <nav className="sidebar-nav">
        <div className="sidebar-section">
          <div className="sidebar-section-label">Tools</div>
          {toolsNav.map(renderItem)}
        </div>
        <div className="sidebar-section">
          <div className="sidebar-section-label">Data</div>
          {dataNav.map(renderItem)}
        </div>
        <div className="sidebar-section">
          <div className="sidebar-section-label">AI</div>
          {aiNav.map(renderItem)}
        </div>
      </nav>
      <div className="sidebar-footer">
        AI-powered book cataloging
      </div>
    </aside>
  );
}
