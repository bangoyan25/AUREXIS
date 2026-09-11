"use client";
/**
 * AUREXIS sidebar navigation.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";

interface NavItem { href: string; label: string; }
interface NavSection { section: string; items: NavItem[]; }

const NAV: NavSection[] = [
  {
    section: "COMMAND",
    items: [{ href: "/", label: "Overview" }],
  },
  {
    section: "TRADING",
    items: [
      { href: "/market",    label: "Market" },
      { href: "/positions", label: "Positions" },
      { href: "/signals",   label: "Signals" },
      { href: "/strategy",  label: "Strategy Engine" },
      { href: "/execution", label: "Execution" },
    ],
  },
  {
    section: "INTELLIGENCE",
    items: [
      { href: "/brain",     label: "Brain" },
      { href: "/structure", label: "Market Structure" },
      { href: "/regime",    label: "Regime" },
      { href: "/news",      label: "News" },
    ],
  },
  {
    section: "RISK",
    items: [
      { href: "/risk",       label: "Risk Center" },
      { href: "/exposure",   label: "Exposure" },
      { href: "/protection", label: "Protection" },
    ],
  },
  {
    section: "SYSTEM",
    items: [
      { href: "/accounts",  label: "Accounts" },
      { href: "/agents",    label: "MT5 Agents" },
      { href: "/activity",  label: "Activity" },
      { href: "/settings",  label: "Settings" },
    ],
  },
  {
    section: "ANALYTICS",
    items: [
      { href: "/performance", label: "Performance" },
      { href: "/backtest",    label: "Backtest" },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <nav
      className="fixed inset-y-0 left-0 z-40 w-sidebar bg-aurexis-surface border-r border-aurexis-border flex flex-col overflow-y-auto"
      aria-label="Main navigation"
    >
      {/* Brand */}
      <div className="px-5 py-5 border-b border-aurexis-border flex-shrink-0">
        <Link href="/" className="block group" aria-label="AUREXIS — back to overview">
          <div className="flex flex-col gap-0.5">
            <span className="text-base font-display font-semibold tracking-[0.2em] text-aurexis-accent leading-none">
              AUREXIS
            </span>
            <span className="text-2xs font-mono tracking-widest text-aurexis-faint uppercase">
              XAUUSD · MT5
            </span>
          </div>
        </Link>
      </div>

      {/* Nav sections */}
      <div className="flex-1 py-4 px-3 space-y-5">
        {NAV.map(({ section, items }) => (
          <div key={section}>
            <p className="px-2 mb-1 text-2xs font-medium tracking-widest text-aurexis-faint uppercase select-none">
              {section}
            </p>
            <ul role="list" className="space-y-0.5">
              {items.map(({ href, label }) => {
                const active = pathname === href;
                return (
                  <li key={href}>
                    <Link
                      href={href}
                      className={clsx(
                        "flex items-center px-3 py-1.5 rounded text-xs transition-colors",
                        active
                          ? "bg-aurexis-muted text-aurexis-text font-medium"
                          : "text-aurexis-subtle hover:text-aurexis-text hover:bg-aurexis-muted/50",
                      )}
                      aria-current={active ? "page" : undefined}
                    >
                      {active && (
                        <span className="w-0.5 h-3 bg-aurexis-accent rounded-full mr-2 flex-shrink-0" aria-hidden="true" />
                      )}
                      {!active && <span className="w-2.5 flex-shrink-0" aria-hidden="true" />}
                      {label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="px-5 py-3 border-t border-aurexis-border flex-shrink-0">
        <p className="text-2xs text-aurexis-faint font-mono">
          v0.1.0-dev
        </p>
        <p className="text-2xs text-aurexis-faint font-mono mt-0.5 uppercase tracking-wide">
          NOT READY FOR LIVE TRADING
        </p>
      </div>
    </nav>
  );
}
