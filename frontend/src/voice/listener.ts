import type { MicVAD } from "@ricky0123/vad-web";
import { encodeWavPcm16 } from "../audio";
import { rootMeanSquare } from "./player";

const VAD_ASSETS = "/vad/";
const VAD_SAMPLE_RATE = 16000;
const LEVEL_SMOOTHING = 0.35;

export const END_OF_TURN_SILENCE_MS = 600;

const OPEN_SENSITIVITY = {
  positiveSpeechThreshold: 0.5,
  negativeSpeechThreshold: 0.35,
  minSpeechMs: 250,
};

const GUARDED_SENSITIVITY = {
  positiveSpeechThreshold: 0.8,
  negativeSpeechThreshold: 0.6,
  minSpeechMs: 400,
};

export interface ListenerEvents {
  onSpeechStart: () => void;
  onSpeechConfirmed: () => void;
  onMisfire: () => void;
  onSpeechEnd: (audio: Blob) => void;
}

export class VoiceListener {
  private smoothedLevel = 0;

  private constructor(private vad: MicVAD) {}

  static async start(events: ListenerEvents): Promise<VoiceListener> {
    const { MicVAD } = await import("@ricky0123/vad-web");
    let listener: VoiceListener | null = null;
    const vad = await MicVAD.new({
      model: "v5",
      baseAssetPath: VAD_ASSETS,
      onnxWASMBasePath: VAD_ASSETS,
      ...OPEN_SENSITIVITY,
      redemptionMs: END_OF_TURN_SILENCE_MS,
      preSpeechPadMs: 300,
      startOnLoad: false,
      getStream: openMicrophone,
      resumeStream: openMicrophone,
      onFrameProcessed: (_, frame) => listener?.track(frame),
      onSpeechStart: events.onSpeechStart,
      onSpeechRealStart: events.onSpeechConfirmed,
      onVADMisfire: events.onMisfire,
      onSpeechEnd: (audio) => events.onSpeechEnd(encodeWavPcm16(audio, VAD_SAMPLE_RATE)),
    });
    listener = new VoiceListener(vad);
    await vad.start();
    return listener;
  }

  level(): number {
    return this.vad.listening ? this.smoothedLevel : 0;
  }

  guard(guarded: boolean): void {
    this.vad.setOptions(guarded ? GUARDED_SENSITIVITY : OPEN_SENSITIVITY);
  }

  async mute(muted: boolean): Promise<void> {
    if (muted) {
      await this.vad.pause();
      this.smoothedLevel = 0;
    } else {
      await this.vad.start();
    }
  }

  destroy(): Promise<void> {
    return this.vad.destroy().catch(() => {});
  }

  private track(frame: Float32Array): void {
    const level = rootMeanSquare(frame);
    this.smoothedLevel += (level - this.smoothedLevel) * LEVEL_SMOOTHING;
  }
}

function openMicrophone(): Promise<MediaStream> {
  return navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });
}
