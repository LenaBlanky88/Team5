"""
build_workspace.py
Reads customer_journey_forensics.db and writes agent-workspace.html
Run from project root: python3 db/build_workspace.py
"""
import sqlite3, json, os, sys, re

DB_PATH  = "customer_journey_forensics.db"
OUT_FILE = "agent-workspace.html"

# ── channel / sentiment helpers ──────────────────────────────────────────────
CH_ICON = {
    "Phone Call":"📞","Email":"📧","Chatbot":"🤖","Live Chat":"💬",
    "WhatsApp":"💬","Callback":"📲","Portal / Self-Service":"🖥️",
    "Social Media":"🌐","Mobile App":"📱","Automated Notification":"🔔",
}
CH_KEY = {
    "Phone Call":"voice","Email":"email","Chatbot":"chat",
    "Live Chat":"livechat","WhatsApp":"whatsapp","Callback":"callback",
    "Portal / Self-Service":"portal","Social Media":"social",
    "Mobile App":"mobile","Automated Notification":"auto",
}
SENT_EMOJI = {
    "Neutral":"😐","Slightly Negative":"😕","Negative":"😞",
    "Very Negative":"😡","Positive":"😊",
}
SENT_KEY = {
    "Neutral":"neutral","Slightly Negative":"slightly-neg",
    "Negative":"neg","Very Negative":"very-neg","Positive":"pos",
}
INDUSTRY_EMOJI = {"Insurance":"📋","Healthcare":"🏥","Banking":"🏦","ISP":"📡"}
RISK_COL = lambda s: "#DC3545" if s>=9 else ("#FD7E14" if s>=7.5 else "#FFC107")

def initials(n):
    p = n.split()
    return (p[0][0]+p[-1][0]).upper() if len(p)>=2 else n[:2].upper()

def fmt_dur(secs):
    if not secs: return None
    m,s = divmod(secs,60)
    return f"{m} min" + (f" {s}s" if s else "")

def parse_transcript(raw):
    if not raw:
        return [{"sp":"sys","nm":"System","tx":"No transcript available."}]
    lines = [l.strip() for l in raw.strip().split("\n") if l.strip()]
    out = []
    for line in lines:
        if ":" in line:
            spk, _, txt = line.partition(":")
            spk, txt = spk.strip(), txt.strip()
            if not txt: continue
            lo = spk.lower()
            if any(w in lo for w in ["bot","system","ivr","portal","auto","notification"]):
                role = "sys"
            elif any(w in lo for w in [
                "customer","michael","james","david","jennifer","robert",
                "emily","sarah","anna","lisa","elena","terry"]):
                role = "cust"
            else:
                role = "agent"
            out.append({"sp":role,"nm":spk,"tx":txt})
        else:
            out.append({"sp":"sys","nm":"System","tx":line})
    return out or [{"sp":"sys","nm":"System","tx":raw[:200]}]

# ── AI opening lines from failure patterns ───────────────────────────────────
OPENER_MAP = {
    "Ownership Gap":
        ("I can see this case has been waiting for a resolution — I'm personally taking ownership right now.",
         "establishes accountability immediately"),
    "Broken Promise":
        ("I understand a commitment was made that wasn't kept. Can you walk me through exactly what you were told?",
         "surfaces the broken promise — lets customer vent and clarifies the gap"),
    "Repeat Contact":
        ("I can see you've reached out to us multiple times on this — that's not acceptable and I want to fix it today.",
         "acknowledges the effort and frustration before anything else"),
    "Financial Impact":
        ("I can see there was a billing impact on your account. Let me pull that up first before we do anything else.",
         "addresses financial pain point immediately — high retention risk"),
    "SLA Breach":
        ("Your case has exceeded our response SLA. I'm escalating priority right now.",
         "shows urgency and accountability for the delay"),
    "Channel Switching":
        ("You've had to reach us across several different channels — I want to be your single point of contact today.",
         "reduces customer effort, builds trust"),
    "No Assessor Assigned":
        ("I can see your claim is still pending an assessor. Let me check the assignment queue right now.",
         "shows immediate action on the root blocker"),
    "Conflicting Information":
        ("I understand you received different information from different people. Let me give you one confirmed answer.",
         "resolves confusion — one voice, one truth"),
    "No Proactive Communication":
        ("I can see no update was sent to you while this was being processed. That should not have happened.",
         "proactive acknowledgement of the silence"),
    "Treatment Delay":
        ("I understand there is a health-related urgency here. I'm flagging this as clinical priority immediately.",
         "signals urgency — critical for healthcare cases"),
    "Escalation Spiral":
        ("I can see this has been escalated multiple times. I'm the right person to resolve this today — no more transfers.",
         "stops the escalation loop, builds confidence"),
    "Billing Impact":
        ("I can see there was a billing concern on your account — let me check that immediately.",
         "addresses financial pain point"),
    "No Proactive Alert":
        ("I notice you weren't alerted before this issue occurred. Let me make sure you have full visibility going forward.",
         "turns reactive into proactive"),
    "Recurring Issue":
        ("I can see this issue has come back more than once. Let me make sure we get to the actual root cause today.",
         "signals intent to fix permanently, not just patch"),
}

def get_opening_lines(patterns):
    lines = []
    seen = set()
    for p in patterns:
        pt = p["pattern_type"]
        if pt in OPENER_MAP and pt not in seen:
            q, hint = OPENER_MAP[pt]
            lines.append({"q": q, "hint": hint, "pattern": pt})
            seen.add(pt)
        if len(lines) == 3:
            break
    # fallback if DB patterns not in map
    if not lines:
        lines = [
            {"q":"What would be the ideal outcome of today's call for you?",
             "hint":"open-ended — lets customer define success"},
            {"q":"Can you walk me through what's happened so far?",
             "hint":"gives full context before offering a solution"},
        ]
    return lines[:3]

