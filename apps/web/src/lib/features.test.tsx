import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { FEATURE_DEFAULTS, NAV_FEATURE } from "./feature-registry.generated";
import { FeatureGate, refreshFeatures, resetFeaturesForTests, enableFeatureFetchForTests, useFeature, useFeatureValue, useNavEnabled } from "./features";
import { featuresApi } from "./features-api";

vi.mock("./features-api", () => ({ featuresApi: { snapshot: vi.fn() } }));
const snapshot = vi.mocked(featuresApi.snapshot);

function Probe() {
  const rooms = useFeature("rooms.booking");
  const tutor = useFeature("learning.tutor");
  const verbatim = useFeatureValue("chat.assistant");
  const navEnabled = useNavEnabled(NAV_FEATURE);
  return <div>rooms:{String(rooms)} tutor:{String(tutor)} v:{String(verbatim)} navrooms:{String(navEnabled("rooms"))}</div>;
}

describe("features", () => {
  beforeEach(() => { enableFeatureFetchForTests(); snapshot.mockReset(); resetFeaturesForTests(); });
  afterEach(() => cleanup());

  it("uses the registry defaults until the server answers", () => {
    snapshot.mockReturnValue(new Promise(() => {}));
    render(<Probe />);
    expect(screen.getByText(/rooms:true tutor:false/)).toBeTruthy();
    expect(FEATURE_DEFAULTS["rooms.booking"]).toBe(true);
  });

  it("applies the server snapshot and hides a switched-off nav item", async () => {
    snapshot.mockResolvedValue({ version: 3, features: { "rooms.booking": false, "learning.tutor": true } });
    render(<Probe />);
    await waitFor(() => expect(screen.getByText(/rooms:false tutor:true/)).toBeTruthy());
    expect(screen.getByText(/navrooms:false/)).toBeTruthy();
  });

  it("keeps the last known values when a refresh fails", async () => {
    snapshot.mockResolvedValueOnce({ version: 1, features: { "rooms.booking": false } });
    render(<Probe />);
    await waitFor(() => expect(screen.getByText(/rooms:false/)).toBeTruthy());
    snapshot.mockRejectedValueOnce(new Error("network"));
    await act(async () => { await refreshFeatures(); });
    expect(screen.getByText(/rooms:false/)).toBeTruthy();
  });

  it("FeatureGate renders children only while the feature is on", async () => {
    snapshot.mockResolvedValue({ version: 1, features: { "rooms.booking": false } });
    render(<FeatureGate feature="rooms.booking" fallback={<span>closed</span>}><span>open</span></FeatureGate>);
    await waitFor(() => expect(screen.getByText("closed")).toBeTruthy());
    expect(screen.queryByText("open")).toBeNull();
  });
});
