const RECORDER_WORKLET = `
class RecorderProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0][0];
    if (channel) this.port.postMessage(channel.slice(0));
    return true;
  }
}
registerProcessor("recorder", RecorderProcessor);
`;

export class Recorder {
  private constructor(
    private context: AudioContext,
    private stream: MediaStream,
    private chunks: Float32Array[],
  ) {}

  static async start(): Promise<Recorder> {
    const context = new AudioContext();
    let stream: MediaStream | null = null;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      await loadRecorderWorklet(context);
      if (context.state === "suspended") await context.resume();
      const chunks: Float32Array[] = [];
      const recorder = new AudioWorkletNode(context, "recorder");
      recorder.port.onmessage = (event) => chunks.push(event.data);
      context.createMediaStreamSource(stream).connect(recorder);
      recorder.connect(context.destination);
      return new Recorder(context, stream, chunks);
    } catch (error) {
      stream?.getTracks().forEach((track) => track.stop());
      await context.close();
      throw error;
    }
  }

  async stop(): Promise<Blob> {
    const sampleRate = this.context.sampleRate;
    await this.release();
    return encodeWavPcm16(concatenate(this.chunks), sampleRate);
  }

  async cancel(): Promise<void> {
    await this.release();
  }

  private async release(): Promise<void> {
    for (const track of this.stream.getTracks()) track.stop();
    if (this.context.state !== "closed") await this.context.close();
  }
}

async function loadRecorderWorklet(context: AudioContext): Promise<void> {
  const module = URL.createObjectURL(
    new Blob([RECORDER_WORKLET], { type: "application/javascript" }),
  );
  try {
    await context.audioWorklet.addModule(module);
  } finally {
    URL.revokeObjectURL(module);
  }
}

function concatenate(chunks: Float32Array[]): Float32Array {
  const total = chunks.reduce((length, chunk) => length + chunk.length, 0);
  const samples = new Float32Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    samples.set(chunk, offset);
    offset += chunk.length;
  }
  return samples;
}

function encodeWavPcm16(samples: Float32Array, sampleRate: number): Blob {
  const view = new DataView(new ArrayBuffer(44 + samples.length * 2));
  writeAscii(view, 0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeAscii(view, 8, "WAVE");
  writeAscii(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeAscii(view, 36, "data");
  view.setUint32(40, samples.length * 2, true);
  samples.forEach((sample, index) => {
    const clamped = Math.max(-1, Math.min(1, sample));
    view.setInt16(44 + index * 2, clamped * 0x7fff, true);
  });
  return new Blob([view.buffer], { type: "audio/wav" });
}

function writeAscii(view: DataView, offset: number, text: string): void {
  for (let index = 0; index < text.length; index++) {
    view.setUint8(offset + index, text.charCodeAt(index));
  }
}
