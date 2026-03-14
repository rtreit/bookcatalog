import { useState, useRef, useEffect } from 'react';
import './AgentChat.css';

interface ClassifiedItem {
  input: string;
  is_book: boolean | null;
  title: string | null;
  authors: string[];
  year: number | null;
  confidence: number;
  decision: string;
  reason: string;
}

interface ChatResponse {
  results: ClassifiedItem[];
  message: string;
  raw_response: string;
  model: string;
  error: string | null;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  results?: ClassifiedItem[];
  error?: string;
  model?: string;
}

export default function AgentChat() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingLabel, setLoadingLabel] = useState('Thinking...');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const lines = text.split('\n').filter(s => s.trim());
    const isMultiItem = lines.length > 1;
    const nextMessages: ChatMessage[] = [...messages, { role: 'user', content: text }];

    setMessages(nextMessages);
    setInput('');
    setLoading(true);
    setLoadingLabel(isMultiItem ? 'Reviewing your items...' : 'Thinking...');

    try {
      const body = {
        message: text,
        messages: nextMessages.map(({ role, content }) => ({ role, content })),
      };

      const res = await fetch('/api/agents/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
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

      const data: ChatResponse = await res.json();

      if (data.error) {
        setMessages(prev => [
          ...prev,
          {
            role: 'assistant',
            content: data.message || data.raw_response,
            error: data.error ?? undefined,
            model: data.model,
          },
        ]);
      } else {
        setMessages(prev => [
          ...prev,
          {
            role: 'assistant',
            content: data.message || data.raw_response,
            results: data.results,
            model: data.model,
          },
        ]);
      }
    } catch (err) {
      setMessages(prev => [
        ...prev,
        {
            role: 'assistant',
            content: '',
            error: err instanceof Error ? err.message : 'An unexpected error occurred',
          },
        ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const loadSample = () => {
    setInput(
      `Dune by Frank Herbert
Logitech MX Master 3S Wireless Mouse
The Hitchhiker's Guide to the Galaxy by Douglas Adams
Apple AirTag 4 Pack
Clean Code: A Handbook of Agile Software Craftsmanship by Robert C. Martin
Samsung T7 Shield Portable SSD 2TB`
    );
  };

  const getDecisionClass = (decision: string): string => {
    if (decision === 'book') return 'book';
    if (decision === 'likely_book') return 'likely_book';
    if (decision === 'not_a_book') return 'not-a-book';
    return 'unknown';
  };

  return (
    <div className="chat">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <div className="chat-empty-title">Book Assistant</div>
            <div className="chat-empty-text">
              Ask about books, authors, or recommendations. You can also paste a
              list of items, one per line, and the assistant will classify which
              ones are books and match them to the local catalog.
            </div>
            <button className="chat-sample-btn" onClick={loadSample}>
              Load sample items
            </button>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`}>
            <div className="chat-message-header">
              {msg.role === 'user' ? 'You' : 'Agent'}
              {msg.model && (
                <span className="chat-model-badge">{msg.model}</span>
              )}
            </div>

            {msg.role === 'user' && (
              <pre className="chat-user-text">{msg.content}</pre>
            )}

            {msg.role === 'assistant' && msg.content && (
              <div className="chat-assistant-text">{msg.content}</div>
            )}

            {msg.error && (
              <div className="chat-error">{msg.error}</div>
            )}

            {msg.results && msg.results.length > 0 && (
              <div className="chat-results">
                {msg.results.map((r, j) => (
                  <div key={j} className="chat-result-card">
                    <div className={`chat-result-indicator ${getDecisionClass(r.decision)}`} />
                    <div className="chat-result-body">
                      <div className="chat-result-input">{r.input}</div>
                      {r.is_book ? (
                        <>
                          <div className="chat-result-title">{r.title}</div>
                          <div className="chat-result-meta">
                            {r.authors.length > 0 && <span>{r.authors.join(', ')}</span>}
                            {r.year && <span>{r.year}</span>}
                          </div>
                        </>
                      ) : (
                        <div className="chat-result-reason">{r.reason || 'Not a book'}</div>
                      )}
                    </div>
                    <div className={`chat-result-badge ${getDecisionClass(r.decision)}`}>
                      {r.decision.replace('_', ' ')}
                    </div>
                    {r.confidence > 0 && (
                      <div className="chat-result-confidence">
                        {Math.round(r.confidence * 100)}%
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="chat-message assistant">
            <div className="chat-message-header">Agent</div>
            <div className="chat-loading">
              <div className="spinner" />
              <span>{loadingLabel}</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-bar">
        <textarea
          ref={textareaRef}
            className="chat-textarea"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about a book, author, or series, or paste items to classify..."
            disabled={loading}
            rows={3}
          />
        <button
          className="chat-send-btn"
          onClick={handleSend}
          disabled={loading || !input.trim()}
        >
          Send
        </button>
      </div>
    </div>
  );
}
