"use client";
/** Settings page. MOCK MODE. */
import { Panel, Label, Badge } from "@/components/ui/primitives";

interface SettingRow { key: string; label: string; status: "DEFINED"|"UNDEFINED"|"NOT_CONFIGURED"; value?: string; note?: string; }

const SETTINGS: Array<{ group: string; items: SettingRow[] }> = [
  {
    group: "Trading",
    items: [
      { key: "htf_timeframe",   label: "HTF Timeframe",        status: "UNDEFINED", note: "Pending backtest calibration" },
      { key: "mtf_timeframe",   label: "MTF Timeframe",        status: "UNDEFINED", note: "Pending backtest calibration" },
      { key: "swing_lookback",  label: "Swing Lookback N",     status: "UNDEFINED" },
      { key: "min_bos_dist",    label: "MIN_BOS_DISTANCE",     status: "UNDEFINED" },
      { key: "ema_period",      label: "EMA Period",           status: "UNDEFINED" },
      { key: "adx_period",      label: "ADX Period",           status: "UNDEFINED" },
      { key: "atr_period",      label: "ATR Period",           status: "UNDEFINED" },
      { key: "rsi_period",      label: "RSI Period",           status: "UNDEFINED" },
    ],
  },
  {
    group: "Risk",
    items: [
      { key: "daily_loss_limit", label: "Daily Loss Limit",    status: "UNDEFINED", note: "Pending approval" },
      { key: "max_drawdown",     label: "Max Drawdown",        status: "UNDEFINED" },
      { key: "max_spread",       label: "Max Spread",          status: "UNDEFINED" },
      { key: "profit_lock_formula", label: "Profit Lock Formula", status: "NOT_CONFIGURED", note: "Formula concept approved, parameters UNDEFINED" },
    ],
  },
  {
    group: "News",
    items: [
      { key: "news_provider",   label: "News Provider",        status: "UNDEFINED" },
      { key: "pre_event_window",label: "Pre-event Window",     status: "UNDEFINED" },
      { key: "post_event_window",label: "Post-event Window",   status: "UNDEFINED" },
    ],
  },
  {
    group: "Signal",
    items: [
      { key: "confidence_threshold", label: "Confidence Threshold", status: "UNDEFINED" },
      { key: "signal_validity",      label: "Signal Validity Period", status: "UNDEFINED" },
    ],
  },
  {
    group: "Execution",
    items: [
      { key: "commission",      label: "Commission (Cent/Standard)", status: "UNDEFINED" },
      { key: "swap_rate",       label: "Swap Rate",             status: "UNDEFINED" },
      { key: "slippage",        label: "Slippage Model",        status: "UNDEFINED" },
    ],
  },
];

export function SettingsPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">Settings</h1>
        <p className="text-2xs text-aurexis-faint mt-0.5">
          Configuration display. Authoritative parameters are backend-controlled and require approval.
        </p>
      </div>

      <div className="bg-aurexis-warning/5 border border-aurexis-warning/20 rounded px-4 py-3">
        <p className="text-xs text-aurexis-warning font-medium">Important</p>
        <p className="text-2xs text-aurexis-faint mt-1">
          All production trading parameters are UNDEFINED pending backtest calibration and explicit approval.
          Frontend displays configuration state — never modifies authoritative backend parameters.
        </p>
      </div>

      {SETTINGS.map(({ group, items }) => (
        <Panel key={group} title={group}>
          <div className="px-4 py-2">
            {items.map((item) => (
              <div key={item.key} className="flex items-center justify-between py-2 border-b border-aurexis-border/40 last:border-0">
                <div>
                  <Label>{item.label}</Label>
                  {item.note && <p className="text-2xs text-aurexis-faint mt-0.5">{item.note}</p>}
                </div>
                <div className="flex items-center gap-2">
                  {item.value && <span className="text-xs font-mono text-aurexis-text">{item.value}</span>}
                  <Badge variant={
                    item.status === "DEFINED" ? "success"
                    : item.status === "NOT_CONFIGURED" ? "warning"
                    : "muted"
                  }>{item.status.replace(/_/g, " ")}</Badge>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      ))}
    </div>
  );
}