# ── customer snapshot bullets ─────────────────────────────────────────────────
def build_snapshot(s, ints, patterns):
    crit = sum(1 for p in patterns if p["severity"]=="CRITICAL")
    last_ch = ints[-1]["channel_name"] if ints else "Unknown"
    first_dt = str(ints[0]["start_time"])[:10] if ints else "Unknown"
    bullets = [
        f"{s['industry']} customer — {s['plan_type'] or 'Standard plan'} · {s['customer_id']}",
        f"{s['total_interactions']} prior contacts since {first_dt} — case still unresolved",
        f"{crit} critical failure pattern{'s' if crit!=1 else ''} detected · Risk score {s['risk_score']} {s['risk_label']}",
        f"Last contact via {last_ch} — {SENT_EMOJI.get(ints[-1]['overall_sentiment'],'😐')} {ints[-1]['overall_sentiment'] or 'Unknown'} sentiment",
    ]
    return bullets

# ── internal note ─────────────────────────────────────────────────────────────
def build_internal_note(s, ints, c):
    n = len(ints)
    last = ints[-1] if ints else {}
    ch = last.get("channel_name","phone")
    return (
        f"{c['customer_name']} has contacted {s['industry']} support "
        f"{n} time{'s' if n!=1 else ''} regarding: <strong>{s['scenario_title']}</strong>. "
        f"Current risk score: <strong>{s['risk_score']} / 10 — {s['risk_label']}</strong>. "
        f"Most recent contact via <strong>{ch}</strong>. "
        f"Root cause: {(s['root_cause'] or 'Under analysis')[:160]}."
    )

# ── main build ────────────────────────────────────────────────────────────────
def build():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found. Run db/seed.py first."); sys.exit(1)

    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    sessions = db.execute("""
        SELECT js.master_contact_id, js.scenario_title, js.case_reference_id,
               js.industry, js.risk_score, js.risk_label, js.total_interactions,
               js.root_cause, js.session_status,
               c.customer_name, c.customer_id, c.plan_type,
               c.account_number, c.member_id, c.policy_number
        FROM journey_sessions js JOIN customers c ON js.customer_id = c.customer_id
        ORDER BY js.risk_score DESC
    """).fetchall()

    cases = []
    for s in sessions:
        key = s["master_contact_id"]
        ints_raw = db.execute("""
            SELECT i.*, ch.channel_name, a.agent_name
            FROM interactions i
            LEFT JOIN channels ch ON i.channel_id = ch.channel_id
            LEFT JOIN agents a ON i.agent_id = a.agent_id
            WHERE i.master_contact_id=? ORDER BY i.interaction_sequence
        """, (key,)).fetchall()
        if not ints_raw: continue

        fps_raw = db.execute("""
            SELECT severity, pattern_type, pattern_description
            FROM failure_patterns WHERE master_contact_id=?
            ORDER BY CASE severity WHEN 'CRITICAL' THEN 1 ELSE 2 END
        """, (key,)).fetchall()

        acts_raw = db.execute("""
            SELECT priority, action_text FROM recommended_actions
            WHERE master_contact_id=?
            ORDER BY CASE priority WHEN 'Critical' THEN 1 WHEN 'High' THEN 2
                     WHEN 'Medium' THEN 3 ELSE 4 END
        """, (key,)).fetchall()

        ints  = [dict(i) for i in ints_raw]
        fps   = [dict(f) for f in fps_raw]
        acts  = [dict(a) for a in acts_raw]

        # transcript = last interaction (current call)
        last_int = ints[-1]
        transcript_bubbles = parse_transcript(last_int.get("transcript",""))

        # journey nodes for Customer History tab
        nodes = []
        for it in ints:
            ch_name = it.get("channel_name") or it.get("media_type","")
            sent_raw = it.get("overall_sentiment") or "Neutral"
            nodes.append({
                "seq":   it["interaction_sequence"],
                "ch":    CH_KEY.get(ch_name,"voice"),
                "icon":  CH_ICON.get(ch_name,"📋"),
                "chNm":  ch_name,
                "ttl":   f"{ch_name} — Contact {it['interaction_sequence']}",
                "dt":    str(it.get("start_time",""))[:10],
                "ag":    it.get("agent_name") or "Unassigned",
                "sent":  SENT_KEY.get(sent_raw,"neutral"),
                "sEmoji":SENT_EMOJI.get(sent_raw,"😐"),
                "csat":  it.get("csat"),
                "esc":   bool(it.get("escalation_flag")),
                "dur":   fmt_dur(it.get("duration_seconds")),
                "lines": parse_transcript(it.get("transcript","")),
                "out":   it.get("outcome") or "—",
            })

        pat_list = [
            {"sev":"🔴" if p["severity"]=="CRITICAL" else "🟠",
             "lbl": p["pattern_type"],
             "desc":p["pattern_description"]}
            for p in fps
        ]
        act_list = [{"pri":a["priority"],"txt":a["action_text"]} for a in acts]

        ref = (s["case_reference_id"] or s["policy_number"] or
               s["account_number"] or s["member_id"] or "N/A")
        score = float(s["risk_score"]) if s["risk_score"] else 7.0

        opening_lines = get_opening_lines(fps)
        snapshot_bullets = build_snapshot(dict(s), ints, fps)
        internal_note = build_internal_note(dict(s), ints, dict(s))

        cases.append({
            "key":      key,
            "name":     s["customer_name"],
            "init":     initials(s["customer_name"]),
            "id":       s["customer_id"],
            "ref":      ref,
            "industry": s["industry"],
            "iEmoji":   INDUSTRY_EMOJI.get(s["industry"],"📋"),
            "prod":     s["plan_type"] or s["industry"],
            "scenario": s["scenario_title"] or "",
            "score":    score,
            "label":    s["risk_label"] or "RISK",
            "col":      RISK_COL(score),
            "status":   s["session_status"] or "Open",
            "totalInts":s["total_interactions"] or len(ints),
            "internalNote":   internal_note,
            "snapshotBullets":snapshot_bullets,
            "openingLines":   opening_lines,
            "transcript":     transcript_bubbles,
            "lastCh":    last_int.get("channel_name","Phone Call"),
            "nodes":    nodes,
            "patterns": pat_list,
            "actions":  act_list,
            "rootCause":s["root_cause"] or "",
        })

    db.close()

    js_data = "const CASES = " + json.dumps(cases, indent=2, ensure_ascii=False) + ";"
    html = HTML_TEMPLATE.replace("/*__DB_DATA__*/", js_data)

    with open(OUT_FILE,"w") as f:
        f.write(html)

    print(f"✓  {OUT_FILE}  —  {len(cases)} cases loaded from DB")
    for c in cases:
        print(f"   {c['key']}  {c['name']:<22}  risk={c['score']}  {len(c['nodes'])} ints")

