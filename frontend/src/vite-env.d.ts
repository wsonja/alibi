/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the FastAPI backend. Default: http://localhost:8000 */
  readonly VITE_API_URL?: string
  /** "webspeech" (default) or "elevenlabs" */
  readonly VITE_TTS_PROVIDER?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
