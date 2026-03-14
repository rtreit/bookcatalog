import { useState, useEffect, useRef, useCallback } from 'react';
import mermaid from 'mermaid';
import './DebugDashboard.css';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FtsQuery {
  source_query: string;
  fts_query: string;
  elapsed_ms: number;
  results_returned: number;
  new_unique: number;
  error?: string;
}

interface Candidate {
  work_key: string;
  title: string;
  authors: string[];
  first_publish_year: number | null;
  score: number;
  title_similarity: number;
  subjects: string;
  description: string;
  cover_id: number | null;
}

interface DebugStages {
  product_filter: {
    elapsed_ms: number;
    score: number;
    threshold: number;
    is_product: boolean;
    verdict: string;
  };
  fts_search?: {
    elapsed_ms: number;
    search_variants: string[];
    queries: FtsQuery[];
    total_unique_candidates: number;
  };
  scoring?: {
    elapsed_ms: number;
    author_hint: string | null;
    candidates: Candidate[];
  };
  edition_enrichment?: {
    elapsed_ms: number;
    edition_count: number;
    isbn?: string | null;
    publisher?: string | null;
    number_of_pages?: number | null;
    publish_date?: string | null;
    physical_format?: string | null;
  };
  result: {
    matched: boolean;
    decision: string | null;
    confidence?: number;
    matched_title?: string;
    authors?: string[];
    first_publish_year?: number | null;
    reason?: string;
  };
}

interface DebugResult {
  input_title: string;
  stages: DebugStages;
  total_elapsed_ms: number;
}

