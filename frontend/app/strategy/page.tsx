import { AppShell } from "@/components/layout/AppShell";
import { StrategyPage } from "@/features/strategy/StrategyPage";

export const metadata = {
  title: "Strategy Engine | AUREXIS",
  description: "Server-side strategy engine control panel.",
};

export default function StrategyRoute() {
  return (
    <AppShell>
      <StrategyPage />
    </AppShell>
  );
}
