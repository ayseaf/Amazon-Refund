import { useEffect, useState, type FormEvent } from "react";
import { deleteAmazonSession, deletePurchases, getSecret, getSettings, putSecret, saveSettings, scanAmazonOrders, startAmazonSignIn } from "../api";
import { useCatalog } from "../catalog";
import { centsToDollars, dollarsToCents } from "../format";
import type { AppSettings } from "../types";

type BooleanSetting = {
  [K in keyof AppSettings]: AppSettings[K] extends boolean ? K : never;
}[keyof AppSettings];

const TOGGLES: Array<{ key: BooleanSetting; label: string; disabled?: boolean; hint?: string }> = [
  { key: "desktop_notifications", label: "Desktop notifications" },
  { key: "notify_price_decrease", label: "Price decreases" },
  { key: "notify_savings", label: "Savings above the threshold" },
  { key: "notify_return_deadlines", label: "Return deadlines at 7, 3, and 1 days" },
  { key: "notify_price_check_failures", label: "Price-check failures" },
  { key: "notify_refund_status", label: "Refund status updates" },
  { key: "notify_monitoring_unavailable", label: "Products that can no longer be monitored" },
  {
    key: "email_notifications",
    label: "Email notifications",
    disabled: true,
    hint: "Not available until a later phase.",
  },
  {
    key: "telegram_notifications",
    label: "Telegram notifications",
    disabled: true,
    hint: "Not available until a later phase.",
  },
];

