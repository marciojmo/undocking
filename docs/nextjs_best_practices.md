---
description: Next.js App Router patterns and conventions
globs: "**/*.{ts,tsx}"
alwaysApply: false
---

# Next.js Patterns

- Use `app/` directory with file-based routing
- Prefer Server Components; mark Client Components explicitly with `"use client"`
- Use `loading.tsx`, `error.tsx`, and `not-found.tsx` for route-level UI states
- Data fetching: use `async` Server Components or Server Actions — avoid client-side `useEffect` fetches
- Use `next/image` for images, `next/link` for navigation
- Environment variables: prefix client-exposed vars with `NEXT_PUBLIC_`
- Server Actions go in files marked `"use server"` or inline in Server Components

## Route Structure

```
app/
  (auth)/          # Auth-gated layout group
  (marketing)/     # Public pages
  api/             # API routes (use sparingly — prefer Server Actions)
  layout.tsx
  page.tsx
```
