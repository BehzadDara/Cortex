import { speakText } from "../api";

const SCHEDULE_LEAD_SECONDS = 0.03;
const RECENT_SPEECH_MS = 15_000;

interface PlayerEvents {
  onPlaying: () => void;
  onIdle: () => void;
}

interface SpokenSegment {
  text: string;
  at: number;
}

export class SpeechPlayer {
  private context = new AudioContext();
  private analyser: AnalyserNode;
  private samples: Float32Array<ArrayBuffer>;
  private synthesis: Promise<void> = Promise.resolve();
  private abort = new AbortController();
  private sources = new Set<AudioBufferSourceNode>();
  private playhead = 0;
  private queued = 0;
  private spoken: SpokenSegment[] = [];

  constructor(private events: PlayerEvents) {
    this.analyser = this.context.createAnalyser();
    this.analyser.fftSize = 512;
    this.samples = new Float32Array(this.analyser.fftSize);
    this.analyser.connect(this.context.destination);
  }

  unlock(): Promise<void> {
    return this.context.resume();
  }

  get busy(): boolean {
    return this.queued > 0;
  }

  get playing(): boolean {
    return this.sources.size > 0 && this.context.state === "running";
  }

  enqueue(text: string): void {
    const signal = this.abort.signal;
    this.queued++;
    this.synthesis = this.synthesis.then(async () => {
      if (signal.aborted) return;
      try {
        const buffer = await this.synthesize(text, signal);
        if (!signal.aborted) this.schedule(buffer, text);
      } catch {
        if (!signal.aborted) this.settle();
      }
    });
  }

  pause(): Promise<void> {
    return this.context.suspend();
  }

  resume(): Promise<void> {
    return this.context.resume();
  }

  clear(): void {
    this.abort.abort();
    this.abort = new AbortController();
    this.synthesis = Promise.resolve();
    for (const source of this.sources) {
      source.onended = null;
      source.stop();
    }
    this.sources.clear();
    this.queued = 0;
    this.playhead = 0;
    void this.context.resume();
  }

  async close(): Promise<void> {
    this.clear();
    await this.context.close();
  }

  level(): number {
    if (!this.playing) return 0;
    this.analyser.getFloatTimeDomainData(this.samples);
    return rootMeanSquare(this.samples);
  }

  recentlySpoken(): string {
    const since = performance.now() - RECENT_SPEECH_MS;
    this.spoken = this.spoken.filter((segment) => segment.at >= since);
    return this.spoken.map((segment) => segment.text).join(" ");
  }

  private async synthesize(text: string, signal: AbortSignal): Promise<AudioBuffer> {
    const audio = await speakText(text, signal);
    return this.context.decodeAudioData(await audio.arrayBuffer());
  }

  private schedule(buffer: AudioBuffer, text: string): void {
    const source = this.context.createBufferSource();
    source.buffer = buffer;
    source.connect(this.analyser);
    const startsAt = Math.max(
      this.context.currentTime + SCHEDULE_LEAD_SECONDS,
      this.playhead,
    );
    this.playhead = startsAt + buffer.duration;
    const wasSilent = this.sources.size === 0;
    this.sources.add(source);
    source.onended = () => {
      this.sources.delete(source);
      this.settle();
    };
    source.start(startsAt);
    this.spoken.push({ text, at: performance.now() });
    if (wasSilent) this.events.onPlaying();
  }

  private settle(): void {
    this.queued = Math.max(0, this.queued - 1);
    if (this.queued === 0) this.events.onIdle();
  }
}

export function rootMeanSquare(samples: Float32Array): number {
  let sum = 0;
  for (const sample of samples) sum += sample * sample;
  return Math.sqrt(sum / samples.length);
}