export function SettingsPage() {
  const catalogState = useCatalog();
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [threshold, setThreshold] = useState("5.00");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [secret, setSecret] = useState("");
  const [secretConfigured, setSecretConfigured] = useState<boolean | null>(null);
  const [secretNote, setSecretNote] = useState<string | null>(null);
  const [phrase, setPhrase] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getSettings()
      .then((loadedSettings) => {
        if (cancelled) {
          return;
        }
        setSettings(loadedSettings);
        setThreshold(centsToDollars(loadedSettings.min_savings_cents));
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : "Settings could not be loaded.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoaded(true);
        }
      });
    getSecret("keepa_api_key")
      .then((secretStatus) => {
        if (!cancelled) {
          setSecretConfigured(secretStatus.configured);
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setSecretConfigured(false);
          setSecretNote(caught instanceof Error ? caught.message : "The secret store could not be read.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSave(event: FormEvent) {
    event.preventDefault();
    if (!settings) {
      return;
    }
    const cents = dollarsToCents(threshold);
    if (cents === null) {
      setError("Enter the savings threshold in dollars, such as 5.00.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const saved = await saveSettings({
        monitoring_interval_minutes: settings.monitoring_interval_minutes,
        min_savings_cents: cents,
        desktop_notifications: settings.desktop_notifications,
        notify_price_decrease: settings.notify_price_decrease,
        notify_savings: settings.notify_savings,
        notify_return_deadlines: settings.notify_return_deadlines,
        notify_price_check_failures: settings.notify_price_check_failures,
        notify_refund_status: settings.notify_refund_status,
        notify_monitoring_unavailable: settings.notify_monitoring_unavailable,
      });
      setSettings(saved);
      setMessage("Saved on this computer.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Settings could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  async function onStoreKey(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await putSecret("keepa_api_key", secret);
      setSecret("");
      setSecretConfigured(true);
      setMessage("Keepa key stored locally. It will not be shown again.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The key could not be stored.");
    } finally {
      setBusy(false);
    }
  }

  async function onAmazon(action: "sign-in" | "scan" | "sign-out") {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      if (action === "sign-in") {
        const result = await startAmazonSignIn();
        setMessage(result.message);
      } else if (action === "scan") {
        const result = await scanAmazonOrders();
        setMessage(result.message);
      } else {
        await deleteAmazonSession();
        setMessage("The Amazon session on this computer was deleted. The password was never stored.");
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Amazon could not be reached from this computer.");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await deletePurchases();
      setPhrase("");
      setMessage(
        `Deleted ${result.deleted.orders} stored orders. Sample illustrations were not removed.`,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Purchase data could not be deleted.");
    } finally {
      setBusy(false);
    }
  }

  function toggle(key: BooleanSetting) {
    setSettings((current) => (current ? { ...current, [key]: !current[key] } : current));
  }

  return (
    <section>
      <header className="page-header">
        <h1>Settings</h1>
        <p>Secrets stay in the local store. Amazon passwords are not accepted. Nothing here is sent to Amazon.</p>
      </header>
      {catalogState.status === "ready" ? (
        <p className="hint">
          Secret store: {catalogState.info.secret_store} ({catalogState.info.secret_backend}). Scheduler:{" "}
          {catalogState.info.scheduler.detail}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="error-text">
          {error}
        </p>
      ) : null}
      {message ? <p role="status">{message}</p> : null}
      {settings ? (
        <form className="panel stack" onSubmit={onSave}>
          <h2>Monitoring and notifications</h2>
          <label htmlFor="interval">Monitoring interval (minutes)</label>
          <input
            id="interval"
            type="number"
            min={60}
            max={10080}
            value={settings.monitoring_interval_minutes}
            onChange={(event) =>
              setSettings({ ...settings, monitoring_interval_minutes: Number(event.target.value) })
            }
          />
          <p className="muted">Phase 1 rejects anything shorter than 60 minutes.</p>
          <label htmlFor="threshold">Minimum savings to highlight (USD)</label>
          <input id="threshold" inputMode="decimal" value={threshold} onChange={(event) => setThreshold(event.target.value)} />
          {TOGGLES.map((item) => (
            <label key={item.key} className="check">
              <input
                type="checkbox"
                checked={Boolean(settings[item.key])}
                disabled={item.disabled}
                onChange={() => toggle(item.key)}
              />
              <span>
                {item.label}
                {item.hint ? <span className="muted"> {item.hint}</span> : null}
              </span>
            </label>
          ))}
          <button type="submit" disabled={busy}>
            Save settings
          </button>
        </form>
      ) : loaded ? null : (
        <p className="status-line">Loading settings…</p>
      )}
      <section className="panel stack">
        <h2>Amazon sign-in</h2>
        <p>
          There is no Amazon password field. Open Amazon in a real browser window and type your password
          and any verification code there yourself. This app stores only the session cookies, encrypted,
          on this computer.
        </p>
        {catalogState.status === "ready" ? (
          <p className="hint">
            Session: {catalogState.session.status}. Marketplace amazon.com. Password stored: no.
            {catalogState.session.last_challenge ? ` Last challenge: ${catalogState.session.last_challenge}.` : ""}
            {catalogState.session.last_error ? ` ${catalogState.session.last_error}` : ""}
          </p>
        ) : null}
        <button type="button" data-testid="amazon-sign-in" disabled={busy} onClick={() => void onAmazon("sign-in")}>
          Open Amazon sign-in
        </button>
        <button type="button" data-testid="amazon-scan" disabled={busy} onClick={() => void onAmazon("scan")}>
          Review orders from the last 30 days
        </button>
        <button type="button" data-testid="amazon-sign-out" disabled={busy} onClick={() => void onAmazon("sign-out")}>
          Sign out / delete Amazon session
        </button>
      </section>
      <form className="panel stack" onSubmit={onStoreKey}>
        <h2>Keepa API key</h2>
        <p className="muted">
          Stored in the local secret store. It is not shown again and is not sent to Amazon.
          {secretConfigured === null ? "" : secretConfigured ? " A key is already stored." : " No key is stored."}
        </p>
        {secretNote ? <p role="status">{secretNote}</p> : null}
        <label htmlFor="keepa_api_key">Keepa API key</label>
        <input
          id="keepa_api_key"
          name="keepa_api_key"
          type="password"
          autoComplete="off"
          spellCheck={false}
          value={secret}
          onChange={(event) => setSecret(event.target.value)}
        />
        <button type="submit" disabled={busy || secret.trim() === ""}>
          Store key locally
        </button>
      </form>
      <section className="panel danger">
        <h2>Delete stored purchase data</h2>
        <p>This removes imported orders from the local database. It does not remove the sample illustrations or a stored Keepa key.</p>
        <label htmlFor="delete-confirm">Type DELETE to enable removal of stored purchase data</label>
        <input
          id="delete-confirm"
          data-testid="delete-confirm"
          value={phrase}
          onChange={(event) => setPhrase(event.target.value)}
        />
        <button type="button" data-testid="delete-purchases" disabled={phrase !== "DELETE" || busy} onClick={onDelete}>
          Delete stored purchase data
        </button>
      </section>
    </section>
  );
}
