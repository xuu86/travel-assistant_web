import { expect, test } from "@playwright/test";

test.describe("owner-scoped IndexedDB storage", () => {
  test("keeps a stable guest id and isolates, updates, and deletes snapshots by owner", async ({ page }) => {
    await page.goto("/");
    const result = await page.evaluate(async () => {
      const repository = await (new Function("return import('/src/features/local-storage/repository.ts')")() as Promise<typeof import("../src/features/local-storage/repository")>);
      const guestFirst = await repository.getGuestOwnerId();
      const guestSecond = await repository.getGuestOwnerId();
      await repository.saveWorkspaceSnapshot("account-a", "notes.items", 1, [{ id: "a", body: "A note" }]);
      await repository.saveWorkspaceSnapshot("account-b", "notes.items", 1, [{ id: "b", body: "B note" }]);
      await repository.saveWorkspaceSnapshot("account-a", "notes.items", 1, [{ id: "a2", body: "Updated" }]);
      const first = await repository.getWorkspaceSnapshot("account-a", "notes.items");
      const other = await repository.getWorkspaceSnapshot("account-b", "notes.items");
      await repository.deleteWorkspaceSnapshot("account-a", "notes.items");
      return {
        guestFirst,
        guestSecond,
        first: first?.data,
        other: other?.data,
        deleted: await repository.getWorkspaceSnapshot("account-a", "notes.items"),
        stillPresent: await repository.getWorkspaceSnapshot("account-b", "notes.items"),
      };
    });

    expect(result.guestFirst).toMatch(/^guest-/);
    expect(result.guestSecond).toBe(result.guestFirst);
    expect(result.first).toEqual([{ id: "a2", body: "Updated" }]);
    expect(result.other).toEqual([{ id: "b", body: "B note" }]);
    expect(result.deleted).toBeUndefined();
    expect(result.stillPresent?.data).toEqual([{ id: "b", body: "B note" }]);
  });

  test("indexes listings only for the requested owner", async ({ page }) => {
    await page.goto("/");
    const listed = await page.evaluate(async () => {
      const repository = await (new Function("return import('/src/features/local-storage/repository.ts')")() as Promise<typeof import("../src/features/local-storage/repository")>);
      await repository.saveWorkspaceSnapshot("owner-one", "one", 1, { ok: true });
      await repository.saveWorkspaceSnapshot("owner-two", "two", 1, { ok: false });
      return {
        one: await repository.listWorkspaceSnapshots("owner-one"),
        two: await repository.listWorkspaceSnapshots("owner-two"),
        empty: await repository.listWorkspaceSnapshots("owner-empty"),
      };
    });

    expect(listed.one.map((item) => item.feature_id)).toEqual(["one"]);
    expect(listed.two.map((item) => item.feature_id)).toEqual(["two"]);
    expect(listed.empty).toEqual([]);
  });

  test("an explicit workspace reset deletes only the current owner partition", async ({ page }) => {
    await page.goto("/");
    const remaining = await page.evaluate(async () => {
      const repository = await (new Function("return import('/src/features/local-storage/repository.ts')")() as Promise<typeof import("../src/features/local-storage/repository")>);
      await repository.saveWorkspaceSnapshot("owner-one", "itinerary.items", 1, ["draft"]);
      await repository.saveWorkspaceSnapshot("owner-two", "itinerary.items", 1, ["other"]);
      await repository.deleteAllWorkspaceSnapshots("owner-one");
      return {
        one: await repository.listWorkspaceSnapshots("owner-one"),
        two: await repository.listWorkspaceSnapshots("owner-two"),
      };
    });

    expect(remaining.one).toEqual([]);
    expect(remaining.two.map((record) => record.data)).toEqual([["other"]]);
  });

  test("preserves an unsupported snapshot without overwriting or deleting it", async ({ page }) => {
    await page.goto("/");
    const retained = await page.evaluate(async () => {
      const repository = await (new Function("return import('/src/features/local-storage/repository.ts')")() as Promise<typeof import("../src/features/local-storage/repository")>);
      await repository.saveWorkspaceSnapshot("owner-versioned", "future.feature", 99, { original: true });
      const record = await repository.getWorkspaceSnapshot("owner-versioned", "future.feature");
      let decodeError = "";
      try {
        const { decodeWorkspaceSnapshot } = await (new Function("return import('/src/features/local-storage/snapshot.ts')")() as Promise<typeof import("../src/features/local-storage/snapshot")>);
        decodeWorkspaceSnapshot(record!);
      } catch (error) {
        decodeError = error instanceof Error ? error.message : "";
      }
      const after = await repository.getWorkspaceSnapshot("owner-versioned", "future.feature");
      return { decodeError, version: after?.schema_version, data: after?.data };
    });

    expect(retained.decodeError).toContain("只读");
    expect(retained.version).toBe(99);
    expect(retained.data).toEqual({ original: true });
  });
});
