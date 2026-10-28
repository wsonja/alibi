import { describe, expect, it, vi } from 'vitest'
import { FACE_DELEGATES, createLandmarkerWithFallback, type FaceDelegate } from './faceLandmarker'

describe('createLandmarkerWithFallback', () => {
  it('lists GPU then CPU so WebGL-less hosts still have a path', () => {
    expect(FACE_DELEGATES).toEqual(['GPU', 'CPU'])
  })

  it('falls back to CPU when GPU create throws (kGpuService / WebGL error 0)', async () => {
    const tries: FaceDelegate[] = []
    const fake = { id: 'cpu-lm' } as never
    const create = vi.fn(async (delegate: FaceDelegate) => {
      tries.push(delegate)
      if (delegate === 'GPU') {
        throw new Error(
          'INTERNAL: Service "kGpuService" ... emscripten_webgl_create_context() returned error 0; StartGraph failed',
        )
      }
      return fake
    })

    const out = await createLandmarkerWithFallback(create)
    expect(tries).toEqual(['GPU', 'CPU'])
    expect(out.delegate).toBe('CPU')
    expect(out.landmarker).toBe(fake)
  })

  it('surfaces the last error when every delegate fails', async () => {
    await expect(
      createLandmarkerWithFallback(async () => {
        throw new Error('nope')
      }),
    ).rejects.toThrow('nope')
  })
})
