import {
  useEffect,
  useRef,
  useState,
  type ComponentType,
  type ReactNode,
} from "react";
import { generatedImageUrl, knowledgeImageUrl } from "../api";
import type { Widget } from "../types";

interface ClockData {
  timezone: string | null;
  label: string;
  utc_offset: string;
}

interface WeatherData {
  city: string;
  country: string;
  temperature_c: number;
  feels_like_c: number;
  humidity: number;
  wind_kmh: number;
  condition: string;
  weather_code: number;
  is_day: boolean;
  high_c: number;
  low_c: number;
}

interface PricePoint {
  t: number;
  p: number;
}

interface PriceChartData {
  coin: string;
  current: number;
  change_pct: number;
  high: number;
  low: number;
  points: PricePoint[];
}

function parseOffsetMinutes(offset: string): number {
  const match = offset.match(/^([+-])(\d{2}):(\d{2})$/);
  if (!match) return 0;
  const minutes = Number(match[2]) * 60 + Number(match[3]);
  return match[1] === "-" ? -minutes : minutes;
}

function isUsableTimezone(timezone: string | null): timezone is string {
  if (!timezone) return false;
  try {
    new Intl.DateTimeFormat("en", { timeZone: timezone });
    return true;
  } catch {
    return false;
  }
}

interface ClockParts {
  hours: number;
  minutes: number;
  seconds: number;
  dateLabel: string;
}

function clockParts(data: ClockData, now: Date): ClockParts {
  if (isUsableTimezone(data.timezone)) {
    const formatted = Object.fromEntries(
      new Intl.DateTimeFormat("en-GB", {
        timeZone: data.timezone,
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        weekday: "long",
        day: "numeric",
        month: "long",
        hour12: false,
      })
        .formatToParts(now)
        .map((part) => [part.type, part.value]),
    );
    return {
      hours: Number(formatted.hour) % 24,
      minutes: Number(formatted.minute),
      seconds: Number(formatted.second),
      dateLabel: `${formatted.weekday}, ${formatted.day} ${formatted.month}`,
    };
  }
  const shifted = new Date(
    now.getTime() + parseOffsetMinutes(data.utc_offset) * 60000,
  );
  return {
    hours: shifted.getUTCHours(),
    minutes: shifted.getUTCMinutes(),
    seconds: shifted.getUTCSeconds(),
    dateLabel: shifted.toLocaleDateString("en-GB", {
      weekday: "long",
      day: "numeric",
      month: "long",
      timeZone: "UTC",
    }),
  };
}

function two(value: number): string {
  return String(value).padStart(2, "0");
}

function hand(angle: number, length: number, width: number, color: string) {
  const radians = ((angle - 90) * Math.PI) / 180;
  return (
    <line
      x1={36}
      y1={36}
      x2={36 + length * Math.cos(radians)}
      y2={36 + length * Math.sin(radians)}
      stroke={color}
      strokeWidth={width}
      strokeLinecap="round"
    />
  );
}

function AnalogClock({ parts }: { parts: ClockParts }) {
  const ticks = Array.from({ length: 12 }, (_, index) => {
    const radians = (index * 30 * Math.PI) / 180;
    const outer = 32;
    const inner = index % 3 === 0 ? 27.5 : 29.5;
    return (
      <line
        key={index}
        x1={36 + inner * Math.cos(radians)}
        y1={36 + inner * Math.sin(radians)}
        x2={36 + outer * Math.cos(radians)}
        y2={36 + outer * Math.sin(radians)}
        stroke={index % 3 === 0 ? "var(--border-strong)" : "var(--border)"}
        strokeWidth={index % 3 === 0 ? 2 : 1.5}
        strokeLinecap="round"
      />
    );
  });
  const hourAngle = ((parts.hours % 12) + parts.minutes / 60) * 30;
  const minuteAngle = (parts.minutes + parts.seconds / 60) * 6;
  const secondAngle = parts.seconds * 6;

  return (
    <svg width="72" height="72" viewBox="0 0 72 72" aria-hidden="true">
      <circle cx={36} cy={36} r={35} fill="var(--surface)" stroke="var(--border)" />
      {ticks}
      {hand(hourAngle, 16, 3.5, "var(--foreground)")}
      {hand(minuteAngle, 24, 2.5, "var(--foreground)")}
      {hand(secondAngle, 27, 1.25, "var(--accent)")}
      <circle cx={36} cy={36} r={2.5} fill="var(--foreground)" />
    </svg>
  );
}

