# Security Notes

## Secret handling

- Do not commit `.env` or any real credentials to Git.
- Use `.env.example` as the only committed environment template.
- Do not place secrets in frontend code, client-side config, or Postman collections.
- Do not hardcode secrets in Python files, Dockerfiles, or CI scripts.

## Sensitive values in this project

Treat these as secrets:

- `MONGODB_URI`
- `JWT_SECRET_KEY`
- `BOOTSTRAP_ADMIN_PASSWORD`
- any Redis password or managed cache URL
- TLS keys, certificates, and private key material

## Operational guidance

- Use separate MongoDB users for development, staging, and production.
- Grant the MongoDB user only the permissions the application needs.
- Restrict MongoDB Atlas network access to the deployment IPs or private networking path.
- Store production secrets in your deployment platform's secret manager, not in source control.
- Rotate secrets immediately if they are pasted into chat, logs, screenshots, tickets, or commits.

## If a secret is exposed

1. Rotate the secret at the provider first.
2. Replace the value in your local `.env`.
3. If it was committed, rewrite Git history before treating the repository as clean.
4. Invalidate any derived tokens or sessions if applicable.

## Container safety

- `.dockerignore` excludes `.env` so Docker image builds do not bake secrets into the image context.
- Keep runtime secrets injected through environment variables or your orchestration platform.

## Immediate recommendation

Secrets have been handled in this workspace during setup. Rotate the MongoDB password, JWT secret, and bootstrap admin password before any real deployment.
