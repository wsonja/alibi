// placeholder — replaced by the sensors lane
// Contract (docs/INTERFACES.md §7): startFace(video, onSample), stopFace(), startVoiceStress(stream, onSample).
// The real implementation runs @mediapipe/tasks-vision FaceLandmarker at ~15 fps and emits a FaceSample every ~2 s.
import type { FaceSample, VoiceSample } from '@/store/sensors'

let running = false

/** Start the face pipeline on a playing <video>. The placeholder emits nothing (the meter shows "calibrating"). */
export async function startFace(_video: HTMLVideoElement, _onSample: (s: FaceSample) => void): Promise<void> {
  running = true
}

export function stopFace(): void {
  running = false
}

export function faceRunning(): boolean {
  return running
}

/** Start voice-stress sampling on a mic stream. Returns a stop function. The placeholder emits nothing. */
export function startVoiceStress(_stream: MediaStream, _onSample: (s: VoiceSample) => void): () => void {
  return () => {}
}
