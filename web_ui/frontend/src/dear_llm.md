# Frontend Development Rules

## Layout

**Every page MUST use `<PageLayout>` as its root wrapper.**

This ensures the sidebar is always visible. No exceptions.

```jsx
import PageLayout from './PageLayout'

export default function MyPage() {
  return (
    <PageLayout size="wide" padded>
      {/* page content */}
    </PageLayout>
  )
}
```

Available `size` values: `'narrow'`, `'medium'`, `'wide'`, `'none'`

## Navigation

When adding a new page:
1. Add the route in `main.jsx`
2. Add a sidebar entry in `Sidebar.jsx` (in the appropriate menu section)
3. Wrap the page component in `<PageLayout>`

## API Calls

Use `apiBase` from `./apiBase` for API URLs:
```jsx
import { apiBase } from './apiBase'
fetch(`${apiBase}/api/endpoint`)
```

The Vite dev server and nginx both proxy `/api/*` to the backend on port 8090.
`apiBase` is normally an empty string (relative URLs).

## Styling

- Tailwind utility classes are available.
- Component-specific CSS goes in a separate `.css` file, imported in the component.
- Use `lucide-react` for icons.
