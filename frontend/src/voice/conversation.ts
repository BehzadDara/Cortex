import { transcribeAudio, warmUpVoice } from "../api";
import { END_OF_TURN_SILENCE_MS, VoiceListener } from "./listener";
import { SpeechPlayer } from "./player";
import { SpeechSegmenter } from "./segmenter";

export type VoicePhase =
  | "starting"
  | "listening"
  | "hearing"
  | "transcribing"
  | "thinking"
  | "speaking"
  | "confirming"
  | "failed";

export interface TurnLatency {
  endpointMs: number;
  transcribeMs: number;
  thinkMs: number;
  voiceMs: number;
  totalMs: number;
}

export interface VoiceSnapshot {
  phase: VoicePhase;
  muted: boolean;
  heard: string | null;
  notice: string | null;
  failure: string | null;
  latency: TurnLatency | null;
}

export interface VoiceHost {
  ask: (question: string) => void;
  decide: (approved: boolean) => void;
}

export interface VoiceApproval {
  name: string;
  arguments: Record<string, unknown>;
}

interface Turn {
  question: string;
  heardAt: number | null;
  askedAt: number;
  firstTokenAt: number | null;
  firstAudioAt: number | null;
  streaming: boolean;
  silenced: boolean;
}

const CONTINUATION_WINDOW_MS = 5000;
const CONSENT_MAX_WORDS = 6;
const ECHO_OVERLAP = 0.8;
const FAILURE_REPLY = "Sorry, I ran into a problem answering that.";
const YES = /\b(yes|yeah|yep|yup|sure|okay|ok|go ahead|do it|please do|allow|approve|go for it|of course|absolutely|sounds good)\b/i;
const NO = /\b(no|nope|nah|don't|do not|cancel|deny|skip|stop|never mind|not now)\b/i;

export class VoiceConversation {
  private listener: VoiceListener | null = null;
  private player: SpeechPlayer;
  private segmenter = new SpeechSegmenter();
  private subscribers = new Set<() => void>();
  private utterances: Promise<void> = Promise.resolve();
  private turn: Turn | null = null;
  private starting = true;
  private stopped = false;
  private muted = false;
  private userSpeaking = false;
  private transcribing = 0;
  private interrupted = false;
  private awaitingConsent = false;
  private heard: string | null = null;
  private notice: string | null = null;
  private failure: string | null = null;
  private latency: TurnLatency | null = null;
  private snapshot: VoiceSnapshot;

  constructor(private host: VoiceHost) {
    this.player = new SpeechPlayer({
      onPlaying: () => this.audioStarted(),
      onIdle: () => this.audioFinished(),
    });
    this.snapshot = this.describe();
  }

  subscribe = (subscriber: () => void): (() => void) => {
    this.subscribers.add(subscriber);
    return () => this.subscribers.delete(subscriber);
  };

  getSnapshot = (): VoiceSnapshot => this.snapshot;

  async start(): Promise<void> {
    const unlocking = this.player.unlock();
    const listening = VoiceListener.start({
      onSpeechStart: () => this.speechStarted(),
      onSpeechConfirmed: () => this.speechConfirmed(),
      onMisfire: () => this.speechDismissed(),
      onSpeechEnd: (audio) => this.speechEnded(audio),
    });
    const [listener, warmed] = await Promise.allSettled([
      listening,
      warmUpVoice(),
      unlocking,
    ]);
    if (listener.status === "fulfilled") {
      if (this.stopped || warmed.status === "rejected") void listener.value.destroy();
      else this.listener = listener.value;
    }
    if (listener.status === "rejected") this.failure = startFailure(listener.reason);
    else if (warmed.status === "rejected") this.failure = startFailure(warmed.reason);
    this.starting = false;
    this.emit();
  }

  stop(): void {
    this.stopped = true;
    void this.listener?.destroy();
    this.listener = null;
    void this.player.close();
    this.subscribers.clear();
  }

  level(): number {
    return this.player.playing ? this.player.level() : (this.listener?.level() ?? 0);
  }

  async setMuted(muted: boolean): Promise<void> {
    this.muted = muted;
    if (muted) {
      this.userSpeaking = false;
      this.resumeInterrupted();
    }
    this.emit();
    await this.listener?.mute(muted);
  }

  silence(): void {
    this.player.clear();
    this.interrupted = false;
    if (this.turn) this.turn.silenced = true;
    this.emit();
  }

  token(text: string): void {
    const turn = this.turn;
    if (!turn || !turn.streaming || turn.silenced) return;
    const first = turn.firstTokenAt === null;
    turn.firstTokenAt ??= performance.now();
    this.speak(this.segmenter.push(text));
    if (first) this.emit();
  }

  finished(): void {
    const turn = this.turn;
    if (!turn || !turn.streaming) return;
    if (!turn.silenced) this.speak(this.segmenter.flush());
    turn.streaming = false;
    this.emit();
  }

  failed(message: string): void {
    const turn = this.turn;
    if (!turn) return;
    this.segmenter.reset();
    if (turn.streaming && !turn.silenced) this.player.enqueue(FAILURE_REPLY);
    turn.streaming = false;
    this.notice = message;
    this.emit();
  }

  approval(request: VoiceApproval): void {
    const turn = this.turn;
    if (!turn) return;
    if (!turn.silenced) {
      this.speak(this.segmenter.flush());
      this.player.enqueue(consentQuestion(request));
    }
    turn.streaming = false;
    this.awaitingConsent = true;
    this.emit();
  }

  approvalDecided(): void {
    this.player.clear();
    this.segmenter.reset();
    this.interrupted = false;
    this.awaitingConsent = false;
    this.turn = this.newTurn(this.turn?.question ?? "", null);
    this.emit();
  }

  private get ready(): boolean {
    return !this.starting && !this.stopped && this.failure === null;
  }

  private speechStarted(): void {
    if (!this.ready) return;
    this.userSpeaking = true;
    this.emit();
  }

  private speechConfirmed(): void {
    if (!this.ready) return;
    if (this.player.busy && !this.interrupted) {
      this.interrupted = true;
      void this.player.pause();
    }
    this.emit();
  }

  private speechDismissed(): void {
    this.userSpeaking = false;
    this.resumeInterrupted();
    this.emit();
  }

  private speechEnded(audio: Blob): void {
    if (!this.ready) return;
    const heardAt = performance.now();
    this.userSpeaking = false;
    this.transcribing++;
    this.emit();
    this.utterances = this.utterances.then(() => this.understand(audio, heardAt));
  }

  private async understand(audio: Blob, heardAt: number): Promise<void> {
    let text = "";
    try {
      text = (await transcribeAudio(audio)).trim();
    } catch {
      this.notice = "Could not transcribe that — please say it again.";
    }
    this.transcribing--;
    if (this.stopped) return;
    this.respond(text, heardAt);
    this.emit();
  }

  private respond(text: string, heardAt: number): void {
    const echo = this.interrupted && isEcho(text, this.player.recentlySpoken());
    if (!hasWords(text) || echo) {
      this.resumeInterrupted();
      return;
    }
    this.notice = null;
    const consent = this.awaitingConsent ? consentIn(text) : null;
    if (consent !== null) {
      this.host.decide(consent);
      return;
    }
    this.ask(text, heardAt);
  }

  private ask(text: string, heardAt: number): void {
    const earlier = this.unansweredQuestion();
    const question = earlier ? `${earlier} ${text}` : text;
    this.player.clear();
    this.segmenter.reset();
    this.interrupted = false;
    this.awaitingConsent = false;
    this.heard = question;
    this.turn = this.newTurn(question, heardAt);
    this.host.ask(question);
  }

  private unansweredQuestion(): string | null {
    const turn = this.turn;
    if (!turn || !turn.streaming || this.awaitingConsent) return null;
    const recent = performance.now() - turn.askedAt < CONTINUATION_WINDOW_MS;
    const unanswered = turn.firstAudioAt === null && turn.heardAt !== null;
    return recent && unanswered ? turn.question : null;
  }

  private newTurn(question: string, heardAt: number | null): Turn {
    return {
      question,
      heardAt,
      askedAt: performance.now(),
      firstTokenAt: null,
      firstAudioAt: null,
      streaming: true,
      silenced: false,
    };
  }

  private speak(segments: string[]): void {
    for (const segment of segments) this.player.enqueue(segment);
  }

  private audioStarted(): void {
    this.listener?.guard(true);
    const turn = this.turn;
    if (turn && turn.firstAudioAt === null) {
      turn.firstAudioAt = performance.now();
      this.latency = measure(turn) ?? this.latency;
    }
    this.emit();
  }

  private audioFinished(): void {
    this.listener?.guard(false);
    this.emit();
  }

  private resumeInterrupted(): void {
    if (!this.interrupted) return;
    this.interrupted = false;
    void this.player.resume();
  }

  private phase(): VoicePhase {
    if (this.failure) return "failed";
    if (this.starting) return "starting";
    if (this.userSpeaking && !this.muted) return "hearing";
    if (this.transcribing > 0) return "transcribing";
    if (this.player.playing) return "speaking";
    if (this.awaitingConsent) return "confirming";
    const turn = this.turn;
    const answering = turn && !turn.silenced && (turn.streaming || this.player.busy);
    return answering ? "thinking" : "listening";
  }

  private describe(): VoiceSnapshot {
    return {
      phase: this.phase(),
      muted: this.muted,
      heard: this.heard,
      notice: this.notice,
      failure: this.failure,
      latency: this.latency,
    };
  }

  private emit(): void {
    const next = this.describe();
    const changed = (Object.keys(next) as (keyof VoiceSnapshot)[]).some(
      (key) => next[key] !== this.snapshot[key],
    );
    if (!changed) return;
    this.snapshot = next;
    for (const subscriber of this.subscribers) subscriber();
  }
}

function measure(turn: Turn): TurnLatency | null {
  const { heardAt, askedAt, firstTokenAt, firstAudioAt } = turn;
  if (heardAt === null || firstTokenAt === null || firstAudioAt === null) return null;
  return {
    endpointMs: END_OF_TURN_SILENCE_MS,
    transcribeMs: askedAt - heardAt,
    thinkMs: firstTokenAt - askedAt,
    voiceMs: firstAudioAt - firstTokenAt,
    totalMs: END_OF_TURN_SILENCE_MS + firstAudioAt - heardAt,
  };
}

function hasWords(text: string): boolean {
  return /[\p{L}\p{N}]/u.test(text);
}

function words(text: string): string[] {
  return text.toLowerCase().match(/[\p{L}\p{N}']+/gu) ?? [];
}

function isEcho(text: string, recentlySpoken: string): boolean {
  const heard = words(text);
  const spoken = new Set(words(recentlySpoken));
  if (heard.length === 0 || spoken.size === 0) return false;
  const overlap = heard.filter((word) => spoken.has(word)).length / heard.length;
  return overlap >= ECHO_OVERLAP;
}

function consentIn(text: string): boolean | null {
  if (words(text).length > CONSENT_MAX_WORDS) return null;
  const yes = YES.exec(text)?.index ?? Infinity;
  const no = NO.exec(text)?.index ?? Infinity;
  if (yes === Infinity && no === Infinity) return null;
  return yes < no;
}

function consentQuestion(request: VoiceApproval): string {
  const query = String(request.arguments.query ?? "").trim();
  if (request.name === "run_python") {
    return "I wrote a short Python script for that. Should I run it?";
  }
  if (!query) return "Should I search the web for that?";
  if (request.name === "web_image_search") {
    return `Should I look for pictures of ${query} on the web?`;
  }
  if (request.name === "web_video_search") {
    return `Should I look for videos of ${query} on the web?`;
  }
  return `Should I search the web for ${query}?`;
}

function startFailure(reason: unknown): string {
  if (reason instanceof DOMException) {
    if (reason.name === "NotAllowedError" || reason.name === "SecurityError") {
      return "Microphone access is blocked. Allow it in the browser's site settings, then try again.";
    }
    if (reason.name === "NotFoundError") {
      return "No microphone was found. Connect one, then try again.";
    }
  }
  return reason instanceof Error ? reason.message : String(reason);
}
