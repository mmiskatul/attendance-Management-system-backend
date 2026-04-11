"use client";

import { Fragment, ReactNode } from "react";

function humanizeKey(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (match) => match.toUpperCase());
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "--";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function isPrimitive(value: unknown): boolean {
  return value === null || ["string", "number", "boolean"].includes(typeof value);
}

function renderTable(rows: Record<string, unknown>[]): ReactNode {
  const headers = Array.from(
    rows.reduce((keys, row) => {
      Object.keys(row).forEach((key) => keys.add(key));
      return keys;
    }, new Set<string>()),
  );

  return (
    <div className="result-table-wrap">
      <table className="result-table">
        <thead>
          <tr>
            {headers.map((header) => (
              <th key={header}>{humanizeKey(header)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={`row-${rowIndex}`}>
              {headers.map((header) => (
                <td key={`${rowIndex}-${header}`}>{formatValue(row[header])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function renderBlock(title: string, value: unknown): ReactNode {
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return (
        <section className="result-block">
          <h3>{humanizeKey(title)}</h3>
          <div className="empty-state">No records returned.</div>
        </section>
      );
    }

    if (value.every((item) => item && typeof item === "object" && !Array.isArray(item))) {
      return (
        <section className="result-block">
          <h3>{humanizeKey(title)}</h3>
          {renderTable(value as Record<string, unknown>[])}
        </section>
      );
    }

    return (
      <section className="result-block">
        <h3>{humanizeKey(title)}</h3>
        <div className="result-list">
          {value.map((item, index) => (
            <div className="result-item" key={`${title}-${index}`}>
              <strong>Item {index + 1}</strong>
              <span>{formatValue(item)}</span>
            </div>
          ))}
        </div>
      </section>
    );
  }

  if (value && typeof value === "object") {
    return (
      <section className="result-block">
        <h3>{humanizeKey(title)}</h3>
        <div className="summary-grid">
          {Object.entries(value as Record<string, unknown>).map(([key, nestedValue]) => (
            <article className="summary-card" key={key}>
              <span className="label">{humanizeKey(key)}</span>
              <span className="value">{formatValue(nestedValue)}</span>
            </article>
          ))}
        </div>
      </section>
    );
  }

  return (
    <section className="result-block">
      <h3>{humanizeKey(title)}</h3>
      <div className="empty-state">{formatValue(value)}</div>
    </section>
  );
}

export interface ResultConsoleProps {
  status: string;
  payload: unknown;
}

export function ResultConsole({ status, payload }: ResultConsoleProps) {
  const summaryEntries =
    payload && typeof payload === "object" && !Array.isArray(payload)
      ? Object.entries(payload).filter(([, value]) => isPrimitive(value))
      : [];
  const detailEntries =
    payload && typeof payload === "object" && !Array.isArray(payload)
      ? Object.entries(payload).filter(([, value]) => !isPrimitive(value))
      : [];

  return (
    <section className="panel result-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Response Console</p>
          <h2>Latest API Result</h2>
        </div>
        <span className={`result-status${status.toLowerCase().includes("error") ? " error" : ""}`}>{status}</span>
      </div>

      <div className="result-render">
        {typeof payload === "string" ? (
          <div className="empty-state">{payload}</div>
        ) : payload && typeof payload === "object" ? (
          <Fragment>
            {summaryEntries.length > 0 ? (
              <div className="summary-grid">
                {summaryEntries.map(([key, value]) => (
                  <article className="summary-card" key={key}>
                    <span className="label">{humanizeKey(key)}</span>
                    <span className="value">{formatValue(value)}</span>
                  </article>
                ))}
              </div>
            ) : null}
            {detailEntries.map(([key, value]) => (
              <Fragment key={key}>{renderBlock(key, value)}</Fragment>
            ))}
            {summaryEntries.length === 0 && detailEntries.length === 0 ? (
              <div className="empty-state">{status}</div>
            ) : null}
          </Fragment>
        ) : (
          <div className="empty-state">{String(payload ?? status)}</div>
        )}
      </div>

      <details className="raw-details">
        <summary>Raw JSON</summary>
        <pre>{typeof payload === "string" ? payload : JSON.stringify(payload, null, 2)}</pre>
      </details>
    </section>
  );
}
