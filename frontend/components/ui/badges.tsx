"use client";
/** AUREXIS domain-state badges */
import { Badge } from "./primitives";
import type { RiskState, NewsState, SignalStatus, CommandState, AgentStatus, RegimeState, BrainMarketState } from "@/types/domain";

type V = "default"|"success"|"danger"|"warning"|"info"|"accent"|"muted";

export function RiskStateBadge({ state }: { state: RiskState }) {
  const m: Record<RiskState, V> = {
    NORMAL:"success", CAUTION:"warning", PROTECTED:"info",
    STOPPED:"danger", EMERGENCY_STOP:"danger", NOT_CONFIGURED:"warning", UNKNOWN:"muted",
  };
  return <Badge variant={m[state]}>{state.replace(/_/g," ")}</Badge>;
}

export function NewsStateBadge({ state }: { state: NewsState }) {
  const m: Record<NewsState, V> = {
    CLEAR:"success", PRE_EVENT:"warning", IN_EVENT:"danger",
    POST_EVENT:"warning", UNKNOWN:"muted", UNAVAILABLE:"muted", STALE:"warning",
  };
  return <Badge variant={m[state]}>{state.replace(/_/g," ")}</Badge>;
}

export function RegimeBadge({ state }: { state: RegimeState }) {
  const m: Record<RegimeState, V> = {
    TREND_UP:"success", TREND_DOWN:"danger", RANGE:"info", BREAKOUT:"accent",
    HIGH_VOLATILITY:"warning", TRANSITION:"warning", UNKNOWN:"muted", NOT_CONFIGURED:"muted",
  };
  return <Badge variant={m[state]}>{state.replace(/_/g," ")}</Badge>;
}

export function SignalStatusBadge({ status }: { status: SignalStatus }) {
  const m: Record<SignalStatus, V> = {
    CANDIDATE_FORMING:"muted", CANDIDATE_READY:"info", NEWS_BLOCKED:"warning",
    PENDING_RISK:"warning", RISK_APPROVED:"success", RISK_REJECTED:"danger",
    FORWARDED:"accent", EXPIRED:"muted", INVALIDATED:"danger",
  };
  return <Badge variant={m[status]}>{status.replace(/_/g," ")}</Badge>;
}

export function CommandStateBadge({ state }: { state: CommandState }) {
  const m: Record<CommandState, V> = {
    CREATED:"muted", SENT:"info", ACKNOWLEDGED:"info", EXECUTING:"warning",
    FILLED:"success", PARTIALLY_FILLED:"warning", REJECTED:"danger", EXPIRED:"muted", RECONCILED:"success",
  };
  return <Badge variant={m[state]}>{state.replace(/_/g," ")}</Badge>;
}

export function AgentStatusBadge({ status }: { status: AgentStatus }) {
  const m: Record<AgentStatus, V> = {
    ONLINE:"success", OFFLINE:"danger", ERROR:"danger", STALE:"warning", UNKNOWN:"muted",
  };
  return <Badge variant={m[status]}>{status}</Badge>;
}

export function BrainStateBadge({ state }: { state: BrainMarketState }) {
  const m: Record<BrainMarketState, V> = {
    INITIALIZING:"muted", WARMING_UP:"info", READY:"success", STALE:"warning", HALTED:"danger", ERROR:"danger",
  };
  return <Badge variant={m[state]}>{state.replace(/_/g," ")}</Badge>;
}
