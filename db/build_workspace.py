"""
build_workspace.py
Reads customer_journey_forensics.db → writes agent-workspace.html
Styled with C26 / Cognigy design system (NICE canonical tokens)
Run from project root: python3 db/build_workspace.py
"""
import sqlite3, json, os, sys, re

DB_PATH  = "customer_journey_forensics.db"
OUT_FILE = "agent-workspace.html"
LOGO_SVG = "blue_smile.svg"

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
SENT_EMOJI = {"Neutral":"😐","Slightly Negative":"😕","Negative":"😞","Very Negative":"😡","Positive":"😊"}
SENT_KEY   = {"Neutral":"neutral","Slightly Negative":"slightly-neg","Negative":"neg","Very Negative":"very-neg","Positive":"pos"}
IND_EMOJI  = {"Insurance":"📋","Healthcare":"🏥","Banking":"🏦","ISP":"📡"}

def initials(n):
    p=n.split(); return (p[0][0]+p[-1][0]).upper() if len(p)>=2 else n[:2].upper()

def fmt_dur(s):
    if not s: return None
    m,sec=divmod(s,60); return f"{m} min" + (f" {sec}s" if sec else "")

def risk_col(s):
    return "#e32926" if s>=9 else ("#ffb800" if s>=7.5 else "#208337")

def parse_transcript(raw):
    if not raw: return [{"sp":"sys","nm":"System","tx":"No transcript available."}]
    out=[]
    for line in [l.strip() for l in raw.strip().split("\n") if l.strip()]:
        if ":" in line:
            spk,_,txt=line.partition(":"); spk,txt=spk.strip(),txt.strip()
            if not txt: continue
            lo=spk.lower()
            if any(w in lo for w in ["bot","system","ivr","portal","auto","notification"]): role="sys"
            elif any(w in lo for w in ["customer","michael","james","david","jennifer","robert","emily","sarah","anna","lisa","elena","terry"]): role="cust"
            else: role="agent"
            out.append({"sp":role,"nm":spk,"tx":txt})
        else:
            out.append({"sp":"sys","nm":"System","tx":line})
    return out or [{"sp":"sys","nm":"System","tx":raw[:200]}]

OPENER_MAP = {
    "Ownership Gap":       ("I can see this case has been waiting — I'm personally taking ownership right now.",        "establishes accountability immediately"),
    "Broken Promise":      ("A commitment was made that wasn't kept. Can you walk me through what you were told?",      "surfaces the broken promise — gives customer space to explain"),
    "Repeat Contact":      ("I can see you've had to contact us multiple times on this — that shouldn't happen.",       "acknowledges effort before offering a solution"),
    "Financial Impact":    ("I can see there was a billing impact on your account. Let me pull that up first.",         "addresses financial pain point immediately"),
    "SLA Breach":          ("Your case has exceeded our response SLA. I'm escalating priority right now.",             "signals urgency and accountability"),
    "Channel Switching":   ("You've reached us across several channels — I want to be your single point of contact.",   "reduces customer effort, builds trust"),
    "No Assessor Assigned":("Your claim is still pending an assessor. Let me check the assignment queue right now.",    "shows immediate action on the root blocker"),
    "Conflicting Information":("You received different information from different agents. Let me give you one confirmed answer.","resolves confusion with one authoritative voice"),
    "Treatment Delay":     ("I understand there is a health-related urgency here. I'm flagging this as clinical priority.", "critical signal for healthcare cases"),
    "Escalation Spiral":   ("This has been escalated multiple times. I'm the right person to resolve it today — no more transfers.", "stops the loop, builds confidence"),
    "No Proactive Communication":("I can see no update was sent while this was being processed — that should not have happened.","proactive acknowledgement of the silence"),
    "Billing Impact":      ("There was a billing concern on your account — let me check that immediately.",              "addresses financial pain point"),
}

def opening_lines(patterns):
    out,seen=[],set()
    for p in patterns:
        pt=p["pattern_type"]
        if pt in OPENER_MAP and pt not in seen:
            q,h=OPENER_MAP[pt]; out.append({"q":q,"hint":h,"pattern":pt}); seen.add(pt)
        if len(out)==3: break
    if not out:
        out=[{"q":"What would be the ideal outcome of this call for you?","hint":"open-ended — lets customer define success","pattern":""},
             {"q":"Can you walk me through what's happened so far?","hint":"full context before any solution","pattern":""}]
    return out[:3]

def snapshot_bullets(s,ints,fps):
    crit=sum(1 for p in fps if p["severity"]=="CRITICAL")
    last_ch=ints[-1]["channel_name"] if ints else "Unknown"
    first_dt=str(ints[0]["start_time"])[:10] if ints else "Unknown"
    return [
        f"{s['industry']} customer — {s['plan_type'] or 'Standard plan'} · {s['customer_id']}",
        f"{s['total_interactions']} prior contacts since {first_dt} — case unresolved",
        f"{crit} critical failure pattern{'s' if crit!=1 else ''} · Risk {s['risk_score']} {s['risk_label']}",
        f"Last contact via {last_ch} · {SENT_EMOJI.get(ints[-1]['overall_sentiment'],'😐')} {ints[-1]['overall_sentiment'] or 'Unknown'} sentiment",
    ]

def internal_note(s,ints):
    last=ints[-1]; ch=last.get("channel_name","phone"); n=len(ints)
    return (f"{s['customer_name']} has contacted {s['industry']} support "
            f"<strong>{n} time{'s' if n!=1 else ''}</strong> regarding: "
            f"<strong>{s['scenario_title']}</strong>. "
            f"Current risk score: <strong>{s['risk_score']} / 10 — {s['risk_label']}</strong>. "
            f"Most recent contact via <strong>{ch}</strong>. "
            f"{(s['root_cause'] or '')[:180]}.")

