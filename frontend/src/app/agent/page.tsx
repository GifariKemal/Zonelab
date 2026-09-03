"use client";

/**
 * THE AI AGENT PAGE, at its own URL because the main dashboard is a chart
 * instrument and a chat is a conversation - two different modes of reading
 * that fight each other in one layout.
 *
 * Three panels, one screen:
 *
 *   - CONTEXT (left). Its own symbol/interval/bars/provider pickers feeding
 *     the SAME /api/draw the dashboard uses, so what the agent discusses is
 *     what the engine actually draws, not a parallel analysis path. The
 *     summary line (zones, plans, provider) is always visible while chatting
 *     so a reply is never read detached from the drawing it came from.
 *   - CHAT (right, the bulk). Messages, a grounding badge on every assistant
 *     reply, and the input. History lives in this browser tab only: the
 *     server is stateless by design (see backend/app/agent.py).
 *   - SETTINGS (collapsible). Base URL, key, model. The key is never read
 *     back - the field starts empty and an empty field means "keep the one
 *     stored", which is the only honest affordance when the UI is shown the
 *     key masked.
 *
 * The grounding badge is not decoration. This project's own history is
 * twelve failed directional hypotheses and a rule-based advisor that exists
 * because a model will answer "is this bullish" fluently whether or not
 * anything supports it. A reply that invented a number must read LOUDLY,
 * because the words around it will still sound true.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  agentChat,
  fetchAgentConfig,
  fetchAgentModels,
  fetchConfig,
  fetchDrawing,
  fetchTriad,
  saveAgentConfig,
} from "@/lib/api";
import {
  DEFAULT_LAYER_PARAMS,
  type AgentChatResponse,
  type ChatMessage,
  type DrawResponse,
  type ServerConfig,
  type TriadResponse,
} from "@/lib/types";

/** What the agent asks the engine for on a scan. Supply and demand is the
 *  validated detector and always on; structure and liquidity give the
 *  discussion its context; the checklist is the ICT reading the agent is
 *  asked about most. Toggles for everything else would re-create the
 *  dashboard's toolbox here, which is a second place for the same knobs to
 *  drift. */
const SCAN_LAYERS = ["supply_demand", "structure", "liquidity", "checklist"];

/** The four POSKO triads, fetched alongside the draw so the agent can answer
 *  "korelasi emas" and "mana truth asset". A triad that fails to load is
 *  dropped, not fatal: the draw alone still makes a grounded conversation. */
const TRIAD_KEYS = ["monetary", "commodity", "risk", "fx"] as const;

