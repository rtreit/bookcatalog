import { useCallback, useEffect, useState } from 'react';

export interface AgentModelOption {
  value: string;
  label: string;
  description: string;
}

interface AgentModelGroup {
  default_model: string;
  options: AgentModelOption[];
}

interface AgentModelOptionsResponse {
  chat: AgentModelGroup;
  vision: AgentModelGroup;
  error?: string;
}

export type AgentModelKind = 'chat' | 'vision';

let cachedModelOptions: AgentModelOptionsResponse | null = null;
let modelOptionsPromise: Promise<AgentModelOptionsResponse> | null = null;

async function loadAgentModelOptions(): Promise<AgentModelOptionsResponse> {
  if (cachedModelOptions) {
    return cachedModelOptions;
  }

  if (!modelOptionsPromise) {
    modelOptionsPromise = fetch('/api/agents/model-options')
      .then(async res => {
        const data = await res.json() as AgentModelOptionsResponse;
        if (!res.ok || data.error) {
          throw new Error(data.error || `API returned ${res.status}`);
        }
        cachedModelOptions = data;
        return data;
      })
      .finally(() => {
        modelOptionsPromise = null;
      });
  }

  return modelOptionsPromise;
}

function readStoredModel(storageKey: string): string | null {
  try {
    return window.localStorage.getItem(storageKey);
  } catch {
    return null;
  }
}

function storeModel(storageKey: string, value: string): void {
  try {
    window.localStorage.setItem(storageKey, value);
  } catch {
    // Ignore storage errors and keep the in-memory selection.
  }
}

export function useAgentModelConfig(kind: AgentModelKind, storageKey: string) {
  const [defaultModel, setDefaultModel] = useState('');
  const [selectedModel, setSelectedModelState] = useState('');
  const [options, setOptions] = useState<AgentModelOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await loadAgentModelOptions();
        if (cancelled) return;

        const group = data[kind];
        const storedModel = readStoredModel(storageKey);
        const hasStoredModel = storedModel != null && group.options.some(
          option => option.value === storedModel
        );
        const nextModel = hasStoredModel
          ? storedModel as string
          : group.default_model;

        setDefaultModel(group.default_model);
        setOptions(group.options);
        setSelectedModelState(nextModel);
        storeModel(storageKey, nextModel);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load model options');
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, [kind, storageKey]);

  const setSelectedModel = useCallback((value: string) => {
    setSelectedModelState(value);
    storeModel(storageKey, value);
  }, [storageKey]);

  return {
    defaultModel,
    selectedModel,
    setSelectedModel,
    options,
    loading,
    error,
  };
}
