# Cashback Tracker (Streamlit, cloud-hosted)

A Streamlit port of the original v0/Next.js Cashback Tracker for UOB ONE & HLB WISE
credit cards, backed by a cloud Postgres database so it can run 24/7 online and
be shared between JRen and Sarah.

## How storage works now

Transactions are no longer stored in a local file. `db.py` uses Streamlit's
built-in SQL connection, which reads a database URL from
`.streamlit/secrets.toml` (local) or the app's **Secrets** panel on Streamlit
Community Cloud (deployed). Point that URL at a free Supabase Postgres
database and the same code works locally and in the cloud — no code changes
between the two.

---

## Part 1 — Create a free cloud database (Supabase)

1. Go to **supabase.com** and sign up (free tier is fine).
2. Click **New project**. Pick any name/region, set a database password
   (save it somewhere — you'll need it in a moment), and wait ~2 minutes for
   it to provision.
3. In your new project, go to **Project Settings → Database → Connection string**.
4. Choose the **Session pooler** tab (not "Direct connection") and copy the
   URI. It looks like:
   ```
   postgresql://postgres.xxxxxxxxxxxx:[YOUR-PASSWORD]@aws-0-xxxxx.pooler.supabase.com:6543/postgres
   ```
5. Replace `[YOUR-PASSWORD]` in that string with the database password you
   set in step 2.

## Part 2 — Run it locally against the cloud database

1. Copy the example secrets file and edit it:
   ```
   copy .streamlit\secrets.toml.example .streamlit\secrets.toml
   ```
   (Mac/Linux: `cp .streamlit/secrets.toml.example .streamlit/secrets.toml`)
2. Open `.streamlit/secrets.toml` and paste your real Supabase connection
   string in as the `url` value.
3. Install dependencies and run as before:
   ```
   pip install -r requirements.txt
   streamlit run app.py
   ```
4. Add a test transaction. If it shows up in Supabase's **Table Editor**
   (under the `transactions` table), the cloud connection works.

`.streamlit/secrets.toml` is in `.gitignore` — it holds your real password,
so it should never be committed to GitHub.

## Part 3 — Deploy it online 24/7 (Streamlit Community Cloud)

1. Push this folder to a **new GitHub repository** (public or private —
   Streamlit Community Cloud's free tier allows one private app).
2. Go to **share.streamlit.io**, sign in with GitHub, and click **New app**.
3. Pick your repository, branch, and set the main file path to `app.py`.
4. Before/after deploying, open the app's **Settings → Secrets** and paste
   the same content as your local `secrets.toml`:
   ```toml
   [connections.db]
   url = "postgresql://postgres.xxxxxxxxxxxx:[YOUR-PASSWORD]@aws-0-xxxxx.pooler.supabase.com:6543/postgres"
   ```
5. Deploy. You'll get a permanent URL like `yourapp.streamlit.app` that both
   of you can bookmark on your phones.

**About uptime:** Streamlit Community Cloud's free tier puts an app to sleep
after 12 hours with no visits. The next visitor sees a "waking up" page for a
few seconds, then the app runs normally — no data is lost, since everything
lives in Supabase, not on the app server. If you ever want it to never sleep,
that requires a paid host (e.g. Render, Railway, Fly.io) instead of the free
Community Cloud tier.

---

## Files

- `app.py` — Streamlit UI: tabs for each card + a "By User" view, add-transaction dialog, export/import
- `cards.py` — card configs and cashback calculation logic
- `db.py` — cloud SQL persistence (via `st.connection`)
- `.streamlit/secrets.toml.example` — template for your database credentials

## About the cashback numbers

`min_spend` and category `cap` values for both cards were confirmed from
screenshots of the original app. The cashback `rate` percentages are still
estimates — open `cards.py` and adjust `CARD_CONFIG` if your actual rates
differ.

## Import/export

- **Export** downloads all transactions as JSON (handy as a manual backup on
  top of Supabase).
- **Import** expects a JSON array of transaction objects (same shape as the
  export) and replaces all current data.