export default function AgentPage() {
  const [config, setConfig] = useState<ServerConfig | null>(null);
  const [agent, setAgent] = useState<{
    baseUrl: string;
    apiKey: string;
    model: string;
    hint: string;
    available: boolean;
    models: string[];
    reachable: boolean | null;
    error: string | null;
  } | null>(null);
  const [showSettings, setShowSettings] = useState(false);

  const [symbol, setSymbol] = useState("XAUUSD");
  const [interval, setIntervalState] = useState("1h");
  const [provider, setProvider] = useState("");
  const [bars, setBars] = useState(500);
  const [drawing, setDrawing] = useState<DrawResponse | null>(null);
  const [triads, setTriads] = useState<TriadResponse[]>([]);
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [thinking, setThinking] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [savingConfig, setSavingConfig] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, thinking]);

  const loadAgent = useCallback(async () => {
    try {
      const [cfg, agentCfg] = await Promise.all([
        fetchConfig(),
        fetchAgentConfig(),
      ]);
      setConfig(cfg);
      setAgent((prev) => ({
        baseUrl: agentCfg.base_url || (prev?.baseUrl ?? ""),
        apiKey: "",
        model: agentCfg.model,
        hint: agentCfg.api_key_hint,
        available: agentCfg.available,
        models: prev?.models ?? [],
        reachable: agentCfg.available ? (prev?.reachable ?? null) : null,
        error: null,
      }));
      setProvider(cfg.default_provider);
      if (agentCfg.available) {
        fetchAgentModels()
          .then((m) =>
            setAgent((prev) =>
              prev ? { ...prev, models: m.models } : prev,
            ),
          )
          .catch(() => {});
      }
    } catch (cause) {
      setScanError(String(cause));
    }
  }, []);

  useEffect(() => {
    void loadAgent();
  }, [loadAgent]);

  async function scan() {
    setScanning(true);
    setScanError(null);
    try {
      const response = await fetchDrawing({
        ...DEFAULT_LAYER_PARAMS,
        symbol,
        interval,
        bars,
        provider: provider || "synthetic",
        layers: SCAN_LAYERS,
        htf: null,
        equity: null,
        broker: "",
        refine: false,
        session_offset_hours: 0,
      });
      setDrawing(response);
      // The triads ride alongside the draw so the agent can discuss correlation
      // and the Truth Asset. Tolerated, not awaited-to-death: a partner that
      // will not load drops out and the draw alone still grounds the chat.
      const results = await Promise.allSettled(
        TRIAD_KEYS.map((t) =>
          fetchTriad(symbol, interval, bars, t, provider || undefined),
        ),
      );
      setTriads(
        results.flatMap((r) => (r.status === "fulfilled" ? [r.value] : [])),
      );
    } catch (cause) {
      setDrawing(null);
      setTriads([]);
      setScanError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setScanning(false);
    }
  }

  async function saveSettings() {
    if (!agent) return;
    setSavingConfig(true);
    try {
      const saved = await saveAgentConfig({
        base_url: agent.baseUrl,
        api_key: agent.apiKey,
        model: agent.model,
        temperature: 0.2,
      });
      setAgent((prev) => ({
        ...(prev ?? agent),
        apiKey: "",
        model: saved.model,
        hint: saved.api_key_hint,
        available: saved.available,
        reachable: saved.reachable,
        error: saved.error,
      }));
      if (saved.reachable) {
        const m = await fetchAgentModels();
        setAgent((prev) => (prev ? { ...prev, models: m.models } : prev));
      }
    } catch (cause) {
      setAgent((prev) =>
        prev
          ? { ...prev, reachable: false, error: String(cause) }
          : prev,
      );
    } finally {
      setSavingConfig(false);
    }
  }

  async function send() {
    const text = draft.trim();
    if (!text || thinking) return;
    if (agent && !agent.available) {
      setChatError(
        "Endpoint belum terpasang. Buka Settings, isi base URL, API key dan model, lalu Save.",
      );
      setShowSettings(true);
      return;
    }
    setDraft("");
    setChatError(null);
    const history = [...messages, { role: "user" as const, content: text }];
    setMessages(history);
    setThinking(true);
    try {
      const reply: AgentChatResponse = await agentChat(
        history.map((m) => ({ role: m.role, content: m.content })),
        drawing ? { draw: drawing, triads } : null,
      );
      setMessages([
        ...history,
        {
          role: "assistant",
          content: reply.reply,
          grounded: reply.grounded,
          reason: reply.reason,
          unsupported: reply.unsupported,
        },
      ]);
    } catch (cause) {
      setChatError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setThinking(false);
    }
  }

  const zoneCount = drawing?.drawing.zones.length ?? 0;
  const planCount = drawing?.plans.length ?? 0;

  return (
    <div className="flex min-h-screen flex-col bg-bg text-text">
      <header className="flex items-center gap-4 border-b border-line px-5 py-3">
        <Link
          href="/"
          className="text-xs uppercase tracking-wider text-text-faint hover:text-accent transition-colors duration-[70ms] active:opacity-70"
        >
          &larr; Dashboard
        </Link>
        <h1 className="text-sm font-semibold uppercase tracking-wider">
          Zonelab AI Agent
        </h1>
        {agent && (
          <span
            className={`text-xs ${agent.available ? "text-demand" : "text-supply"}`}
            title={
              agent.available
                ? `model: ${agent.model}`
                : "endpoint belum terpasang"
            }
          >
            {agent.available
              ? `model: ${agent.model}`
              : "endpoint belum terpasang"}
          </span>
        )}
        <button
          onClick={() => setShowSettings((v) => !v)}
          className="ml-auto rounded border border-line px-3 py-1 text-xs text-text-dim hover:border-accent hover:text-accent transition-colors duration-[70ms] active:translate-y-px"
        >
          Settings
        </button>
      </header>

      {showSettings && agent && (
        <section className="border-b border-line bg-panel px-5 py-4">
          <div className="grid max-w-3xl gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-xs text-text-dim">
              Base URL (OpenAI-compatible)
              <input
                className="rounded border border-line bg-panel-2 px-2 py-1.5 text-sm text-text"
                value={agent.baseUrl}
                onChange={(e) =>
                  setAgent({ ...agent, baseUrl: e.target.value })
                }
                placeholder="https://host/v1"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-text-dim">
              API key{" "}
              {agent.hint && (
                <span className="text-text-faint">
                  (tersimpan: {agent.hint}; kosongkan untuk pertahankan)
                </span>
              )}
              <input
                type="password"
                className="rounded border border-line bg-panel-2 px-2 py-1.5 text-sm text-text"
                value={agent.apiKey}
                onChange={(e) =>
                  setAgent({ ...agent, apiKey: e.target.value })
                }
                placeholder={agent.hint ? "unchanged" : "sk-..."}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-text-dim">
              Model
              {agent.models.length > 0 ? (
                <select
                  className="rounded border border-line bg-panel-2 px-2 py-1.5 text-sm text-text"
                  value={agent.model}
                  onChange={(e) =>
                    setAgent({ ...agent, model: e.target.value })
                  }
                >
                  {agent.models.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  className="rounded border border-line bg-panel-2 px-2 py-1.5 text-sm text-text"
                  value={agent.model}
                  onChange={(e) =>
                    setAgent({ ...agent, model: e.target.value })
                  }
                  placeholder="model id"
                />
              )}
            </label>
            <div className="flex items-end gap-3">
              <button
                onClick={saveSettings}
                disabled={savingConfig}
                className="rounded border border-accent bg-accent/10 px-4 py-1.5 text-xs text-accent hover:bg-accent/20 disabled:opacity-50 transition-colors duration-[70ms] active:translate-y-px"
              >
                {savingConfig ? "Menyimpan..." : "Save & Probe"}
              </button>
              {agent.reachable === true && (
                <span className="text-xs text-demand">endpoint menjawab</span>
              )}
              {agent.reachable === false && (
                <span className="max-w-xs text-xs text-supply">
                  {agent.error ?? "endpoint tidak menjawab"}
                </span>
              )}
            </div>
          </div>
        </section>
      )}

      <div className="flex flex-1 flex-col gap-4 overflow-hidden p-4 lg:flex-row">
        {/* Context panel */}
        <aside className="flex w-full shrink-0 flex-col gap-3 rounded border border-line bg-panel p-4 lg:w-80">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-text-dim">
            Context
          </h2>
          <label className="flex flex-col gap-1 text-xs text-text-dim">
            Symbol
            <select
              className="rounded border border-line bg-panel-2 px-2 py-1.5 text-sm text-text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
            >
              {(config?.symbols ?? [{ id: symbol, providers: [] }]).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.id}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-text-dim">
            Interval
            <select
              className="rounded border border-line bg-panel-2 px-2 py-1.5 text-sm text-text"
              value={interval}
              onChange={(e) => setIntervalState(e.target.value)}
            >
              {(config?.intervals ?? [interval]).map((i) => (
                <option key={i} value={i}>
                  {i}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-text-dim">
            Provider
            <select
              className="rounded border border-line bg-panel-2 px-2 py-1.5 text-sm text-text"
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
            >
              {(config?.providers ?? [{ id: provider, available: true, needs_key: false }]).map(
                (p) => (
                  <option key={p.id} value={p.id} disabled={!p.available}>
                    {p.id}
                    {p.available ? "" : " (offline)"}
                  </option>
                ),
              )}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-text-dim">
            Bars
            <input
              type="number"
              min={100}
              max={50000}
              step={100}
              className="num rounded border border-line bg-panel-2 px-2 py-1.5 text-sm text-text"
              value={bars}
              onChange={(e) => setBars(Number(e.target.value) || 500)}
            />
          </label>
          <button
            onClick={scan}
            disabled={scanning}
            className="rounded border border-accent bg-accent/10 px-4 py-2 text-xs font-semibold uppercase tracking-wider text-accent hover:bg-accent/20 disabled:opacity-50 transition-colors duration-[70ms] active:translate-y-px"
          >
            {scanning ? "Scanning..." : "Scan"}
          </button>
          {scanError && (
            <p className="text-xs text-supply">{scanError}</p>
          )}
          {drawing && (
            <div className="mt-2 rounded border border-line bg-panel-2 p-3 text-xs leading-relaxed text-text-dim">
              <div className="mb-1 font-semibold text-text">
                {drawing.symbol} {drawing.interval}
              </div>
              <div>
                {drawing.candles.length} bar, provider {drawing.provider}
              </div>
              <div>
                {zoneCount} zone, {planCount} plan
              </div>
              <div className="mt-2 text-text-faint">
                Layers: {SCAN_LAYERS.join(", ")}
              </div>
            </div>
          )}
          <p className="mt-auto text-xs leading-relaxed text-text-faint">
            Agent membaca hasil Scan ini dan hanya boleh mengutip angka dari
            sini. Tanpa Scan, ia bisa menjawab pertanyaan umum tanpa angka.
          </p>
        </aside>

        {/* Chat panel */}
        <main className="scroll-thin flex min-h-[60vh] flex-1 flex-col overflow-y-auto rounded border border-line bg-panel p-4">
          {messages.length === 0 && !thinking && (
            <div className="m-auto max-w-md text-center text-sm leading-relaxed text-text-faint">
              <p className="mb-2">
                Tanya apa pun tentang kondisi market dari hasil Scan.
              </p>
              <p>
                Contoh: &quot;kondisi market sekarang gimana?&quot;, &quot;susun
                checklist order untuk zona terdekat&quot;, &quot;kenapa zona ini
                placeable false?&quot;
              </p>
            </div>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              className={`mb-3 max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm leading-relaxed ${
                m.role === "user"
                  ? "self-end bg-accent/15 text-text"
                  : "self-start border border-line bg-panel-2 text-text"
              }`}
            >
              {m.content}
              {m.role === "assistant" && m.grounded === true && (
                <div className="mt-2 text-xs text-demand">
                  semua angka terlacak ke data engine
                </div>
              )}
              {m.role === "assistant" && m.grounded === false && (
                <div className="mt-2 rounded border border-supply/40 bg-supply/10 p-2 text-xs text-supply">
                  reply mengandung angka yang tidak ada di data engine:{" "}
                  {(m.unsupported ?? []).join(", ")}. Baca dengan hati-hati.
                </div>
              )}
            </div>
          ))}
          {thinking && (
            <div className="mb-3 self-start rounded-lg border border-line bg-panel-2 px-3 py-2 text-sm text-text-faint">
              model sedang menjawab...
            </div>
          )}
          <div ref={endRef} />
        </main>
      </div>

      {/* Input */}
      <div className="border-t border-line bg-panel px-4 py-3">
        {chatError && (
          <p className="mb-2 text-xs text-supply">{chatError}</p>
        )}
        <div className="flex gap-2">
          <input
            className="flex-1 rounded border border-line bg-panel-2 px-3 py-2 text-sm text-text placeholder:text-text-faint focus:border-accent"
            placeholder={
              drawing
                ? `Tanya tentang ${drawing.symbol} ${drawing.interval}...`
                : "Tanya apa pun (Scan dulu untuk analisa berangka)..."
            }
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
            disabled={thinking}
          />
          <button
            onClick={() => void send()}
            disabled={thinking || !draft.trim()}
            className="rounded border border-accent bg-accent/10 px-5 text-xs font-semibold uppercase tracking-wider text-accent hover:bg-accent/20 disabled:opacity-50 transition-colors duration-[70ms] active:translate-y-px"
          >
            Kirim
          </button>
        </div>
      </div>
    </div>
  );
}
