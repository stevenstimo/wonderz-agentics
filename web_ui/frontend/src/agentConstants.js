// Backend app/routes/agents.py is single source of truth; keep this list in sync.
export const VALID_TOOLS = [
  'read_product', 'write_copy', 'read_analytics', 'write_social',
  'read_tickets', 'write_tickets', 'read_jobs', 'send_report', 'write_report',
  'web_search', 'read_lessons', 'write_email', 'read_seo',
  'review_content', 'optimize_seo', 'keyword_research', 'provide_feedback',
]

export const VALID_CATEGORIES = [
  'Management', 'Content', 'Marketing', 'Operations',
  'Technical', 'Support', 'Analytics', 'Custom',
]
