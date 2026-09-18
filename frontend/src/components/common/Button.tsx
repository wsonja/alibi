import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Link, type LinkProps } from 'react-router-dom'
import { cn } from '@/lib/cn'

export type ButtonVariant = 'red' | 'black' | 'ghost'
export type ButtonSize = 'sm' | 'md' | 'lg'

interface StyleProps {
  variant?: ButtonVariant
  size?: ButtonSize
  block?: boolean
}

export function buttonClass({ variant = 'red', size = 'md', block }: StyleProps, extra?: string): string {
  return cn('btn', variant === 'red' && 'btn-red', variant === 'black' && 'btn-black', variant === 'ghost' && 'btn-ghost', size === 'lg' && 'btn--lg', size === 'sm' && 'btn--sm', block && 'btn--block', extra)
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, StyleProps {
  loading?: boolean
  children?: ReactNode
}

/** Red/black lacquer button (DESIGN §7). `loading` shows a spinner and disables the button. */
export function Button({ variant, size, block, loading, className, children, disabled, type = 'button', ...rest }: ButtonProps) {
  return (
    <button type={type} className={buttonClass({ variant, size, block }, cn(loading && 'btn--loading', className))} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {children}
    </button>
  )
}

export interface ButtonLinkProps extends LinkProps, StyleProps {
  children?: ReactNode
}

/** A react-router <Link> styled as a button. */
export function ButtonLink({ variant, size, block, className, children, ...rest }: ButtonLinkProps) {
  return (
    <Link className={buttonClass({ variant, size, block }, className)} {...rest}>
      {children}
    </Link>
  )
}

export default Button
