# Deploying MeatTrace

Four environments share one VPS. Each has its own folder under `/usr/apps/nyama_tamu/`, systemd
service, database and nginx server block. The server's address and SSH port are deliberately not
recorded in this public repository; keep them in your password manager.

| Environment | API | Admin dashboard | Backend folder | Service |
|---|---|---|---|---|
| production | `https://dev.shambabora.co.tz` | (not on this server) | `meattrace_backend` | `gunicorn_meattrace` |
| staging | `https://staging.<server-ip>.nip.io` | `https://admin-staging.<server-ip>.nip.io` | `meattrace_backend_staging` | `gunicorn_meattrace_staging` |
| dev | `https://dev.<server-ip>.nip.io` | `https://admin-dev.<server-ip>.nip.io` | `meattrace_backend_dev` | `gunicorn_meattrace_dev` |
| demo | `https://demo.<server-ip>.nip.io` | `https://admin-demo.<server-ip>.nip.io` | `meattrace_backend_demo` | `gunicorn_meattrace_demo` |

(`<server-ip>` is the VPS address. The nip.io hostnames are temporary until DNS for
`*.shambabora.co.tz` is added in Cloudflare.)

## Backend: `meattrace-deploy`

Installed on the server at `/usr/local/bin/meattrace-deploy` (source: `deploy/meattrace-deploy`).

```
meattrace-deploy <production|staging|dev|demo> [ref] [--dry-run] [--force] [--bundle FILE] [--yes-production]
```

* `ref` is a branch, tag or commit; the default is `main`.
* It refuses to run on a dirty working tree or with under 500 MB of free disk.
* It backs the SQLite database up first (last 5 kept in `<env folder>/backups/`).
* It runs `manage.py check` **before** restarting, so a broken commit never takes an environment down.
* After migrating and restarting it health-checks `/api/v2/health/`; if that fails it rolls the code back
  to the previous commit automatically. Migrations are not reverted; use the backup if you need to.
* Every run is logged to `/var/log/meattrace-deploy.log`; the deployed commit is in `<env folder>/DEPLOYED`.

Typical flow: `meattrace-deploy staging` -> test -> `meattrace-deploy production --yes-production`.
Try `--dry-run` first to see which commits and migrations would be applied.

Production currently has **uncommitted edits in its working tree** (it was deployed by hand), so
`meattrace-deploy production` will refuse until that tree is reconciled with git.

## Admin dashboard: `meattrace-deploy-admin`

From `meattrace_frontend/`: `./deploy-admin.sh <staging|dev|demo>` builds with the right API URL
(`.env.<env>`), uploads and publishes it. The server side reads the environment's API host from its
backend `.env` and refuses a build that points anywhere else. On the server, the previous version
stays in `dist.prev`; to roll back:
`cd /usr/apps/nyama_tamu/meattrace_frontend_<env> && mv dist dist.bad && mv dist.prev dist`.

## Mobile app

Android flavors give each environment its own application id, so all of them install side by side:

| Flavor | Application id | Launcher name |
|---|---|---|
| production (default) | `tz.co.shambabora.nyamatamu` | MeatTrace Pro |
| staging | `tz.co.shambabora.nyamatamu.staging` | MeatTrace STG |
| dev | `tz.co.shambabora.nyamatamu.dev` | MeatTrace DEV |
| demo | `tz.co.shambabora.nyamatamu.demo` | MeatTrace Demo |

```
flutter build apk --release --split-per-abi --flavor staging     # also: dev, demo
flutter build appbundle --release --flavor production            # Play Store (scripts/release_appbundle.*)
```

The API host follows the flavor automatically (`lib/utils/constants.dart`);
`--dart-define=API_HOST=https://...` overrides it for a one-off build.
