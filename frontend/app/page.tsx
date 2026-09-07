import { AppShell } from "@/components/layout/AppShell";
import { OverviewPage } from "@/features/overview/OverviewPage";

export default function Home() {
  return (
    <AppShell>
      <OverviewPage />
    </AppShell>
  );
}

