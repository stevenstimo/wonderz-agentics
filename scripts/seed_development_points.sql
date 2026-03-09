-- Seed development_points for HR Improvements UI validation testing
-- Point IDs: DP-2026-001 through DP-2026-006

INSERT INTO development_points (
    point_id,
    agent_id,
    issue_description,
    evidence_example,
    frequency,
    impact,
    source_url,
    status,
    proposed_by
) VALUES
    (
        'DP-2026-001',
        'agent:copywriter:skilled-001',
        'HR validation form labels are truncated on narrow viewports, causing confusion for users submitting feedback.',
        'Screenshot: "Employee satisfact..." instead of full "Employee satisfaction score" on 320px width.',
        12,
        'high',
        'https://app.example.com/hr/validation',
        'OPEN',
        'qa-team'
    ),
    (
        'DP-2026-002',
        'agent:seo:skilled-001',
        'HR improvement cards lack proper ARIA labels for screen readers, reducing accessibility compliance.',
        'VoiceOver reads "button" without context; should announce "Approve HR improvement DP-2026-002".',
        8,
        'medium',
        'https://app.example.com/hr/improvements',
        'AWAITING_APPROVAL',
        'accessibility-audit'
    ),
    (
        'DP-2026-003',
        'agent:reviewer:skilled-001',
        'Status dropdown in HR validation UI does not persist selection when navigating between tabs.',
        'User selects IN_TRAINING, switches to Evidence tab, returns to Status tab — selection reset to OPEN.',
        15,
        'high',
        'https://app.example.com/hr/validation/edit',
        'IN_TRAINING',
        'dev-team'
    ),
    (
        'DP-2026-004',
        'agent:ads:meta',
        'HR development point list pagination shows inconsistent item counts when filtering by agent.',
        'Filter by agent:copywriter shows "Showing 1-10 of 7" — count mismatch in pagination footer.',
        3,
        'low',
        'https://app.example.com/hr/points',
        'RESOLVED',
        'qa-team'
    ),
    (
        'DP-2026-005',
        'agent:email:specialist',
        'Evidence example textarea in HR validation form has no character limit indicator, leading to truncation on submit.',
        'User pastes 2000 chars; backend truncates at 500 without warning; data loss on save.',
        5,
        'medium',
        'https://app.example.com/hr/validation',
        'OPEN',
        'support'
    ),
    (
        'DP-2026-006',
        'agent:copywriter:skilled-001',
        'Impact badge color contrast fails WCAG AA on light theme (yellow on white).',
        'Low impact badge: #FEF3C7 on #FFFFFF background — contrast ratio 1.4:1, fails 4.5:1 requirement.',
        20,
        'low',
        'https://app.example.com/hr/improvements',
        'RESOLVED',
        'accessibility-audit'
    )
ON CONFLICT (point_id) DO NOTHING;
