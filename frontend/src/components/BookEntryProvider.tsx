import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';
import type { ReactNode } from 'react';
import './BookEntryProvider.css';

export interface BookEntryReference {
  workKey?: string | null;
  title?: string | null;
  authors?: string[];
}

interface BookEntryLinkItem {
  title: string;
  url: string;
}

interface BookEdition {
  key: string;
  title: string | null;
  isbn_10: string[];
  isbn_13: string[];
  sample_isbn: string | null;
  publishers: string[];
  publish_date: string | null;
  number_of_pages: number | null;
  physical_format: string | null;
  languages: string[];
  cover_id: number | null;
  cover_image_url: string | null;
}

interface BookEntry {
  found: boolean;
  work_key: string | null;
  title: string | null;
  subtitle: string | null;
  authors: string[];
  first_publish_year: number | null;
  cover_id: number | null;
  cover_image_url: string | null;
  description: string | null;
  first_sentence: string | null;
  subjects: string[];
  subject_places: string[];
  subject_people: string[];
  subject_times: string[];
  lc_classifications: string[];
  dewey_numbers: string[];
  links: BookEntryLinkItem[];
  excerpts: string[];
  openlibrary_url: string | null;
  edition_count: number;
  best_edition: BookEdition | null;
  editions: BookEdition[];
  error: string | null;
}

interface BookEntryContextValue {
  openEntry: (reference: BookEntryReference) => void;
  closeEntry: () => void;
}

const BookEntryContext = createContext<BookEntryContextValue | null>(null);

function FieldRow({
  label,
  value,
}: {
  label: string;
  value: ReactNode;
}) {
  return (
    <>
      <div className="book-entry-field-label">{label}</div>
      <div className="book-entry-field-value">{value}</div>
    </>
  );
}

function ChipList({
  values,
  emptyLabel = '(none)',
}: {
  values: string[];
  emptyLabel?: string;
}) {
  if (values.length === 0) {
    return <span className="book-entry-empty">{emptyLabel}</span>;
  }
  return (
    <div className="book-entry-chip-list">
      {values.map(value => (
        <span key={value} className="book-entry-chip">{value}</span>
      ))}
    </div>
  );
}