# ── HTML TEMPLATE ─────────────────────────────────────────────────────────────
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Agent Workspace — NiCE CXone</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>
:root{
  --navy:#001B44; --blue:#0D6EFD; --light-blue:#E8F1FF;
  --green:#198754; --green-bg:#F0FFF4; --green-border:#C3E6CB;
  --red:#DC3545; --orange:#FD7E14; --yellow:#FFC107;
  --bg:#F4F6FA; --border:#DEE2E6; --white:#fff;
  --text:#1A2332; --muted:#6C757D;
  --sidebar-w:210px; --transcript-w:300px;
  --hdr-h:44px; --tabbar-h:38px;
}
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  height:100vh;overflow:hidden;display:flex;flex-direction:column;
  background:var(--bg);color:var(--text);font-size:13px;}

/* ── HEADER ── */
.hdr{height:var(--hdr-h);background:var(--navy);display:flex;align-items:center;
  padding:0 14px;gap:10px;flex-shrink:0;z-index:100;}
.hdr-menu{color:rgba(255,255,255,.5);font-size:14px;cursor:pointer;padding:4px;}
.hdr-title{color:#fff;font-size:13px;font-weight:600;letter-spacing:.2px;}
.hdr-tabs{display:flex;align-items:stretch;flex:1;height:100%;overflow:hidden;}
.hdr-tab{display:flex;align-items:center;gap:6px;padding:0 14px;
  color:rgba(255,255,255,.55);font-size:12px;cursor:pointer;
  border-bottom:2px solid transparent;white-space:nowrap;transition:all .2s;
  border-right:1px solid rgba(255,255,255,.08);}
.hdr-tab:hover{color:rgba(255,255,255,.85);}
.hdr-tab.active{color:#fff;border-bottom-color:var(--blue);}
.hdr-tab .tab-close{opacity:0;font-size:10px;margin-left:4px;transition:opacity .2s;}
.hdr-tab:hover .tab-close{opacity:.6;}
.hdr-tab-add{display:flex;align-items:center;padding:0 10px;
  color:rgba(255,255,255,.4);cursor:pointer;font-size:14px;}
.hdr-tab-add:hover{color:rgba(255,255,255,.7);}
.hdr-right{margin-left:auto;display:flex;align-items:center;gap:12px;flex-shrink:0;}
.hdr-bell{color:rgba(255,255,255,.6);font-size:14px;position:relative;cursor:pointer;}
.hdr-bell-badge{position:absolute;top:-4px;right:-4px;width:14px;height:14px;
  background:var(--red);border-radius:50%;font-size:8px;font-weight:700;
  color:#fff;display:flex;align-items:center;justify-content:center;
  border:1.5px solid var(--navy);}
.hdr-avatar{width:28px;height:28px;border-radius:50%;background:var(--blue);
  color:#fff;font-size:10px;font-weight:700;display:flex;align-items:center;justify-content:center;}
.in-call-badge{display:flex;align-items:center;gap:6px;
  background:rgba(25,135,84,.25);border:1px solid rgba(25,135,84,.4);
  border-radius:4px;padding:3px 10px;color:#6EE2A0;font-size:11px;font-weight:600;}
.in-call-dot{width:7px;height:7px;border-radius:50%;background:#28A745;
  animation:pulse-g 1.5s infinite;}
@keyframes pulse-g{0%,100%{opacity:1;transform:scale(1);}50%{opacity:.6;transform:scale(.8);}}

/* ── BODY ── */
.body{flex:1;display:flex;overflow:hidden;}

/* ── SIDEBAR ── */
.sidebar{width:var(--sidebar-w);background:var(--white);
  border-right:1px solid var(--border);display:flex;flex-direction:column;flex-shrink:0;}
.sb-cases-hdr{padding:10px 12px 6px;display:flex;align-items:center;justify-content:space-between;}
.sb-cases-lbl{font-size:11px;font-weight:700;color:var(--text);}
.sb-cases-sub{font-size:10px;color:var(--muted);}
.sb-new{margin:0 10px 8px;padding:6px;border:1.5px dashed var(--border);
  border-radius:6px;background:none;font-size:11px;color:var(--muted);
  cursor:pointer;width:calc(100% - 20px);transition:all .2s;}
.sb-new:hover{border-color:var(--blue);color:var(--blue);}
.sb-list{flex:1;overflow-y:auto;}
.sb-case{padding:9px 10px;cursor:pointer;border-left:3px solid transparent;
  transition:all .2s;border-bottom:1px solid var(--bg);}
.sb-case:hover{background:var(--bg);}
.sb-case.active{background:var(--light-blue);border-left-color:var(--blue);}
.sb-case-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:3px;}
.sb-case-name{font-size:12px;font-weight:700;color:var(--text);}
.sb-case-badge{font-size:9px;font-weight:700;padding:2px 6px;border-radius:10px;
  background:var(--light-blue);color:var(--blue);}
.sb-case-badge.critical{background:#FFF3F3;color:var(--red);}
.sb-case-desc{font-size:10px;color:var(--muted);line-height:1.4;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}
.sb-case-foot{display:flex;align-items:center;gap:5px;margin-top:4px;}
.sb-tag{font-size:9px;padding:1px 5px;border-radius:3px;font-weight:600;
  background:var(--bg);color:var(--muted);}
.sb-tag.voice{background:#E8F1FF;color:var(--blue);}
.sb-controls{padding:8px 10px;border-top:1px solid var(--border);flex-shrink:0;}
.sb-ctrl-row{display:flex;gap:6px;margin-bottom:6px;}
.sb-ctrl-btn{flex:1;padding:6px;border:1px solid var(--border);border-radius:5px;
  background:var(--white);font-size:10px;font-weight:600;cursor:pointer;
  display:flex;flex-direction:column;align-items:center;gap:2px;
  color:var(--muted);transition:all .2s;}
.sb-ctrl-btn:hover{background:var(--bg);}
.sb-ctrl-btn.end{border-color:#FFCDD2;background:#FFF3F3;color:var(--red);}
.sb-ctrl-btn.end:hover{background:#FFEBEE;}
.sb-ctrl-btn i{font-size:12px;}
.sb-nav{border-top:1px solid var(--border);padding:6px 0;display:flex;flex-direction:column;}
.sb-nav-item{display:flex;align-items:center;gap:8px;padding:7px 14px;
  color:var(--muted);cursor:pointer;font-size:11px;transition:all .2s;position:relative;}
.sb-nav-item:hover{background:var(--bg);color:var(--text);}
.sb-nav-item.active{color:var(--blue);background:var(--light-blue);}
.sb-nav-item i{width:16px;text-align:center;font-size:13px;}
.sb-nav-badge{margin-left:auto;background:var(--red);color:#fff;
  font-size:9px;font-weight:700;padding:1px 5px;border-radius:10px;}

/* ── MAIN ── */
.main{flex:1;display:flex;flex-direction:column;overflow:hidden;min-width:0;}
.tab-bar{height:var(--tabbar-h);background:var(--white);
  border-bottom:1px solid var(--border);display:flex;align-items:stretch;flex-shrink:0;}
.m-tab{display:flex;align-items:center;gap:6px;padding:0 16px;
  font-size:12px;font-weight:500;cursor:pointer;color:var(--muted);
  border-bottom:2px solid transparent;white-space:nowrap;transition:all .2s;}
.m-tab:hover{color:var(--text);}
.m-tab.active{color:var(--blue);border-bottom-color:var(--blue);font-weight:600;}
.m-tab i{font-size:12px;}
.tab-content{flex:1;overflow-y:auto;padding:14px 16px;}

/* ── VOICE TAB ── */
.convo-lbl{font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;
  letter-spacing:.6px;margin-bottom:8px;display:flex;align-items:center;gap:6px;}
.connected-line{display:flex;align-items:center;gap:8px;padding:8px 12px;
  background:var(--green-bg);border:1px solid var(--green-border);
  border-radius:6px;margin-bottom:10px;font-size:12px;color:var(--green);font-weight:600;}
.connected-line i{font-size:14px;}

/* INTERNAL NOTE */
.int-note{background:#fff;border:1px solid var(--green-border);border-left:4px solid var(--green);
  border-radius:8px;padding:13px 15px;margin-bottom:10px;}
.int-note-hdr{display:flex;align-items:center;gap:7px;margin-bottom:9px;}
.int-note-tag{background:var(--green-bg);border:1px solid var(--green-border);
  color:var(--green);font-size:10px;font-weight:700;padding:2px 8px;
  border-radius:4px;letter-spacing:.3px;}
.int-note-body{font-size:12px;color:var(--text);line-height:1.7;}
.int-note-body strong{color:var(--text);}

/* CUSTOMER SNAPSHOT */
.snapshot{background:var(--white);border:1px solid var(--border);border-radius:8px;
  padding:13px 15px;margin-bottom:10px;}
.snap-hdr{display:flex;align-items:center;gap:10px;margin-bottom:10px;}
.snap-av{width:38px;height:38px;border-radius:50%;background:var(--light-blue);
  color:var(--blue);font-size:13px;font-weight:700;
  display:flex;align-items:center;justify-content:center;flex-shrink:0;}
.snap-name{font-size:14px;font-weight:700;}
.snap-sub{font-size:11px;color:var(--muted);}
.snap-tags{display:flex;gap:5px;flex-wrap:wrap;margin-top:4px;}
.snap-tag{font-size:10px;padding:2px 7px;border-radius:10px;
  border:1px solid var(--border);color:var(--muted);background:var(--bg);}
.snap-bullets{margin-top:8px;}
.snap-lbl{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;
  color:var(--muted);margin-bottom:5px;}
.snap-bullet{display:flex;align-items:flex-start;gap:6px;
  font-size:12px;color:var(--text);padding:3px 0;line-height:1.5;}
.snap-bullet::before{content:"•";color:var(--blue);font-weight:700;flex-shrink:0;margin-top:1px;}

/* AI OPENING LINES */
.ai-lines{background:var(--white);border:1px solid var(--border);
  border-radius:8px;padding:13px 15px;margin-bottom:10px;}
.ai-lines-hdr{display:flex;align-items:center;gap:7px;margin-bottom:10px;
  font-size:11px;font-weight:700;color:var(--text);}
.ai-lines-hdr i{color:var(--blue);}
.ai-line{padding:9px 12px;border:1px solid var(--border);border-radius:6px;
  margin-bottom:7px;cursor:pointer;transition:all .2s;}
.ai-line:last-child{margin-bottom:0;}
.ai-line:hover{border-color:var(--blue);background:var(--light-blue);}
.ai-line-q{font-size:12px;color:var(--text);line-height:1.5;margin-bottom:3px;}
.ai-line-hint{font-size:10px;color:var(--muted);font-style:italic;}

/* ── CUSTOMER HISTORY TAB ── */
.history-wrap{display:flex;gap:14px;min-height:100%;}
/* Journey timeline */
.hist-tl{width:36%;min-width:240px;display:flex;flex-direction:column;gap:0;}
.hist-tl-hdr{font-size:11px;font-weight:700;color:var(--muted);
  text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px;
  display:flex;align-items:center;gap:6px;}
.risk-pill{display:inline-flex;align-items:center;gap:5px;padding:4px 10px;
  border-radius:20px;font-size:11px;font-weight:700;
  background:#FFF3F3;color:var(--red);margin-bottom:10px;}
.tl-node{display:flex;gap:10px;padding:8px;border-radius:7px;
  cursor:pointer;transition:all .2s;position:relative;margin-bottom:1px;}
.tl-node:hover{background:var(--bg);}
.tl-node.sel{background:var(--light-blue);outline:1.5px solid #B8D0FF;}
.tl-node:not(:last-child)::after{content:'';position:absolute;
  left:26px;top:42px;width:2px;height:calc(100% - 14px);
  background:var(--border);z-index:0;}
.tl-ic{width:32px;height:32px;border-radius:50%;border:2px solid var(--border);
  background:#fff;display:flex;align-items:center;justify-content:center;
  font-size:12px;flex-shrink:0;z-index:1;position:relative;}
.tl-body{flex:1;min-width:0;}
.tl-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:2px;}
.tl-ttl{font-size:11px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.tl-dt{font-size:10px;color:var(--muted);white-space:nowrap;margin-left:4px;flex-shrink:0;}
.tl-ag{font-size:10px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-bottom:3px;}
.tl-foot{display:flex;gap:4px;align-items:center;flex-wrap:wrap;}
.tl-csat{font-size:9px;padding:1px 5px;border-radius:8px;font-weight:700;}
.c1{background:#FFF3F3;color:var(--red);}.c2{background:#FFF0E6;color:var(--orange);}
.c3{background:#FFFDE7;color:#856404;}.c4{background:#F0FFF4;color:var(--green);}
.c5{background:#E8F5E9;color:#1B5E20;}
.esc-tag{font-size:9px;background:#FFF3F3;color:var(--red);padding:1px 5px;border-radius:3px;font-weight:700;}
/* AI Brief */
.hist-brief{flex:1;display:flex;flex-direction:column;gap:10px;min-width:0;}
.brief-card{background:var(--white);border:1px solid var(--border);
  border-radius:8px;padding:13px 15px;}
.brief-card-hdr{font-size:10px;font-weight:700;text-transform:uppercase;
  letter-spacing:.5px;color:var(--muted);margin-bottom:8px;
  display:flex;align-items:center;gap:6px;}
.brief-card-hdr i{color:var(--blue);}
/* Risk hero */
.risk-hero{display:flex;align-items:center;gap:16px;}
.risk-ring{width:76px;height:76px;position:relative;flex-shrink:0;}
.risk-ring svg{transform:rotate(-90deg);}
.risk-ring .bg{fill:none;stroke:#f0f0f0;stroke-width:8;}
.risk-ring .fg{fill:none;stroke-width:8;stroke-linecap:round;
  stroke-dasharray:207;stroke-dashoffset:207;transition:stroke-dashoffset 1.2s ease;}
.risk-inner{position:absolute;inset:0;display:flex;flex-direction:column;
  align-items:center;justify-content:center;}
.risk-num{font-size:18px;font-weight:800;line-height:1;}
.risk-denom{font-size:9px;color:var(--muted);}
.risk-label-big{font-size:18px;font-weight:800;margin-bottom:5px;}
.risk-sum{font-size:12px;color:var(--muted);line-height:1.6;}
/* Pattern table */
.pat-tbl{width:100%;border-collapse:collapse;}
.pat-tbl tr{border-bottom:1px solid var(--bg);}
.pat-tbl tr:last-child{border-bottom:none;}
.pat-tbl td{padding:6px 4px;font-size:11px;vertical-align:top;}
.pt-sev{width:18px;} .pt-lbl{font-weight:700;width:36%;padding-right:8px;}
.pt-desc{color:var(--muted);}
/* Actions */
.act-item{display:flex;gap:9px;padding:8px 0;
  border-bottom:1px solid var(--bg);align-items:flex-start;}
.act-item:last-child{border-bottom:none;}
.act-num{width:20px;height:20px;border-radius:50%;background:var(--blue);
  color:#fff;font-size:10px;font-weight:700;
  display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px;}
.act-pri{font-size:9px;font-weight:700;text-transform:uppercase;
  padding:2px 5px;border-radius:3px;display:inline-block;margin-bottom:3px;}
.pri-critical{background:#FFF3F3;color:var(--red);}
.pri-high{background:#FFF8F0;color:var(--orange);}
.pri-medium{background:#FFFDE7;color:#856404;}
.act-txt{font-size:12px;line-height:1.5;}

/* ── TRANSCRIPT PANEL ── */
.tr-panel{width:var(--transcript-w);background:var(--white);
  border-left:1px solid var(--border);display:flex;flex-direction:column;flex-shrink:0;}
.tr-hdr{padding:10px 13px;background:var(--navy);color:#fff;
  display:flex;align-items:center;justify-content:space-between;flex-shrink:0;}
.tr-hdr-lbl{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;}
.tr-hdr-name{font-size:11px;opacity:.7;margin-top:1px;}
.tr-live{display:flex;align-items:center;gap:5px;font-size:10px;font-weight:700;color:#6EE2A0;}
.tr-live-dot{width:6px;height:6px;border-radius:50%;background:#28A745;animation:pulse-g 1.5s infinite;}
.tr-body{flex:1;overflow-y:auto;padding:12px 10px;}
.bubble{margin-bottom:8px;}
.bubble-sp{font-size:9px;font-weight:700;color:var(--muted);
  margin-bottom:2px;text-transform:uppercase;letter-spacing:.4px;}
.bubble-txt{padding:8px 11px;border-radius:10px;font-size:11px;
  line-height:1.6;max-width:90%;white-space:pre-line;}
.b-cust .bubble-txt{background:var(--light-blue);}
.b-agent .bubble-txt{background:var(--bg);}
.b-sys .bubble-sp{color:var(--green);}
.b-sys .bubble-txt{background:var(--green-bg);color:#155724;font-style:italic;}

/* ── DRAWER (transcript detail) ── */
.overlay{position:fixed;inset:0;background:rgba(0,0,0,.25);z-index:200;
  opacity:0;pointer-events:none;transition:opacity .3s;}
.overlay.on{opacity:1;pointer-events:all;}
.drawer{position:fixed;right:0;top:0;bottom:0;width:400px;background:#fff;
  box-shadow:-4px 0 30px rgba(0,0,0,.15);z-index:201;
  transform:translateX(100%);transition:transform .35s cubic-bezier(.4,0,.2,1);
  display:flex;flex-direction:column;}
.drawer.on{transform:translateX(0);}
.dr-hdr{padding:12px 16px;background:var(--navy);color:#fff;
  display:flex;align-items:center;gap:10px;flex-shrink:0;}
.dr-hdr-info h3{font-size:13px;font-weight:700;}
.dr-hdr-info p{font-size:10px;opacity:.6;}
.dr-close{margin-left:auto;width:26px;height:26px;border-radius:5px;
  background:rgba(255,255,255,.15);color:#fff;border:none;cursor:pointer;
  display:flex;align-items:center;justify-content:center;font-size:12px;}
.dr-close:hover{background:rgba(255,255,255,.25);}
.dr-meta{padding:8px 16px;background:var(--bg);border-bottom:1px solid var(--border);
  display:flex;gap:12px;flex-shrink:0;}
.dr-mi{text-align:center;}
.dr-mlbl{font-size:9px;text-transform:uppercase;letter-spacing:.4px;color:var(--muted);font-weight:700;}
.dr-mval{font-size:12px;font-weight:700;margin-top:1px;}
.dr-body{flex:1;overflow-y:auto;padding:12px 16px;}
.dr-out{padding:10px 16px;border-top:1px solid var(--border);flex-shrink:0;}
.dr-out-lbl{font-size:9px;text-transform:uppercase;letter-spacing:.4px;color:var(--muted);font-weight:700;margin-bottom:3px;}
.dr-out-txt{font-size:12px;line-height:1.5;}

/* ── scrollbars ── */
::-webkit-scrollbar{width:4px;}::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{background:#ccc;border-radius:2px;}
</style>
</head>
<body>

<!-- HEADER -->
<header class="hdr">
  <div class="hdr-menu"><i class="fas fa-th"></i></div>
  <span class="hdr-title">Agent Workspace</span>
  <div class="hdr-tabs" id="hdr-tabs"></div>
  <div class="hdr-right">
    <div class="hdr-bell"><i class="fas fa-bell"></i>
      <div class="hdr-bell-badge">4</div>
    </div>
    <div class="in-call-badge" id="in-call-badge">
      <div class="in-call-dot"></div>
      <span>In a Call</span>
      <span id="call-timer">00:00:00</span>
    </div>
    <div class="hdr-avatar" id="hdr-av">SR</div>
  </div>
</header>

<!-- BODY -->
<div class="body">

  <!-- SIDEBAR -->
  <div class="sidebar">
    <div class="sb-cases-hdr">
      <div><div class="sb-cases-lbl">Cases</div>
        <div class="sb-cases-sub">3 completed today</div></div>
    </div>
    <button class="sb-new"><i class="fas fa-plus"></i> New Case</button>
    <div class="sb-list" id="sb-list"></div>
    <div class="sb-controls">
      <div class="sb-ctrl-row">
        <button class="sb-ctrl-btn"><i class="fas fa-random"></i><span>Transfer</span></button>
        <button class="sb-ctrl-btn"><i class="fas fa-pause"></i><span>Hold</span></button>
        <button class="sb-ctrl-btn end"><i class="fas fa-phone-slash"></i><span>End Call</span></button>
      </div>
    </div>
    <nav class="sb-nav">
      <div class="sb-nav-item active"><i class="fas fa-headset"></i>Control Center</div>
      <div class="sb-nav-item"><i class="fas fa-list"></i>Queue
        <span class="sb-nav-badge">33</span></div>
      <div class="sb-nav-item"><i class="fas fa-address-book"></i>Directory</div>
      <div class="sb-nav-item"><i class="fas fa-calendar"></i>Schedule</div>
      <div class="sb-nav-item"><i class="fas fa-cog"></i>Settings</div>
    </nav>
  </div>

  <!-- MAIN -->
  <div class="main">
    <div class="tab-bar" id="tab-bar"></div>
    <div class="tab-content" id="tab-content"></div>
  </div>

  <!-- TRANSCRIPT PANEL -->
  <div class="tr-panel">
    <div class="tr-hdr">
      <div><div class="tr-hdr-lbl">Call Transcript</div>
        <div class="tr-hdr-name" id="tr-name">—</div></div>
      <div class="tr-live"><div class="tr-live-dot"></div>LIVE</div>
    </div>
    <div class="tr-body" id="tr-body"></div>
  </div>
</div>

<!-- DRAWER -->
<div class="overlay" id="overlay" onclick="closeDrawer()"></div>
<div class="drawer" id="drawer">
  <div class="dr-hdr">
    <div style="font-size:18px" id="dr-ic">📞</div>
    <div class="dr-hdr-info"><h3 id="dr-ttl">—</h3><p id="dr-sub">—</p></div>
    <button class="dr-close" onclick="closeDrawer()"><i class="fas fa-times"></i></button>
  </div>
  <div class="dr-meta">
    <div class="dr-mi"><div class="dr-mlbl">Sentiment</div><div class="dr-mval" id="dr-sent">—</div></div>
    <div class="dr-mi"><div class="dr-mlbl">CSAT</div><div class="dr-mval" id="dr-csat">—</div></div>
    <div class="dr-mi"><div class="dr-mlbl">Duration</div><div class="dr-mval" id="dr-dur">—</div></div>
    <div class="dr-mi"><div class="dr-mlbl">Escalated</div><div class="dr-mval" id="dr-esc">No</div></div>
  </div>
  <div class="dr-body" id="dr-body"></div>
  <div class="dr-out"><div class="dr-out-lbl">Outcome</div><div class="dr-out-txt" id="dr-out">—</div></div>
</div>

<script>
/*__DB_DATA__*/

/* ── state ── */
let curKey  = CASES[0]?.key;
let curTab  = 'voice';
let callSec = 0;

/* ── boot ── */
(function init(){
  buildSidebar();
  selectCase(curKey);
  setInterval(tickTimer, 1000);
})();

/* ── timer ── */
function tickTimer(){
  callSec++;
  const h=Math.floor(callSec/3600), m=Math.floor((callSec%3600)/60), s=callSec%60;
  const el=document.getElementById('call-timer');
  if(el) el.textContent=[h,m,s].map(x=>String(x).padStart(2,'0')).join(':');
}

/* ── sidebar ── */
function buildSidebar(){
  const list=document.getElementById('sb-list');
  list.innerHTML=CASES.map(c=>`
    <div class="sb-case${c.key===curKey?' active':''}" id="sb-${c.key}" onclick="selectCase('${c.key}')">
      <div class="sb-case-top">
        <div class="sb-case-name">${c.name}</div>
        <div class="sb-case-badge${c.score>=9?' critical':''}">${c.label}</div>
      </div>
      <div class="sb-case-desc">${c.iEmoji} ${c.scenario}</div>
      <div class="sb-case-foot">
        <span class="sb-tag voice">VOICE</span>
        <span class="sb-tag">${c.industry}</span>
        <span class="sb-tag">Risk ${c.score}</span>
      </div>
    </div>`).join('');
}

/* ── select case ── */
function selectCase(key){
  curKey=key;
  curTab='voice';
  document.querySelectorAll('.sb-case').forEach(el=>el.classList.remove('active'));
  const sb=document.getElementById('sb-'+key);
  if(sb){sb.classList.add('active');sb.scrollIntoView({block:'nearest'});}
  const c=CASES.find(x=>x.key===key);
  if(!c) return;
  renderHdrTabs(c);
  renderTranscript(c);
  renderVoiceTab(c);
  callSec=0;
  closeDrawer();
}

/* ── header tabs ── */
function renderHdrTabs(c){
  document.getElementById('hdr-tabs').innerHTML=`
    <div class="hdr-tab active">
      <i class="fas fa-user" style="font-size:11px"></i> ${c.name}
      <span class="tab-close">✕</span>
    </div>
    <div class="hdr-tab${curTab==='voice'?' active':''}" onclick="switchTab('voice')">
      <i class="fas fa-phone" style="font-size:11px"></i> Voice
    </div>
    <div class="hdr-tab${curTab==='history'?' active':''}" onclick="switchTab('history')">
      <i class="fas fa-route" style="font-size:11px"></i> Customer History
    </div>
    <div class="hdr-tab-add"><i class="fas fa-plus"></i></div>`;
  document.getElementById('hdr-av').textContent=c.init;
  document.getElementById('tr-name').textContent=c.name;
}

/* ── switch tab ── */
function switchTab(tab){
  curTab=tab;
  const c=CASES.find(x=>x.key===curKey);
  if(!c) return;
  renderHdrTabs(c);
  // update main tab bar highlight
  document.querySelectorAll('.m-tab').forEach(el=>{
    el.classList.toggle('active', el.dataset.tab===tab);
  });
  document.getElementById('tab-bar').querySelectorAll('.m-tab').forEach(el=>{
    el.classList.toggle('active', el.dataset.tab===tab);
  });
  if(tab==='voice')   renderVoiceTab(c);
  if(tab==='history') renderHistoryTab(c);
}

/* ── voice tab ── */
function renderVoiceTab(c){
  const tb=document.getElementById('tab-bar');
  tb.innerHTML=`
    <div class="m-tab active" data-tab="voice" onclick="switchTab('voice')">
      <i class="fas fa-phone"></i> Voice
    </div>
    <div class="m-tab" data-tab="history" onclick="switchTab('history')">
      <i class="fas fa-route"></i> Customer History
    </div>`;

  const tc=document.getElementById('tab-content');
  const openingLines=c.openingLines.map((l,i)=>`
    <div class="ai-line">
      <div class="ai-line-q">${l.q}</div>
      <div class="ai-line-hint">— ${l.hint}</div>
    </div>`).join('');

  const bullets=c.snapshotBullets.map(b=>`<div class="snap-bullet">${b}</div>`).join('');

  tc.innerHTML=`
    <div class="convo-lbl">
      <i class="fas fa-comment-dots" style="color:var(--blue)"></i>
      Voice · New conversation
    </div>

    <div class="connected-line">
      <i class="fas fa-circle"></i>
      You are now connected with ${c.name}.
    </div>

    <div class="int-note">
      <div class="int-note-hdr">
        <span class="int-note-tag">⚡ Internal note</span>
      </div>
      <div class="int-note-body">${c.internalNote}</div>
    </div>

    <div class="snapshot">
      <div class="snap-hdr">
        <div class="snap-av">${c.init}</div>
        <div>
          <div class="snap-name">${c.name}</div>
          <div class="snap-sub">${c.industry} · ${c.ref}</div>
          <div class="snap-tags">
            <span class="snap-tag">${c.industry}</span>
            <span class="snap-tag">Risk ${c.score}</span>
            <span class="snap-tag">${c.label}</span>
            <span class="snap-tag">${c.prod}</span>
          </div>
        </div>
      </div>
      <div class="snap-bullets">
        <div class="snap-lbl">Customer Snapshot</div>
        ${bullets}
      </div>
    </div>

    <div class="ai-lines">
      <div class="ai-lines-hdr">
        <i class="fas fa-robot"></i>
        ⚡ AI Suggested Opening Lines
      </div>
      ${openingLines}
    </div>`;
}

/* ── history tab ── */
function renderHistoryTab(c){
  const tb=document.getElementById('tab-bar');
  tb.innerHTML=`
    <div class="m-tab" data-tab="voice" onclick="switchTab('voice')">
      <i class="fas fa-phone"></i> Voice
    </div>
    <div class="m-tab active" data-tab="history" onclick="switchTab('history')">
      <i class="fas fa-route"></i> Customer History
    </div>`;

  const chColors={voice:'#0D6EFD',email:'#6C757D',chat:'#20C997',
    livechat:'#20C997',whatsapp:'#25D366',portal:'#6F42C1',
    callback:'#0D6EFD',social:'#E91E63',mobile:'#FF9800',auto:'#9C27B0'};

  const nodes=c.nodes.map((n,i)=>{
    const col=chColors[n.ch]||'#0D6EFD';
    const csat=n.csat?`<span class="tl-csat c${n.csat}">CSAT ${n.csat}/5</span>`:'';
    const esc=n.esc?'<span class="esc-tag">↑ ESC</span>':'';
    return `<div class="tl-node" id="hn${i}" onclick="openDrawer(${i})">
      <div class="tl-ic" style="border-color:${col};color:${col}">${n.icon}</div>
      <div class="tl-body">
        <div class="tl-top">
          <div class="tl-ttl">${n.ttl}</div>
          <div class="tl-dt">${n.dt}</div>
        </div>
        <div class="tl-ag">${n.ag}</div>
        <div class="tl-foot"><span>${n.sEmoji}</span>${csat}${esc}</div>
      </div>
    </div>`;
  }).join('');

  const pats=c.patterns.map(p=>`
    <tr><td class="pt-sev">${p.sev}</td>
        <td class="pt-lbl">${p.lbl}</td>
        <td class="pt-desc">${p.desc}</td></tr>`).join('');

  const acts=c.actions.map((a,i)=>`
    <div class="act-item">
      <div class="act-num">${i+1}</div>
      <div><span class="act-pri pri-${a.pri.toLowerCase()}">${a.pri}</span>
        <div class="act-txt">${a.txt}</div></div>
    </div>`).join('');

  // risk ring
  const circ=207, offset=circ - (c.score/10)*circ;

  document.getElementById('tab-content').innerHTML=`
    <div class="history-wrap">
      <div class="hist-tl">
        <div class="hist-tl-hdr"><i class="fas fa-route"></i> Journey Timeline</div>
        <div class="risk-pill" style="background:#FFF3F3;color:${c.col}">
          ${c.score} / 10 &nbsp;${c.label}
        </div>
        ${nodes}
      </div>
      <div class="hist-brief">
        <div class="brief-card">
          <div class="brief-card-hdr"><i class="fas fa-tachometer-alt"></i> Risk Assessment</div>
          <div class="risk-hero">
            <div class="risk-ring">
              <svg width="76" height="76" viewBox="0 0 76 76">
                <circle class="bg" cx="38" cy="38" r="33"/>
                <circle class="fg" id="score-fg" cx="38" cy="38" r="33" stroke="${c.col}"/>
              </svg>
              <div class="risk-inner">
                <div class="risk-num" style="color:${c.col}">${c.score}</div>
                <div class="risk-denom">/ 10</div>
              </div>
            </div>
            <div>
              <div class="risk-label-big" style="color:${c.col}">${c.label}</div>
              <div class="risk-sum">${c.scenario}</div>
            </div>
          </div>
        </div>
        <div class="brief-card">
          <div class="brief-card-hdr"><i class="fas fa-search"></i> Root Cause</div>
          <div style="font-size:12px;line-height:1.7;color:var(--text)">${c.rootCause||'Analysis in progress.'}</div>
        </div>
        <div class="brief-card">
          <div class="brief-card-hdr"><i class="fas fa-exclamation-triangle"></i> Failure Patterns</div>
          <table class="pat-tbl">${pats}</table>
        </div>
        <div class="brief-card">
          <div class="brief-card-hdr"><i class="fas fa-tasks"></i> Recommended Actions</div>
          ${acts}
        </div>
      </div>
    </div>`;

  // animate ring
  requestAnimationFrame(()=>{
    const fg=document.getElementById('score-fg');
    if(fg){fg.style.strokeDasharray=circ;fg.style.strokeDashoffset=offset;}
  });
}

/* ── right transcript ── */
function renderTranscript(c){
  const last=c.transcript;
  document.getElementById('tr-name').textContent=c.name;
  document.getElementById('tr-body').innerHTML=last.map(l=>{
    let cls=l.sp==='cust'?'b-cust':l.sp==='sys'?'b-sys':'b-agent';
    return `<div class="bubble ${cls}">
      <div class="bubble-sp">${l.nm}</div>
      <div class="bubble-txt">${l.tx}</div>
    </div>`;
  }).join('');
}

/* ── drawer (interaction detail) ── */
function openDrawer(idx){
  const c=CASES.find(x=>x.key===curKey);
  if(!c) return;
  const n=c.nodes[idx];
  document.querySelectorAll('.tl-node').forEach(el=>el.classList.remove('sel'));
  const nd=document.getElementById('hn'+idx);
  if(nd) nd.classList.add('sel');
  document.getElementById('dr-ic').textContent=n.icon;
  document.getElementById('dr-ttl').textContent=`Contact ${n.seq} — ${n.chNm}`;
  document.getElementById('dr-sub').textContent=`${n.dt} · ${n.ag}`;
  document.getElementById('dr-sent').textContent=`${n.sEmoji} ${sentLabel(n.sent)}`;
  document.getElementById('dr-csat').textContent=n.csat?`${n.csat}/5`:'—';
  document.getElementById('dr-dur').textContent=n.dur||'—';
  const escEl=document.getElementById('dr-esc');
  escEl.textContent=n.esc?'⚠️ Yes':'No';
  escEl.style.color=n.esc?'var(--red)':'inherit';
  document.getElementById('dr-out').textContent=n.out;
  document.getElementById('dr-body').innerHTML=n.lines.map(l=>{
    let cls=l.sp==='cust'?'b-cust':l.sp==='sys'?'b-sys':'b-agent';
    return `<div class="bubble ${cls}">
      <div class="bubble-sp">${l.nm}</div>
      <div class="bubble-txt">${l.tx}</div>
    </div>`;
  }).join('');
  document.getElementById('overlay').classList.add('on');
  document.getElementById('drawer').classList.add('on');
}

function closeDrawer(){
  document.getElementById('overlay').classList.remove('on');
  document.getElementById('drawer').classList.remove('on');
  document.querySelectorAll('.tl-node').forEach(el=>el.classList.remove('sel'));
}

const SENT_LABELS={neutral:'Neutral','slightly-neg':'Slightly Negative',
  neg:'Negative','very-neg':'Very Negative',pos:'Positive'};
function sentLabel(s){return SENT_LABELS[s]||s;}
</script>
</body>
</html>"""

if __name__ == "__main__":
    build()
