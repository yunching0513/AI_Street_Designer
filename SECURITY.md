# Security Policy

## Supported version

Security fixes are applied to the latest `main` branch and current production
deployment.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository when
available. Do not include API keys, uploaded images, or other sensitive data in
a public issue.

## Deployment requirements

- Store `GOOGLE_API_KEY`, `OPENAI_API_KEY`, and `DIAG_TOKEN` only in the
  deployment platform's secret environment variables.
- Store `REDIS_URL` and `BLOB_READ_WRITE_TOKEN` as secrets when those optional
  services are enabled.
- Never commit a populated `.env` file.
- Keep `/api/diag` protected with a strong `DIAG_TOKEN`.
- Keep the supplied one-worker Gunicorn setting unless the Redis-backed state,
  distributed session locks, and the image-generation concurrency strategy
  have all been reviewed for the intended instance size.

## Current safeguards and limits

- Uploads are limited by byte size, decoded image type, dimensions, and pixel
  count.
- Image generation, chat, and Street View proxy requests are rate limited.
- Co-creation sessions expire and have bounded history and image versions.
- With `REDIS_URL`, session state, rate limits, and per-session operation locks
  are shared across workers. Redis values use expiring JSON, not Python pickle.
- API errors include a request ID but do not expose internal exception details.

Without `REDIS_URL`, sessions and limits are process-local and reset when the
worker restarts. Redis preserves co-creation state, but generated image URLs
are restart-safe only when `BLOB_READ_WRITE_TOKEN` is also configured. This
anonymous, expiring session store is not a substitute for authenticated user
storage.
