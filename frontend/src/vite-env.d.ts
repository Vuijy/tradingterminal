/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the backend API. Empty -> use the dev proxy at /api/v1. */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
