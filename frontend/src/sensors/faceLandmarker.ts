/**
 * FaceLandmarker creation with GPU → CPU fallback.
 * Many browsers (and cloud VMs) fail `emscripten_webgl_create_context`; CPU still works.
 */
import { FaceLandmarker, FilesetResolver, type FaceLandmarkerOptions } from '@mediapipe/tasks-vision'

export const FACE_WASM_CDN = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.1.1/wasm'
export const FACE_MODEL_URL =
  'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task'

export type FaceDelegate = 'GPU' | 'CPU'

/** Try GPU first for speed; always keep CPU so WebGL-less environments still run. */
export const FACE_DELEGATES: readonly FaceDelegate[] = ['GPU', 'CPU']

export function landmarkerOptions(delegate: FaceDelegate): FaceLandmarkerOptions {
  return {
    baseOptions: { modelAssetPath: FACE_MODEL_URL, delegate },
    runningMode: 'VIDEO',
    numFaces: 1,
    outputFaceBlendshapes: true,
    outputFacialTransformationMatrixes: true,
  }
}

/**
 * Walk FACE_DELEGATES until one create() succeeds.
 * Used by the live pipeline and unit-tested with a fake create().
 */
export async function createLandmarkerWithFallback(
  create: (delegate: FaceDelegate) => Promise<FaceLandmarker>,
  delegates: readonly FaceDelegate[] = FACE_DELEGATES,
): Promise<{ landmarker: FaceLandmarker; delegate: FaceDelegate }> {
  let lastError: unknown
  for (const delegate of delegates) {
    try {
      const landmarker = await create(delegate)
      return { landmarker, delegate }
    } catch (err) {
      lastError = err
    }
  }
  throw lastError instanceof Error ? lastError : new Error(String(lastError ?? 'FaceLandmarker create failed'))
}

export async function loadVisionFileset() {
  return FilesetResolver.forVisionTasks(FACE_WASM_CDN)
}

export async function createBrowserFaceLandmarker(): Promise<{ landmarker: FaceLandmarker; delegate: FaceDelegate }> {
  const vision = await loadVisionFileset()
  return createLandmarkerWithFallback((delegate) => FaceLandmarker.createFromOptions(vision, landmarkerOptions(delegate)))
}
