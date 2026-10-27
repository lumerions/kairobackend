<h1 align="center">Kairo Backend</h1>

<p align="center">
  The FastAPI backend for Kairo, a Roblox revival: accounts, 2FA, memberships, inventory, trades, messages, forums, and groups.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Roblox-000000?style=for-the-badge&logo=roblox&logoColor=white" alt="Roblox">
  <img src="https://img.shields.io/badge/status-inactive-lightgrey?style=for-the-badge" alt="Status: inactive">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Dragonfly-Redis%20compatible-DC382D?logo=redis&logoColor=white" alt="Dragonfly">
  <img src="https://img.shields.io/badge/Pydantic-E92063?logo=pydantic&logoColor=white" alt="Pydantic">
  <img src="https://img.shields.io/badge/Resend-000000?logo=resend&logoColor=white" alt="Resend">
  <img src="https://img.shields.io/badge/Argon2-6B46C1" alt="Argon2">
  <img src="https://img.shields.io/badge/maintained-no-red" alt="Not maintained">
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#tech-stack">Tech Stack</a> •
  <a href="#installation">Installation</a> •
  <a href="#configuration">Configuration</a> •
  <a href="#project-structure">Structure</a>
</p>

> [!NOTE]
> This project is **no longer actively maintained**.

---

## Features

- **Authentication**: register/login with Argon2 password hashing and signed, versioned session cookies
- **Session management**: per-device sessions with IP-based location and user agent, plus "log out of all sessions"
- **Two-factor authentication**: TOTP via authenticator apps (`pyotp`)
- **Email verification**: Resend-powered codes that expire after 15 minutes, with per-user send limits
- **CSRF protection**: token middleware on all state-changing routes
- **Memberships**: Free, Classic, Turbo, and Outrageous tiers with a periodic Robux stipend
- **Economy**: Robux balances, inventory, and paid actions such as username changes
- **Social**: messages and replies, friend requests, connections (friends, followers, followings), forums, threads, and groups
- **Privacy settings**: control who can message, invite, follow, view your inventory, or trade with you
- **Caching**: auth, settings, and tier data cached with short TTLs
- **Rate limiting**: per-user limits with SlowAPI
- **Auto docs**: Swagger UI at `/docs`

## Tech Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI, Uvicorn, Pydantic |
| Database | PostgreSQL (`asyncpg` connection pool) |
| Cache | Dragonfly / Redis |
| Auth | Argon2, PyOTP, signed cookie serializer |
| Email | Resend |
| Rate limiting | SlowAPI |

## Installation

```bash
git clone https://github.com/lumerions/kairobackend.git
cd kairobackend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Run the dev server:

```bash
uvicorn main:app --reload
```

Then open <http://localhost:8000/docs>.

## Configuration

Settings are loaded through `config/Config.py`. Set these environment variables before starting the app (verify the exact names there):

| Variable | Description |
|---|---|
| `POSTGRES_DATABASE_URL` | PostgreSQL connection string |
| `DRAGONFLY_URL` | Dragonfly/Redis connection string |
| `RESEND_API_KEY` | Resend API key for verification emails |
| `SECRET_KEY` | Secret used to sign session cookies and CSRF tokens |

You'll also need to:

- Replace the sender addresses in `sendEmail(...)` with a domain verified in Resend
- Replace the hardcoded default avatar URL used for messages
- Provide an IP geolocation source for `getIPData`

## Project Structure

```
kairobackend/
├── main.py          # app setup, auth, settings, membership, and 2FA routes
├── config/          # Config class and environment loading
├── lib/             # schemas, DB/cache connections, serializer, emails, helpers
├── middleware/      # session validation and CSRF middleware
├── routes/          # forums, messages, threads, groups routers
├── services/        # business logic
└── requirements.txt
```