interface DebugResponse {
  results: DebugResult[];
  total: number;
  elapsed_seconds: number;
  error?: string;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type ToolResult = Record<string, any>;

interface AgentGraphInfo {
  name: string;
  model: string;
  mermaid: string;
  recursion_limit: number;
  tools: string[];
}

type TabId = 'pipeline' | 'tools' | 'graph';

// ---------------------------------------------------------------------------
// Shared sub-components
// ---------------------------------------------------------------------------

function StagePanel({
  name,
  timing,
  verdict,
  verdictType,
  children,
  defaultOpen = false,
}: {
  name: string;
  timing: number;
  verdict?: string;
  verdictType?: 'pass' | 'fail' | 'neutral';
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="debug-stage">
      <div className="debug-stage-header" onClick={() => setOpen(!open)}>
        <span className={`debug-expand-icon ${open ? 'open' : ''}`}>&#9654;</span>
        <span className="debug-stage-name">{name}</span>
        {verdict && (
          <span className={`debug-stage-verdict ${verdictType || 'neutral'}`}>
            {verdict}
          </span>
        )}
        <span className="debug-stage-timing">{timing.toFixed(1)}ms</span>
      </div>
      {open && <div className="debug-stage-body">{children}</div>}
    </div>
  );
}

function CandidatePanel({ candidate, rank }: { candidate: Candidate; rank: number }) {
  const [open, setOpen] = useState(false);
  const scoreColor =
    candidate.score >= 0.85 ? 'var(--green)' :
    candidate.score >= 0.70 ? 'var(--amber)' :
    'var(--red)';

  return (
    <div className="debug-candidate">
      <div className="debug-candidate-header" onClick={() => setOpen(!open)}>
        <span className={`debug-expand-icon ${open ? 'open' : ''}`}>&#9654;</span>
        <span className="debug-candidate-rank">#{rank}</span>
        <span className="debug-candidate-title">
          {candidate.title}
          {candidate.authors.length > 0 && (
            <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>
              {' '}by {candidate.authors.join(', ')}
            </span>
          )}
        </span>
        <span className="debug-candidate-score" style={{ color: scoreColor }}>
          {(candidate.score * 100).toFixed(1)}%
        </span>
      </div>
      {open && (
        <div className="debug-candidate-body">
          <div className="debug-kv">
            <span className="debug-kv-key">Work Key</span>
            <span className="debug-kv-value">{candidate.work_key}</span>
            <span className="debug-kv-key">Title Similarity</span>
            <span className="debug-kv-value">{(candidate.title_similarity * 100).toFixed(1)}%</span>
            <span className="debug-kv-key">Final Score</span>
            <span className="debug-kv-value">{(candidate.score * 100).toFixed(2)}%</span>
            <span className="debug-kv-key">Authors</span>
            <span className="debug-kv-value">{candidate.authors.join(', ') || '(none)'}</span>
            <span className="debug-kv-key">Year</span>
            <span className="debug-kv-value">{candidate.first_publish_year ?? '(unknown)'}</span>
            {candidate.subjects && (
              <>
                <span className="debug-kv-key">Subjects</span>
                <span className="debug-kv-value">{candidate.subjects}</span>
              </>
            )}
            {candidate.description && (
              <>
                <span className="debug-kv-key">Description</span>
                <span className="debug-kv-value" style={{ whiteSpace: 'pre-wrap' }}>
                  {candidate.description}
                </span>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function DebugResultCard({ result }: { result: DebugResult }) {
  const [expanded, setExpanded] = useState(false);
  const { stages } = result;
  const decision = stages.result.decision;
  const indicatorClass = stages.product_filter.is_product
    ? 'product'
    : decision || 'no-match';
  const badgeClass = indicatorClass;
  const badgeText = stages.product_filter.is_product
    ? 'product'
    : decision?.replace('_', ' ') || 'no match';

  return (
    <div className="debug-result-card">
      <div className="debug-result-header" onClick={() => setExpanded(!expanded)}>
        <span className={`debug-expand-icon ${expanded ? 'open' : ''}`}>&#9654;</span>
        <span className={`debug-result-indicator ${indicatorClass}`} />
        <div className="debug-result-title">
          <div className="debug-result-input">{result.input_title}</div>
          {stages.result.matched && stages.result.matched_title && (
            <div className="debug-result-match">{stages.result.matched_title}</div>
          )}
        </div>
        <span className="debug-result-timing">{result.total_elapsed_ms.toFixed(0)}ms</span>
        <span className={`debug-result-badge ${badgeClass}`}>{badgeText}</span>
      </div>

      {expanded && (
        <div className="debug-stages">
          <StagePanel
            name="1. Product Filter"
            timing={stages.product_filter.elapsed_ms}
            verdict={stages.product_filter.verdict}
            verdictType={stages.product_filter.is_product ? 'fail' : 'pass'}
            defaultOpen={stages.product_filter.is_product}
          >
            <div className="debug-kv">
              <span className="debug-kv-key">Product Score</span>
              <span className="debug-kv-value">
                {(stages.product_filter.score * 100).toFixed(1)}%
              </span>
              <span className="debug-kv-key">Threshold</span>
              <span className="debug-kv-value">
                {(stages.product_filter.threshold * 100).toFixed(0)}%
              </span>
              <span className="debug-kv-key">Is Product</span>
              <span className="debug-kv-value">
                {stages.product_filter.is_product ? 'Yes' : 'No'}
              </span>
            </div>
          </StagePanel>

          {stages.fts_search && (
            <StagePanel
              name="2. FTS Search"
              timing={stages.fts_search.elapsed_ms}
              verdict={`${stages.fts_search.total_unique_candidates} candidates`}
              verdictType={stages.fts_search.total_unique_candidates > 0 ? 'pass' : 'fail'}
            >
              <div className="debug-kv" style={{ marginBottom: 12 }}>
                <span className="debug-kv-key">Search Variants</span>
                <span className="debug-kv-value">
                  {stages.fts_search.search_variants.length}
                </span>
                <span className="debug-kv-key">Queries Executed</span>
                <span className="debug-kv-value">
                  {stages.fts_search.queries.length}
                </span>
                <span className="debug-kv-key">Unique Candidates</span>
                <span className="debug-kv-value">
                  {stages.fts_search.total_unique_candidates}
                </span>
              </div>
              <table className="debug-fts-table">
                <thead>
                  <tr>
                    <th>FTS Query</th>
                    <th>Source</th>
                    <th>Results</th>
                    <th>New</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {stages.fts_search.queries.map((q, i) => (
                    <tr key={i}>
                      <td title={q.fts_query}>{q.fts_query}</td>
                      <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={q.source_query}>
                        {q.source_query.substring(0, 40)}
                        {q.source_query.length > 40 ? '...' : ''}
                      </td>
                      <td>{q.results_returned}</td>
                      <td>{q.new_unique}</td>
                      <td>{q.elapsed_ms.toFixed(1)}ms</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </StagePanel>
          )}

          {stages.scoring && (
            <StagePanel
              name="3. Candidate Scoring"
              timing={stages.scoring.elapsed_ms}
              verdict={`${stages.scoring.candidates.length} scored`}
              verdictType="neutral"
            >
              {stages.scoring.author_hint && (
                <div className="debug-kv" style={{ marginBottom: 8 }}>
                  <span className="debug-kv-key">Author Hint</span>
                  <span className="debug-kv-value">{stages.scoring.author_hint}</span>
                </div>
              )}
              {stages.scoring.candidates.map((c, i) => (
                <CandidatePanel key={c.work_key} candidate={c} rank={i + 1} />
              ))}
            </StagePanel>
          )}

          {stages.edition_enrichment && (
            <StagePanel
              name="4. Edition Enrichment"
              timing={stages.edition_enrichment.elapsed_ms}
              verdict={
                stages.edition_enrichment.edition_count > 0
                  ? `${stages.edition_enrichment.edition_count} editions`
                  : 'No editions'
              }
              verdictType={stages.edition_enrichment.edition_count > 0 ? 'pass' : 'neutral'}
            >
              <div className="debug-kv">
                <span className="debug-kv-key">Edition Count</span>
                <span className="debug-kv-value">{stages.edition_enrichment.edition_count}</span>
                <span className="debug-kv-key">ISBN</span>
                <span className="debug-kv-value">{stages.edition_enrichment.isbn || '(none)'}</span>
                <span className="debug-kv-key">Publisher</span>
                <span className="debug-kv-value">{stages.edition_enrichment.publisher || '(none)'}</span>
                <span className="debug-kv-key">Pages</span>
                <span className="debug-kv-value">{stages.edition_enrichment.number_of_pages ?? '(unknown)'}</span>
                <span className="debug-kv-key">Format</span>
                <span className="debug-kv-value">{stages.edition_enrichment.physical_format || '(unknown)'}</span>
                <span className="debug-kv-key">Publish Date</span>
                <span className="debug-kv-value">{stages.edition_enrichment.publish_date || '(unknown)'}</span>
              </div>
            </StagePanel>
          )}

          <StagePanel
            name="5. Decision"
            timing={0}
            verdict={stages.result.matched ? stages.result.decision || '' : 'No match'}
            verdictType={stages.result.matched ? 'pass' : 'fail'}
            defaultOpen
          >
            <div className="debug-kv">
              <span className="debug-kv-key">Matched</span>
              <span className="debug-kv-value">{stages.result.matched ? 'Yes' : 'No'}</span>
              <span className="debug-kv-key">Decision</span>
              <span className="debug-kv-value">{stages.result.decision || '(none)'}</span>
              {stages.result.confidence != null && (
                <>
                  <span className="debug-kv-key">Confidence</span>
                  <span className="debug-kv-value">
                    {(stages.result.confidence * 100).toFixed(2)}%
                  </span>
                </>
              )}
              {stages.result.matched_title && (
                <>
                  <span className="debug-kv-key">Matched Title</span>
                  <span className="debug-kv-value">{stages.result.matched_title}</span>
                </>
              )}
              {stages.result.authors && stages.result.authors.length > 0 && (
                <>
                  <span className="debug-kv-key">Authors</span>
                  <span className="debug-kv-value">{stages.result.authors.join(', ')}</span>
                </>
              )}
              <span className="debug-kv-key">Reason</span>
              <span className="debug-kv-value">{stages.result.reason || ''}</span>
            </div>
          </StagePanel>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab: Pipeline Debug (existing functionality)
// ---------------------------------------------------------------------------

function PipelineDebugTab() {
  const [orders, setOrders] = useState<string[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [filter, setFilter] = useState('');
  const [results, setResults] = useState<DebugResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadingOrders, setLoadingOrders] = useState(true);

  useEffect(() => {
    fetch('/api/books/test-orders')
      .then(res => res.json())
      .then(data => {
        setOrders(data.orders);
        setLoadingOrders(false);
      })
      .catch(err => {
        setError('Failed to load test orders: ' + err.message);
        setLoadingOrders(false);
      });
  }, []);

  const filteredOrders = orders
    .map((order, index) => ({ order, index }))
    .filter(({ order }) =>
      !filter || order.toLowerCase().includes(filter.toLowerCase())
    );

  const toggleOrder = (index: number) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  const selectAll = () => setSelected(new Set(filteredOrders.map(o => o.index)));
  const selectNone = () => setSelected(new Set());
  const selectBooks = () => {
    const bookLike = filteredOrders.filter(({ order }) => {
      const lower = order.toLowerCase();
      return (
        order.length < 80 &&
        !lower.includes('usb') &&
        !lower.includes('cable') &&
        !lower.includes('adapter') &&
        !lower.includes('battery') &&
        !lower.includes('charger')
      );
    });
    setSelected(new Set(bookLike.map(o => o.index)));
  };

  const handleAnalyze = async () => {
    if (selected.size === 0) return;
    setLoading(true);
    setError(null);
    setResults(null);

    const titles = Array.from(selected)
      .sort((a, b) => a - b)
      .map(i => orders[i]);

    try {
      const res = await fetch('/api/books/debug-match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ titles }),
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
        } catch { /* ignore */ }
        throw new Error(`API returned ${res.status}${detail ? ': ' + detail : ''}`);
      }

      const data: DebugResponse = await res.json();
      setResults(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred');
    } finally {
      setLoading(false);
    }
  };

  const matchedCount = results?.results.filter(r => r.stages.result.matched).length ?? 0;
  const productCount = results?.results.filter(r => r.stages.product_filter.is_product).length ?? 0;

  return (
    <>
      <div className="debug-selector">
        <div className="debug-selector-header">
          <button
            className="matcher-btn"
            onClick={handleAnalyze}
            disabled={loading || selected.size === 0}
          >
            {loading ? 'Analyzing...' : `Analyze ${selected.size} order(s)`}
          </button>
          <span className="debug-selector-info">
            {loadingOrders
              ? 'Loading test orders...'
              : `${orders.length} orders available, ${selected.size} selected`}
          </span>
          <div className="debug-selector-actions">
            <button onClick={selectAll} disabled={loading}>All</button>
            <button onClick={selectNone} disabled={loading}>None</button>
            <button onClick={selectBooks} disabled={loading}>Likely books</button>
          </div>
        </div>

        {!loadingOrders && (
          <div className="debug-order-list">
            <input
              className="debug-filter-input"
              type="text"
              placeholder="Filter orders..."
              value={filter}
              onChange={e => setFilter(e.target.value)}
              disabled={loading}
            />
            {filteredOrders.map(({ order, index }) => (
              <label
                key={index}
                className={`debug-order-item ${selected.has(index) ? 'selected' : ''}`}
              >
                <input
                  type="checkbox"
                  checked={selected.has(index)}
                  onChange={() => toggleOrder(index)}
                  disabled={loading}
                />
                <span className="debug-order-index">{index + 1}</span>
                <span className="debug-order-text" title={order}>{order}</span>
              </label>
            ))}
          </div>
        )}
      </div>

      {error && <div className="debug-error">{error}</div>}

      {loading && (
        <div className="debug-loading">
          <div className="spinner" />
          <div>Analyzing {selected.size} order(s) with debug tracing...</div>
          <div style={{ fontSize: 13, marginTop: 4, color: 'var(--text-muted)' }}>
            Each order runs through the full matching pipeline
          </div>
        </div>
      )}

      {results && (
        <>
          <div className="debug-perf-bar">
            <span>{results.elapsed_seconds}s total</span>
            <span className="debug-perf-sep" />
            <span>{results.total} orders</span>
            <span className="debug-perf-sep" />
            <span>{matchedCount} matched</span>
            <span className="debug-perf-sep" />
            <span>{productCount} filtered as products</span>
            <span className="debug-perf-sep" />
            <span>{results.total - matchedCount - productCount} no match</span>
          </div>

          <div className="debug-results">
            {results.results.map((result, i) => (
              <DebugResultCard key={i} result={result} />
            ))}
          </div>
        </>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Tab: Search Tools
// ---------------------------------------------------------------------------

type ToolName = 'search_books' | 'match_book' | 'get_database_stats';

const TOOL_DESCRIPTIONS: Record<ToolName, string> = {
  search_books:
    'Full-text search over the local Open Library database. Returns matching works with metadata.',
  match_book:
    'Match a single title to the best catalog entry. Returns work + edition data (ISBN, publisher, pages).',
  get_database_stats:
    'Return high-level statistics about the local Open Library database (work/author/edition counts).',
};

function SearchToolsTab() {
  const [activeTool, setActiveTool] = useState<ToolName>('search_books');
  const [query, setQuery] = useState('');
  const [maxResults, setMaxResults] = useState(10);
  const [author, setAuthor] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ToolResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<Array<{ tool: ToolName; params: string; result: ToolResult; elapsed_ms: number }>>([]);

  const executeSearch = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch('/api/books/tools/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, max_results: maxResults }),
      });
      const data = await res.json();
      setResult(data);
      setHistory(prev => [{ tool: 'search_books', params: `query="${query}", max_results=${maxResults}`, result: data, elapsed_ms: data.elapsed_ms }, ...prev]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  const executeMatch = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const body: Record<string, string> = { title: query };
      if (author.trim()) body.author = author.trim();
      const res = await fetch('/api/books/tools/match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      setResult(data);
      const paramStr = author.trim()
        ? `title="${query}", author="${author}"`
        : `title="${query}"`;
      setHistory(prev => [{ tool: 'match_book', params: paramStr, result: data, elapsed_ms: data.elapsed_ms }, ...prev]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  const executeStats = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch('/api/books/tools/stats');
      const data = await res.json();
      setResult(data);
      setHistory(prev => [{ tool: 'get_database_stats', params: '(none)', result: data, elapsed_ms: data.elapsed_ms }, ...prev]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  const handleExecute = () => {
    if (activeTool === 'search_books') executeSearch();
    else if (activeTool === 'match_book') executeMatch();
    else executeStats();
  };

  const needsInput = activeTool !== 'get_database_stats';

  return (
    <div className="tools-tab">
      <div className="tools-description">
        Call the same search tools the LLM agents use. Results are returned
        exactly as the agent would see them, with full raw data.
      </div>

      <div className="tools-selector">
        {(Object.keys(TOOL_DESCRIPTIONS) as ToolName[]).map(tool => (
          <button
            key={tool}
            className={`tools-tool-btn ${activeTool === tool ? 'active' : ''}`}
            onClick={() => { setActiveTool(tool); setResult(null); setError(null); }}
          >
            {tool}
          </button>
        ))}
      </div>

      <div className="tools-tool-desc">{TOOL_DESCRIPTIONS[activeTool]}</div>

      <div className="tools-input-area">
        {needsInput && (
          <div className="tools-input-row">
            <label className="tools-label">
              {activeTool === 'search_books' ? 'Query' : 'Title'}
            </label>
            <input
              className="tools-input"
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder={activeTool === 'search_books' ? 'e.g. Irish fairy tales' : 'e.g. The Count of Monte Cristo'}
              onKeyDown={e => e.key === 'Enter' && query.trim() && handleExecute()}
            />
          </div>
        )}

        {activeTool === 'search_books' && (
          <div className="tools-input-row">
            <label className="tools-label">Max Results</label>
            <input
              className="tools-input tools-input-short"
              type="number"
              min={1}
              max={50}
              value={maxResults}
              onChange={e => setMaxResults(Number(e.target.value) || 10)}
            />
          </div>
        )}

        {activeTool === 'match_book' && (
          <div className="tools-input-row">
            <label className="tools-label">Author (optional)</label>
            <input
              className="tools-input"
              type="text"
              value={author}
              onChange={e => setAuthor(e.target.value)}
              placeholder="e.g. Alexandre Dumas"
              onKeyDown={e => e.key === 'Enter' && query.trim() && handleExecute()}
            />
          </div>
        )}

        <button
          className="matcher-btn"
          onClick={handleExecute}
          disabled={loading || (needsInput && !query.trim())}
        >
          {loading ? 'Executing...' : `Execute ${activeTool}()`}
        </button>
      </div>

      {error && <div className="debug-error">{error}</div>}

      {result && (
        <div className="tools-result">
          <div className="tools-result-header">
            <span className="tools-result-tool">{result.tool}</span>
            {result.elapsed_ms != null && (
              <span className="debug-stage-timing">{result.elapsed_ms}ms</span>
            )}
            {result.result_count != null && (
              <span className="debug-stage-verdict neutral">
                {result.result_count} result{result.result_count !== 1 ? 's' : ''}
              </span>
            )}
          </div>
          <pre className="tools-result-json">
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}

      {history.length > 0 && (
        <div className="tools-history">
          <div className="tools-history-header">
            <span>Call History ({history.length})</span>
            <button className="tools-clear-btn" onClick={() => setHistory([])}>Clear</button>
          </div>
          {history.map((entry, i) => (
            <HistoryEntry key={i} entry={entry} />
          ))}
        </div>
      )}
    </div>
  );
}

function HistoryEntry({ entry }: { entry: { tool: ToolName; params: string; result: ToolResult; elapsed_ms: number } }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="tools-history-entry">
      <div className="tools-history-entry-header" onClick={() => setOpen(!open)}>
        <span className={`debug-expand-icon ${open ? 'open' : ''}`}>&#9654;</span>
        <code className="tools-history-call">{entry.tool}({entry.params})</code>
        <span className="debug-stage-timing">{entry.elapsed_ms}ms</span>
      </div>
      {open && (
        <pre className="tools-result-json tools-history-json">
          {JSON.stringify(entry.result, null, 2)}
        </pre>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab: Agent Graph
// ---------------------------------------------------------------------------

// Initialize mermaid once. securityLevel 'loose' is needed because LangGraph
// outputs HTML tags (<p>) inside node labels.
mermaid.initialize({
  startOnLoad: false,
  securityLevel: 'loose',
  theme: 'dark',
  themeVariables: {
    primaryColor: '#6366f1',
    primaryTextColor: '#e2e8f0',
    primaryBorderColor: '#818cf8',
    lineColor: '#94a3b8',
    secondaryColor: '#1e293b',
    tertiaryColor: '#0f172a',
    fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
  },
});

function MermaidDiagram({ chart, id }: { chart: string; id: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const renderIdRef = useRef(0);

  useEffect(() => {
    if (!containerRef.current || !chart) return;

    renderIdRef.current += 1;
    const renderId = `mermaid-${id}-${renderIdRef.current}`;

    const render = async () => {
      try {
        // Strip any YAML front-matter that LangGraph may include
        const cleanChart = chart.replace(/^---\n[\s\S]*?\n---\n/, '');
        const { svg } = await mermaid.render(renderId, cleanChart);
        if (containerRef.current) {
          containerRef.current.innerHTML = svg;
        }
      } catch (err) {
        console.error('Mermaid render error:', err);
        if (containerRef.current) {
          containerRef.current.innerHTML =
            `<pre class="debug-error" style="margin:0">${err instanceof Error ? err.message : 'Failed to render diagram'}</pre>`;
        }
      }
    };
    render();
  }, [chart, id]);

  return <div ref={containerRef} className="mermaid-container" />;
}

function AgentGraphTab() {
  const [graphs, setGraphs] = useState<Record<string, AgentGraphInfo>>({});
  const [toolNames, setToolNames] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<string>('preprocessor');

  const loadGraphs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/books/agent-graph');
      const data = await res.json();
      if (data.error) {
        setError(data.error);
      } else {
        setGraphs(data.graphs || {});
        setToolNames(data.tool_names || []);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load agent graphs');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadGraphs(); }, [loadGraphs]);

  const currentGraph = graphs[selectedAgent];

  return (
    <div className="graph-tab">
      <div className="tools-description">
        Visual representation of the LangGraph agent execution flow.
        Both agents use a ReAct-style loop: the model decides which tool to
        call, executes it, then returns to the model until done.
      </div>

      {loading && (
        <div className="debug-loading">
          <div className="spinner" />
          <div>Loading agent graphs...</div>
        </div>
      )}

      {error && <div className="debug-error">{error}</div>}

      {!loading && !error && Object.keys(graphs).length > 0 && (
        <>
          <div className="tools-selector">
            {Object.entries(graphs).map(([key, info]) => (
              <button
                key={key}
                className={`tools-tool-btn ${selectedAgent === key ? 'active' : ''}`}
                onClick={() => setSelectedAgent(key)}
              >
                {info.name}
              </button>
            ))}
          </div>

          {currentGraph && (
            <div className="graph-content">
              <div className="graph-info-grid">
                <div className="graph-info-card">
                  <div className="graph-info-label">Model</div>
                  <div className="graph-info-value">{currentGraph.model}</div>
                </div>
                <div className="graph-info-card">
                  <div className="graph-info-label">Recursion Limit</div>
                  <div className="graph-info-value">{currentGraph.recursion_limit}</div>
                </div>
                <div className="graph-info-card">
                  <div className="graph-info-label">Tools</div>
                  <div className="graph-info-value">{currentGraph.tools.length}</div>
                </div>
              </div>

              <div className="graph-diagram-section">
                <div className="graph-diagram-title">Execution Graph</div>
                <MermaidDiagram
                  chart={currentGraph.mermaid}
                  id={selectedAgent}
                />
              </div>

              <div className="graph-tools-section">
                <div className="graph-diagram-title">Available Tools</div>
                <div className="graph-tool-list">
                  {toolNames.map(name => (
                    <div key={name} className="graph-tool-item">
                      <code>{name}</code>
                      <span className="graph-tool-desc">
                        {TOOL_DESCRIPTIONS[name as ToolName] || ''}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="graph-mermaid-source">
                <div className="graph-diagram-title">Mermaid Source</div>
                <pre className="tools-result-json">{currentGraph.mermaid}</pre>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Dashboard with Tabs
// ---------------------------------------------------------------------------

const TABS: { id: TabId; label: string }[] = [
  { id: 'pipeline', label: 'Pipeline Debug' },
  { id: 'tools', label: 'Search Tools' },
  { id: 'graph', label: 'Agent Graph' },
];

export default function DebugDashboard() {
  const [activeTab, setActiveTab] = useState<TabId>('pipeline');

  return (
    <div className="debug">
      <div className="debug-tabs">
        {TABS.map(tab => (
          <button
            key={tab.id}
            className={`debug-tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'pipeline' && <PipelineDebugTab />}
      {activeTab === 'tools' && <SearchToolsTab />}
      {activeTab === 'graph' && <AgentGraphTab />}
    </div>
  );
}
