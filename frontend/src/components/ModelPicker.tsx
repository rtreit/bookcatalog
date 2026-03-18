import './ModelPicker.css';
import type { AgentModelOption } from '../hooks/useAgentModelConfig';

interface ModelPickerProps {
  title: string;
  helperText: string;
  selectedModel: string;
  defaultModel: string;
  options: AgentModelOption[];
  loading: boolean;
  disabled?: boolean;
  error?: string | null;
  onChange: (value: string) => void;
}

export default function ModelPicker({
  title,
  helperText,
  selectedModel,
  defaultModel,
  options,
  loading,
  disabled = false,
  error = null,
  onChange,
}: ModelPickerProps) {
  const selectedOption = options.find(option => option.value === selectedModel);
  const effectiveModel = selectedModel || defaultModel;

  return (
    <div className="model-picker">
      <div className="model-picker-header">
        <div className="model-picker-title">{title}</div>
        <div className="model-picker-helper">{helperText}</div>
      </div>

      <div className="model-picker-controls">
        <label className="model-picker-field">
          <span className="model-picker-label">Model</span>
          <select
            className="model-picker-select"
            value={effectiveModel}
            onChange={e => onChange(e.target.value)}
            disabled={loading || disabled || options.length === 0}
          >
            {options.map(option => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="model-picker-meta">
        {loading ? (
          <span>Loading available models...</span>
        ) : (
          <>
            <span>Configured default: <code>{defaultModel || '(unknown)'}</code></span>
            {selectedOption?.description && (
              <span>{selectedOption.description}</span>
            )}
          </>
        )}
      </div>

      {error && <div className="model-picker-error">{error}</div>}
    </div>
  );
}
