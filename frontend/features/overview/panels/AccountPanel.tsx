"use client";
import { Panel, StatRow, Badge } from "@/components/ui/primitives";
import { useSelectedAccount } from "@/lib/account-context";

export function AccountPanel() {
  const { selectedAccount, loading, error } = useSelectedAccount();

  if (loading) {
    return (
      <Panel title="Account">
        <div className="px-4 py-6 text-center">
          <span className="text-2xs font-mono text-aurexis-faint animate-pulse">LOADING...</span>
        </div>
      </Panel>
    );
  }

  if (error) {
    return (
      <Panel title="Account">
        <div className="px-4 py-6 text-center">
          <p className="text-2xs font-mono text-aurexis-danger">Unable to load account</p>
        </div>
      </Panel>
    );
  }

  if (!selectedAccount) {
    return (
      <Panel title="Account">
        <div className="px-4 py-6 text-center">
          <p className="text-xs text-aurexis-subtle">No account registered.</p>
          <p className="text-2xs text-aurexis-faint mt-1">Register an MT5 account to begin.</p>
        </div>
      </Panel>
    );
  }

  const a = selectedAccount;
  return (
    <Panel title="Account">
      <div className="px-4 py-3">
        <StatRow label="Label" value={a.label} />
        <StatRow label="Broker" value={a.broker || <Badge variant="muted">UNSPECIFIED</Badge>} />
        <StatRow label="MT5 Server" value={
          a.mt5_server
            ? <span className="font-mono text-aurexis-faint text-2xs">{a.mt5_server}</span>
            : <Badge variant="muted">UNSPECIFIED</Badge>
        } />
        <StatRow label="Account Number" value={<span className="font-mono text-aurexis-faint text-2xs">{a.mt5_account_number}</span>} />
        <StatRow label="Currency" value={a.broker_currency} />
        <StatRow label="Account Type" value={a.is_cent_account ? "Cent account" : "Standard"} />
        <StatRow label="Status" value={
          a.is_active
            ? <Badge variant="success">ACTIVE</Badge>
            : <Badge variant="danger">INACTIVE</Badge>
        } />
      </div>
    </Panel>
  );
}

