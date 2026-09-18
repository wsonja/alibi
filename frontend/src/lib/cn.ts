/** Tiny classnames helper: cn('a', cond && 'b', undefined) → "a b". */
export function cn(...parts: Array<string | false | null | undefined | 0>): string {
  return parts.filter(Boolean).join(' ')
}
