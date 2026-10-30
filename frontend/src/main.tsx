import React, { useState, useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import { api, init, download } from "./api";
import { Product, Queue, currencies } from "./types";
import "./style.css";
const fresh = (): Product => ({
  id: crypto.randomUUID(),
  name: "",
  barcode: "",
  price: "",
  symbol: "Rs.",
  currency: "PKR",
  quantity: 1,
  source: "manual",
  reference: "",
});
function Currency({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <>
      <input
        aria-label="Currency symbol"
        list="currencies"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      <datalist id="currencies">
        {currencies.map(([c, n, s]) => (
          <option key={c + s} value={s}>
            {c} · {n}
          </option>
        ))}
      </datalist>
    </>
  );
}
function App() {
  const [q, setQ] = useState<Queue>();
  const [tab, setTab] = useState("Manual entry");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState<any>();
  const [draft, setDraft] = useState(fresh());
  const [editing, setEditing] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [symbol, setSymbol] = useState("Rs.");
  const [printer, setPrinter] = useState("");
  const [printers, setPrinters] = useState<any[]>([]);
  const [mode, setMode] = useState("driver");
  const [productionReady, setProductionReady] = useState(false);
  const [jobs, setJobs] = useState<any[]>([]);
  const [page, setPage] = useState(0);
  const [images, setImages] = useState<string[]>([]);
  const [book, setBook] = useState<any>();
  const [sheet, setSheet] = useState("");
  const [header, setHeader] = useState(0);
  const [mapping, setMapping] = useState<Record<string, number | null>>({});
  const [qmode, setQmode] = useState("fixed");
  const [fixed, setFixed] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [numeric, setNumeric] = useState(false);
  const [decimal, setDecimal] = useState(".");
  const [converted, setConverted] = useState<any>();
  const [odoo, setOdoo] = useState({ url: "", database: "", key: "" });
  const [search, setSearch] = useState("");
  const [products, setProducts] = useState<any[]>([]);
  const [odooQty, setOdooQty] = useState("");
  const [ocurrencies, setOcurrencies] = useState<any[]>([]);
  const [pricelists, setPricelists] = useState<any[]>([]);
  const [pricing, setPricing] = useState("sales");
  const [checks, setChecks] = useState<Record<string, boolean>>({});
  const jobKey = useRef(crypto.randomUUID());
  const saves = useRef(Promise.resolve());
  const [saveState, setSaveState] = useState("Saved locally");
  const act = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    act(async () => {
      await init();
      setQ(await api("queue"));
      const p = await api("printers");
      setPrinters(p.printers);
      setPrinter(p.selected);
      setJobs(await api("jobs"));
    });
  }, []);
  useEffect(() => {
    if (!q) return;
    let active = true;
    setSaveState("Saving queue…");
    jobKey.current = crypto.randomUUID();
    setChecks({});
    saves.current = saves.current
      .catch(() => {})
      .then(async () => {
        try {
          await api("queue", "PUT", q);
          if (active) setSaveState("Saved locally");
        } catch (e) {
          if (active) {
            setSaveState("Queue not saved");
            setError(String(e));
          }
        }
      });
    const t = setTimeout(() => {
      api("validate", "POST", q)
        .then((r) => {
          if (active) setReport(r);
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    }, 250);
    return () => {
      active = false;
      clearTimeout(t);
    };
  }, [q]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (saveState !== "Saved locally") {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [saveState]);
  useEffect(() => {
    if (!q) return;
    let active = true;
    setProductionReady(false);
    api("readiness", "POST", { geometry: q.geometry, printer, mode })
      .then((r) => {
        if (active) setProductionReady(r.production_ready);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [q?.geometry, printer, mode]);
  useEffect(() => {
    if (tab !== "Print preview" || !q) return;
    let disposed = false;
    let urls: string[] = [];
    act(async () => {
      const count = Math.ceil(
        q.products.reduce((n, p) => n + p.quantity, 0) / 3,
      );
      for (let i = page * 8; i < Math.min(count, page * 8 + 8); i++) {
        const b = await api("preview/" + i, "POST", q);
        urls.push(URL.createObjectURL(b));
      }
      if (!disposed) setImages(urls);
    });
    return () => {
      disposed = true;
      urls.forEach(URL.revokeObjectURL);
    };
  }, [q, tab, page]);
  if (!q)
    return (
      <main>
        <h1>Barcode Studio</h1>
        <p>{error || "Opening local workspace…"}</p>
      </main>
    );
  const changeProducts = (p: Product[]) => setQ({ ...q, products: p });
  const append = async (p: Product[]) => {
    const next = { ...q, products: [...q.products, ...p] };
    await api("validate", "POST", next);
    setQ(next);
    setNotice(`${p.length} products added to queue`);
  };
  const chooseSheet = (s: string, b = book) => {
    setSheet(s);
    setHeader(b.proposals[s].header);
    setMapping(b.proposals[s].mapping);
    setConfirmed(false);
    setConverted(undefined);
  };
  const labels = q.products.reduce((n, p) => n + p.quantity, 0);
  const totalRows = Math.ceil(labels / 3);
  const addOdoo = async (p: any) => {
    if (!p.barcode)
      throw Error(
        "Product has no barcode. Use manual entry for a local override.",
      );
    const c = ocurrencies.find((c) => c.id === p.currency_id?.[0]);
    if (!c)
      throw Error(
        "Load currencies and review the product currency before adding.",
      );
    await append([
      {
        ...fresh(),
        name: p.display_name,
        barcode: p.barcode,
        price: String(p.lst_price),
        symbol: c.symbol,
        currency: c.name,
        quantity: Number(odooQty),
        source: "odoo",
        reference: String(p.id),
      },
    ]);
  };
  return (
    <div className="shell">
      <aside>
        <div className="brand">
          ▥{" "}
          <span>
            Barcode Studio<small>TSC TE200 · Retail labels</small>
          </span>
        </div>
        <nav>
          {[
            "Manual entry",
            "CSV / Excel import",
            "Odoo products",
            "Print queue",
            "Print preview",
            "Printer settings",
          ].map((t, i) => (
            <button
              key={t}
              className={tab === t ? "active" : ""}
              onClick={() => setTab(t)}
            >
              <span>0{i + 1}</span>
              {t}
            </button>
          ))}
        </nav>
        <div className="offline">
          ● Local workspace<small>Manual entry and imports work offline</small>
        </div>
      </aside>
      <main>
        <header>
          <div>
            <p className="eyebrow">YOUR LABEL WORKSPACE</p>
            <h1>{tab}</h1>
          </div>
          <button onClick={() => setTab("Print preview")}>
            Preview labels →
          </button>
        </header>
        <div className="stats">
          <div>
            <b>{q.products.length}</b>
            <span>Products in queue</span>
          </div>
          <div>
            <b>{labels}</b>
            <span>Exact label count</span>
          </div>
          <div>
            <b>{totalRows}</b>
            <span>Physical rows · 3 columns</span>
          </div>
        </div>
        {error && (
          <div role="alert" className="error">
            {error}
            <button onClick={() => setError("")}>Dismiss</button>
          </div>
        )}
        {notice && (
          <div role="status" className="success">
            {notice}
          </div>
        )}
        <div className="warning">
          <b>
            {productionReady
              ? "Production Ready — operator calibration recorded"
              : report?.state || "Checking readiness"}
          </b>
          {report?.geometry_errors?.map((s: string) => (
            <p key={s}>{s}</p>
          ))}
          <small>
            Digital preview does not prove physical alignment. Production
            requires confirmed dimensions and calibration.
          </small>
        </div>
        {report?.content_errors?.length > 0 && (
          <div className="error">
            {report.content_errors.map((e: any) => (
              <p key={e.id}>
                {q.products.find((p) => p.id === e.id)?.name}: {e.error}
              </p>
            ))}
          </div>
        )}
        {tab === "Manual entry" && (
          <section>
            <div className="section-head">
              <div>
                <h2>{editing ? "Edit queue product" : "Add a product"}</h2>
                <p>Keep every barcode character exactly as supplied.</p>
              </div>
              <span className="badge">OFFLINE READY</span>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                act(async () => {
                  const products = editing
                    ? q.products.map((p) => (p.id === draft.id ? draft : p))
                    : [...q.products, draft];
                  await api("validate", "POST", { ...q, products });
                  changeProducts(products);
                  setDraft(fresh());
                  setEditing(false);
                  setNotice("Product saved. Check preview for content fit.");
                });
              }}
            >
              <div className="fields">
                <label className="wide">
                  Product name
                  <input
                    required
                    maxLength={300}
                    value={draft.name}
                    onChange={(e) =>
                      setDraft({ ...draft, name: e.target.value })
                    }
                  />
                </label>
                <label>
                  Barcode
                  <input
                    required
                    value={draft.barcode}
                    onChange={(e) =>
                      setDraft({ ...draft, barcode: e.target.value })
                    }
                    placeholder="0001234567"
                  />
                </label>
                <label>
                  Numeric price
                  <input
                    required
                    inputMode="decimal"
                    value={draft.price}
                    onChange={(e) =>
                      setDraft({ ...draft, price: e.target.value })
                    }
                  />
                </label>
                <label>
                  Printed currency
                  <Currency
                    value={draft.symbol}
                    onChange={(symbol) => setDraft({ ...draft, symbol })}
                  />
                </label>
                <label>
                  Label quantity
                  <input
                    required
                    type="number"
                    min={1}
                    max={10000}
                    step={1}
                    value={draft.quantity}
                    onChange={(e) =>
                      setDraft({ ...draft, quantity: Number(e.target.value) })
                    }
                  />
                </label>
              </div>
              <p className="muted">
                Changing the symbol never converts the numeric amount. Check the
                selling currency before printing.
              </p>
              <div className="actions">
                <button className="primary" disabled={busy}>
                  Save to queue
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setDraft(fresh());
                    setEditing(false);
                  }}
                >
                  Clear entry
                </button>
              </div>
            </form>
          </section>
        )}
        {tab === "Print queue" && (
          <section>
            <h2>One queue, exact quantities</h2>
            <div className="actions">
              <button
                onClick={() =>
                  download(
                    new Blob([JSON.stringify(q, null, 2)], {
                      type: "application/json",
                    }),
                    "label-queue.json",
                  )
                }
              >
                Save queue file
              </button>
              <label className="file-button">
                Open queue
                <input
                  type="file"
                  accept=".json"
                  onChange={(e) =>
                    act(async () => {
                      const f = e.target.files?.[0];
                      if (!f) return;
                      if (f.size > 2000000)
                        throw Error("Queue file exceeds 2 MB");
                      const v = JSON.parse(await f.text());
                      await api("validate", "POST", v);
                      if (
                        confirm(
                          "Replace the current queue with this saved queue?",
                        )
                      )
                        setQ(v);
                    })
                  }
                />
              </label>
              <button
                onClick={() => {
                  if (confirm("Clear all queued products?")) changeProducts([]);
                }}
              >
                Clear queue
              </button>
            </div>
            <div className="actions">
              <Currency value={symbol} onChange={setSymbol} />
              <button
                onClick={() =>
                  changeProducts(
                    q.products.map((p) =>
                      selected.includes(p.id) ? { ...p, symbol } : p,
                    ),
                  )
                }
              >
                Apply symbol to selected
              </button>
              <button
                onClick={() => {
                  if (
                    confirm(
                      "Change every printed symbol without converting prices?",
                    )
                  )
                    changeProducts(q.products.map((p) => ({ ...p, symbol })));
                }}
              >
                Apply to all
              </button>
            </div>
            <p className="muted">Symbol changes do not convert prices.</p>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Select</th>
                    <th>Product / Barcode</th>
                    <th>Price</th>
                    <th>Symbol</th>
                    <th>Labels</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {q.products.map((p, i) => (
                    <tr key={p.id}>
                      <td>
                        <input
                          aria-label={"Select " + p.name}
                          type="checkbox"
                          checked={selected.includes(p.id)}
                          onChange={(e) =>
                            setSelected(
                              e.target.checked
                                ? [...selected, p.id]
                                : selected.filter((id) => id !== p.id),
                            )
                          }
                        />
                      </td>
                      <td>
                        <b>{p.name}</b>
                        <small>
                          {p.barcode} · {p.source}
                        </small>
                      </td>
                      <td>{p.price}</td>
                      <td>{p.symbol}</td>
                      <td>
                        <input
                          aria-label={"Quantity for " + p.name}
                          type="number"
                          min={1}
                          max={10000}
                          value={p.quantity}
                          onChange={(e) => {
                            const n = Number(e.target.value);
                            if (Number.isInteger(n) && n > 0 && n <= 10000)
                              changeProducts(
                                q.products.map((x) =>
                                  x.id === p.id ? { ...x, quantity: n } : x,
                                ),
                              );
                          }}
                        />
                      </td>
                      <td>
                        <div className="actions">
                          <button
                            onClick={() => {
                              setDraft(p);
                              setEditing(true);
                              setTab("Manual entry");
                            }}
                          >
                            Edit
                          </button>
                          <button
                            onClick={() =>
                              act(() =>
                                append([{ ...p, id: crypto.randomUUID() }]),
                              )
                            }
                          >
                            Copy
                          </button>
                          <button
                            disabled={!i}
                            onClick={() => {
                              const ps = [...q.products];
                              [ps[i - 1], ps[i]] = [ps[i], ps[i - 1]];
                              changeProducts(ps);
                            }}
                          >
                            ↑
                          </button>
                          <button
                            onClick={() =>
                              changeProducts(
                                q.products.filter((x) => x.id !== p.id),
                              )
                            }
                          >
                            Remove
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!q.products.length && (
              <p className="empty">
                Your queue is empty. Add a product or import a file to begin.
              </p>
            )}
          </section>
        )}
        {tab === "CSV / Excel import" && (
          <section>
            <h2>Import products locally</h2>
            <p>
              Your spreadsheet stays on this computer. Choose how inventory
              quantities should be interpreted.
            </p>
            <div className="actions">
              <input
                aria-label="Product spreadsheet"
                type="file"
                accept=".csv,.xlsx,.xls"
                onChange={(e) =>
                  act(async () => {
                    const f = e.target.files?.[0];
                    if (!f) return;
                    const body = new FormData();
                    body.append("file", f);
                    const b = await api("import/inspect", "POST", body);
                    setBook({ ...b, filename: f.name });
                    chooseSheet(Object.keys(b.sheets)[0], b);
                  })
                }
              />
              {["csv", "xlsx"].map((kind) => (
                <button
                  key={kind}
                  onClick={() =>
                    act(async () =>
                      download(
                        await api("templates/" + kind),
                        "products." + kind,
                      ),
                    )
                  }
                >
                  Sample {kind.toUpperCase()}
                </button>
              ))}
            </div>
            {book && (
              <>
                <h3>{book.filename}</h3>
                <label>
                  Worksheet
                  <select
                    value={sheet}
                    onChange={(e) => chooseSheet(e.target.value)}
                  >
                    {Object.keys(book.sheets).map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Header row (1-based)
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={header + 1}
                    onChange={(e) => {
                      setHeader(Number(e.target.value) - 1);
                      setConfirmed(false);
                      setConverted(undefined);
                    }}
                  />
                </label>
                <p>
                  {book.sheets[sheet].length - header - 1} data rows. All
                  mappings require confirmation.
                </p>
                <div className="fields">
                  {["barcode", "name", "quantity", "price", "symbol"].map(
                    (field) => (
                      <label key={field}>
                        {field}
                        <select
                          value={mapping[field] ?? ""}
                          onChange={(e) => {
                            setMapping({
                              ...mapping,
                              [field]:
                                e.target.value === ""
                                  ? null
                                  : Number(e.target.value),
                            });
                            setConfirmed(false);
                            setConverted(undefined);
                          }}
                        >
                          <option value="">Not mapped</option>
                          {book.sheets[sheet][header]?.map(
                            (h: any, i: number) => (
                              <option key={i} value={i}>
                                {i + 1}: {String(h ?? "")}
                              </option>
                            ),
                          )}
                        </select>
                      </label>
                    ),
                  )}
                </div>
                <details>
                  <summary>Workbook warnings ({book.warnings.length})</summary>
                  {book.warnings.map((w: string, i: number) => (
                    <p key={i}>{w}</p>
                  ))}
                </details>
                <div className="fields">
                  <label>
                    Print quantity meaning
                    <select
                      value={qmode}
                      onChange={(e) => {
                        setQmode(e.target.value);
                        setConverted(undefined);
                      }}
                    >
                      <option value="fixed">
                        Ignore stock; apply explicit label quantity
                      </option>
                      <option value="column">
                        Mapped column is label-print quantity
                      </option>
                    </select>
                  </label>
                  {qmode === "fixed" && (
                    <label>
                      Labels per imported product
                      <input
                        type="number"
                        min={1}
                        value={fixed}
                        onChange={(e) => {
                          setFixed(e.target.value);
                          setConverted(undefined);
                        }}
                      />
                    </label>
                  )}
                  <label>
                    Decimal convention
                    <select
                      value={decimal}
                      onChange={(e) => {
                        setDecimal(e.target.value);
                        setConverted(undefined);
                      }}
                    >
                      <option value=".">1,234.56</option>
                      <option value=",">1.234,56</option>
                    </select>
                  </label>
                </div>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={confirmed}
                    onChange={(e) => {
                      setConfirmed(e.target.checked);
                      setConverted(undefined);
                    }}
                  />
                  I confirm the mappings, barcode meaning, and print quantity
                  choice.
                </label>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={numeric}
                    onChange={(e) => {
                      setNumeric(e.target.checked);
                      setConverted(undefined);
                    }}
                  />
                  I reviewed numeric barcode cells for lost leading zeros.
                </label>
                <button
                  disabled={busy || !confirmed}
                  onClick={() =>
                    act(async () =>
                      setConverted(
                        await api("import/convert", "POST", {
                          table: book.sheets[sheet],
                          header,
                          mapping,
                          quantity_mode: qmode,
                          default_quantity: fixed ? Number(fixed) : null,
                          confirmed,
                          numeric_confirmed: numeric,
                          decimal_separator: decimal,
                        }),
                      ),
                    )
                  }
                >
                  Validate and preview import
                </button>
                {converted && (
                  <>
                    <h3>
                      {converted.products.length} valid ·{" "}
                      {converted.errors.length} invalid
                    </h3>
                    {converted.errors.map((r: any) => (
                      <p className="error" key={r.row}>
                        Row {r.row}: {r.error}
                      </p>
                    ))}
                    <p>
                      Correct errors in the source file or mapping, then
                      validate again. Valid products can be edited in the queue
                      before printing.
                    </p>
                    <div className="table-wrap">
                      <table>
                        <tbody>
                          {converted.products.map((p: Product) => (
                            <tr key={p.id}>
                              <td>{p.name}</td>
                              <td>{p.barcode}</td>
                              <td>
                                {p.symbol} {p.price}
                              </td>
                              <td>{p.quantity} labels</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="actions">
                      <button
                        disabled={!converted.products.length || busy}
                        onClick={() => act(() => append(converted.products))}
                      >
                        Append valid products
                      </button>
                      <button
                        disabled={!converted.products.length || busy}
                        onClick={() =>
                          act(async () => {
                            await api("validate", "POST", {
                              ...q,
                              products: converted.products,
                            });
                            if (
                              confirm(
                                "Replace the current queue with valid import rows?",
                              )
                            )
                              changeProducts(converted.products);
                          })
                        }
                      >
                        Replace queue…
                      </button>
                    </div>
                  </>
                )}
              </>
            )}
          </section>
        )}
        {tab === "Odoo products" && (
          <section>
            <h2>Odoo Enterprise · read-only connection</h2>
            <p>
              API keys stay in the trusted local backend and Windows Credential
              Manager. A live connection has not been verified.
            </p>
            <div className="fields">
              {(["url", "database", "key"] as const).map((k) => (
                <label key={k}>
                  {k === "key" ? "API key" : k}
                  <input
                    type={k === "key" ? "password" : "text"}
                    autoComplete="off"
                    value={odoo[k]}
                    onChange={(e) => setOdoo({ ...odoo, [k]: e.target.value })}
                  />
                </label>
              ))}
            </div>
            <div className="actions">
              <button
                onClick={() =>
                  act(async () => {
                    await api("odoo/config", "POST", odoo);
                    setOdoo({ ...odoo, key: "" });
                    setNotice(
                      "Credentials saved to Windows Credential Manager",
                    );
                  })
                }
              >
                Save connection securely
              </button>
              <button
                onClick={() =>
                  act(async () => {
                    await api("odoo/config", "DELETE");
                    setProducts([]);
                    setNotice("Stored Windows credentials removed");
                  })
                }
              >
                Disconnect / remove credentials
              </button>
            </div>
            <div className="fields">
              <label>
                Search name, barcode or SKU
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </label>
              <label>
                Explicit label quantity
                <input
                  type="number"
                  min={1}
                  value={odooQty}
                  onChange={(e) => setOdooQty(e.target.value)}
                />
              </label>
              <label>
                Pricing source
                <select
                  value={pricing}
                  onChange={(e) => setPricing(e.target.value)}
                >
                  <option value="sales">Sales Price</option>
                  <option value="pricelist">
                    Selected Pricelist — verification required
                  </option>
                </select>
              </label>
            </div>
            <button
              disabled={busy}
              onClick={() =>
                act(async () => {
                  const currencies = await api("odoo/currencies");
                  setOcurrencies(currencies);
                  setProducts(
                    await api(
                      "odoo/products?search=" + encodeURIComponent(search),
                    ),
                  );
                  setNotice(
                    "Read-only request succeeded. Review products and currency.",
                  );
                  if (pricing === "pricelist")
                    setPricelists(await api("odoo/pricelists"));
                })
              }
            >
              Test connection / search
            </button>
            {pricing === "pricelist" && (
              <div className="warning">
                <label>
                  Available pricelist
                  <select>
                    <option>Choose for review</option>
                    {pricelists.map((p) => (
                      <option key={p.id}>{p.name}</option>
                    ))}
                  </select>
                </label>
                <p>
                  Price calculation unavailable until a public, authorized
                  operation and quantity/date/partner context are verified
                  against your database /doc. Sales prices will not be presented
                  as pricelist prices.
                </p>
              </div>
            )}
            <table>
              <tbody>
                {products.map((p) => (
                  <tr key={p.id}>
                    <td>
                      {p.display_name}
                      <small>
                        {p.barcode || "No barcode"} · {p.default_code}
                      </small>
                    </td>
                    <td>{p.lst_price} (Sales Price)</td>
                    <td>
                      <button
                        disabled={pricing !== "sales" || !odooQty || busy}
                        onClick={() => act(() => addOdoo(p))}
                      >
                        Add to queue
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <button
              disabled={!products.length || busy}
              onClick={() =>
                act(async () =>
                  setProducts([
                    ...products,
                    ...(await api(
                      "odoo/products?search=" +
                        encodeURIComponent(search) +
                        "&offset=" +
                        products.length,
                    )),
                  ]),
                )
              }
            >
              Load more
            </button>
          </section>
        )}
        {tab === "Print preview" && (
          <section>
            <h2>Physical row preview</h2>
            <p>
              Black and white rendering is shared with printer output. Empty
              positions remain blank. Invalid geometry is shown at its full
              stated extent.
            </p>
            <div className="actions">
              <button disabled={!page} onClick={() => setPage(page - 1)}>
                Previous 8 rows
              </button>
              <span>
                Rows {totalRows ? page * 8 + 1 : 0}–
                {Math.min(totalRows, page * 8 + 8)} of {totalRows}
              </span>
              <button
                disabled={(page + 1) * 8 >= totalRows}
                onClick={() => setPage(page + 1)}
              >
                Next 8 rows
              </button>
            </div>
            <div className="preview">
              {images.map((url, i) => (
                <figure key={url}>
                  <figcaption>
                    Row {page * 8 + i + 1} · LEFT → MIDDLE → RIGHT
                  </figcaption>
                  <img
                    src={url}
                    alt={"Rendered physical row " + (page * 8 + i + 1)}
                  />
                </figure>
              ))}
              {!labels && <p className="empty">No labels to preview</p>}
            </div>
            <button onClick={() => setTab("Printer settings")}>
              Review printer and print →
            </button>
          </section>
        )}
        {tab === "Printer settings" && (
          <>
            <section>
              <h2>Printer &amp; physical media</h2>
              <p>
                Original measurements are preserved as defaults. Every geometry,
                printer or method change requires new calibration.
              </p>
              <div className="fields">
                <label>
                  Windows printer
                  <select
                    value={printer}
                    onChange={(e) => {
                      setPrinter(e.target.value);
                      jobKey.current = crypto.randomUUID();
                      setChecks({});
                    }}
                  >
                    <option value="">Choose TSC TE200</option>
                    {printers.map((p) => (
                      <option key={p.name}>{p.name}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Print method
                  <select
                    value={mode}
                    onChange={(e) => {
                      setMode(e.target.value);
                      jobKey.current = crypto.randomUUID();
                      setChecks({});
                    }}
                  >
                    <option value="driver">Windows driver (GDI)</option>
                    <option value="raw">Direct TSPL bitmap</option>
                  </select>
                </label>
              </div>
              <label>
                Barcode bar width
                <select
                  aria-label="Barcode bar width"
                  value={q.geometry.barcode_module ?? 2}
                  onChange={(e) =>
                    setQ({
                      ...q,
                      geometry: {
                        ...q.geometry,
                        barcode_module: Number(e.target.value),
                      },
                    })
                  }
                >
                  <option value={2}>Standard bars · 2 printer dots</option>
                  <option value={1}>
                    Narrow bars · 1 printer dot · scan test required
                  </option>
                </select>
              </label>
              {q.geometry.barcode_module === 1 && (
                <p className="warning">
                  Narrow bars fit longer barcodes on small stickers. At 203 DPI,
                  scanning may be less reliable. Print the new calibration
                  sample and scan every label with your usual scanner before
                  recording calibration. Test your longest real product barcode
                  too.
                </p>
              )}
              <button
                onClick={() =>
                  act(async () => {
                    const p = await api("printers");
                    setPrinters(p.printers);
                    setNotice(
                      p.windows
                        ? "Windows printers refreshed"
                        : "Printer discovery requires Windows; offline preparation remains available",
                    );
                  })
                }
              >
                Refresh printers
              </button>
              <details>
                <summary>Advanced media geometry · millimeters</summary>
                <div className="fields">
                  {Object.entries(q.geometry)
                    .filter(([k]) => k !== "barcode_module")
                    .map(([k, v]) => (
                      <label key={k}>
                        {
                          (
                            {
                              backing: "Backing width",
                              width: "Label width",
                              height: "Label height",
                              gap_x: "Horizontal gap",
                              gap_y: "Vertical gap",
                              left: "Left margin",
                              right: "Right margin",
                              top: "Top print offset",
                              offset_x: "Horizontal print offset",
                              origin: "Printable origin",
                              safe: "Internal safe margin",
                              printable: "Printable width",
                              dpi: "Resolution (DPI)",
                              columns: "Columns",
                              density: "Darkness (0–15)",
                              speed: "Speed (in/s)",
                            } as Record<string, string>
                          )[k]
                        }
                        <input
                          type="number"
                          step="0.1"
                          disabled={k === "dpi" || k === "columns"}
                          value={v}
                          onChange={(e) =>
                            setQ({
                              ...q,
                              geometry: {
                                ...q.geometry,
                                [k]: Number(e.target.value),
                              },
                            })
                          }
                        />
                      </label>
                    ))}
                </div>
                <p>
                  Row pitch: {q.geometry.height + q.geometry.gap_y} mm · Gap
                  media only. No automatic correction or scaling.
                </p>
              </details>
            </section>
            <section>
              <h2>Physical verification checklist</h2>
              <button
                disabled={
                  busy || !printer || report?.geometry_errors?.length > 0
                }
                onClick={() =>
                  act(async () => {
                    if (
                      !confirm(
                        "Physically print 7 calibration labels across 3 rows? This consumes media. Geometry must be measured and safe.",
                      )
                    )
                      return;
                    const r = await api("calibration-test", "POST", {
                      id: crypto.randomUUID(),
                      geometry: q.geometry,
                      printer,
                      mode,
                      approved: true,
                      command_reference_verified:
                        checks.command_reference_verified || false,
                    });
                    setNotice([r.status, r.detail].filter(Boolean).join(": "));
                    setJobs(await api("jobs"));
                  })
                }
              >
                Print approved 7-label calibration sample…
              </button>
              <p>
                Use the procedures in docs/PRINTER.md with a technician. These
                confirmations record operator evidence; software cannot verify
                the physical output.
              </p>
              {[
                ["measured", "I measured and confirmed every media dimension"],
                ["alignment", "All three columns align within safe margins"],
                ["scanned", "Every barcode scans to its exact value"],
                ["multirow", "Consecutive rows show no vertical drift"],
                ["boundary", "Separate jobs each start LEFT on a fresh row"],
                ["counts", "Physical counts match requested quantities"],
                [
                  "command_reference_verified",
                  "For direct mode: TSPL commands verified against the official TE200 manual",
                ],
              ].map(([k, t]) => (
                <label className="check" key={k}>
                  <input
                    type="checkbox"
                    checked={checks[k] || false}
                    onChange={(e) =>
                      setChecks({ ...checks, [k]: e.target.checked })
                    }
                  />
                  {t}
                </label>
              ))}
              <button
                disabled={
                  busy || !printer || report?.geometry_errors?.length > 0
                }
                onClick={() =>
                  act(async () => {
                    const c = await api("calibration", "POST", {
                      geometry: q.geometry,
                      printer,
                      mode,
                      ...checks,
                    });
                    setNotice(c.state);
                    setProductionReady(true);
                  })
                }
              >
                Record completed physical calibration
              </button>
              <p className="warning">
                Production printing is blocked until calibration is recorded.
                Driver setup, alignment tests, scanner checks and exact feeding
                must be performed on Windows.
              </p>
              <button
                className="primary"
                disabled={
                  busy ||
                  !printer ||
                  !labels ||
                  !productionReady ||
                  report?.geometry_errors?.length > 0 ||
                  report?.content_errors?.length > 0
                }
                onClick={() =>
                  act(async () => {
                    if (
                      !confirm(
                        `Submit exactly ${labels} labels in ${totalRows} rows to ${printer}? Check that the previous job was not already printed.`,
                      )
                    )
                      return;
                    const r = await api("print", "POST", {
                      id: jobKey.current,
                      queue: q,
                      printer,
                      mode,
                    });
                    setNotice([r.status, r.detail].filter(Boolean).join(": "));
                    setJobs(await api("jobs"));
                  })
                }
              >
                Print {labels} labels
              </button>
            </section>
            <section>
              <h2>Recent print submissions</h2>
              <button
                onClick={() => {
                  if (
                    confirm(
                      "Create a NEW independent job? First inspect previous output to avoid duplicates.",
                    )
                  ) {
                    jobKey.current = crypto.randomUUID();
                    setNotice(
                      "New independent job ready. It will start LEFT on a fresh row.",
                    );
                  }
                }}
              >
                Prepare new independent job…
              </button>
              <button
                onClick={() => act(async () => setJobs(await api("jobs")))}
              >
                Refresh history
              </button>
              {jobs.map((j) => (
                <div className="job" key={j.id}>
                  <b>{j.status}</b>
                  <small>
                    {j.id} · {j.printer}
                  </small>
                  <p>{j.detail}</p>
                  {j.spool_id && (
                    <button
                      onClick={() =>
                        act(async () => {
                          const r = await api(
                            "jobs/" + j.id + "/cancel",
                            "POST",
                          );
                          setNotice(
                            [r.status, r.detail].filter(Boolean).join(": "),
                          );
                          setJobs(await api("jobs"));
                        })
                      }
                    >
                      Request cancellation
                    </button>
                  )}
                </div>
              ))}
            </section>
          </>
        )}
        <footer>
          <span role="status" aria-label="Queue save status">
            {saveState}
          </span>{" "}
          · Barcode Studio · Offline preparation · Physical output requires
          verified calibration
        </footer>
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
