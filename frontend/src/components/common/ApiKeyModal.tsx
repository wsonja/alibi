/**
 * ApiKeyModal — paste a Gemini API key. It is POSTed once to the local backend (/api/settings/api-key), which
 * writes it into backend/.env. The key is never logged, never stored in the browser, and cleared from the
 * input as soon as the dialog closes.
 */
import { useRef, useState, type FormEvent } from 'react'
import { api, errorMessage } from '@/api/client'
import type { LlmMode } from '@/api/types'
import { Button } from './Button'
import { Modal } from './Modal'

export interface ApiKeyModalProps {
  open: boolean
  onClose: () => void
  onSaved?: (mode: LlmMode) => void
  currentMode?: LlmMode | null
}

export function ApiKeyModal({ open, onClose, onSaved, currentMode }: ApiKeyModalProps) {
  const [value, setValue] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [savedMode, setSavedMode] = useState<LlmMode | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)

  /** Close and forget everything typed — the key never lingers in component state. */
  const close = () => {
    setValue('')
    setError(null)
    setBusy(false)
    setSavedMode(null)
    onClose()
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const key = value.trim()
    if (!key) {
      setError('Paste a key first.')
      return
    }
    if (key.length < 20 || /\s/.test(key)) {
      setError('That does not look like a Gemini API key.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const res = await api.setApiKey(key)
      setValue('')
      setSavedMode(res.llm_mode)
      onSaved?.(res.llm_mode)
    } catch (err) {
      setError(errorMessage(err, 'The backend refused the key.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open={open} onClose={close} title="Gemini API key" width={520} initialFocus={inputRef}>
      <form onSubmit={submit} className="flex flex-col gap-3" autoComplete="off">
        <p className="ink" style={{ margin: 0 }}>
          Live suspects are performed by Google Gemini. Paste a key from{' '}
          <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noreferrer">
            Google AI Studio
          </a>
          . It is sent once to your <em>local</em> backend, which stores it only in <code className="mono">backend/.env</code> (gitignored). Nothing is kept in this browser.
        </p>
        {currentMode ? (
          <p className="ink-soft" style={{ margin: 0, fontSize: 14 }}>
            Current mode: <strong>{currentMode === 'gemini' ? 'Live Gemini' : 'Scripted (offline performer)'}</strong>
          </p>
        ) : null}
        <label className="flex flex-col gap-1">
          <span className="label-caps">API key</span>
          <input
            ref={inputRef}
            type="password"
            className="field mono"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="AIza…"
            autoComplete="off"
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            name="gemini-api-key"
            aria-invalid={error ? true : undefined}
            aria-describedby="apikey-help"
            disabled={busy}
          />
        </label>
        <p id="apikey-help" className="ink-soft" style={{ margin: 0, fontSize: 13 }}>
          Never share the key. You can revoke it in AI Studio at any time; the backend switches to the scripted performer when no key is set.
        </p>
        {error ? (
          <p role="alert" style={{ margin: 0, color: 'var(--red-600)', fontSize: 14 }}>
            {error}
          </p>
        ) : null}
        {savedMode ? (
          <p role="status" style={{ margin: 0, color: 'var(--truth)', fontSize: 14 }}>
            Saved. Suspects are now {savedMode === 'gemini' ? 'Live Gemini' : 'Scripted'}.
          </p>
        ) : null}
        <div className="flex flex-wrap justify-end gap-2 pt-1">
          <Button variant="black" onClick={close} disabled={busy}>
            {savedMode ? 'Done' : 'Cancel'}
          </Button>
          <Button type="submit" loading={busy} disabled={!value.trim()}>
            Save key
          </Button>
        </div>
      </form>
    </Modal>
  )
}

export default ApiKeyModal
