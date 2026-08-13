"use client";

import type { ServerConfig, SupplyDemandParams } from "@/lib/types";

interface Props {
  params: SupplyDemandParams;
  onChange: (patch: Partial<SupplyDemandParams>) => void;
  onReset: () => void;
  stats?: Record<string, number>;
  config: ServerConfig | null;
}

export function Toolbox({ params, onChange, onReset, stats }: Props) {
  return (
    <div className="scroll-thin flex h-full flex-col overflow-y-auto">
      <Group title="Detector">
        <Segmented
          label="Zone basis"
          hint="Wick uses the base high/low. Body ignores wicks and draws tighter."
          value={params.zone_basis}
          options={[
            ["wick", "Wick"],
            ["body", "Body"],
          ]}
          onChange={(v) => onChange({ zone_basis: v as "wick" | "body" })}
        />
        <Slider
          label="Impulse size"
          hint="A leg candle's range must exceed this many ATR. Lower finds more, weaker legs."
          suffix="ATR"
          min={0.3}
          max={3}
          step={0.1}
          value={params.impulse_atr}
          onChange={(v) => onChange({ impulse_atr: v })}
        />
        <Slider
          label="Impulse body"
          hint="Body as a share of the candle's own range. Separates decisive candles from dojis."
          min={0.2}
          max={0.9}
          step={0.05}
          value={params.impulse_body_ratio}
          onChange={(v) => onChange({ impulse_body_ratio: v })}
        />
        <Slider
          label="Departure gate"
          hint="How far the leg-out must run from the zone. The main quality filter."
          suffix="ATR"
          min={0}
          max={6}
          step={0.25}
          value={params.departure_min_atr}
          onChange={(v) => onChange({ departure_min_atr: v })}
        />
      </Group>

      <Group title="Base">
        <Slider
          label="Max base bars"
          hint="Longer consolidations are clipped to the bars the move actually left from."
          min={1}
          max={20}
          step={1}
          value={params.base_max_bars}
          onChange={(v) => onChange({ base_max_bars: v })}
        />
        <Slider
          label="Max base height"
          hint="Measured against the volatility before the base, so a tall base cannot excuse itself."
          suffix="ATR"
          min={0.5}
          max={6}
          step={0.25}
          value={params.base_max_atr}
          onChange={(v) => onChange({ base_max_atr: v })}
        />
        <Slider
          label="ATR period"
          min={5}
          max={50}
          step={1}
          value={params.atr_period}
          onChange={(v) => onChange({ atr_period: v })}
        />
      </Group>

      <Group title="Lifecycle">
        <Slider
          label="Mitigation depth"
          hint="Share of the zone price must eat before it counts as used up."
          min={0.1}
          max={1}
          step={0.05}
          value={params.mitigation_pct}
          onChange={(v) => onChange({ mitigation_pct: v })}
        />
        <Toggle
          label="Show mitigated"
          value={params.show_mitigated}
          onChange={(v) => onChange({ show_mitigated: v })}
        />
        <Toggle
          label="Show broken"
          value={params.show_broken}
          onChange={(v) => onChange({ show_broken: v })}
        />
      </Group>

      <Group title="Display">
        <Slider
          label="Zones per side"
          min={1}
          max={40}
          step={1}
          value={params.max_zones_per_side}
          onChange={(v) => onChange({ max_zones_per_side: v })}
        />
        <Slider
          label="Merge overlap"
          hint="Two zones overlapping more than this collapse into the stronger one."
          min={0.2}
          max={1}
          step={0.05}
          value={params.merge_overlap_pct}
          onChange={(v) => onChange({ merge_overlap_pct: v })}
        />
      </Group>

      {stats ? (
        <Group title="Filter trace">
          <p className="mb-2 text-[11px] leading-relaxed text-text-faint">
            Why the chart looks the way it does. An empty chart and an
            over-filtered one are not the same problem.
          </p>
          <Stat label="Formations found" value={stats.candidates} />
          <Stat label="Base too tall" value={stats.rejected_base_too_tall} muted />
          <Stat label="Weak departure" value={stats.rejected_weak_departure} muted />
          <Stat label="Merged as duplicate" value={stats.rejected_overlap} muted />
          <Stat label="Hidden by state" value={stats.rejected_state_filter} muted />
          <div className="mt-2 border-t border-line pt-2">
            <Stat label="Drawn" value={stats.zones} strong />
          </div>
        </Group>
      ) : null}

      <div className="mt-auto border-t border-line p-3">
        <button
          onClick={onReset}
          className="w-full border border-line-strong px-3 py-2 text-[11px] uppercase tracking-wider text-text-dim transition-colors hover:border-accent hover:text-accent"
        >
          Reset parameters
        </button>
      </div>
    </div>
  );
}

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-b border-line px-3 py-3">
      <h3 className="mb-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-text-faint">
        {title}
      </h3>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function Slider({
  label,
  hint,
  suffix,
  min,
  max,
  step,
  value,
  onChange,
}: {
  label: string;
  hint?: string;
  suffix?: string;
  min: number;
  max: number;
  step: number;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block" title={hint}>
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <span className="text-[12px] text-text-dim">{label}</span>
        <span className="num text-[12px] text-text">
          {step < 1 ? value.toFixed(2) : value}
          {suffix ? <span className="ml-1 text-text-faint">{suffix}</span> : null}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-1 w-full cursor-pointer appearance-none rounded bg-line-strong"
      />
    </label>
  );
}

function Toggle({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-2">
      <span className="text-[12px] text-text-dim">{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={value}
        aria-label={label}
        onClick={() => onChange(!value)}
        className={`h-4 w-8 shrink-0 border transition-colors ${
          value ? "border-accent bg-accent/25" : "border-line-strong bg-transparent"
        }`}
      >
        <span
          className={`block h-3 w-3 transition-transform ${
            value ? "translate-x-4 bg-accent" : "translate-x-0.5 bg-text-faint"
          }`}
        />
      </button>
    </label>
  );
}

function Segmented({
  label,
  hint,
  value,
  options,
  onChange,
}: {
  label: string;
  hint?: string;
  value: string;
  options: [string, string][];
  onChange: (value: string) => void;
}) {
  return (
    <div title={hint}>
      <div className="mb-1 text-[12px] text-text-dim">{label}</div>
      <div className="flex border border-line-strong">
        {options.map(([id, text]) => (
          <button
            key={id}
            onClick={() => onChange(id)}
            className={`flex-1 px-2 py-1 text-[11px] transition-colors ${
              value === id
                ? "bg-accent/15 text-accent"
                : "text-text-faint hover:text-text-dim"
            }`}
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  muted,
  strong,
}: {
  label: string;
  value: number | undefined;
  muted?: boolean;
  strong?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-2 py-0.5">
      <span
        className={`text-[12px] ${muted ? "text-text-faint" : strong ? "text-text" : "text-text-dim"}`}
      >
        {label}
      </span>
      <span
        className={`num text-[12px] ${strong ? "text-accent" : muted ? "text-text-faint" : "text-text-dim"}`}
      >
        {value ?? 0}
      </span>
    </div>
  );
}
