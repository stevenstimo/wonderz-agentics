Gevonden:
- `web_ui/frontend/src/HRImprovements.jsx:149` -> `className="max-w-5xl mx-auto"`
- `web_ui/frontend/src/DevbotHome.jsx:25` -> `className="max-w-5xl mx-auto space-y-6"`

Oorzaak:
- Beide wrappers zijn gelijk op containerniveau; de smallere indruk komt van `md:grid-cols-2` in de issue-grid.

Fix voorstel:
- Wijzig `web_ui/frontend/src/HRImprovements.jsx` van `md:grid-cols-2` naar `md:grid-cols-1 lg:grid-cols-2`.
- Command: `sed -i '' 's/md:grid-cols-2/md:grid-cols-1 lg:grid-cols-2/g' web_ui/frontend/src/HRImprovements.jsx`

Vraag:
- Wil je dat ik deze wijziging direct doorvoer?
