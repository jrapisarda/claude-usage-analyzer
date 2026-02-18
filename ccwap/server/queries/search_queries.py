from typing import List, Dict, Optional
import aiosqlite

STATIC_PAGES = [
    {"label": "Dashboard", "url": "/"},
    {"label": "Projects", "url": "/projects"},
    {"label": "Sessions", "url": "/sessions"},
    {"label": "Cost Analysis", "url": "/cost"},
    {"label": "Productivity", "url": "/productivity"},
    {"label": "Deep Analytics", "url": "/analytics"},
    {"label": "Experiments", "url": "/experiments"},
    {"label": "Live Monitor", "url": "/live"},
    {"label": "Settings", "url": "/settings"},
    {"label": "Activity Heatmap", "url": "/heatmap"},
    {"label": "Model Comparison", "url": "/models"},
    {"label": "Workflows", "url": "/workflows"},
    {"label": "Visualization Lab", "url": "/visualizations"},
]


async def search_all(
    db: aiosqlite.Connection,
    query: str,
    limit: int = 5,
) -> List[Dict]:
    """Cross-entity search for Cmd+K command palette."""
    if not query or len(query) < 1:
        return []

    results = []
    q = f"%{query}%"

    # Static page matches
    query_lower = query.lower()
    for page in STATIC_PAGES:
        if query_lower in page["label"].lower():
            results.append({
                "category": "page",
                "label": page["label"],
                "sublabel": "Page",
                "url": page["url"],
            })

    # Projects
    cursor = await db.execute(
        """SELECT DISTINCT project_display, project_path
           FROM sessions
           WHERE project_display LIKE ?
           ORDER BY project_display
           LIMIT ?""",
        (q, limit),
    )
    rows = await cursor.fetchall()
    for row in rows:
        results.append({
            "category": "project",
            "label": row[0] or row[1],
            "sublabel": "Project",
            "url": f"/projects?search={row[0] or ''}",
        })

    # Sessions
    cursor = await db.execute(
        """SELECT session_id, project_display
           FROM sessions
           WHERE session_id LIKE ? OR project_display LIKE ?
           ORDER BY first_timestamp DESC
           LIMIT ?""",
        (q, q, limit),
    )
    rows = await cursor.fetchall()
    for row in rows:
        results.append({
            "category": "session",
            "label": row[0][:12] + "...",
            "sublabel": row[1] or "Session",
            "url": f"/sessions/{row[0]}",
        })

    # Models
    cursor = await db.execute(
        """SELECT DISTINCT model
           FROM turns
           WHERE model LIKE ? AND model IS NOT NULL AND model NOT LIKE '<%'
           LIMIT ?""",
        (q, limit),
    )
    rows = await cursor.fetchall()
    for row in rows:
        results.append({
            "category": "model",
            "label": row[0],
            "sublabel": "Model",
            "url": f"/models",
        })

    # Branches
    cursor = await db.execute(
        """SELECT DISTINCT git_branch
           FROM sessions
           WHERE git_branch LIKE ? AND git_branch IS NOT NULL
           LIMIT ?""",
        (q, limit),
    )
    rows = await cursor.fetchall()
    for row in rows:
        results.append({
            "category": "branch",
            "label": row[0],
            "sublabel": "Branch",
            "url": f"/analytics",
        })

    # Tags
    cursor = await db.execute(
        """SELECT DISTINCT tag_name
           FROM experiment_tags
           WHERE tag_name LIKE ?
           LIMIT ?""",
        (q, limit),
    )
    rows = await cursor.fetchall()
    for row in rows:
        results.append({
            "category": "tag",
            "label": row[0],
            "sublabel": "Experiment Tag",
            "url": f"/experiments",
        })

    return results
