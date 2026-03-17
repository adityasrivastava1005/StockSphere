# StockSphere — Inventory Management System

Advanced Waterfall Model project

Ensuring a structured flow from requirements to deployment with clear phase validation.

It uses a modular full-stack architecture with a browser-based frontend and a Python backend, along with SQLite for data storage and RBAC for secure access control.

The system is lightweight, dependency-free, and designed for easy deployment and maintainability.

## Architecture

```
stocksphere/
├── frontend/              # Client (runs in browser)
│   ├── index.html         # App shell, all pages
│   ├── css/
│   │   ├── main.css       # Layout, variables, auth, topbar, sidebar
│   │   └── components.css # Buttons, forms, cards, tables, badges
│   └── js/
│       ├── ui.js          # API client, toast, modal, nav, shared helpers
│       ├── auth.js        # Login, register, session, RBAC
│       ├── dashboard.js   # Metrics, chart, category breakdown
│       ├── inventory.js   # Products, inward, outward, alerts
│       └── reports.js     # Valuation, ledger, audit, users
│
├── backend/               # Server (Python stdlib, no dependencies)
│   ├── server.py          # HTTP server, REST router, static serving
│   ├── db.py              # SQLite connection, schema init, seed data
│   ├── middleware/
│   │   └── auth.py        # Token generation, verification, RBAC
│   └── controllers/
│       ├── auth_controller.py
│       ├── product_controller.py
│       ├── transaction_controller.py
│       └── report_controller.py
│
└── database/
    └── stocksphere.db     # Auto-created on first run
```

## How to run

**Requires: Python 3.8+**

```bash
cd stocksphere/backend
python server.py
```

Then open: **http://localhost:8000**

## Demo accounts

| Username | Password    | Role    |
|----------|-------------|---------|
| admin    | admin123    | Admin   |
| rahul    | staff123    | Staff   |
| anjali   | manager123  | Manager |
| finance  | finance123  | Finance |

## REST API

| Method | Endpoint                    | Auth     | Description                |
|--------|-----------------------------|----------|----------------------------|
| POST   | /api/auth/login             | —        | Login                      |
| POST   | /api/auth/register          | —        | Register                   |
| POST   | /api/auth/logout            | Token    | Logout                     |
| GET    | /api/auth/me                | Token    | Current user               |
| GET    | /api/products               | Token    | List products              |
| POST   | /api/products               | Staff+   | Add product                |
| PUT    | /api/products/:id           | Staff+   | Update product             |
| DELETE | /api/products/:id           | Staff+   | Deactivate product         |
| GET    | /api/transactions           | Token    | List transactions          |
| POST   | /api/transactions/inward    | Staff+   | Record stock inward        |
| POST   | /api/transactions/outward   | Staff+   | Record stock outward       |
| GET    | /api/dashboard              | Token    | Dashboard data             |
| GET    | /api/reports/alerts         | Token    | Low stock alerts           |
| GET    | /api/reports/valuation      | Token    | Category valuation         |
| GET    | /api/reports/ledger         | Token    | Full stock ledger          |
| GET    | /api/reports/aging          | Token    | Inventory aging            |
| GET    | /api/audit                  | Token    | Audit trail                |
| GET    | /api/users                  | Admin    | List users                 |
| PUT    | /api/users/:id/toggle       | Admin    | Enable/disable user        |

## Role hierarchy

Admin > Manager > Finance > Staff

- **Admin**: full access including user management
- **Manager**: all inventory + reports, no user management
- **Finance**: read-only reports and dashboard
- **Staff**: inventory operations (products, inward, outward)

## Tech stack

- **Frontend**: Vanilla HTML/CSS/JS — IBM Plex Sans, modular JS files
- **Backend**: Python 3 stdlib (`http.server`, `sqlite3`, `json`, `hashlib`)
- **Database**: SQLite 3 via Python's built-in `sqlite3` module
- **Auth**: Session tokens stored in SQLite, 8-hour expiry
- **No external dependencies** — runs anywhere Python 3 is installed
