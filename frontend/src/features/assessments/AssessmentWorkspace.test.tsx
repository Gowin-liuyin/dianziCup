import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { assetFixture, fixtureAssetId, fixtureTenant, snapshotFixture } from "../assets/synthetic-fixtures";
import { AssessmentWorkspace } from "./AssessmentWorkspace";
import { syntheticScope, syntheticUser } from "./assessment.fixture";

function response(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }); }
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
describe("R17 independent assessment asset selector · synthetic HTTP fixture", () => {
  it("selects an existing asset and rereads fixed history through existing asset client", async () => {
    const fetch = vi.fn(async (path: string) => response(path.startsWith("/v1/assets?") ? { items: [assetFixture()], next_cursor: null } : path.endsWith("/snapshots?limit=20") ? { items: [snapshotFixture(1)], next_cursor: null } : path.endsWith(snapshotFixture(1).snapshot_id) ? snapshotFixture(1) : assetFixture())); vi.stubGlobal("fetch", fetch);
    render(<AssessmentWorkspace user={syntheticUser} authScope="synthetic-session" isCurrent={() => true} />);
    await screen.findByRole("option", { name: /Synthetic fixture · 资产工作台/ }); fireEvent.change(screen.getByRole("combobox", { name: "授权资产" }), { target: { value: fixtureAssetId } }); await screen.findByText("快照 #2");
    await screen.findByRole("option", { name: /保存快照 #1/ }); fireEvent.change(screen.getByRole("combobox", { name: "固定快照" }), { target: { value: snapshotFixture(1).snapshot_id } }); await screen.findByText("快照 #1"); expect(screen.getByText(/选择的是历史输入/)).toBeTruthy();
    expect(fetch).toHaveBeenCalledWith(`/v1/assets/${fixtureAssetId}/snapshots/${snapshotFixture(1).snapshot_id}`, expect.anything());
    expect(fetch.mock.calls.every(([path]) => !path.includes("tenant"))).toBe(true);
  });
  it("does not request assets without authenticated read:asset and an explicit tenant", () => {
    const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
    const { rerender } = render(<AssessmentWorkspace user={{ ...syntheticUser, permissions: [] }} authScope="synthetic" isCurrent={() => true} />); expect(screen.getByRole("heading", { name: "当前会话无资产研判权限" })).toBeTruthy();
    rerender(<AssessmentWorkspace user={{ ...syntheticUser, tenant_id: null }} authScope="synthetic" isCurrent={() => true} />); expect(fetch).not.toHaveBeenCalled();
  });
  it("clears the entire private selector on cross-tenant asset response", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => response({ items: [{ ...assetFixture(), tenant_id: `${fixtureTenant}-other` }], next_cursor: null })));
    render(<AssessmentWorkspace user={syntheticUser} authScope="synthetic" isCurrent={() => true} />); await screen.findByRole("alert"); expect(screen.queryByRole("combobox", { name: "授权资产" })).toBeNull(); expect(screen.queryByText(syntheticScope.snapshotId)).toBeNull();
  });
  it("keeps empty catalog distinct from 503 failure", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => response({ items: [], next_cursor: null })));
    const { unmount } = render(<AssessmentWorkspace user={syntheticUser} authScope="synthetic" isCurrent={() => true} />); await screen.findByRole("heading", { name: "没有已读的授权资产" }); expect(screen.queryByRole("alert")).toBeNull(); unmount();
    vi.stubGlobal("fetch", vi.fn(async () => response({ error: { code: "dependency_unavailable", retryable: true } }, 503)));
    render(<AssessmentWorkspace user={syntheticUser} authScope="synthetic-2" isCurrent={() => true} />); await screen.findByRole("alert"); expect(screen.queryByRole("heading", { name: "没有已读的授权资产" })).toBeNull();
  });
});
