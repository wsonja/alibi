/**
 * BackdropThumb — concept-board scene plate (scene_originals) for crime-scene / search previews.
 */
import { cn } from '@/lib/cn'
import { backdropUrls, sceneForLocation, type BackdropScene } from '@/lib/backdrops'

export interface BackdropThumbProps {
  /** Case location id (study, garden, …) or an explicit scene key. */
  locationId?: string | null
  scene?: BackdropScene
  className?: string
  style?: React.CSSProperties
  title?: string
}

export function BackdropThumb({ locationId, scene, className, style, title }: BackdropThumbProps) {
  const key = scene ?? sceneForLocation(locationId)
  const src = backdropUrls(key).original
  return (
    <img
      src={src}
      alt={title ?? ''}
      className={cn('backdrop-thumb', className)}
      style={{ objectFit: 'cover', objectPosition: 'center', display: 'block', background: '#1a0f0a', ...style }}
      draggable={false}
    />
  )
}

export default BackdropThumb
