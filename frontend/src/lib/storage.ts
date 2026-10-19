import { useEffect, useState, type Dispatch, type SetStateAction } from 'react'

/**
 * localStorage helpers. Storage can be missing or throw (private mode, blocked site
 * data), so every access is guarded and callers always get a usable value.
 */

export function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key)
    return raw === null ? fallback : (JSON.parse(raw) as T)
  } catch {
    return fallback
  }
}

export function writeJson(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // storage unavailable; the in-memory state still works for this session
  }
}

/** useState that persists to localStorage under `key`. */
export function useStoredState<T>(key: string, initial: T): [T, Dispatch<SetStateAction<T>>] {
  const [state, setState] = useState<T>(() => readJson(key, initial))
  useEffect(() => {
    writeJson(key, state)
  }, [key, state])
  return [state, setState]
}
