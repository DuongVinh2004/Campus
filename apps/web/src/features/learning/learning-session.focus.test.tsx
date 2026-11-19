import React, { useLayoutEffect } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { useLearningSession } from "./learning-session";

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("handles a focus identity change before the newly identified view is painted", async () => {
  vi.stubGlobal("BroadcastChannel", undefined);
  const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
    user_id: "another-actor", roles: ["STUDENT"],
  })));
  function Guard({ actorId }: { actorId: string }) {
    const session = useLearningSession(actorId, ["STUDENT"]);
    // Browser focus can arrive as soon as the identified view becomes visible.
    useLayoutEffect(() => { if (actorId) window.dispatchEvent(new Event("focus")); }, [actorId]);
    return <p>{session.state}</p>;
  }
  const view = render(<Guard actorId="" />);
  view.rerender(<Guard actorId="original-actor" />);
  expect(await screen.findByText("changed")).toBeDefined();
  expect(fetcher).toHaveBeenCalledTimes(1);
});