function BookEntryModal({
  reference,
  entry,
  loading,
  error,
  onClose,
}: {
  reference: BookEntryReference | null;
  entry: BookEntry | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}) {
  if (!reference) {
    return null;
  }

  const title = entry?.title || reference.title || 'Book entry';

  return (
    <div className="book-entry-overlay" onClick={onClose}>
      <div
        className="book-entry-modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={event => event.stopPropagation()}
      >
        <div className="book-entry-header">
          <div>
            <div className="book-entry-title">{title}</div>
            {entry?.subtitle && (
              <div className="book-entry-subtitle">{entry.subtitle}</div>
            )}
            {entry?.authors && entry.authors.length > 0 && (
              <div className="book-entry-authors">{entry.authors.join(', ')}</div>
            )}
          </div>
          <button
            type="button"
            className="book-entry-close"
            onClick={onClose}
            aria-label="Close book entry"
          >
            ×
          </button>
        </div>

        <div className="book-entry-body">
          {loading && (
            <div className="book-entry-state">Loading book entry...</div>
          )}

          {!loading && (error || entry?.error) && (
            <div className="book-entry-error">{error || entry?.error}</div>
          )}

          {!loading && entry && entry.found && !error && (
            <>
              <div className="book-entry-hero">
                <div className="book-entry-cover-panel">
                  {entry.cover_image_url ? (
                    <img
                      src={entry.cover_image_url}
                      alt={entry.title || 'Book cover'}
                      className="book-entry-cover"
                    />
                  ) : (
                    <div className="book-entry-cover-placeholder">No cover</div>
                  )}
                </div>

                <div className="book-entry-summary">
                  <div className="book-entry-fields">
                    <FieldRow label="Work key" value={<code>{entry.work_key}</code>} />
                    <FieldRow
                      label="First published"
                      value={entry.first_publish_year ?? <span className="book-entry-empty">(unknown)</span>}
                    />
                    <FieldRow
                      label="Edition count"
                      value={entry.edition_count}
                    />
                    <FieldRow
                      label="LC classes"
                      value={<ChipList values={entry.lc_classifications} />}
                    />
                    <FieldRow
                      label="Dewey"
                      value={<ChipList values={entry.dewey_numbers} />}
                    />
                  </div>

                  {entry.best_edition && (
                    <div className="book-entry-best-edition">
                      <div className="book-entry-section-title">Best edition</div>
                      <div className="book-entry-fields">
                        <FieldRow
                          label="ISBN"
                          value={entry.best_edition.sample_isbn ?? <span className="book-entry-empty">(none)</span>}
                        />
                        <FieldRow
                          label="Publisher"
                          value={entry.best_edition.publishers[0] ?? <span className="book-entry-empty">(none)</span>}
                        />
                        <FieldRow
                          label="Publish date"
                          value={entry.best_edition.publish_date ?? <span className="book-entry-empty">(unknown)</span>}
                        />
                        <FieldRow
                          label="Pages"
                          value={entry.best_edition.number_of_pages ?? <span className="book-entry-empty">(unknown)</span>}
                        />
                        <FieldRow
                          label="Format"
                          value={entry.best_edition.physical_format ?? <span className="book-entry-empty">(unknown)</span>}
                        />
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {entry.description && (
                <div className="book-entry-section">
                  <div className="book-entry-section-title">Description</div>
                  <div className="book-entry-copy">{entry.description}</div>
                </div>
              )}

              {entry.first_sentence && (
                <div className="book-entry-section">
                  <div className="book-entry-section-title">First sentence</div>
                  <blockquote className="book-entry-quote">{entry.first_sentence}</blockquote>
                </div>
              )}

              <div className="book-entry-section">
                <div className="book-entry-section-title">Subjects</div>
                <ChipList values={entry.subjects} />
              </div>

              {(entry.subject_places.length > 0 || entry.subject_people.length > 0 || entry.subject_times.length > 0) && (
                <div className="book-entry-section">
                  <div className="book-entry-section-title">Additional subject facets</div>
                  <div className="book-entry-fields">
                    <FieldRow label="Places" value={<ChipList values={entry.subject_places} />} />
                    <FieldRow label="People" value={<ChipList values={entry.subject_people} />} />
                    <FieldRow label="Times" value={<ChipList values={entry.subject_times} />} />
                  </div>
                </div>
              )}

              {(entry.links.length > 0 || entry.openlibrary_url) && (
                <div className="book-entry-section">
                  <div className="book-entry-section-title">Links</div>
                  <div className="book-entry-link-list">
                    {entry.links.map(link => (
                      <a
                        key={`${link.title}-${link.url}`}
                        href={link.url}
                        target="_blank"
                        rel="noreferrer"
                        className="book-entry-external-link"
                      >
                        {link.title}
                      </a>
                    ))}
                    {entry.openlibrary_url && (
                      <a
                        href={entry.openlibrary_url}
                        target="_blank"
                        rel="noreferrer"
                        className="book-entry-external-link"
                      >
                        Open Library work
                      </a>
                    )}
                  </div>
                </div>
              )}

              {entry.excerpts.length > 0 && (
                <div className="book-entry-section">
                  <div className="book-entry-section-title">Excerpts</div>
                  <div className="book-entry-copy">
                    {entry.excerpts.map(excerpt => (
                      <p key={excerpt}>{excerpt}</p>
                    ))}
                  </div>
                </div>
              )}

              {entry.editions.length > 0 && (
                <div className="book-entry-section">
                  <div className="book-entry-section-title">Sample editions</div>
                  <div className="book-entry-edition-list">
                    {entry.editions.map(edition => (
                      <div key={edition.key} className="book-entry-edition-card">
                        <div className="book-entry-edition-title">
                          {edition.title || entry.title}
                        </div>
                        <div className="book-entry-edition-meta">
                          {edition.publishers[0] && <span>{edition.publishers[0]}</span>}
                          {edition.publish_date && <span>{edition.publish_date}</span>}
                          {edition.sample_isbn && <span>ISBN: {edition.sample_isbn}</span>}
                          {edition.number_of_pages && <span>{edition.number_of_pages} pages</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export function BookEntryProvider({ children }: { children: ReactNode }) {
  const [activeReference, setActiveReference] = useState<BookEntryReference | null>(null);
  const [entry, setEntry] = useState<BookEntry | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const closeEntry = useCallback(() => {
    setActiveReference(null);
    setEntry(null);
    setLoading(false);
    setError(null);
  }, []);

  const openEntry = useCallback((reference: BookEntryReference) => {
    if (!reference.workKey && !reference.title) {
      return;
    }
    setActiveReference(reference);
  }, []);

  useEffect(() => {
    if (!activeReference) {
      return;
    }

    let cancelled = false;

    const loadEntry = async () => {
      setLoading(true);
      setError(null);
      setEntry(null);
      try {
        const res = await fetch('/api/books/entry', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            work_key: activeReference.workKey || undefined,
            title: activeReference.title || undefined,
            authors: activeReference.authors || [],
          }),
        });
        const data = await res.json() as BookEntry;
        if (!res.ok) {
          throw new Error(`API returned ${res.status}`);
        }
        if (!cancelled) {
          setEntry(data);
          if (!data.found && data.error) {
            setError(data.error);
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load book entry');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadEntry();
    return () => {
      cancelled = true;
    };
  }, [activeReference]);

  useEffect(() => {
    if (!activeReference) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        closeEntry();
      }
    };

    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.body.style.overflow = '';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [activeReference, closeEntry]);

  return (
    <BookEntryContext.Provider value={{ openEntry, closeEntry }}>
      {children}
      <BookEntryModal
        reference={activeReference}
        entry={entry}
        loading={loading}
        error={error}
        onClose={closeEntry}
      />
    </BookEntryContext.Provider>
  );
}

export function useBookEntryViewer() {
  const context = useContext(BookEntryContext);
  if (!context) {
    throw new Error('useBookEntryViewer must be used within a BookEntryProvider');
  }
  return context;
}
