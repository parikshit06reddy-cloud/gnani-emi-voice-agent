"""Renders docs/architecture-diagram.png (component diagram) using graphviz.

Run: python3 docs/render_architecture_diagram.py
Requires: graphviz python package + the `dot` binary (apt package `graphviz`).
Kept in docs/ for reproducibility; not part of the app/tests/scripts ownership boundary.
"""
from __future__ import annotations

import graphviz

g = graphviz.Digraph("architecture", format="png")
g.attr(
    rankdir="TB",
    bgcolor="#0f172a",
    fontname="Helvetica",
    fontsize="30",
    label="Gnani EMI Collections Voice Agent \u2014 Component Architecture",
    labelloc="t",
    labeljust="c",
    fontcolor="#e2e8f0",
    pad="0.7",
    nodesep="0.6",
    ranksep="0.9 equally",
    dpi="200",
    compound="true",
)
g.attr("node", fontname="Helvetica", fontsize="16", color="#64748b", fontcolor="#0f172a", margin="0.2,0.14")
g.attr("edge", fontname="Helvetica", fontsize="13", color="#94a3b8", fontcolor="#f1f5f9")

# ---- Rank 1: Client / Ops layer ----
with g.subgraph(name="cluster_client") as c:
    c.attr(
        label="Client / Ops Layer",
        style="rounded,filled",
        fillcolor="#1e293b",
        color="#475569",
        fontcolor="#e2e8f0",
        fontsize="18",
        labelloc="t",
    )
    c.node("seed", "scripts/seed_scenarios.py\n+ cURL / Postman", shape="box", style="rounded,filled", fillcolor="#38bdf8")
    c.node("browser", "Dashboard Browser\n(app/static)", shape="box", style="rounded,filled", fillcolor="#38bdf8")
    c.body.append("{rank=same; seed; browser}")

# ---- Rank 2: Trust boundary 1 - FastAPI ----
with g.subgraph(name="cluster_fastapi") as c:
    c.attr(
        label="Trust Boundary: Public Internet  \u2014  FastAPI Application (app/)",
        style="rounded,filled",
        fillcolor="#134e4a",
        color="#2dd4bf",
        fontcolor="#e2e8f0",
        fontsize="18",
        labelloc="t",
    )
    c.node("init", "POST /api/Initial_Message\n(X-API-Key)", shape="box", style="rounded,filled", fillcolor="#5eead4")
    c.node("webhook", "POST /api/v1/webhooks/post-call\n(X-Webhook-Key)", shape="box", style="rounded,filled", fillcolor="#5eead4")
    c.node("read", "GET /api/v1/calls, /calls/{id}, /stats\n(X-API-Key)", shape="box", style="rounded,filled", fillcolor="#5eead4")
    c.node("ws", "WS /ws/calls", shape="box", style="rounded,filled", fillcolor="#5eead4")
    c.body.append("{rank=same; init; webhook; read; ws}")
    c.node("svc", "Services\ninitial_message \u00b7 gnani_client\nstage_code \u00b7 disposition \u00b7 call_service", shape="box", style="rounded,filled", fillcolor="#99f6e4")
    c.node("repo", "Repository layer\nmongo_repo / json_repo", shape="box", style="rounded,filled", fillcolor="#99f6e4")

# ---- Rank 3: Trust boundary 2 - Gnani Cloud ----
with g.subgraph(name="cluster_gnani") as c:
    c.attr(
        label="Trust Boundary: Gnani Cloud (external)",
        style="rounded,filled",
        fillcolor="#3b0764",
        color="#c084fc",
        fontcolor="#e2e8f0",
        fontsize="18",
        labelloc="t",
    )
    c.node("trigger", "Call-Trigger API", shape="box", style="rounded,filled", fillcolor="#d8b4fe")
    c.node("console", "Gnani Agents Console\n(call orchestration)", shape="box", style="rounded,filled", fillcolor="#e9d5ff")
    c.body.append("{rank=same; trigger; console}")
    c.node("prisma", "Gnani Prisma ASR", shape="box", style="rounded,filled", fillcolor="#f0abfc")
    c.node("evon", "Gnani Evon LLM\n+ prompts/01, 02, 04, 05", shape="box", style="rounded,filled", fillcolor="#f0abfc")
    c.node("timbre", "Gnani Timbre 2.5 TTS", shape="box", style="rounded,filled", fillcolor="#f0abfc")
    c.body.append("{rank=same; prisma; evon; timbre}")
    c.node("analytics", "Analytics Prompt\nprompts/03", shape="box", style="rounded,filled", fillcolor="#d8b4fe")

# ---- Rank 4: Data layer ----
with g.subgraph(name="cluster_data") as c:
    c.attr(
        label="Data Layer",
        style="rounded,filled",
        fillcolor="#1e293b",
        color="#475569",
        fontcolor="#e2e8f0",
        fontsize="18",
        labelloc="t",
    )
    c.node("mongo", "MongoDB\ncalls collection", shape="cylinder", style="filled", fillcolor="#fbbf24")
    c.node("jsonfile", "JSON file store\ndata/calls.json", shape="cylinder", style="filled", fillcolor="#fde68a")
    c.body.append("{rank=same; mongo; jsonfile}")

# ---- Edges: numbered to reflect the call lifecycle order ----
# 1-2: client triggers / reads
g.edge("seed", "init", label=" 1. X-API-Key ", fontcolor="#f1f5f9")
g.edge("browser", "read", label=" X-API-Key ", fontcolor="#f1f5f9")
g.edge("browser", "ws", label=" live push ", style="dashed", fontcolor="#f1f5f9")

# 2-3: FastAPI internal + trigger call
g.edge("init", "svc", label=" 2 ")
g.edge("svc", "repo", label=" 3. persist queued ")
g.edge("svc", "trigger", label=" 4. retry x3, backoff ", fontcolor="#f1f5f9")

# 5-8: Gnani call orchestration loop
g.edge("trigger", "console", label=" 5 ")
g.edge("console", "prisma", dir="both", label=" 6 ")
g.edge("console", "evon", dir="both", label=" 6 ")
g.edge("console", "timbre", dir="both", label=" 6 ")
g.edge("console", "analytics", label=" 7. call ends ")

# 8: post-call webhook back into FastAPI
g.edge("analytics", "webhook", label=" 8. X-Webhook-Key POST ", fontcolor="#f1f5f9")
g.edge("webhook", "svc", label=" 9 ")
g.edge("webhook", "ws", label=" 10. broadcast ")
g.edge("ws", "browser", style="dashed", label=" live update ", fontcolor="#f1f5f9")

# persistence
g.edge("repo", "mongo", label=" 11 ")
g.edge("repo", "jsonfile", label=" fallback if\n MONGODB_URI unset ", style="dashed", fontcolor="#f1f5f9")
g.edge("read", "repo", label=" query ")

g.render("/home/user/workspace/gnani-emi-voice-agent/docs/architecture-diagram", cleanup=True)
print("rendered docs/architecture-diagram.png")
