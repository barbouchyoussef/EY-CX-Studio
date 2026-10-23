/**
 * The client-link panel's fields, and copying the link.
 *
 * The copy path is the interesting one. `navigator.clipboard` only exists in a secure context,
 * and this application is served over plain HTTP, so the execCommand fallback is the branch that
 * actually runs in production -- the one nobody exercises while developing on localhost.
 */

import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useClientLink } from "./use-client-link";

describe("useClientLink", () => {
  beforeEach(() => vi.unstubAllGlobals());

  it("starts empty", () => {
    const { result } = renderHook(() => useClientLink());
    expect(result.current.name).toBe("");
    expect(result.current.role).toBe("");
    expect(result.current.email).toBe("");
    expect(result.current.link).toBeNull();
    expect(result.current.copied).toBe(false);
  });

  it("reset clears every field and the generated link", () => {
    const { result } = renderHook(() => useClientLink());

    act(() => {
      result.current.setName("Nayrouz");
      result.current.setRole("CX Lead");
      result.current.setEmail("someone@example.com");
      result.current.setLink("http://example.test/a/tok");
    });
    expect(result.current.link).not.toBeNull();

    act(() => result.current.reset());

    expect(result.current.name).toBe("");
    expect(result.current.role).toBe("");
    expect(result.current.email).toBe("");
    expect(result.current.link).toBeNull();
    expect(result.current.copied).toBe(false);
  });

  it("copies through the clipboard API when there is one", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    const { result } = renderHook(() => useClientLink());

    act(() => result.current.setLink("http://example.test/a/tok"));
    await act(async () => await result.current.copyLink());

    expect(writeText).toHaveBeenCalledWith("http://example.test/a/tok");
    expect(result.current.copied).toBe(true);
  });

  it("falls back to execCommand when there is no clipboard API", async () => {
    // This is the production path: plain HTTP means navigator.clipboard is undefined.
    vi.stubGlobal("navigator", {});
    const execCommand = vi.fn().mockReturnValue(true);
    Object.defineProperty(document, "execCommand", { value: execCommand, configurable: true });
    const { result } = renderHook(() => useClientLink());

    act(() => result.current.setLink("http://example.test/a/tok"));
    await act(async () => await result.current.copyLink());

    expect(execCommand).toHaveBeenCalledWith("copy");
    expect(result.current.copied).toBe(true);
    // The temporary textarea must not be left in the document.
    expect(document.querySelectorAll("textarea")).toHaveLength(0);
  });

  it("stops showing 'copied' after a couple of seconds", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("navigator", { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
    const { result } = renderHook(() => useClientLink());

    act(() => result.current.setLink("http://example.test/a/tok"));
    await act(async () => await result.current.copyLink());
    expect(result.current.copied).toBe(true);

    act(() => vi.advanceTimersByTime(2500));
    expect(result.current.copied).toBe(false);
    vi.useRealTimers();
  });

  it("does nothing when there is no link yet", async () => {
    const writeText = vi.fn();
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    const { result } = renderHook(() => useClientLink());

    await act(async () => await result.current.copyLink());

    expect(writeText).not.toHaveBeenCalled();
    expect(result.current.copied).toBe(false);
  });

  it("survives a clipboard the browser refuses", async () => {
    vi.stubGlobal("navigator", {
      clipboard: { writeText: vi.fn().mockRejectedValue(new DOMException("denied")) },
    });
    const { result } = renderHook(() => useClientLink());

    act(() => result.current.setLink("http://example.test/a/tok"));
    // The link stays on screen for manual copying; this must not throw.
    await act(async () => await result.current.copyLink());

    await waitFor(() => expect(result.current.link).toBe("http://example.test/a/tok"));
    expect(result.current.copied).toBe(false);
  });
});