def build():
    if not os.path.exists(DB_PATH): print(f"ERROR: {DB_PATH} not found."); sys.exit(1)

    # Load logo SVG inline
    logo_svg = ""
    if os.path.exists(LOGO_SVG):
        with open(LOGO_SVG) as f: logo_svg = f.read().strip()

    db=sqlite3.connect(DB_PATH); db.row_factory=sqlite3.Row
    sessions=db.execute("""
        SELECT js.*,c.customer_name,c.customer_id as cust_id,c.plan_type,
               c.account_number,c.member_id,c.policy_number
        FROM journey_sessions js JOIN customers c ON js.customer_id=c.customer_id
        ORDER BY js.risk_score DESC
    """).fetchall()

    cases=[]
    for s in sessions:
        key=s["master_contact_id"]
        ints_r=db.execute("""
            SELECT i.*,ch.channel_name,a.agent_name
            FROM interactions i
            LEFT JOIN channels ch ON i.channel_id=ch.channel_id
            LEFT JOIN agents a ON i.agent_id=a.agent_id
            WHERE i.master_contact_id=? ORDER BY i.interaction_sequence
        """,(key,)).fetchall()
        if not ints_r: continue
        fps_r=db.execute("SELECT severity,pattern_type,pattern_description FROM failure_patterns WHERE master_contact_id=? ORDER BY CASE severity WHEN 'CRITICAL' THEN 1 ELSE 2 END",(key,)).fetchall()
        acts_r=db.execute("SELECT priority,action_text FROM recommended_actions WHERE master_contact_id=? ORDER BY CASE priority WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END",(key,)).fetchall()
        ints=[dict(i) for i in ints_r]; fps=[dict(f) for f in fps_r]; acts=[dict(a) for a in acts_r]

        nodes=[]
        for it in ints:
            ch_n=it.get("channel_name") or it.get("media_type","")
            sr=it.get("overall_sentiment") or "Neutral"
            nodes.append({"seq":it["interaction_sequence"],"ch":CH_KEY.get(ch_n,"voice"),
                "icon":CH_ICON.get(ch_n,"📋"),"chNm":ch_n,"ttl":f"{ch_n} — Contact {it['interaction_sequence']}",
                "dt":str(it.get("start_time",""))[:10],"ag":it.get("agent_name") or "Unassigned",
                "sent":SENT_KEY.get(sr,"neutral"),"sEmoji":SENT_EMOJI.get(sr,"😐"),
                "csat":it.get("csat"),"esc":bool(it.get("escalation_flag")),
                "dur":fmt_dur(it.get("duration_seconds")),
                "lines":parse_transcript(it.get("transcript","")),
                "out":it.get("outcome") or "—"})

        score=float(s["risk_score"]) if s["risk_score"] else 7.0
        ref=s["case_reference_id"] or s["policy_number"] or s["account_number"] or s["member_id"] or "N/A"
        cases.append({
            "key":key,"name":s["customer_name"],"init":initials(s["customer_name"]),
            "id":s["customer_id"],"ref":ref,"industry":s["industry"],
            "iEmoji":IND_EMOJI.get(s["industry"],"📋"),
            "prod":s["plan_type"] or s["industry"],"scenario":s["scenario_title"] or "",
            "score":score,"label":s["risk_label"] or "RISK","col":risk_col(score),
            "status":s["session_status"] or "Open","totalInts":s["total_interactions"] or len(ints),
            "internalNote":internal_note(dict(s),ints),
            "snapshotBullets":snapshot_bullets(dict(s),ints,fps),
            "openingLines":opening_lines(fps),
            "transcript":parse_transcript(ints[-1].get("transcript","")),
            "lastCh":ints[-1].get("channel_name","Phone Call"),
            "nodes":nodes,
            "patterns":[{"sev":"🔴" if p["severity"]=="CRITICAL" else "🟠","lbl":p["pattern_type"],"desc":p["pattern_description"]} for p in fps],
            "actions":[{"pri":a["priority"],"txt":a["action_text"]} for a in acts],
            "rootCause":s["root_cause"] or "",
        })
    db.close()

    js_data="const CASES = "+json.dumps(cases,indent=2,ensure_ascii=False)+";"
    html=HTML_TEMPLATE.replace("/*__DB_DATA__*/",js_data).replace("<!--__LOGO__-->",logo_svg)
    with open(OUT_FILE,"w") as f: f.write(html)
    print(f"✓  {OUT_FILE}  —  {len(cases)} cases  (C26 theme)")
    for c in cases:
        print(f"   {c['key']}  {c['name']:<22}  risk={c['score']}")

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Agent Workspace — NiCE CXone</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>
/* ── C26 / Cognigy design tokens (NICE canonical) ── */
:root{
  /* Primary blue */
  --primary-25:#ecf5fe; --primary-50:#e5f2ff; --primary-100:#d2e7fe;
  --primary-200:#a7d0fe; --primary-300:#5ea9fd; --primary-400:#308ff8;
  --primary-500:#126bce; --primary-600:#17569b; --primary-700:#164479;
  --primary-800:#0e2d4e; --primary-900:#0b233d;
  /* Neutral */
  --neutral-0:#ffffff; --neutral-25:#f9fafb; --neutral-50:#f3f4f6;
  --neutral-100:#e5e7eb; --neutral-200:#d1d5db; --neutral-300:#9ca3af;
  --neutral-400:#6b7280; --neutral-500:#4b5563; --neutral-600:#374151;
  --neutral-700:#1f2937; --neutral-800:#111827; --neutral-900:#000000;
  /* Status */
  --success:#208337; --success-bg:#effbf1; --success-border:#24943e;
  --warning:#ffb800; --warning-bg:#fff6e0; --warning-border:#a37a00;
  --error:#e32926;   --error-bg:#fdeaea;   --error-border:#e53935;
  /* Teal accent */
  --teal-300:#00bfa6; --teal-50:#bff4ec;
  /* Shadows */
  --shadow-xs:0 1px 2px #1f29370f; --shadow-sm:0 1px 3px #1f29371a;
  --shadow-md:0 4px 6px #1f29371f; --shadow-lg:0 10px 15px #1f293724;
  /* Radius */
  --r-xs:4px; --r-sm:6px; --r-md:8px; --r-lg:12px; --r-full:9999px;
  /* Spacing */
  --sp-1:4px; --sp-2:8px; --sp-3:12px; --sp-4:16px; --sp-5:20px;
  --sp-6:24px; --sp-7:32px;
  /* Layout */
  --sidebar-w:220px; --transcript-w:296px; --hdr-h:48px; --tabbar-h:40px;
}
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:'Inter',system-ui,-apple-system,sans-serif;
  height:100vh;overflow:hidden;display:flex;flex-direction:column;
  background:var(--neutral-50);color:var(--neutral-800);font-size:13px;
  -webkit-font-smoothing:antialiased;}

