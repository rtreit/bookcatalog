import './Placeholder.css';

interface PlaceholderProps {
  icon: string;
  title: string;
  description: string;
  features: string[];
}

export default function Placeholder({ icon, title, description, features }: PlaceholderProps) {
  return (
    <div className="placeholder">
      <div className="placeholder-icon">{icon}</div>
      <div className="placeholder-title">{title}</div>
      <div className="placeholder-text">{description}</div>
      {features.length > 0 && (
        <div className="placeholder-features">
          {features.map((f, i) => (
            <div key={i} className="placeholder-feature">
              <span style={{ color: 'var(--text-muted)' }}>-</span>
              {f}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
