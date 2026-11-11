import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "./App";
import { fixtureCatalog, fixtureInfo, fixtureSettings, fixtureStats, jsonResponse } from "./test/fixtures";

const SECTIONS: Array<[string, string]> = [
  ["nav-dashboard", "Dashboard"],
  ["nav-orders", "Amazon Orders"],
  ["nav-monitoring", "Price Monitoring"],
  ["nav-refunds", "Refund Assistant"],
  ["nav-returns", "Returns and Deadlines"],
  ["nav-savings", "Savings History"],
  ["nav-settings", "Settings"],
];

function installFetch() {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      calls.push({ url, init });
      if (url.endsWith("/api/v1/sample/catalog")) return jsonResponse(fixtureCatalog);
      if (url.endsWith("/api/v1/info")) return jsonResponse(fixtureInfo);
      if (url.endsWith("/api/v1/stats")) return jsonResponse(fixtureStats);
      if (url.endsWith("/api/v1/settings") && (!init?.method || init.method === "GET")) return jsonResponse(fixtureSettings);
      if (url.endsWith("/api/v1/settings") && init?.method === "PUT") {
        return jsonResponse({ ...fixtureSettings, monitoring_interval_minutes: 120 });
      }
      if (url.endsWith("/api/v1/secrets/keepa_api_key") && (!init?.method || init.method === "GET")) {
        return jsonResponse({ name: "keepa_api_key", configured: false, backend: "encrypted_file" });
      }
      if (url.endsWith("/api/v1/secrets/keepa_api_key") && init?.method === "PUT") {
        return new Response(null, { status: 204 });
      }
      if (url.endsWith("/api/v1/price-checks")) {
        return jsonResponse(
          {
            error: {
              code: "provider_not_configured",
              message: "No permitted price source is configured. No price was fetched, and nothing was sent to Amazon.",
            },
            checked: false,
            price_cents: null,
            recorded_run_status: "skipped",
          },
          409,
        );
      }
      if (url.endsWith("/api/v1/purchases") && init?.method === "DELETE") {
        return jsonResponse({ deleted: { orders: 0 }, sample_data_affected: false });
      }
      return jsonResponse({ error: { code: "not_mocked", message: url } }, 500);
    }),
  );
  return calls;
}

function renderApp() {
  return render(
    <MemoryRouter>
      <AppRoutes />
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("application shell", () => {
  it("labels sample data and opens every section", async () => {
    const user = userEvent.setup();
    installFetch();
    renderApp();
    expect(screen.getByTestId("sample-banner")).toHaveTextContent("SAMPLE DATA");
    expect(screen.getByTestId("sample-banner")).toHaveTextContent("not guaranteed");
    expect(await screen.findByTestId("stat-estimated-savings")).toHaveTextContent("$31.00");
    expect(screen.getByTestId("stored-orders")).toHaveTextContent("0");
    expect(screen.getByText("Not connected")).toBeInTheDocument();
    expect(screen.getByText("Never")).toBeInTheDocument();

    for (const [testId, heading] of SECTIONS) {
      await user.click(screen.getByTestId(testId));
      expect(screen.getByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
      expect(screen.getByTestId("sample-banner")).toBeInTheDocument();
    }
  });

  it("shows an error when the local API is down", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("network down");
      }),
    );
    renderApp();
    expect(await screen.findByRole("alert")).toHaveTextContent("Local API is unavailable");
    expect(screen.getByTestId("sample-banner")).toBeInTheDocument();
  });

  it("does not invent a price when a manual check is requested", async () => {
    const user = userEvent.setup();
    installFetch();
    renderApp();
    await screen.findByTestId("stat-estimated-savings");
    await user.click(screen.getByTestId("nav-monitoring"));
    expect(await screen.findByText("$64.99")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Check prices now" }));
    const result = await screen.findByTestId("price-check-result");
    expect(result).toHaveTextContent("nothing was sent to Amazon");
    expect(result).toHaveTextContent("No price was recorded.");
    expect(screen.getByText("$64.99")).toBeInTheDocument();
  });

  it("requires DELETE before removing stored purchase data", async () => {
    const user = userEvent.setup();
    const calls = installFetch();
    renderApp();
    await screen.findByTestId("stat-estimated-savings");
    await user.click(screen.getByTestId("nav-settings"));
    const button = await screen.findByTestId("delete-purchases");
    expect(button).toBeDisabled();
    await user.type(screen.getByTestId("delete-confirm"), "DELETE");
    expect(button).toBeEnabled();
    await user.click(button);
    expect(await screen.findByText("Deleted 0 stored orders. Sample illustrations were not removed.")).toBeInTheDocument();
    const deletion = calls.find((call) => call.url.endsWith("/api/v1/purchases"));
    expect(deletion?.init?.method).toBe("DELETE");
    expect(new Headers(deletion?.init?.headers).get("X-Confirm-Delete")).toBe("DELETE-PURCHASE-DATA");
  });

  it("still shows settings when the secret store is locked", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/api/v1/sample/catalog")) return jsonResponse(fixtureCatalog);
        if (url.endsWith("/api/v1/info")) return jsonResponse(fixtureInfo);
        if (url.endsWith("/api/v1/stats")) return jsonResponse(fixtureStats);
        if (url.endsWith("/api/v1/settings") && (!init?.method || init.method === "GET")) return jsonResponse(fixtureSettings);
        if (url.endsWith("/api/v1/secrets/keepa_api_key")) {
          return jsonResponse(
            { error: { code: "secret_store_locked", message: "The secret store is locked." } },
            503,
          );
        }
        return jsonResponse({ error: { code: "not_mocked", message: url } }, 500);
      }),
    );
    renderApp();
    await screen.findByTestId("stat-estimated-savings");
    await user.click(screen.getByTestId("nav-settings"));
    expect(await screen.findByLabelText("Monitoring interval (minutes)")).toBeInTheDocument();
    expect(await screen.findByText("The secret store is locked.")).toBeInTheDocument();
  });

  it("shows the sample return warning and refund draft", async () => {
    const user = userEvent.setup();
    installFetch();
    renderApp();
    await screen.findByTestId("stat-estimated-savings");
    await user.click(screen.getByTestId("nav-returns"));
    expect(await screen.findByText("1 day")).toBeInTheDocument();
    expect(screen.getByText(/without your confirmation/)).toBeInTheDocument();
    await user.click(screen.getByTestId("nav-refunds"));
    expect(await screen.findByText(/Nothing has been sent to Amazon/)).toBeInTheDocument();
    expect(screen.getByLabelText("Draft message")).toHaveValue("I understand that a refund is not guaranteed.");
    await user.click(screen.getByTestId("nav-orders"));
    expect(await screen.findByText("[SAMPLE] Over-ear headphones")).toBeInTheDocument();
    await user.click(screen.getByTestId("nav-savings"));
    expect(await screen.findByText("Estimated gap")).toBeInTheDocument();
  });
});
