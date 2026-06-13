import { cn } from "@/lib/utils";

// The Cockpit — agent-native IDE (PTY terminal + editor + live agent overlay).
// Served by the dashboard backend at /cockpit-ide/ (mounted in web_server.py);
// embedded here as a same-origin iframe so it shows up as a dashboard tab.
export default function CockpitPage() {
  return (
    <div
      className={cn(
        "flex min-h-0 w-full min-w-0 flex-1 flex-col",
        "pt-1 sm:pt-2",
      )}
    >
      <iframe
        title="Cockpit"
        src="/cockpit-ide/"
        className={cn(
          "min-h-0 w-full min-w-0 flex-1",
          "rounded-sm border border-current/20",
        )}
        sandbox="allow-scripts allow-same-origin allow-popups allow-forms allow-modals"
      />
    </div>
  );
}