/* ══════════════════════════════════════
   HEADER
══════════════════════════════════════ */
.hdr{height:var(--hdr-h);background:var(--primary-800);
  display:flex;align-items:center;padding:0 var(--sp-4);gap:var(--sp-3);
  flex-shrink:0;z-index:100;box-shadow:var(--shadow-md);}
.hdr-logo{display:flex;align-items:center;gap:var(--sp-2);flex-shrink:0;}
.hdr-logo svg{width:22px;height:22px;}
.hdr-logo-name{color:var(--neutral-0);font-size:14px;font-weight:600;letter-spacing:-0.01em;}
.hdr-logo-name span{color:var(--primary-300);font-weight:700;}
.hdr-div{width:1px;height:20px;background:rgba(255,255,255,.15);flex-shrink:0;}
.hdr-prod{color:rgba(255,255,255,.55);font-size:12px;font-weight:500;white-space:nowrap;}
.hdr-tabs{display:flex;align-items:stretch;flex:1;height:100%;overflow:hidden;margin-left:var(--sp-2);}
.hdr-tab{display:flex;align-items:center;gap:var(--sp-1);padding:0 var(--sp-3);
  color:rgba(255,255,255,.5);font-size:12px;font-weight:500;cursor:pointer;
  border-bottom:2px solid transparent;white-space:nowrap;transition:all .18s;
  border-right:1px solid rgba(255,255,255,.06);}
.hdr-tab:hover{color:rgba(255,255,255,.8);}
.hdr-tab.active{color:var(--neutral-0);border-bottom-color:var(--primary-300);}
.hdr-tab .tc{opacity:0;font-size:9px;margin-left:4px;transition:opacity .15s;}
.hdr-tab:hover .tc{opacity:.5;}
.hdr-tab-add{display:flex;align-items:center;padding:0 var(--sp-3);
  color:rgba(255,255,255,.3);cursor:pointer;font-size:13px;transition:color .15s;}
.hdr-tab-add:hover{color:rgba(255,255,255,.6);}
.hdr-right{margin-left:auto;display:flex;align-items:center;gap:var(--sp-3);flex-shrink:0;}
.hdr-bell{color:rgba(255,255,255,.5);font-size:14px;position:relative;cursor:pointer;padding:4px;}
.hdr-bell:hover{color:var(--neutral-0);}
.hdr-bell-dot{position:absolute;top:2px;right:2px;width:8px;height:8px;
  border-radius:50%;background:var(--error);border:1.5px solid var(--primary-800);}
.in-call{display:flex;align-items:center;gap:var(--sp-2);
  background:rgba(32,131,55,.2);border:1px solid rgba(36,148,62,.35);
  border-radius:var(--r-sm);padding:4px var(--sp-3);
  color:#6ee2a0;font-size:11px;font-weight:600;}
.in-call-dot{width:7px;height:7px;border-radius:50%;background:var(--success);
  animation:pulse-g 1.6s infinite;}
@keyframes pulse-g{0%,100%{opacity:1;transform:scale(1);}50%{opacity:.5;transform:scale(.75);}}
.hdr-av{width:30px;height:30px;border-radius:50%;
  background:var(--primary-600);color:var(--neutral-0);
  font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;}

/* ══════════════════════════════════════
   BODY LAYOUT
══════════════════════════════════════ */
.body{flex:1;display:flex;overflow:hidden;}

/* ══════════════════════════════════════
   SIDEBAR
══════════════════════════════════════ */
.sidebar{width:var(--sidebar-w);background:var(--neutral-0);
  border-right:1px solid var(--neutral-100);display:flex;flex-direction:column;
  flex-shrink:0;box-shadow:var(--shadow-xs);}
.sb-top{padding:var(--sp-3) var(--sp-3) var(--sp-2);}
.sb-cases-lbl{font-size:11px;font-weight:700;color:var(--neutral-700);letter-spacing:.02em;}
.sb-cases-sub{font-size:10px;color:var(--neutral-400);margin-top:1px;}
.sb-new{margin:0 var(--sp-3) var(--sp-2);padding:6px var(--sp-3);
  border:1.5px dashed var(--neutral-200);border-radius:var(--r-sm);
  background:none;font-size:11px;font-weight:500;color:var(--neutral-400);
  cursor:pointer;width:calc(100% - 24px);transition:all .18s;text-align:center;}
.sb-new:hover{border-color:var(--primary-500);color:var(--primary-500);}
.sb-list{flex:1;overflow-y:auto;}
.sb-case{padding:var(--sp-2) var(--sp-3);cursor:pointer;
  border-left:3px solid transparent;transition:all .18s;
  border-bottom:1px solid var(--neutral-50);}
.sb-case:hover{background:var(--neutral-25);}
.sb-case.active{background:var(--primary-50);border-left-color:var(--primary-500);}
.sb-case-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:3px;}
.sb-case-name{font-size:12px;font-weight:600;color:var(--neutral-800);}
.sb-risk{font-size:9px;font-weight:700;padding:2px 6px;border-radius:var(--r-full);
  white-space:nowrap;}
