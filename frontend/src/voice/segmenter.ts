const FENCE = "```";
const FIRST_SEGMENT_MIN_CHARS = 12;
const FIRST_CLAUSE_MIN_CHARS = 24;
const SEGMENT_MIN_CHARS = 60;
const SEGMENT_MAX_CHARS = 280;
const SENTENCE_END = /[.!?…؟]+["'”’»)\]]*(?=\s)/g;
const CLAUSE_END = /[,;:—–،؛](?=\s)/g;
const BULLET = /^[-*+•]\s+/;
const ABBREVIATIONS = new Set([
  "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc", "e.g", "i.e", "approx", "no",
]);

export class SpeechSegmenter {
  private raw = "";
  private prose = "";
  private inFence = false;
  private emitted = 0;

  push(text: string): string[] {
    this.raw += text;
    this.absorbRaw(false);
    return this.takeSegments(false);
  }

  flush(): string[] {
    this.absorbRaw(true);
    const segments = this.takeSegments(true);
    this.reset();
    return segments;
  }

  reset(): void {
    this.raw = "";
    this.prose = "";
    this.inFence = false;
    this.emitted = 0;
  }

  private absorbRaw(final: boolean): void {
    while (this.raw) {
      const fence = this.raw.indexOf(FENCE);
      if (this.inFence) {
        if (fence < 0) {
          this.raw = final ? "" : this.raw.slice(-(FENCE.length - 1));
          return;
        }
        this.raw = this.raw.slice(fence + FENCE.length);
        this.inFence = false;
        continue;
      }
      if (fence >= 0) {
        this.prose += this.raw.slice(0, fence) + "\n";
        this.raw = this.raw.slice(fence + FENCE.length);
        this.inFence = true;
        continue;
      }
      const held = final ? 0 : trailingBackticks(this.raw);
      this.prose += this.raw.slice(0, this.raw.length - held);
      this.raw = this.raw.slice(this.raw.length - held);
      return;
    }
  }

  private takeSegments(final: boolean): string[] {
    const segments: string[] = [];
    for (let cut = this.nextCut(); cut > 0; cut = this.nextCut()) {
      this.emit(this.prose.slice(0, cut), segments);
      this.prose = this.prose.slice(cut);
    }
    if (final) {
      this.emit(this.prose, segments);
      this.prose = "";
    }
    return segments;
  }

  private nextCut(): number {
    const newline = this.prose.indexOf("\n");
    const cuts = [this.sentenceCut(), newline >= 0 ? newline + 1 : -1];
    if (this.emitted === 0) {
      cuts.push(firstBoundaryFrom(this.prose, CLAUSE_END, FIRST_CLAUSE_MIN_CHARS));
    }
    const ready = cuts.filter((cut) => cut > 0);
    if (ready.length > 0) return Math.min(...ready);
    if (this.prose.length > SEGMENT_MAX_CHARS) return hardCut(this.prose);
    return -1;
  }

  private sentenceCut(): number {
    const minimum = this.emitted === 0 ? FIRST_SEGMENT_MIN_CHARS : SEGMENT_MIN_CHARS;
    for (const match of this.prose.matchAll(SENTENCE_END)) {
      const end = (match.index ?? 0) + match[0].length;
      if (end < minimum) continue;
      if (isAbbreviation(this.prose.slice(0, match.index ?? 0))) continue;
      return end;
    }
    return -1;
  }

  private emit(text: string, segments: string[]): void {
    const segment = text.replace(/\s+/g, " ").trim().replace(BULLET, "");
    if (!isSpeakable(segment)) return;
    segments.push(segment);
    this.emitted++;
  }
}

function trailingBackticks(text: string): number {
  let count = 0;
  while (count < FENCE.length - 1 && text[text.length - 1 - count] === "`") count++;
  return count;
}

function isAbbreviation(before: string): boolean {
  const word = /([A-Za-z.]+)$/.exec(before)?.[1]?.toLowerCase();
  return word !== undefined && ABBREVIATIONS.has(word);
}

function firstBoundaryFrom(text: string, pattern: RegExp, minimum: number): number {
  for (const match of text.matchAll(pattern)) {
    const end = (match.index ?? 0) + match[0].length;
    if (end >= minimum) return end;
  }
  return -1;
}

function hardCut(text: string): number {
  const window = text.slice(0, SEGMENT_MAX_CHARS);
  const clause = Math.max(...[",", ";", ":"].map((mark) => window.lastIndexOf(mark)));
  if (clause > SEGMENT_MAX_CHARS / 2) return clause + 1;
  const space = window.lastIndexOf(" ");
  return space > 0 ? space + 1 : SEGMENT_MAX_CHARS;
}

function isSpeakable(segment: string): boolean {
  if (segment.startsWith("|")) return false;
  return /[\p{L}\p{N}]/u.test(segment);
}
