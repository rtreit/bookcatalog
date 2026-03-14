import { useState } from 'react';
import './BookMatcher.css';

interface MatchedBook {
  input_title: string;
  matched: boolean;
  matched_title: string | null;
  decision: string | null;
  confidence: number | null;
  title_similarity: number | null;
  authors: string[];
  first_publish_year: number | null;
  edition_count: number | null;
  isbn: string | null;
}

interface MatchResponse {
  results: MatchedBook[];
  total: number;
  matched_count: number;
  unmatched_count: number;
  elapsed_seconds: number;
  max_concurrent: number;
}

type InputMode = 'titles' | 'amazon' | 'custom';

const INPUT_MODES: { id: InputMode; label: string; hint: string }[] = [
  { id: 'titles', label: 'One per line', hint: 'Each line is treated as a separate title' },
  { id: 'amazon', label: 'Amazon orders', hint: 'Lines are split on | to separate bundled items' },
  { id: 'custom', label: 'Custom delimiter', hint: 'Specify your own delimiter character' },
];

const SAMPLE_TITLES = `The Great Gatsby
A Brief History of Time
some random product name
Harry Potter and the Sorcerer's Stone
1984
definitely not a book title xyz123`;

const SAMPLE_AMAZON = `Studio Ghibli: The Complete Works | Van Richten's Guide to Ravenloft | The Hardware Hacking Handbook: Breaking Embedded Security with Hardware Attacks | Backcountry Skiing: Skills for Ski Touring and Ski Mountaineering (Mountaineers Outdoor Expert) | The Ninth Hour: A Novel | Prayers & Promises for First Responders
Boy in a China Shop: Life, Clay and Everything (-)
Complete Pottery Techniques: Design, Form, Throw, Decorate and More, with Workshops from Professional Makers
Mastering Hand Building: Techniques, Tips, and Tricks for Slabs, Coils, and More (Mastering Ceramics)
Cherry MX Board 3.0 S Wired Gamer Mechanical Keyboard with Aluminum Housing - MX Brown Switches (Slight Clicky)
Irish Fairy Tales and Folklore
Logitech G502 HERO High Performance Wired Gaming Mouse, HERO 25K Sensor, 25,600 DPI, RGB | KTRIO Large Gaming Mouse Pad Desk Mat, Superior Micro-Weave Cloth`;

