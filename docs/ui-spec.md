# UI spec (frozen)

Owner of index.css: P6. Everyone else uses ONLY the class names below. If a class you need is missing, send a query. Do not invent one and do not style with inline styles. Until P6 phase 1 merges, pages render unstyled. That is expected.

Look: light grey page, white panels, one indigo accent for primary buttons and links. Red, green and amber are used only for status. Money actions are labelled with words, never icon-only.

## Navigation (AppLayout, a layout route that renders Outlet)
Items in order: Invoices (/invoices), New invoice (/invoices/new), Aging Report (/aging), Customers (/customers), Products (/products), Log out. No Dashboard, PDF or e-invoice link anywhere. Those are planned, not built. Use NavLink; active link gets app-nav__link--active.
Classes: app-shell, app-nav, app-nav__brand, app-nav__link, app-nav__link--active, app-nav__spacer, app-nav__logout, app-main.

## Page structure
page-header, page-title, page-actions, panel, panel__title.
summary (a dl), summary__row, summary__row--total for subtotal, tax and total blocks.

## Tables
table-wrap (horizontal scroll), table, table__num (right-aligned numeric cell, tabular figures), table__link, table__empty (empty-state row).
Every th has scope="col".

## Money
Wrap every displayed amount: <span className="money">{formatMoney(value)}</span>. Money values are strings from the API. Never parseFloat or Number them.

## Long text
Use truncate (single-line ellipsis) together with a title attribute holding the full value. Customer names can be 60 characters.

## Status
<span className={"status status--" + invoice.status}>{invoice.status}</span>
Variants: status--draft (grey), status--sent (amber), status--overdue (red), status--paid (green), status--cancelled (grey, struck through). The word is always shown.

## Buttons
btn plus one of btn--primary, btn--secondary, btn--danger. Use the disabled attribute for unavailable actions. A Link may carry btn.

## Forms
field (wrapper), field--invalid, field__label (bound with htmlFor), input (also on select and textarea), field__error, form-actions.

## Messages
alert plus alert--error, alert--success or alert--info. Errors carry role="alert".

## Filters
filter-bar, filter-bar__btn, filter-bar__btn--active. The active button also sets aria-pressed="true".

## Aging report
bucket, bucket__title, bucket__subtotal. Titles in order: Not due, 1-30 days overdue, 31-60 days overdue, 61-90 days overdue, 90+ days overdue, mapped to not_due, days_0_30, days_31_60, days_61_90, days_90_plus.
