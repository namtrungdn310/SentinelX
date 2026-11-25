import { useEffect, useState } from "react";
import { fetchAgentBundleInfo } from "../api";
import type { AgentBundleInfo } from "../types";

export function useAgentBundleInfo(enabled: boolean): {
  bundleInfo: AgentBundleInfo | null;
  bundleLoading: boolean;
} {
  const [bundleInfo, setBundleInfo] = useState<AgentBundleInfo | null | undefined>(undefined);

  useEffect(() => {
    if (!enabled) return;
    let active = true;
    fetchAgentBundleInfo()
      .then((info) => {
        if (active) setBundleInfo(info);
      })
      .catch(() => {
        if (active) setBundleInfo(null);
      });
    return () => {
      active = false;
    };
  }, [enabled]);

  return {
    bundleInfo: bundleInfo ?? null,
    bundleLoading: enabled && bundleInfo === undefined,
  };
}