function ClockCard({ data }: { data: Record<string, unknown> }) {
  const clock = data as unknown as ClockData;
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const parts = clockParts(clock, now);
  const summary = `Current time in ${clock.label}: ${two(parts.hours)}:${two(parts.minutes)}, UTC${clock.utc_offset}`;

  return (
    <div className="widget-card clock-card" role="img" aria-label={summary}>
      <div className="clock-readout">
        <span className="clock-time">
          {two(parts.hours)}:{two(parts.minutes)}
          <span className="clock-seconds">:{two(parts.seconds)}</span>
        </span>
        <span className="widget-title">{clock.label}</span>
        <span className="widget-subtle">
          {parts.dateLabel} · UTC{clock.utc_offset}
        </span>
      </div>
      <AnalogClock parts={parts} />
    </div>
  );
}

function weatherIcon(code: number, isDay: boolean): ReactNode {
  const paths: Record<string, string[]> = {
    sun: [
      "M12 2v2",
      "M12 20v2",
      "m4.93 4.93 1.41 1.41",
      "m17.66 17.66 1.41 1.41",
      "M2 12h2",
      "M20 12h2",
      "m6.34 17.66-1.41 1.41",
      "m19.07 4.93-1.41 1.41",
    ],
    moon: ["M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"],
    cloudSun: [
      "M12 2v2",
      "m4.93 4.93 1.41 1.41",
      "M20 12h2",
      "m19.07 4.93-1.41 1.41",
      "M15.947 12.65a4 4 0 0 0-5.925-4.128",
      "M13 22H7a5 5 0 1 1 4.9-6H13a3 3 0 0 1 0 6Z",
    ],
    cloud: ["M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"],
    fog: [
      "M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242",
      "M16 17H7",
      "M17 21H9",
    ],
    drizzle: [
      "M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242",
      "M8 19v1",
      "M8 14v1",
      "M16 19v1",
      "M16 14v1",
      "M12 21v1",
      "M12 16v1",
    ],
    rain: [
      "M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242",
      "M16 14v6",
      "M8 14v6",
      "M12 16v6",
    ],
    snow: [
      "M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242",
      "M8 15h.01",
      "M8 19h.01",
      "M12 17h.01",
      "M12 21h.01",
      "M16 15h.01",
      "M16 19h.01",
    ],
    storm: [
      "M6 16.326A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 .5 8.973",
      "m13 12-3 5h4l-3 5",
    ],
  };
  const key =
    code === 0 || code === 1
      ? isDay
        ? "sun"
        : "moon"
      : code === 2
        ? "cloudSun"
        : code === 3
          ? "cloud"
          : code === 45 || code === 48
            ? "fog"
            : code >= 51 && code <= 57
              ? "drizzle"
              : (code >= 61 && code <= 67) || (code >= 80 && code <= 82)
                ? "rain"
                : (code >= 71 && code <= 77) || code === 85 || code === 86
                  ? "snow"
                  : code >= 95
                    ? "storm"
                    : "cloud";

  return (
    <svg
      width="40"
      height="40"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {key === "sun" && <circle cx="12" cy="12" r="4" />}
      {paths[key].map((path) => (
        <path key={path} d={path} />
      ))}
    </svg>
  );
}