.sb-risk.critical{background:var(--error-bg);color:var(--error);}
.sb-risk.warning{background:var(--warning-bg);color:#856404;}
.sb-case-desc{font-size:10px;color:var(--neutral-500);line-height:1.45;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;margin-bottom:4px;}
.sb-tags{display:flex;gap:4px;flex-wrap:wrap;}
.sb-tag{font-size:9px;padding:1px 6px;border-radius:var(--r-full);
  border:1px solid var(--neutral-100);color:var(--neutral-500);background:var(--neutral-50);}
.sb-tag.voice{background:var(--primary-50);color:var(--primary-600);border-color:var(--primary-100);}
.sb-ctrl{padding:var(--sp-2) var(--sp-3) var(--sp-3);border-top:1px solid var(--neutral-100);}
.sb-ctrl-row{display:flex;gap:var(--sp-2);}
.sb-btn{flex:1;padding:6px 4px;border:1px solid var(--neutral-200);border-radius:var(--r-sm);
  background:var(--neutral-0);font-size:10px;font-weight:600;cursor:pointer;
  display:flex;flex-direction:column;align-items:center;gap:2px;
  color:var(--neutral-500);transition:all .18s;}
.sb-btn:hover{background:var(--neutral-50);border-color:var(--neutral-300);}
.sb-btn.end{border-color:#fca5a5;background:var(--error-bg);color:var(--error);}
.sb-btn.end:hover{background:#fecaca;}
.sb-btn i{font-size:12px;}
.sb-nav{border-top:1px solid var(--neutral-100);padding:var(--sp-1) 0;}
.sb-nav-i{display:flex;align-items:center;gap:var(--sp-2);padding:7px var(--sp-3);
  color:var(--neutral-400);cursor:pointer;font-size:11px;font-weight:500;
  transition:all .18s;border-radius:0;}
.sb-nav-i:hover{background:var(--neutral-50);color:var(--neutral-700);}
.sb-nav-i.on{color:var(--primary-500);background:var(--primary-50);}
.sb-nav-i i{width:16px;text-align:center;font-size:13px;}
.sb-nav-badge{margin-left:auto;background:var(--error);color:#fff;
  font-size:9px;font-weight:700;padding:1px 5px;border-radius:var(--r-full);}

/* ══════════════════════════════════════
   MAIN AREA
══════════════════════════════════════ */
.main{flex:1;display:flex;flex-direction:column;overflow:hidden;min-width:0;}
.tab-bar{height:var(--tabbar-h);background:var(--neutral-0);
  border-bottom:1px solid var(--neutral-100);display:flex;align-items:stretch;
  flex-shrink:0;padding:0 var(--sp-1);}
.m-tab{display:flex;align-items:center;gap:var(--sp-1);padding:0 var(--sp-4);
  font-size:12px;font-weight:500;cursor:pointer;color:var(--neutral-400);
  border-bottom:2px solid transparent;white-space:nowrap;transition:all .18s;}
.m-tab:hover{color:var(--neutral-600);}
.m-tab.active{color:var(--primary-500);border-bottom-color:var(--primary-500);font-weight:600;}
.tab-content{flex:1;overflow-y:auto;padding:var(--sp-4) var(--sp-5);}

/* ══════════════════════════════════════
   VOICE TAB
══════════════════════════════════════ */
.conv-lbl{font-size:10px;font-weight:700;color:var(--neutral-400);
  text-transform:uppercase;letter-spacing:.06em;margin-bottom:var(--sp-3);
  display:flex;align-items:center;gap:6px;}
.connected-line{display:flex;align-items:center;gap:var(--sp-2);
  padding:var(--sp-2) var(--sp-3);background:var(--success-bg);
  border:1px solid var(--success-border);border-radius:var(--r-md);
  margin-bottom:var(--sp-3);font-size:12px;color:var(--success);font-weight:600;}
/* Internal Note */
.int-note{background:var(--neutral-0);border:1px solid var(--success-border);
  border-left:3px solid var(--success);border-radius:var(--r-md);
  padding:var(--sp-3) var(--sp-4);margin-bottom:var(--sp-3);
  box-shadow:var(--shadow-xs);}
.note-tag{display:inline-flex;align-items:center;gap:5px;
  background:var(--success-bg);border:1px solid var(--success-border);
  color:var(--success);font-size:10px;font-weight:700;
  padding:2px var(--sp-2);border-radius:var(--r-xs);letter-spacing:.03em;margin-bottom:var(--sp-2);}
.note-body{font-size:12px;color:var(--neutral-700);line-height:1.7;}
.note-body strong{color:var(--neutral-800);font-weight:600;}
/* Snapshot */
.snapshot{background:var(--neutral-0);border:1px solid var(--neutral-100);
  border-radius:var(--r-md);padding:var(--sp-3) var(--sp-4);
  margin-bottom:var(--sp-3);box-shadow:var(--shadow-xs);}
.snap-hdr{display:flex;align-items:center;gap:var(--sp-3);margin-bottom:var(--sp-3);}
.snap-av{width:38px;height:38px;border-radius:50%;
  background:var(--primary-50);color:var(--primary-600);
  font-size:13px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;}
.snap-name{font-size:14px;font-weight:600;color:var(--neutral-800);}
.snap-sub{font-size:11px;color:var(--neutral-400);margin-top:1px;}
.snap-tags{display:flex;gap:4px;flex-wrap:wrap;margin-top:5px;}
.snap-tag{font-size:10px;padding:2px 7px;border-radius:var(--r-full);
  border:1px solid var(--neutral-100);color:var(--neutral-500);background:var(--neutral-50);}
.snap-sec-lbl{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;
  color:var(--neutral-400);margin-bottom:var(--sp-2);}
.snap-bullet{display:flex;align-items:flex-start;gap:6px;
  font-size:12px;color:var(--neutral-700);padding:3px 0;line-height:1.5;}
.snap-bullet::before{content:"·";color:var(--primary-400);font-weight:700;flex-shrink:0;font-size:16px;line-height:1.1;}
/* AI Opening Lines */
.ai-lines{background:var(--neutral-0);border:1px solid var(--neutral-100);
  border-radius:var(--r-md);padding:var(--sp-3) var(--sp-4);
  margin-bottom:var(--sp-3);box-shadow:var(--shadow-xs);}
.ai-lines-hdr{display:flex;align-items:center;gap:var(--sp-2);
  margin-bottom:var(--sp-3);font-size:11px;font-weight:700;color:var(--neutral-700);}
.ai-lines-hdr i{color:var(--primary-500);}
.ai-line{padding:var(--sp-2) var(--sp-3);border:1px solid var(--neutral-100);
  border-radius:var(--r-sm);margin-bottom:var(--sp-2);cursor:pointer;
  transition:all .18s;background:var(--neutral-25);}
.ai-line:last-child{margin-bottom:0;}
.ai-line:hover{border-color:var(--primary-300);background:var(--primary-50);}
.ai-line-q{font-size:12px;color:var(--neutral-800);line-height:1.5;margin-bottom:2px;}
.ai-line-hint{font-size:10px;color:var(--neutral-400);font-style:italic;}

/* ══════════════════════════════════════
   CUSTOMER HISTORY TAB
══════════════════════════════════════ */
.hist-wrap{display:flex;gap:var(--sp-4);}
.hist-tl{width:35%;min-width:230px;}
.hist-tl-hdr{font-size:10px;font-weight:700;color:var(--neutral-400);
  text-transform:uppercase;letter-spacing:.06em;margin-bottom:var(--sp-2);
  display:flex;align-items:center;gap:5px;}
.risk-pill{display:inline-flex;align-items:center;gap:5px;
  padding:4px var(--sp-3);border-radius:var(--r-full);
  font-size:11px;font-weight:700;margin-bottom:var(--sp-3);}
.tl-node{display:flex;gap:var(--sp-2);padding:var(--sp-2);
  border-radius:var(--r-sm);cursor:pointer;transition:all .18s;
  position:relative;margin-bottom:1px;}
.tl-node:hover{background:var(--neutral-50);}
.tl-node.sel{background:var(--primary-50);outline:1.5px solid var(--primary-200);}
.tl-node:not(:last-child)::after{content:'';position:absolute;
  left:23px;top:40px;width:2px;height:calc(100% - 12px);
  background:var(--neutral-100);z-index:0;}
.tl-ic{width:30px;height:30px;border-radius:50%;border:2px solid var(--neutral-100);
  background:var(--neutral-0);display:flex;align-items:center;justify-content:center;
  font-size:12px;flex-shrink:0;z-index:1;position:relative;}
.tl-body{flex:1;min-width:0;}
.tl-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:1px;}
.tl-ttl{font-size:11px;font-weight:600;color:var(--neutral-700);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.tl-dt{font-size:9px;color:var(--neutral-400);white-space:nowrap;margin-left:4px;flex-shrink:0;}
.tl-ag{font-size:10px;color:var(--neutral-400);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-bottom:3px;}
.tl-foot{display:flex;gap:4px;align-items:center;flex-wrap:wrap;}
.tl-csat{font-size:9px;padding:1px 5px;border-radius:var(--r-full);font-weight:700;}
.c1{background:var(--error-bg);color:var(--error);}
.c2{background:var(--warning-bg);color:#856404;}
.c3{background:#fffde7;color:#795b00;}
.c4{background:var(--success-bg);color:var(--success);}
.c5{background:#e8f5e9;color:#1b5e20;}
.esc-tag{font-size:9px;background:var(--error-bg);color:var(--error);
  padding:1px 5px;border-radius:var(--r-xs);font-weight:700;}
/* AI Brief */
.hist-brief{flex:1;display:flex;flex-direction:column;gap:var(--sp-3);min-width:0;}
.brief-card{background:var(--neutral-0);border:1px solid var(--neutral-100);
  border-radius:var(--r-md);padding:var(--sp-3) var(--sp-4);box-shadow:var(--shadow-xs);}
.brief-hdr{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;
  color:var(--neutral-400);margin-bottom:var(--sp-3);
  display:flex;align-items:center;gap:5px;}
.brief-hdr i{color:var(--primary-500);}
.risk-hero{display:flex;align-items:center;gap:var(--sp-4);}
.risk-ring{width:72px;height:72px;position:relative;flex-shrink:0;}
.risk-ring svg{transform:rotate(-90deg);}
.rr-bg{fill:none;stroke:var(--neutral-100);stroke-width:7;}
.rr-fg{fill:none;stroke-width:7;stroke-linecap:round;
  stroke-dasharray:201;stroke-dashoffset:201;transition:stroke-dashoffset 1.3s ease;}
.rr-inner{position:absolute;inset:0;display:flex;flex-direction:column;
  align-items:center;justify-content:center;}
.rr-num{font-size:17px;font-weight:700;line-height:1;}
.rr-denom{font-size:9px;color:var(--neutral-400);}
.risk-lbl{font-size:17px;font-weight:700;margin-bottom:4px;}
.risk-scenario{font-size:12px;color:var(--neutral-500);line-height:1.5;}
.pat-tbl{width:100%;border-collapse:collapse;}
.pat-tbl tr{border-bottom:1px solid var(--neutral-50);}
.pat-tbl tr:last-child{border-bottom:none;}
.pat-tbl td{padding:6px 3px;font-size:11px;vertical-align:top;}
.pt-sev{width:18px;}.pt-lbl{font-weight:600;width:36%;padding-right:8px;color:var(--neutral-700);}
.pt-desc{color:var(--neutral-400);}
.act-item{display:flex;gap:var(--sp-2);padding:var(--sp-2) 0;
  border-bottom:1px solid var(--neutral-50);align-items:flex-start;}
.act-item:last-child{border-bottom:none;}
.act-num{width:20px;height:20px;border-radius:50%;background:var(--primary-500);
  color:var(--neutral-0);font-size:10px;font-weight:700;
  display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px;}
.act-pri{font-size:9px;font-weight:700;text-transform:uppercase;
  padding:2px 5px;border-radius:var(--r-xs);display:inline-block;margin-bottom:3px;}
.pri-critical{background:var(--error-bg);color:var(--error);}
.pri-high{background:var(--warning-bg);color:#92400e;}
.pri-medium{background:#fffde7;color:#795b00;}
.act-txt{font-size:12px;line-height:1.5;color:var(--neutral-700);}

/* ══════════════════════════════════════
   TRANSCRIPT PANEL
══════════════════════════════════════ */
.tr-panel{width:var(--transcript-w);background:var(--neutral-0);
  border-left:1px solid var(--neutral-100);display:flex;flex-direction:column;flex-shrink:0;}
.tr-hdr{padding:var(--sp-2) var(--sp-3);background:var(--primary-800);
  display:flex;align-items:center;justify-content:space-between;flex-shrink:0;}
.tr-hdr-left .tr-lbl{font-size:9px;font-weight:700;text-transform:uppercase;
  letter-spacing:.08em;color:rgba(255,255,255,.5);}
.tr-hdr-left .tr-name{font-size:12px;font-weight:600;color:var(--neutral-0);margin-top:1px;}
.tr-live{display:flex;align-items:center;gap:5px;font-size:10px;font-weight:700;color:#6ee2a0;}
.tr-live-dot{width:6px;height:6px;border-radius:50%;background:var(--success);animation:pulse-g 1.5s infinite;}
.tr-body{flex:1;overflow-y:auto;padding:var(--sp-3);}
.bubble{margin-bottom:var(--sp-2);}
.bubble-sp{font-size:9px;font-weight:700;color:var(--neutral-300);
  margin-bottom:2px;text-transform:uppercase;letter-spacing:.05em;}
.bubble-txt{padding:var(--sp-2) var(--sp-3);border-radius:var(--r-md);
  font-size:11px;line-height:1.6;max-width:92%;white-space:pre-line;}
.b-cust .bubble-sp{color:var(--primary-400);}
.b-cust .bubble-txt{background:var(--primary-50);color:var(--neutral-700);}
.b-agent .bubble-sp{color:var(--neutral-400);}
.b-agent .bubble-txt{background:var(--neutral-50);color:var(--neutral-700);}
.b-sys .bubble-sp{color:var(--success);}
.b-sys .bubble-txt{background:var(--success-bg);color:#155724;font-style:italic;font-size:10px;}

/* ══════════════════════════════════════
   DRAWER
══════════════════════════════════════ */
.overlay{position:fixed;inset:0;background:rgba(17,24,39,.3);z-index:200;
  opacity:0;pointer-events:none;transition:opacity .25s;}
.overlay.on{opacity:1;pointer-events:all;}
.drawer{position:fixed;right:0;top:0;bottom:0;width:400px;background:var(--neutral-0);
  box-shadow:var(--shadow-2xl);z-index:201;transform:translateX(100%);
  transition:transform .3s cubic-bezier(.4,0,.2,1);display:flex;flex-direction:column;}
.drawer.on{transform:translateX(0);}
.dr-hdr{padding:var(--sp-3) var(--sp-4);background:var(--primary-800);
  display:flex;align-items:center;gap:var(--sp-2);flex-shrink:0;}
.dr-ic{font-size:18px;}
.dr-info h3{font-size:13px;font-weight:600;color:var(--neutral-0);}
.dr-info p{font-size:10px;color:rgba(255,255,255,.5);}
.dr-close{margin-left:auto;width:26px;height:26px;border-radius:var(--r-sm);
  background:rgba(255,255,255,.1);color:var(--neutral-0);border:none;cursor:pointer;
  display:flex;align-items:center;justify-content:center;font-size:12px;transition:all .15s;}
.dr-close:hover{background:rgba(255,255,255,.2);}
.dr-meta{padding:var(--sp-2) var(--sp-4);background:var(--neutral-25);
  border-bottom:1px solid var(--neutral-100);display:flex;gap:var(--sp-4);flex-shrink:0;}
.dr-mi .dr-ml{font-size:9px;text-transform:uppercase;letter-spacing:.05em;
  color:var(--neutral-400);font-weight:700;}
.dr-mi .dr-mv{font-size:12px;font-weight:600;margin-top:1px;color:var(--neutral-700);}
.dr-body{flex:1;overflow-y:auto;padding:var(--sp-3) var(--sp-4);}
.dr-out{padding:var(--sp-3) var(--sp-4);border-top:1px solid var(--neutral-100);flex-shrink:0;}
.dr-out-lbl{font-size:9px;text-transform:uppercase;letter-spacing:.05em;
  color:var(--neutral-400);font-weight:700;margin-bottom:3px;}
.dr-out-txt{font-size:12px;line-height:1.5;color:var(--neutral-700);}

/* scrollbar */
::-webkit-scrollbar{width:4px;}::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{background:var(--neutral-200);border-radius:var(--r-full);}
::-webkit-scrollbar-thumb:hover{background:var(--neutral-300);}
</style>
</head>
<body>

<!-- HEADER -->
<header class="hdr">
  <div class="hdr-logo">
    <!--__LOGO__-->
    <span class="hdr-logo-name">NiCE <span>CXone</span></span>
  </div>
  <div class="hdr-div"></div>
  <span class="hdr-prod">Agent Workspace</span>
  <div class="hdr-tabs" id="hdr-tabs"></div>
  <div class="hdr-right">
    <div class="hdr-bell"><i class="fas fa-bell"></i><div class="hdr-bell-dot"></div></div>
    <div class="in-call" id="in-call">
      <div class="in-call-dot"></div>
      <span>In a Call</span>
      <span id="call-timer">00:00:00</span>
    </div>
    <div class="hdr-av" id="hdr-av">SR</div>
  </div>
</header>

<!-- BODY -->
<div class="body">

  <!-- SIDEBAR -->
  <div class="sidebar">
    <div class="sb-top">
      <div class="sb-cases-lbl">Cases</div>
      <div class="sb-cases-sub">3 completed today</div>
    </div>
    <button class="sb-new"><i class="fas fa-plus" style="font-size:10px"></i>  New Case</button>
    <div class="sb-list" id="sb-list"></div>
    <div class="sb-ctrl">
      <div class="sb-ctrl-row">
        <button class="sb-btn"><i class="fas fa-random"></i><span>Transfer</span></button>
        <button class="sb-btn"><i class="fas fa-pause"></i><span>Hold</span></button>
        <button class="sb-btn end"><i class="fas fa-phone-slash"></i><span>End Call</span></button>
      </div>
    </div>
    <nav class="sb-nav">
      <div class="sb-nav-i on"><i class="fas fa-headset"></i>Control Center</div>
      <div class="sb-nav-i"><i class="fas fa-list-ul"></i>Queue<span class="sb-nav-badge">33</span></div>
      <div class="sb-nav-i"><i class="fas fa-address-book"></i>Directory</div>
      <div class="sb-nav-i"><i class="fas fa-calendar-alt"></i>Schedule</div>
      <div class="sb-nav-i"><i class="fas fa-cog"></i>Settings</div>
    </nav>
  </div>

  <!-- MAIN -->
  <div class="main">
    <div class="tab-bar" id="tab-bar"></div>
    <div class="tab-content" id="tab-content"></div>
  </div>

  <!-- TRANSCRIPT -->
  <div class="tr-panel">
    <div class="tr-hdr">
      <div class="tr-hdr-left">
        <div class="tr-lbl">Call Transcript</div>
        <div class="tr-name" id="tr-name">—</div>
      </div>
      <div class="tr-live"><div class="tr-live-dot"></div>LIVE</div>
    </div>
    <div class="tr-body" id="tr-body"></div>
  </div>
</div>

<!-- DRAWER -->
<div class="overlay" id="overlay" onclick="closeDrawer()"></div>
<div class="drawer" id="drawer">
  <div class="dr-hdr">
    <div class="dr-ic" id="dr-ic">📞</div>
    <div class="dr-info"><h3 id="dr-ttl">—</h3><p id="dr-sub">—</p></div>
    <button class="dr-close" onclick="closeDrawer()"><i class="fas fa-times"></i></button>
  </div>
  <div class="dr-meta">
    <div class="dr-mi"><div class="dr-ml">Sentiment</div><div class="dr-mv" id="dr-sent">—</div></div>
    <div class="dr-mi"><div class="dr-ml">CSAT</div><div class="dr-mv" id="dr-csat">—</div></div>
    <div class="dr-mi"><div class="dr-ml">Duration</div><div class="dr-mv" id="dr-dur">—</div></div>
    <div class="dr-mi"><div class="dr-ml">Escalated</div><div class="dr-mv" id="dr-esc">No</div></div>
  </div>
  <div class="dr-body" id="dr-body"></div>
  <div class="dr-out"><div class="dr-out-lbl">Outcome</div><div class="dr-out-txt" id="dr-out">—</div></div>
</div>

<script>
/*__DB_DATA__*/

let curKey=CASES[0]?.key, curTab='voice', callSec=0;

(function init(){
  buildSidebar();
  selectCase(curKey);
  setInterval(()=>{
    callSec++;
    const h=Math.floor(callSec/3600),m=Math.floor((callSec%3600)/60),s=callSec%60;
    const el=document.getElementById('call-timer');
    if(el) el.textContent=[h,m,s].map(x=>String(x).padStart(2,'0')).join(':');
  },1000);
})();

function buildSidebar(){
  document.getElementById('sb-list').innerHTML=CASES.map(c=>`
    <div class="sb-case${c.key===curKey?' active':''}" id="sb-${c.key}" onclick="selectCase('${c.key}')">
      <div class="sb-case-top">
        <div class="sb-case-name">${c.name}</div>
        <div class="sb-risk ${c.score>=9?'critical':'warning'}">${c.score} ${c.label}</div>
      </div>
      <div class="sb-case-desc">${c.iEmoji} ${c.scenario}</div>
      <div class="sb-tags">
        <span class="sb-tag voice">VOICE</span>
        <span class="sb-tag">${c.industry}</span>
      </div>
    </div>`).join('');
}

function selectCase(key){
  curKey=key; curTab='voice';
  document.querySelectorAll('.sb-case').forEach(el=>el.classList.remove('active'));
  const sb=document.getElementById('sb-'+key);
  if(sb){sb.classList.add('active');sb.scrollIntoView({block:'nearest'});}
  const c=CASES.find(x=>x.key===key); if(!c) return;
  renderHdrTabs(c); renderTranscript(c); renderVoiceTab(c); callSec=0; closeDrawer();
}

function renderHdrTabs(c){
  document.getElementById('hdr-tabs').innerHTML=`
    <div class="hdr-tab active">
      <i class="fas fa-user" style="font-size:10px"></i>${c.name}<span class="tc">✕</span>
    </div>
    <div class="hdr-tab${curTab==='voice'?' active':''}" onclick="switchTab('voice')">
      <i class="fas fa-phone" style="font-size:10px"></i>Voice
    </div>
    <div class="hdr-tab${curTab==='history'?' active':''}" onclick="switchTab('history')">
      <i class="fas fa-route" style="font-size:10px"></i>Customer History
    </div>
    <div class="hdr-tab-add"><i class="fas fa-plus"></i></div>`;
  document.getElementById('hdr-av').textContent=c.init;
  document.getElementById('tr-name').textContent=c.name;
}

function switchTab(tab){
  curTab=tab;
  const c=CASES.find(x=>x.key===curKey); if(!c) return;
  renderHdrTabs(c);
  document.querySelectorAll('.m-tab').forEach(el=>el.classList.toggle('active',el.dataset.tab===tab));
  if(tab==='voice')   renderVoiceTab(c);
  if(tab==='history') renderHistoryTab(c);
}

function renderVoiceTab(c){
  document.getElementById('tab-bar').innerHTML=`
    <div class="m-tab active" data-tab="voice" onclick="switchTab('voice')"><i class="fas fa-phone"></i>Voice</div>
    <div class="m-tab" data-tab="history" onclick="switchTab('history')"><i class="fas fa-route"></i>Customer History</div>`;

  const bullets=c.snapshotBullets.map(b=>`<div class="snap-bullet">${b}</div>`).join('');
  const lines=c.openingLines.map(l=>`
    <div class="ai-line">
      <div class="ai-line-q">${l.q}</div>
      <div class="ai-line-hint">— ${l.hint}</div>
    </div>`).join('');

  document.getElementById('tab-content').innerHTML=`
    <div class="conv-lbl"><i class="fas fa-comment-dots" style="color:var(--primary-400)"></i>Voice · New conversation</div>
    <div class="connected-line"><i class="fas fa-check-circle"></i>You are now connected with ${c.name}.</div>
    <div class="int-note">
      <div class="note-tag"><i class="fas fa-bolt" style="font-size:9px"></i>Internal note</div>
      <div class="note-body">${c.internalNote}</div>
    </div>
    <div class="snapshot">
      <div class="snap-hdr">
        <div class="snap-av">${c.init}</div>
        <div>
          <div class="snap-name">${c.name}</div>
          <div class="snap-sub">${c.industry} · ${c.ref}</div>
          <div class="snap-tags">
            <span class="snap-tag">${c.industry}</span>
            <span class="snap-tag">${c.prod}</span>
            <span class="snap-tag" style="background:var(--error-bg);color:var(--error);border-color:#fca5a5">Risk ${c.score} ${c.label}</span>
          </div>
        </div>
      </div>
      <div class="snap-sec-lbl">Customer Snapshot</div>
      ${bullets}
    </div>
    <div class="ai-lines">
      <div class="ai-lines-hdr"><i class="fas fa-robot"></i>⚡ AI Suggested Opening Lines</div>
      ${lines}
    </div>`;
}

function renderHistoryTab(c){
  document.getElementById('tab-bar').innerHTML=`
    <div class="m-tab" data-tab="voice" onclick="switchTab('voice')"><i class="fas fa-phone"></i>Voice</div>
    <div class="m-tab active" data-tab="history" onclick="switchTab('history')"><i class="fas fa-route"></i>Customer History</div>`;

  const chCol={voice:'#126bce',email:'#6b7280',chat:'#00bfa6',livechat:'#00bfa6',
    whatsapp:'#25d366',portal:'#556cd6',callback:'#126bce',social:'#e754a8',mobile:'#ffb800',auto:'#9ca3af'};

  const nodes=c.nodes.map((n,i)=>{
    const col=chCol[n.ch]||'#126bce';
    const csat=n.csat?`<span class="tl-csat c${n.csat}">CSAT ${n.csat}/5</span>`:'';
    const esc=n.esc?'<span class="esc-tag">↑ ESC</span>':'';
    return `<div class="tl-node" id="hn${i}" onclick="openDrawer(${i})">
      <div class="tl-ic" style="border-color:${col};color:${col}">${n.icon}</div>
      <div class="tl-body">
        <div class="tl-top"><div class="tl-ttl">${n.ttl}</div><div class="tl-dt">${n.dt}</div></div>
        <div class="tl-ag">${n.ag}</div>
        <div class="tl-foot"><span>${n.sEmoji}</span>${csat}${esc}</div>
      </div>
    </div>`;
  }).join('');

  const pats=c.patterns.map(p=>`
    <tr><td class="pt-sev">${p.sev}</td><td class="pt-lbl">${p.lbl}</td><td class="pt-desc">${p.desc}</td></tr>`).join('');

  const acts=c.actions.map((a,i)=>`
    <div class="act-item">
      <div class="act-num">${i+1}</div>
      <div><span class="act-pri pri-${a.pri.toLowerCase()}">${a.pri}</span><div class="act-txt">${a.txt}</div></div>
    </div>`).join('');

  const circ=201, offset=circ-(c.score/10)*circ;
  document.getElementById('tab-content').innerHTML=`
    <div class="hist-wrap">
      <div class="hist-tl">
        <div class="hist-tl-hdr"><i class="fas fa-route"></i>Journey Timeline</div>
        <div class="risk-pill" style="background:${c.col}18;color:${c.col};border:1px solid ${c.col}40">
          ${c.score} / 10 &nbsp; ${c.label}
        </div>
        ${nodes}
      </div>
      <div class="hist-brief">
        <div class="brief-card">
          <div class="brief-hdr"><i class="fas fa-tachometer-alt"></i>Risk Assessment</div>
          <div class="risk-hero">
            <div class="risk-ring">
              <svg width="72" height="72" viewBox="0 0 72 72">
                <circle class="rr-bg" cx="36" cy="36" r="32"/>
                <circle class="rr-fg" id="score-fg" cx="36" cy="36" r="32" stroke="${c.col}"/>
              </svg>
              <div class="rr-inner">
                <div class="rr-num" style="color:${c.col}">${c.score}</div>
                <div class="rr-denom">/ 10</div>
              </div>
            </div>
            <div>
              <div class="risk-lbl" style="color:${c.col}">${c.label}</div>
              <div class="risk-scenario">${c.scenario}</div>
            </div>
          </div>
        </div>
        <div class="brief-card">
          <div class="brief-hdr"><i class="fas fa-search"></i>Root Cause</div>
          <div style="font-size:12px;line-height:1.7;color:var(--neutral-600)">${c.rootCause||'Analysis in progress.'}</div>
        </div>
        <div class="brief-card">
          <div class="brief-hdr"><i class="fas fa-exclamation-triangle"></i>Failure Patterns</div>
          <table class="pat-tbl">${pats}</table>
        </div>
        <div class="brief-card">
          <div class="brief-hdr"><i class="fas fa-tasks"></i>Recommended Actions</div>
          ${acts}
        </div>
      </div>
    </div>`;

  requestAnimationFrame(()=>{
    const fg=document.getElementById('score-fg');
    if(fg){fg.style.strokeDasharray=circ;fg.style.strokeDashoffset=offset;}
  });
}

function renderTranscript(c){
  document.getElementById('tr-name').textContent=c.name;
  document.getElementById('tr-body').innerHTML=c.transcript.map(l=>{
    const cls=l.sp==='cust'?'b-cust':l.sp==='sys'?'b-sys':'b-agent';
    return `<div class="bubble ${cls}">
      <div class="bubble-sp">${l.nm}</div>
      <div class="bubble-txt">${l.tx}</div>
    </div>`;
  }).join('');
}

function openDrawer(idx){
  const c=CASES.find(x=>x.key===curKey); if(!c) return;
  const n=c.nodes[idx];
  document.querySelectorAll('.tl-node').forEach(el=>el.classList.remove('sel'));
  const nd=document.getElementById('hn'+idx); if(nd) nd.classList.add('sel');
  document.getElementById('dr-ic').textContent=n.icon;
  document.getElementById('dr-ttl').textContent=`Contact ${n.seq} — ${n.chNm}`;
  document.getElementById('dr-sub').textContent=`${n.dt} · ${n.ag}`;
  document.getElementById('dr-sent').textContent=`${n.sEmoji} ${sentLabel(n.sent)}`;
  document.getElementById('dr-csat').textContent=n.csat?`${n.csat}/5`:'—';
  document.getElementById('dr-dur').textContent=n.dur||'—';
  const ee=document.getElementById('dr-esc');
  ee.textContent=n.esc?'⚠️ Yes':'No'; ee.style.color=n.esc?'var(--error)':'inherit';
  document.getElementById('dr-out').textContent=n.out;
  document.getElementById('dr-body').innerHTML=n.lines.map(l=>{
    const cls=l.sp==='cust'?'b-cust':l.sp==='sys'?'b-sys':'b-agent';
    return `<div class="bubble ${cls}"><div class="bubble-sp">${l.nm}</div><div class="bubble-txt">${l.tx}</div></div>`;
  }).join('');
  document.getElementById('overlay').classList.add('on');
  document.getElementById('drawer').classList.add('on');
}
function closeDrawer(){
  document.getElementById('overlay').classList.remove('on');
  document.getElementById('drawer').classList.remove('on');
  document.querySelectorAll('.tl-node').forEach(el=>el.classList.remove('sel'));
}
const SL={neutral:'Neutral','slightly-neg':'Slightly Negative',neg:'Negative','very-neg':'Very Negative',pos:'Positive'};
function sentLabel(s){return SL[s]||s;}
</script>
</body>
</html>"""

if __name__ == "__main__":
    build()