export default function BookMatcher() {
  const [input, setInput] = useState('');
  const [inputMode, setInputMode] = useState<InputMode>('titles');
  const [customDelimiter, setCustomDelimiter] = useState('|');
  const [results, setResults] = useState<MatchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [maxConcurrent, setMaxConcurrent] = useState(5);

  const getDelimiter = (): string | null => {
    if (inputMode === 'amazon') return '|';
    if (inputMode === 'custom') return customDelimiter || null;
    return null;
  };

  const splitText = (text: string): string => {
    const delim = getDelimiter();
    if (!delim) return text;
    return text
      .split('\n')
      .flatMap(line => line.split(delim).map(s => s.trim()).filter(Boolean))
      .join('\n');
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const delim = getDelimiter();
    if (!delim) return;
    e.preventDefault();
    const pasted = e.clipboardData.getData('text');
    const split = splitText(pasted);
    const start = e.currentTarget.selectionStart;
    const end = e.currentTarget.selectionEnd;
    setInput(prev => prev.substring(0, start) + split + prev.substring(end));
  };

  const getItemCount = (): number => {
    return input.split('\n').filter(s => s.trim()).length;
  };

  const handleMatch = async () => {
    const titles = input.split('\n').filter(s => s.trim());
    if (titles.length === 0) return;

    setLoading(true);
    setError(null);
    setResults(null);

    try {
      const res = await fetch('/api/books/match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ titles, max_concurrent: maxConcurrent }),
      });

      if (!res.ok) {
        let detail = '';
        try {
          const errBody = await res.json();
          if (errBody.detail) {
            detail = typeof errBody.detail === 'string'
              ? errBody.detail
              : JSON.stringify(errBody.detail, null, 2);
          }
        } catch { /* ignore parse errors */ }
        throw new Error(
          `API returned ${res.status}${detail ? ': ' + detail : ''}`
        );
      }

      const data: MatchResponse = await res.json();
      setResults(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred');
    } finally {
      setLoading(false);
    }
  };

  const loadSample = () => {
    if (inputMode === 'amazon' || inputMode === 'custom') {
      setInput(splitText(SAMPLE_AMAZON));
    } else {
      setInput(SAMPLE_TITLES);
    }
  };

  const bookCount = results?.results.filter(r => r.decision === 'book').length ?? 0;
  const likelyCount = results?.results.filter(r => r.decision === 'likely_book').length ?? 0;

  return (
    <div className="matcher">
      <div className="matcher-input-section">
        <div className="matcher-mode-bar">
          <span className="matcher-mode-label">Input format:</span>
          <div className="matcher-mode-tabs">
            {INPUT_MODES.map(mode => (
              <button
                key={mode.id}
                className={`matcher-mode-tab ${inputMode === mode.id ? 'active' : ''}`}
                onClick={() => setInputMode(mode.id)}
                title={mode.hint}
                disabled={loading}
              >
                {mode.label}
              </button>
            ))}
          </div>
          {inputMode === 'custom' && (
            <input
              className="matcher-delimiter-input"
              type="text"
              maxLength={3}
              value={customDelimiter}
              onChange={e => setCustomDelimiter(e.target.value)}
              placeholder="|"
              disabled={loading}
            />
          )}
          <span className="matcher-mode-hint">
            {INPUT_MODES.find(m => m.id === inputMode)?.hint}
          </span>
        </div>

        <textarea
          className="matcher-textarea"
          placeholder={
            inputMode === 'amazon'
              ? 'Paste Amazon order lines here...\nItems separated by | will be split into separate lines automatically'
              : inputMode === 'custom'
                ? `Paste text here...\nItems separated by "${customDelimiter}" will be split into separate lines`
                : 'Paste book titles here, one per line...'
          }
          value={input}
          onChange={e => setInput(e.target.value)}
          onPaste={handlePaste}
          disabled={loading}
        />
        <div className="matcher-controls">
          <button
            className="matcher-btn"
            onClick={handleMatch}
            disabled={loading || !input.trim()}
          >
            {loading ? 'Matching...' : 'Match Books'}
          </button>
          <button
            className="matcher-btn"
            onClick={loadSample}
            disabled={loading}
            style={{ background: 'var(--bg-tertiary)' }}
          >
            Load Sample
          </button>
          <span className="matcher-hint">
            {input.trim()
              ? `${getItemCount()} item(s) to match`
              : 'Enter titles or load a sample to get started'}
          </span>
          <button
            className="matcher-advanced-toggle"
            onClick={() => setShowAdvanced(!showAdvanced)}
            type="button"
          >
            {showAdvanced ? 'Hide advanced' : 'Advanced'}
          </button>
        </div>

        {showAdvanced && (
          <div className="matcher-advanced">
            <label className="matcher-advanced-item">
              <span>Concurrency</span>
              <input
                type="range"
                min={1}
                max={20}
                value={maxConcurrent}
                onChange={e => setMaxConcurrent(Number(e.target.value))}
                disabled={loading}
              />
              <span className="matcher-advanced-value">{maxConcurrent}</span>
            </label>
          </div>
        )}
      </div>

      {error && <div className="matcher-error">{error}</div>}

      {loading && (
        <div className="matcher-loading">
          <div className="spinner" />
          <div>Searching Open Library...</div>
          <div style={{ fontSize: 13, marginTop: 4, color: 'var(--text-muted)' }}>
            This may take a moment for multiple titles
          </div>
        </div>
      )}

      {results && (
        <>
          <div className="matcher-stats">
            <div className="stat-card">
              <div className="stat-label">Total</div>
              <div className="stat-value">{results.total}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Matched</div>
              <div className="stat-value green">{bookCount}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Likely</div>
              <div className="stat-value amber">{likelyCount}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">No Match</div>
              <div className="stat-value red">{results.unmatched_count}</div>
            </div>
          </div>

          <div className="matcher-perf-bar">
            <span>{results.elapsed_seconds}s</span>
            <span className="matcher-perf-sep" />
            <span>{results.total > 0 ? (results.elapsed_seconds / results.total).toFixed(2) : 0}s/item</span>
            <span className="matcher-perf-sep" />
            <span>concurrency: {results.max_concurrent}</span>
          </div>

          <div className="matcher-results">
            {results.results.map((r, i) => (
              <div key={i} className="result-card">
                <div className={`result-indicator ${r.matched ? r.decision : 'no-match'}`} />
                <div className="result-body">
                  <div className="result-info">
                    <div className="result-input-title">{r.input_title}</div>
                    {r.matched ? (
                      <>
                        <div className="result-matched-title">{r.matched_title}</div>
                        <div className="result-meta">
                          {r.authors.length > 0 && <span>{r.authors.join(', ')}</span>}
                          {r.first_publish_year && <span>{r.first_publish_year}</span>}
                          {r.isbn && <span>ISBN: {r.isbn}</span>}
                          {r.edition_count != null && r.edition_count > 0 && (
                            <span>{r.edition_count} edition(s)</span>
                          )}
                        </div>
                      </>
                    ) : (
                      <div className="result-no-match-text">No matching book found</div>
                    )}
                  </div>
                  <div className={`result-badge ${r.matched ? r.decision : 'no-match'}`}>
                    {r.matched ? r.decision?.replace('_', ' ') : 'no match'}
                  </div>
                  {r.confidence != null && (
                    <div className="result-confidence">
                      <div className="result-confidence-value">
                        {Math.round(r.confidence * 100)}%
                      </div>
                      <div className="result-confidence-label">confidence</div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