function WeatherCard({ data }: { data: Record<string, unknown> }) {
  const weather = data as unknown as WeatherData;
  const summary =
    `Weather in ${weather.city}: ${weather.condition}, ` +
    `${Math.round(weather.temperature_c)} degrees Celsius`;

  return (
    <div className="widget-card weather-card" role="img" aria-label={summary}>
      <div className="weather-main">
        <span className="weather-icon">
          {weatherIcon(weather.weather_code, weather.is_day)}
        </span>
        <div className="weather-readout">
          <span className="weather-temp">
            {Math.round(weather.temperature_c)}°C
          </span>
          <span className="widget-title">
            {weather.city}
            {weather.country ? `, ${weather.country}` : ""}
          </span>
          <span className="widget-subtle">{weather.condition}</span>
        </div>
      </div>
      <dl className="weather-meta">
        <div>
          <dt>Feels like</dt>
          <dd>{Math.round(weather.feels_like_c)}°</dd>
        </div>
        <div>
          <dt>Humidity</dt>
          <dd>{Math.round(weather.humidity)}%</dd>
        </div>
        <div>
          <dt>Wind</dt>
          <dd>{Math.round(weather.wind_kmh)} km/h</dd>
        </div>
        <div>
          <dt>High / Low</dt>
          <dd>
            {Math.round(weather.high_c)}° / {Math.round(weather.low_c)}°
          </dd>
        </div>
      </dl>
    </div>
  );
}

function formatMoney(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: value >= 1 ? 2 : 6,
  }).format(value);
}

