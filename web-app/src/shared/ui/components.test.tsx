import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { Badge } from "./badge";
import { Button } from "./button";
import { Card } from "./card";
import { EmptyState } from "./empty-state";
import { PaginationControls } from "./pagination-controls";
import { ProgressBar } from "./progress-bar";
import { StatusBadge } from "./status-badge";

test("Badge Button and Card render expected classes", () => {
  const badge = renderToStaticMarkup(<Badge className="custom-badge">Ready</Badge>);
  const button = renderToStaticMarkup(<Button variant="secondary">Run</Button>);
  const card = renderToStaticMarkup(<Card className="custom-card">Metrics</Card>);

  assert.match(badge, /custom-badge/);
  assert.match(button, /border-\[color:var\(--color-border-strong\)\]/);
  assert.match(card, /custom-card/);
});

test("StatusBadge renders known and fallback states", () => {
  const known = renderToStaticMarkup(<StatusBadge value="SUCCESS" />);
  const fallback = renderToStaticMarkup(<StatusBadge value={null} />);

  assert.match(known, /SUCCESS/);
  assert.match(fallback, /UNKNOWN/);
});

test("ProgressBar bounds values and keeps custom className", () => {
  const markup = renderToStaticMarkup(<ProgressBar value={140} className="wide" />);

  assert.match(markup, /wide/);
  assert.match(markup, /width:100%/);
});

test("EmptyState renders title description and optional action", () => {
  const withoutAction = renderToStaticMarkup(
    <EmptyState title="No data" description="Upload files to continue." />,
  );
  const withAction = renderToStaticMarkup(
    <EmptyState
      title="No data"
      description="Upload files to continue."
      action={<Button>Upload</Button>}
    />,
  );

  assert.match(withoutAction, /No data/);
  assert.match(withoutAction, /Upload files to continue/);
  assert.doesNotMatch(withoutAction, /Upload<\/button>/);
  assert.match(withAction, /Upload<\/button>/);
});

test("PaginationControls hides single-page state and renders previous next links", () => {
  const hidden = renderToStaticMarkup(
    <PaginationControls
      page={{
        content: [],
        totalElements: 1,
        totalPages: 1,
        number: 0,
        size: 10,
        numberOfElements: 1,
        first: true,
        last: true,
        empty: false,
      }}
      pathname="/collections"
      searchParams={{}}
      pageParam="page"
    />,
  );
  const visible = renderToStaticMarkup(
    <PaginationControls
      page={{
        content: [],
        totalElements: 30,
        totalPages: 3,
        number: 1,
        size: 10,
        numberOfElements: 10,
        first: false,
        last: false,
        empty: false,
      }}
      pathname="/collections"
      searchParams={{ sort: "createdAt,desc" }}
      pageParam="page"
    />,
  );

  assert.equal(hidden, "");
  assert.match(visible, /Page 2 of 3/);
  assert.match(visible, /href="\/collections\?sort=createdAt%2Cdesc&amp;page=0"/);
  assert.match(visible, /href="\/collections\?sort=createdAt%2Cdesc&amp;page=2"/);
});

test("PaginationControls preserves array search params and disabled states", () => {
  const visible = renderToStaticMarkup(
    <PaginationControls
      page={{
        content: [],
        totalElements: 20,
        totalPages: 2,
        number: 0,
        size: 10,
        numberOfElements: 10,
        first: true,
        last: false,
        empty: false,
      }}
      pathname="/jobs"
      searchParams={{ sort: ["createdAt,desc", "status,asc"], filter: undefined }}
      pageParam="page"
    />,
  );

  assert.match(visible, /aria-disabled="true"/);
  assert.match(visible, /tabindex="-1"/);
  assert.match(visible, /href="\/jobs\?sort=createdAt%2Cdesc&amp;sort=status%2Casc&amp;page=0"/);
  assert.match(visible, /href="\/jobs\?sort=createdAt%2Cdesc&amp;sort=status%2Casc&amp;page=1"/);
});
