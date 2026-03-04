import { readdirSync, readFileSync, statSync } from 'node:fs'
import { extname, join, relative, basename } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = fileURLToPath(new URL('../', import.meta.url))
const SRC_DIR = join(ROOT, 'src')
const ALLOWED_FILE = 'PageLayout.jsx'

const violations = []

function collectFiles(dir) {
  const out = []
  for (const name of readdirSync(dir)) {
    const fullPath = join(dir, name)
    const stat = statSync(fullPath)
    if (stat.isDirectory()) {
      out.push(...collectFiles(fullPath))
      continue
    }
    const ext = extname(name)
    if (ext === '.jsx' || ext === '.tsx') {
      out.push(fullPath)
    }
  }
  return out
}

const files = collectFiles(SRC_DIR)
for (const file of files) {
  if (basename(file) === ALLOWED_FILE) {
    continue
  }

  const code = readFileSync(file, 'utf8')
  const hasSidebarImport = /import\s+Sidebar\s+from\s+['"]\.\/Sidebar['"]/.test(code)
  const hasSidebarRender = /<Sidebar\b/.test(code)

  if (hasSidebarImport || hasSidebarRender) {
    violations.push(relative(ROOT, file))
  }
}

if (violations.length > 0) {
  console.error('Layout shell check failed. Use PageLayout instead of direct Sidebar usage in:')
  for (const file of violations) {
    console.error(`- ${file}`)
  }
  process.exit(1)
}

console.log('Layout shell check passed.')