function formatClockTime(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function capitalize(word: string): string {
  return word.charAt(0).toUpperCase() + word.slice(1);
}

const CHART_WIDTH = 320;
const CHART_HEIGHT = 96;
const CHART_PAD = 6;

interface HoverPoint {
  x: number;
  y: number;
  point: PricePoint;
}

function PriceChartCard({ data }: { data: Record<string, unknown> }) {
  const chart = data as unknown as PriceChartData;
  const [hover, setHover] = useState<HoverPoint | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const gradientId = useRef(`price-fill-${Math.random().toString(36).slice(2)}`);

  const points = chart.points ?? [];
  if (points.length < 2) return null;

  const firstTime = points[0].t;
  const lastTime = points[points.length - 1].t;
  const span = Math.max(chart.high - chart.low, 1e-9);
  const toX = (point: PricePoint) =>
    ((point.t - firstTime) / (lastTime - firstTime)) * CHART_WIDTH;
  const toY = (point: PricePoint) =>
    CHART_PAD +
    (1 - (point.p - chart.low) / span) * (CHART_HEIGHT - CHART_PAD * 2);

  const line = points
    .map((point, index) =>
      `${index === 0 ? "M" : "L"}${toX(point).toFixed(2)},${toY(point).toFixed(2)}`,
    )
    .join("");
  const area = `${line}L${CHART_WIDTH},${CHART_HEIGHT}L0,${CHART_HEIGHT}Z`;

  function moveHover(event: React.PointerEvent<SVGSVGElement>) {
    const svg = svgRef.current;
    if (!svg) return;
    const bounds = svg.getBoundingClientRect();
    const x = ((event.clientX - bounds.left) / bounds.width) * CHART_WIDTH;
    let nearest = points[0];
    for (const point of points) {
      if (Math.abs(toX(point) - x) < Math.abs(toX(nearest) - x)) nearest = point;
    }
    setHover({ x: toX(nearest), y: toY(nearest), point: nearest });
  }

  const rising = chart.change_pct >= 0;
  const summary =
    `${capitalize(chart.coin)} price over the last 24 hours: ` +
    `currently ${formatMoney(chart.current)}, ` +
    `${rising ? "up" : "down"} ${Math.abs(chart.change_pct).toFixed(2)}%, ` +
    `high ${formatMoney(chart.high)}, low ${formatMoney(chart.low)}`;

  return (
    <div className="widget-card price-card">
      <div className="price-header">
        <div className="price-readout">
          <span className="widget-title">{capitalize(chart.coin)} · 24h</span>
          <span className="price-current">{formatMoney(chart.current)}</span>
        </div>
        <span className={rising ? "price-change up" : "price-change down"}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            {rising ? (
              <>
                <path d="M7 7h10v10" />
                <path d="M7 17 17 7" />
              </>
            ) : (
              <>
                <path d="M17 7v10H7" />
                <path d="M7 7l10 10" />
              </>
            )}
          </svg>
          {rising ? "+" : "−"}
          {Math.abs(chart.change_pct).toFixed(2)}%
        </span>
      </div>
      <div className="price-plot">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
          preserveAspectRatio="none"
          role="img"
          aria-label={summary}
          onPointerMove={moveHover}
          onPointerLeave={() => setHover(null)}
        >
          <defs>
            <linearGradient id={gradientId.current} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.16" />
              <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
            </linearGradient>
          </defs>
          {[0.25, 0.5, 0.75].map((fraction) => (
            <line
              key={fraction}
              x1="0"
              x2={CHART_WIDTH}
              y1={CHART_PAD + fraction * (CHART_HEIGHT - CHART_PAD * 2)}
              y2={CHART_PAD + fraction * (CHART_HEIGHT - CHART_PAD * 2)}
              stroke="var(--border)"
              strokeWidth="1"
              vectorEffect="non-scaling-stroke"
            />
          ))}
          <path d={area} fill={`url(#${gradientId.current})`} />
          <path
            d={line}
            fill="none"
            stroke="var(--accent)"
            strokeWidth="2"
            strokeLinejoin="round"
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
          />
          {hover && (
            <>
              <line
                x1={hover.x}
                x2={hover.x}
                y1={CHART_PAD}
                y2={CHART_HEIGHT}
                stroke="var(--border-strong)"
                strokeWidth="1"
                vectorEffect="non-scaling-stroke"
              />
              <circle
                cx={hover.x}
                cy={hover.y}
                r="4"
                fill="var(--surface)"
                stroke="var(--accent)"
                strokeWidth="2"
                vectorEffect="non-scaling-stroke"
              />
            </>
          )}
        </svg>
        {hover && (
          <div
            className="chart-tooltip"
            style={{ left: `${(hover.x / CHART_WIDTH) * 100}%` }}
          >
            {formatMoney(hover.point.p)} · {formatClockTime(hover.point.t)}
          </div>
        )}
      </div>
      <div className="price-axis">
        <span>{formatClockTime(firstTime)}</span>
        <span className="price-range">
          H {formatMoney(chart.high)} · L {formatMoney(chart.low)}
        </span>
        <span>{formatClockTime(lastTime)}</span>
      </div>
    </div>
  );
}

interface KbStatsData {
  documents: number;
  chunks: number;
  images?: number;
  collections: number;
  conversations: number;
}

function KbStatsCard({ data }: { data: Record<string, unknown> }) {
  const stats = data as unknown as KbStatsData;
  const tiles = (
    [
      ["Documents", stats.documents],
      ["Chunks", stats.chunks],
      ["Images", stats.images],
      ["Collections", stats.collections],
      ["Chats", stats.conversations],
    ] as [string, number | undefined][]
  ).filter((tile): tile is [string, number] => tile[1] !== undefined);
  const summary =
    "Knowledge base: " +
    tiles.map(([label, value]) => `${value} ${label.toLowerCase()}`).join(", ");

  return (
    <div className="widget-card stats-card" role="img" aria-label={summary}>
      <span className="widget-title">Knowledge base</span>
      <div className="stats-grid">
        {tiles.map(([label, value]) => (
          <div key={label} className="stat-tile">
            <span className="stat-value">{(value ?? 0).toLocaleString()}</span>
            <span className="stat-label">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

interface UsageDay {
  date: string;
  prompts: number;
  tokens: number;
}

interface UsageData {
  days: UsageDay[];
  total_prompts: number;
  total_tokens: number;
  average_latency_ms: number | null;
}

function formatTokens(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}k`;
  return value.toLocaleString();
}

function roundedTopBar(
  x: number,
  y: number,
  width: number,
  height: number,
): string {
  const radius = Math.min(3, height);
  return (
    `M${x},${y + height}V${y + radius}` +
    `Q${x},${y} ${x + radius},${y}` +
    `H${x + width - radius}` +
    `Q${x + width},${y} ${x + width},${y + radius}` +
    `V${y + height}Z`
  );
}

const USAGE_WIDTH = 320;
const USAGE_HEIGHT = 64;
const USAGE_TOP_PAD = 4;

function UsageCard({ data }: { data: Record<string, unknown> }) {
  const usage = data as unknown as UsageData;
  const [hoverDay, setHoverDay] = useState<number | null>(null);
  const days = usage.days ?? [];
  if (days.length === 0) return null;

  const slot = USAGE_WIDTH / days.length;
  const barWidth = Math.min(26, slot * 0.6);
  const maxTokens = Math.max(...days.map((day) => day.tokens), 1);
  const latency =
    usage.average_latency_ms === null
      ? null
      : usage.average_latency_ms >= 1000
        ? `${(usage.average_latency_ms / 1000).toFixed(1)}s`
        : `${usage.average_latency_ms}ms`;
  const summary =
    `Cortex usage over the last ${days.length} days: ` +
    `${usage.total_tokens.toLocaleString()} tokens across ` +
    `${usage.total_prompts.toLocaleString()} prompts`;
  const hovered = hoverDay === null ? null : days[hoverDay];

  return (
    <div className="widget-card usage-card">
      <span className="widget-title">Cortex · Last {days.length} days</span>
      <div className="usage-hero">
        <span className="usage-total">{formatTokens(usage.total_tokens)}</span>
        <span className="widget-subtle">
          tokens · {usage.total_prompts.toLocaleString()} prompts
          {latency ? ` · avg ${latency}` : ""}
        </span>
      </div>
      <div className="usage-plot">
        <svg
          viewBox={`0 0 ${USAGE_WIDTH} ${USAGE_HEIGHT}`}
          preserveAspectRatio="none"
          role="img"
          aria-label={summary}
          onPointerLeave={() => setHoverDay(null)}
        >
          <line
            x1="0"
            x2={USAGE_WIDTH}
            y1={USAGE_HEIGHT - 0.5}
            y2={USAGE_HEIGHT - 0.5}
            stroke="var(--border)"
            strokeWidth="1"
            vectorEffect="non-scaling-stroke"
          />
          {days.map((day, index) => {
            const height = Math.max(
              (day.tokens / maxTokens) * (USAGE_HEIGHT - USAGE_TOP_PAD - 1),
              day.tokens > 0 ? 3 : 1.5,
            );
            const x = index * slot + (slot - barWidth) / 2;
            return (
              <g key={day.date}>
                <rect
                  x={index * slot}
                  y={0}
                  width={slot}
                  height={USAGE_HEIGHT}
                  fill="transparent"
                  onPointerEnter={() => setHoverDay(index)}
                />
                <path
                  d={roundedTopBar(
                    x,
                    USAGE_HEIGHT - 1 - height,
                    barWidth,
                    height,
                  )}
                  fill={
                    day.tokens === 0
                      ? "var(--border)"
                      : hoverDay === index
                        ? "var(--primary-hover)"
                        : "var(--accent)"
                  }
                  pointerEvents="none"
                />
              </g>
            );
          })}
        </svg>
        {hovered && hoverDay !== null && (
          <div
            className="chart-tooltip"
            style={{ left: `${((hoverDay + 0.5) / days.length) * 100}%` }}
          >
            {hovered.tokens.toLocaleString()} tokens · {hovered.prompts}{" "}
            {hovered.prompts === 1 ? "prompt" : "prompts"}
          </div>
        )}
      </div>
      <div className="usage-days">
        {days.map((day) => (
          <span key={day.date}>
            {new Date(`${day.date}T00:00:00`).toLocaleDateString([], {
              weekday: "short",
            })}
          </span>
        ))}
      </div>
    </div>
  );
}

interface ImageData {
  filename: string;
  prompt: string;
  width: number;
  height: number;
}

function DownloadIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" x2="12" y1="15" y2="3" />
    </svg>
  );
}

function downloadName(prompt: string, filename: string): string {
  const extension = filename.split(".").pop() ?? "png";
  const slug = prompt
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 40);
  return `${slug || "cortex-image"}.${extension}`;
}

function ImageCard({ data }: { data: Record<string, unknown> }) {
  const image = data as unknown as ImageData;
  const [failed, setFailed] = useState(false);
  const url = generatedImageUrl(image.filename);

  if (failed) {
    return (
      <div className="widget-card image-card">
        <span className="widget-subtle">Image unavailable · {image.prompt}</span>
      </div>
    );
  }
  return (
    <figure className="widget-card image-card">
      <a
        className="image-link"
        href={url}
        target="_blank"
        rel="noreferrer"
        aria-label={`Open full-size image: ${image.prompt}`}
      >
        <img
          src={url}
          alt={image.prompt}
          width={image.width}
          height={image.height}
          loading="lazy"
          onError={() => setFailed(true)}
        />
      </a>
      <div className="image-footer">
        <figcaption className="widget-subtle">{image.prompt}</figcaption>
        <a
          className="image-download"
          href={url}
          download={downloadName(image.prompt, image.filename)}
          aria-label="Download image"
        >
          <DownloadIcon />
          Download
        </a>
      </div>
    </figure>
  );
}

interface GalleryImage {
  filename: string;
  caption: string;
  source: string | null;
  source_url: string | null;
}

interface GalleryData {
  query: string;
  images: GalleryImage[];
}

function ExternalLinkIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M15 3h6v6" />
      <path d="M10 14 21 3" />
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
    </svg>
  );
}

function gallerySource(image: GalleryImage): string | null {
  if (image.source) return image.source;
  if (!image.source_url) return null;
  try {
    return new URL(image.source_url).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

function GalleryItem({ image }: { image: GalleryImage }) {
  const [failed, setFailed] = useState(false);
  const url = knowledgeImageUrl(image.filename);
  const source = gallerySource(image);

  if (failed) return null;
  return (
    <figure className="gallery-item">
      <a
        className="image-link"
        href={url}
        target="_blank"
        rel="noreferrer"
        aria-label={`Open full-size image: ${image.caption}`}
      >
        <img
          className="gallery-thumb"
          src={url}
          alt={image.caption}
          loading="lazy"
          onError={() => setFailed(true)}
        />
      </a>
      <figcaption className="gallery-caption" title={image.caption}>
        {image.caption}
      </figcaption>
      {source &&
        (image.source_url ? (
          <a
            className="gallery-source"
            href={image.source_url}
            target="_blank"
            rel="noreferrer"
            aria-label={`Open image source: ${source}`}
          >
            <ExternalLinkIcon />
            <span className="gallery-source-name">{source}</span>
          </a>
        ) : (
          <span className="gallery-source">
            <FileIcon />
            <span className="gallery-source-name">{source}</span>
          </span>
        ))}
    </figure>
  );
}

function FileIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
      <path d="M14 2v4a2 2 0 0 0 2 2h4" />
    </svg>
  );
}

function ImageGalleryCard({ data }: { data: Record<string, unknown> }) {
  const gallery = data as unknown as GalleryData;
  const images = gallery.images ?? [];
  if (images.length === 0) return null;

  return (
    <div
      className="widget-card gallery-card"
      role="group"
      aria-label={`${images.length} related ${images.length === 1 ? "image" : "images"}`}
    >
      <span className="widget-title">Related images</span>
      <div className={images.length === 1 ? "gallery-grid single" : "gallery-grid"}>
        {images.map((image) => (
          <GalleryItem key={image.filename} image={image} />
        ))}
      </div>
    </div>
  );
}

const WIDGET_COMPONENTS: Record<
  string,
  ComponentType<{ data: Record<string, unknown> }>
> = {
  clock: ClockCard,
  weather: WeatherCard,
  price_chart: PriceChartCard,
  kb_stats: KbStatsCard,
  usage: UsageCard,
  image: ImageCard,
  image_gallery: ImageGalleryCard,
};

export function WidgetCard({ widget }: { widget: Widget }) {
  const Component = WIDGET_COMPONENTS[widget.kind];
  if (!Component) return null;
  return <Component data={widget.data} />;
}

export function WidgetList({ widgets }: { widgets: Widget[] }) {
  if (widgets.length === 0) return null;
  return (
    <div className="widgets">
      {widgets.map((widget, index) => (
        <WidgetCard key={index} widget={widget} />
      ))}
    </div>
  );
}
