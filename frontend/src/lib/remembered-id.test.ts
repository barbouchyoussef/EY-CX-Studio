/**
 * The memory behind "reload lands back where I was".
 *
 * This is one half of the fix for a real bug: reloading mid-assessment used to drop the
 * consultant on the history list. The other half lives in the hub, which only offers to restore
 * when the browser *loaded* on the module's own URL, so walking in from the services hub still
 * lands on the list. This module is the part that can be tested in isolation.
 *
 * The failure mode worth covering is that localStorage THROWS rather than returning null when
 * site data is blocked, which is easy to get wrong and impossible to notice in a normal browser.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import { forgetId, rememberId, rememberedId } from "./remembered-id";

const KEY = "cx_test_active_id";

describe("remembered-id", () => {
  beforeEach(() => localStorage.clear());

  it("remembers an id across a read", () => {
    rememberId(KEY, 42);
    expect(rememberedId(KEY)).toBe(42);
  });

  it("returns null when nothing was remembered", () => {
    expect(rememberedId(KEY)).toBeNull();
  });

  it("forgets on null, so a closed conversation is not revived by a later reload", () => {
    rememberId(KEY, 42);
    rememberId(KEY, null);
    expect(rememberedId(KEY)).toBeNull();
  });

  it("forgetId does the same", () => {
    rememberId(KEY, 7);
    forgetId(KEY);
    expect(rememberedId(KEY)).toBeNull();
  });

  it.each([
    ["not a number", "abc"],
    ["zero", "0"],
    ["negative", "-3"],
    ["empty", ""],
  ])("treats a %s value as nothing remembered", (_label, raw) => {
    localStorage.setItem(KEY, raw);
    expect(rememberedId(KEY)).toBeNull();
  });

  it("survives storage that throws on read", () => {
    // A private window or blocked site data makes this throw, not return null.
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("blocked");
    });
    expect(() => rememberedId(KEY)).not.toThrow();
    expect(rememberedId(KEY)).toBeNull();
  });

  it("survives storage that throws on write", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("quota exceeded");
    });
    expect(() => rememberId(KEY, 1)).not.toThrow();
  });

  it("keeps separate keys apart, so one module cannot resume into another", () => {
    rememberId("cx_a", 1);
    rememberId("cx_b", 2);
    expect(rememberedId("cx_a")).toBe(1);
    expect(rememberedId("cx_b")).toBe(2);
  });
});
