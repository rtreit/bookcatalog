import { useState, useRef } from 'react';
import './PhotoImport.css';

interface IdentifiedBook {
  extracted_title: string | null;
  extracted_author: string | null;
  matched_title: string | null;
  matched_authors: string[];
  year: number | null;
  confidence: number;
  match_confidence: number | null;
  notes: string;
}

interface PhotoResponse {
  books: IdentifiedBook[];
  total_identified: number;
  total_matched: number;
  error: string | null;
}

export default function PhotoImport() {
  const [preview, setPreview] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [results, setResults] = useState<PhotoResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (!selected) return;

    if (!selected.type.startsWith('image/')) {
      setError('Please select an image file (JPEG, PNG, GIF, or WebP)');
      return;
    }

    if (selected.size > 20 * 1024 * 1024) {
      setError('Image too large. Maximum size is 20 MB.');
      return;
    }

    setFile(selected);
    setError(null);
    setResults(null);

    const reader = new FileReader();
    reader.onload = () => setPreview(reader.result as string);
    reader.readAsDataURL(selected);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();

    const dropped = e.dataTransfer.files[0];
    if (dropped && dropped.type.startsWith('image/')) {
      const syntheticEvent = {
        target: { files: e.dataTransfer.files },
      } as unknown as React.ChangeEvent<HTMLInputElement>;
      handleFileSelect(syntheticEvent);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleAnalyze = async () => {
    if (!file || loading) return;

    setLoading(true);
    setError(null);
    setResults(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch('/api/agents/analyze-photo', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        throw new Error(`API returned ${res.status}`);
      }

      const data: PhotoResponse = await res.json();
      if (data.error) {
        setError(data.error);
      } else {
        setResults(data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setFile(null);
    setPreview(null);
    setResults(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="photo">
      <div className="photo-upload-section">
        <div
          className={`photo-dropzone ${preview ? 'has-image' : ''}`}
          onClick={() => fileInputRef.current?.click()}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
        >
          {preview ? (
            <img src={preview} alt="Selected" className="photo-preview" />
          ) : (
            <div className="photo-dropzone-content">
              <div className="photo-dropzone-icon">+</div>
              <div className="photo-dropzone-text">
                Drop an image here or click to select
              </div>
              <div className="photo-dropzone-hint">
                JPEG, PNG, GIF, or WebP - up to 20 MB
              </div>
            </div>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/gif,image/webp"
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />
        </div>

        <div className="photo-controls">
          <button
            className="photo-btn primary"
            onClick={handleAnalyze}
            disabled={!file || loading}
          >
            {loading ? 'Analyzing...' : 'Identify Books'}
          </button>
          <button
            className="photo-btn"
            onClick={handleClear}
            disabled={loading}
          >
            Clear
          </button>
          {file && (
            <span className="photo-file-info">
              {file.name} ({(file.size / 1024).toFixed(0)} KB)
            </span>
          )}
        </div>
      </div>

      {error && <div className="photo-error">{error}</div>}

      {loading && (
        <div className="photo-loading">
          <div className="spinner" />
          <div>Analyzing image with vision AI...</div>
          <div className="photo-loading-hint">
            Identifying books and looking up metadata
          </div>
        </div>
      )}

      {results && (
        <>
          <div className="photo-stats">
            <div className="stat-card">
              <div className="stat-label">Identified</div>
              <div className="stat-value">{results.total_identified}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Matched</div>
              <div className="stat-value green">{results.total_matched}</div>
            </div>
          </div>

          <div className="photo-results">
            {results.books.map((book, i) => (
              <div key={i} className="photo-result-card">
                <div className={`photo-result-indicator ${book.matched_title ? 'matched' : 'unmatched'}`} />
                <div className="photo-result-body">
                  <div className="photo-result-extracted">
                    {book.extracted_title || 'Unknown title'}
                    {book.extracted_author && (
                      <span className="photo-result-author"> by {book.extracted_author}</span>
                    )}
                  </div>
                  {book.matched_title ? (
                    <>
                      <div className="photo-result-matched">{book.matched_title}</div>
                      <div className="photo-result-meta">
                        {book.matched_authors.length > 0 && (
                          <span>{book.matched_authors.join(', ')}</span>
                        )}
                        {book.year && <span>{book.year}</span>}
                      </div>
                    </>
                  ) : (
                    <div className="photo-result-no-match">No database match</div>
                  )}
                  {book.notes && (
                    <div className="photo-result-notes">{book.notes}</div>
                  )}
                </div>
                <div className="photo-result-confidence">
                  <div className="photo-result-confidence-value">
                    {Math.round(book.confidence * 100)}%
                  </div>
                  <div className="photo-result-confidence-label">visual</div>
                  {book.match_confidence != null && (
                    <>
                      <div className="photo-result-confidence-value">
                        {Math.round(book.match_confidence * 100)}%
                      </div>
                      <div className="photo-result-confidence-label">match</div>
                    </>
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
