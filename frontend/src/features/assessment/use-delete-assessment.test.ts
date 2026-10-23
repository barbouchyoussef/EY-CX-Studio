/**
 * The delete confirmation's three flags, which have to agree.
 *
 * The states this covers are the ones that used to be possible when they were three separate
 * useState calls in a 1,600-line component: a spinner with nothing pending, an error left over
 * from a previous attempt, a row removed from the list after a failed request.
 */

import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useDeleteAssessment } from "./use-delete-assessment";

const ROW = { id: 7, company_name: "Acme" };

const mockFetch = (response: Response) => {
  const f = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", f);
  return f;
};

describe("useDeleteAssessment", () => {
  beforeEach(() => vi.unstubAllGlobals());

  it("starts with nothing pending, idle and no error", () => {
    const { result } = renderHook(() => useDeleteAssessment(vi.fn(), false));
    expect(result.current.pending).toBeNull();
    expect(result.current.busy).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("asking opens the confirmation for that row", () => {
    const { result } = renderHook(() => useDeleteAssessment(vi.fn(), false));
    act(() => result.current.ask(ROW));
    expect(result.current.pending).toEqual(ROW);
  });

  it("removes the row and closes on success", async () => {
    mockFetch(new Response(null, { status: 204 }));
    const onDeleted = vi.fn();
    const { result } = renderHook(() => useDeleteAssessment(onDeleted, false));

    act(() => result.current.ask(ROW));
    await act(async () => await result.current.confirm());

    expect(onDeleted).toHaveBeenCalledWith(7);
    expect(result.current.pending).toBeNull();
    expect(result.current.busy).toBe(false);
  });

  it("keeps the row and explains when the server refuses", async () => {
    mockFetch(new Response("", { status: 404 }));
    const onDeleted = vi.fn();
    const { result } = renderHook(() => useDeleteAssessment(onDeleted, false));

    act(() => result.current.ask(ROW));
    await act(async () => await result.current.confirm());

    // The row must NOT disappear from the list when the delete did not happen.
    expect(onDeleted).not.toHaveBeenCalled();
    expect(result.current.pending).toEqual(ROW);
    expect(result.current.error).toMatch(/owner/i);
    expect(result.current.busy).toBe(false);
  });

  it("clears the previous error when the dialog is reopened", async () => {
    mockFetch(new Response("", { status: 404 }));
    const { result } = renderHook(() => useDeleteAssessment(vi.fn(), false));

    act(() => result.current.ask(ROW));
    await act(async () => await result.current.confirm());
    expect(result.current.error).not.toBeNull();

    act(() => result.current.ask({ id: 8, company_name: "Other" }));
    expect(result.current.error).toBeNull();
  });

  it("cancelling closes the dialog and drops the message with it", async () => {
    mockFetch(new Response("", { status: 404 }));
    const { result } = renderHook(() => useDeleteAssessment(vi.fn(), false));

    act(() => result.current.ask(ROW));
    await act(async () => await result.current.confirm());
    act(() => result.current.cancel());

    expect(result.current.pending).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("does nothing when confirm is called with nothing pending", async () => {
    const f = mockFetch(new Response(null, { status: 204 }));
    const { result } = renderHook(() => useDeleteAssessment(vi.fn(), false));

    await act(async () => await result.current.confirm());

    expect(f).not.toHaveBeenCalled();
  });

  it("clears busy even when the request throws", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));
    const { result } = renderHook(() => useDeleteAssessment(vi.fn(), false));

    act(() => result.current.ask(ROW));
    await act(async () => {
      await result.current.confirm().catch(() => {});
    });

    await waitFor(() => expect(result.current.busy).toBe(false));
  });

  it("speaks French when asked to", async () => {
    mockFetch(new Response("", { status: 404 }));
    const { result } = renderHook(() => useDeleteAssessment(vi.fn(), true));

    act(() => result.current.ask(ROW));
    await act(async () => await result.current.confirm());

    expect(result.current.error).toMatch(/Suppression impossible/);
  });
});
