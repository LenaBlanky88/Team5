"""
build_agent.py
Reads customer_journey_forensics.db → writes agent-view.html
Agent View: single ongoing call, large left panel, full detail.
Run from project root: python3 db/build_agent.py
"""
import sqlite3, json, os, sys

DB_PATH  = "customer_journey_forensics.db"
OUT_FILE = "agent-view.html"
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
            elif any(w in lo for w in ["customer","michael","james","david","jennifer","robert","emily","sarah","anna","lisa","elena"]): role="cust"
            else: role="agent"
            out.append({"sp":role,"nm":spk,"tx":txt})
        else:
            out.append({"sp":"sys","nm":"System","tx":line})
    return out or [{"sp":"sys","nm":"System","tx":raw[:200]}]

OPENER_MAP = {
    "Ownership Gap":          ("I'm personally taking ownership of this right now — no more transfers.",      "establishes accountability immediately"),
    "Broken Promise":         ("A commitment was made that wasn't kept. What were you told exactly?",         "surfaces the promise — lets customer clarify"),
    "Repeat Contact":         ("I can see you've had to contact us multiple times — that shouldn't happen.",  "acknowledges frustration before solving"),
    "Financial Impact":       ("I can see there was a billing impact. Let me pull that up right now.",        "addresses financial pain point first"),
    "SLA Breach":             ("Your case has exceeded our response SLA. I'm escalating priority now.",      "signals urgency and accountability"),
    "Channel Switching":      ("You've reached us across several channels — I'll be your single contact.",    "reduces effort, builds trust"),
    "No Assessor Assigned":   ("Your claim is still pending an assessor. Let me check the queue now.",       "immediate action on the root blocker"),
    "Conflicting Information":("You got different answers from different agents. Let me give you one confirmed answer.", "one voice, one truth"),
    "Treatment Delay":        ("I understand there's a health urgency. I'm flagging this as clinical priority.", "critical for healthcare cases"),
    "Escalation Spiral":      ("This has been escalated too many times. I'm the right person to resolve this today.", "stops the loop"),
    "No Proactive Communication":("No update was sent while this was processing — that should not have happened.", "proactive acknowledgement"),
    "Billing Impact":         ("There was a billing concern — let me check that immediately.",                 "financial pain point addressed first"),
}

def opening_lines(patterns):
    out,seen=[],set()
    for p in patterns:
        pt=p["pattern_type"]
        if pt in OPENER_MAP and pt not in seen:
            q,h=OPENER_MAP[pt]; out.append({"q":q,"hint":h}); seen.add(pt)
        if len(out)==3: break
    if not out:
        out=[{"q":"What would be the ideal outcome of this call for you?","hint":"open-ended — lets customer define success"},
             {"q":"Can you walk me through what's happened so far?","hint":"full context before any solution"}]
    return out[:3]

def snapshot_bullets(s, ints, fps):
    crit=sum(1 for p in fps if p["severity"]=="CRITICAL")
    last_ch=ints[-1]["channel_name"] if ints else "Unknown"
    first_dt=str(ints[0]["start_time"])[:10] if ints else "Unknown"
    return [
        f"{s['industry']} customer · {s['plan_type'] or 'Standard plan'} · {s['customer_id']}",
        f"{s['total_interactions']} prior contacts since {first_dt} — case unresolved",
        f"{crit} critical failure pattern{'s' if crit!=1 else ''} · Risk {s['risk_score']} {s['risk_label']}",
        f"Last contact via {last_ch} · {SENT_EMOJI.get(ints[-1]['overall_sentiment'],'😐')} {ints[-1]['overall_sentiment'] or 'Unknown'} sentiment",
    ]

def internal_note(s, ints):
    n=len(ints); last=ints[-1]; ch=last.get("channel_name","phone")
    return (f"{s['customer_name']} has contacted {s['industry']} support "
            f"<strong>{n} time{'s' if n!=1 else ''}</strong> regarding: "
            f"<strong>{s['scenario_title']}</strong>. "
            f"Risk score: <strong>{s['risk_score']} / 10 — {s['risk_label']}</strong>. "
            f"Most recent contact via <strong>{ch}</strong>. "
            f"{(s['root_cause'] or '')[:200]}.")

def build():
    if not os.path.exists(DB_PATH): print(f"ERROR: {DB_PATH} not found."); sys.exit(1)

    logo_svg=""
    if os.path.exists(LOGO_SVG):
        with open(LOGO_SVG) as f: logo_svg=f.read().strip()

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
                "icon":CH_ICON.get(ch_n,"📋"),"chNm":ch_n,
                "ttl":f"{ch_n} — Contact {it['interaction_sequence']}",
                "dt":str(it.get("start_time",""))[:10],"ag":it.get("agent_name") or "Unassigned",
                "sent":SENT_KEY.get(sr,"neutral"),"sEmoji":SENT_EMOJI.get(sr,"😐"),
                "csat":it.get("csat"),"esc":bool(it.get("escalation_flag")),
                "dur":fmt_dur(it.get("duration_seconds")),
                "lines":parse_transcript(it.get("transcript","")),
                "out":it.get("outcome") or "—"})

        score=float(s["risk_score"]) if s["risk_score"] else 7.0
        ref=s["case_reference_id"] or s["policy_number"] or s["account_number"] or s["member_id"] or "N/A"

        # sentiment trend from interactions
        trend=[SENT_KEY.get(it.get("overall_sentiment") or "Neutral","neutral") for it in ints]

        cases.append({
            "key":key,"name":s["customer_name"],"init":initials(s["customer_name"]),
            "id":s["customer_id"],"ref":ref,"industry":s["industry"],
            "iEmoji":IND_EMOJI.get(s["industry"],"📋"),
            "prod":s["plan_type"] or s["industry"],
            "scenario":s["scenario_title"] or "",
            "score":score,"label":s["risk_label"] or "RISK","col":risk_col(score),
            "status":s["session_status"] or "Open",
            "totalInts":s["total_interactions"] or len(ints),
            "lastCh":ints[-1].get("channel_name","Phone Call"),
            "internalNote":internal_note(dict(s),ints),
            "snapshotBullets":snapshot_bullets(dict(s),ints,fps),
            "openingLines":opening_lines(fps),
            "transcript":parse_transcript(ints[-1].get("transcript","")),
            "sentimentTrend":trend,
            "nodes":nodes,
            "patterns":[{"sev":"🔴" if p["severity"]=="CRITICAL" else "🟠","lbl":p["pattern_type"],"desc":p["pattern_description"]} for p in fps],
            "actions":[{"pri":a["priority"],"txt":a["action_text"]} for a in acts],
            "rootCause":s["root_cause"] or "",
        })
    db.close()

    js_data="const CASES="+json.dumps(cases,indent=2,ensure_ascii=False)+";"
    html=HTML_TEMPLATE.replace("/*__DB_DATA__*/",js_data).replace("<!--__LOGO__-->",logo_svg)
    with open(OUT_FILE,"w") as f: f.write(html)
    print(f"✓  {OUT_FILE}  —  {len(cases)} cases available  (Agent View)")
    for c in cases:
        print(f"   {c['key']}  {c['name']:<22}  risk={c['score']}")

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Agent View — NiCE CXone</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>
:root{
  --p0:#ffffff;--p25:#ecf5fe;--p50:#e5f2ff;--p100:#d2e7fe;--p200:#a7d0fe;
  --p300:#5ea9fd;--p400:#308ff8;--p500:#126bce;--p600:#17569b;--p700:#164479;--p800:#0e2d4e;
  --n0:#ffffff;--n25:#f9fafb;--n50:#f3f4f6;--n100:#e5e7eb;--n200:#d1d5db;
  --n300:#9ca3af;--n400:#6b7280;--n500:#4b5563;--n600:#374151;--n700:#1f2937;--n800:#111827;
  --ok:#208337;--ok-bg:#effbf1;--ok-bd:#24943e;
  --warn:#ffb800;--warn-bg:#fff6e0;
  --err:#e32926;--err-bg:#fdeaea;--err-bd:#e53935;
  --sh-xs:0 1px 2px #1f29370f;--sh-sm:0 1px 3px #1f29371a;--sh-md:0 4px 6px #1f29371f;--sh-lg:0 10px 15px #1f293724;
  --r-xs:4px;--r-sm:6px;--r-md:8px;--r-lg:12px;--r-xl:16px;--r-full:9999px;
  --left-w:320px;--tr-w:288px;--hdr-h:48px;--tabbar-h:40px;
}
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:'Inter',system-ui,sans-serif;height:100vh;overflow:hidden;
  display:flex;flex-direction:column;background:var(--n50);color:var(--n800);
  font-size:13px;-webkit-font-smoothing:antialiased;}

/* ── HEADER ── */
.hdr{height:var(--hdr-h);background:var(--p500);display:flex;align-items:center;
  padding:0 16px;gap:12px;flex-shrink:0;box-shadow:var(--sh-md);}
.hdr-logo{display:flex;align-items:center;gap:8px;flex-shrink:0;}
.hdr-logo svg{width:22px;height:22px;}
.hdr-logo-name{color:#fff;font-size:14px;font-weight:600;letter-spacing:-.01em;}
.hdr-div{width:1px;height:20px;background:rgba(255,255,255,.2);flex-shrink:0;}
.hdr-prod{color:rgba(255,255,255,.6);font-size:12px;font-weight:500;}
.hdr-right{margin-left:auto;display:flex;align-items:center;gap:12px;}
.hdr-bell{color:rgba(255,255,255,.55);font-size:14px;position:relative;cursor:pointer;padding:4px;}
.hdr-bell-dot{position:absolute;top:2px;right:2px;width:8px;height:8px;
  border-radius:50%;background:var(--err);border:1.5px solid var(--p500);}
.in-call{display:flex;align-items:center;gap:6px;
  background:rgba(32,131,55,.2);border:1px solid rgba(36,148,62,.35);
  border-radius:var(--r-sm);padding:4px 12px;color:#6ee2a0;font-size:11px;font-weight:600;}
.in-call-dot{width:7px;height:7px;border-radius:50%;background:var(--ok);
  animation:pulse 1.6s infinite;}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1);}50%{opacity:.5;transform:scale(.75);}}
.hdr-av{width:30px;height:30px;border-radius:50%;background:var(--p600);
  color:#fff;font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;}

/* ── BODY ── */
.body{flex:1;display:flex;overflow:hidden;}

/* ══════════════════════════════════════
   LEFT PANEL — ACTIVE CALL CARD
══════════════════════════════════════ */
.left{width:var(--left-w);background:var(--n0);border-right:1px solid var(--n100);
  display:flex;flex-direction:column;flex-shrink:0;box-shadow:var(--sh-xs);overflow:hidden;}

/* call switcher strip */
.call-strip{padding:8px 12px;background:var(--n25);border-bottom:1px solid var(--n100);
  display:flex;align-items:center;justify-content:space-between;flex-shrink:0;}
.call-strip-lbl{font-size:10px;font-weight:700;color:var(--n400);text-transform:uppercase;letter-spacing:.06em;}
.call-strip-sel{display:flex;align-items:center;gap:6px;font-size:11px;font-weight:600;
  color:var(--p600);cursor:pointer;background:var(--p50);border:1px solid var(--p100);
  border-radius:var(--r-full);padding:3px 10px;transition:all .18s;}
.call-strip-sel:hover{background:var(--p100);}
.call-strip-sel i{font-size:10px;}

/* main call card — scrollable */
.call-card{flex:1;overflow-y:auto;padding:16px 16px 0;}

/* avatar + status */
.cc-av-row{display:flex;align-items:center;gap:12px;margin-bottom:14px;}
.cc-av{width:56px;height:56px;border-radius:50%;background:var(--p50);color:var(--p600);
  font-size:20px;font-weight:700;display:flex;align-items:center;justify-content:center;
  flex-shrink:0;border:2px solid var(--p100);}
.cc-name{font-size:17px;font-weight:700;color:var(--n800);line-height:1.2;}
.cc-sub{font-size:11px;color:var(--n400);margin-top:2px;}
.live-badge{margin-left:auto;display:flex;align-items:center;gap:5px;
  background:var(--ok-bg);border:1px solid var(--ok-bd);
  color:var(--ok);font-size:10px;font-weight:700;
  padding:3px 9px;border-radius:var(--r-full);flex-shrink:0;}
.live-dot{width:6px;height:6px;border-radius:50%;background:var(--ok);animation:pulse 1.5s infinite;}

/* call timer (large) */
.cc-timer-row{display:flex;align-items:center;justify-content:center;
  padding:10px 0 14px;border-bottom:1px solid var(--n100);margin-bottom:14px;}
.cc-timer{font-size:32px;font-weight:700;color:var(--n700);letter-spacing:.04em;font-variant-numeric:tabular-nums;}
.cc-timer-lbl{font-size:10px;color:var(--n400);text-align:center;margin-top:2px;}

/* risk score row */
.cc-risk-row{display:flex;align-items:center;gap:10px;
  background:var(--err-bg);border:1px solid #fca5a5;border-radius:var(--r-md);
  padding:10px 14px;margin-bottom:14px;}
.cc-risk-ring{width:44px;height:44px;position:relative;flex-shrink:0;}
.cc-risk-ring svg{transform:rotate(-90deg);}
.rr-bg{fill:none;stroke:var(--n100);stroke-width:6;}
.rr-fg{fill:none;stroke-width:6;stroke-linecap:round;
  stroke-dasharray:120;stroke-dashoffset:120;transition:stroke-dashoffset 1.2s ease;}
.rr-in{position:absolute;inset:0;display:flex;flex-direction:column;
  align-items:center;justify-content:center;}
.rr-num{font-size:12px;font-weight:700;line-height:1;}
.rr-den{font-size:8px;color:var(--n400);}
.cc-risk-info .cc-risk-lbl{font-size:13px;font-weight:700;}
.cc-risk-info .cc-risk-sub{font-size:11px;color:var(--n500);margin-top:2px;line-height:1.4;}

/* meta grid */
.cc-meta{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px;}
.cc-mi{background:var(--n25);border:1px solid var(--n100);border-radius:var(--r-sm);padding:8px 10px;}
.cc-mi-lbl{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--n400);}
.cc-mi-val{font-size:12px;font-weight:600;color:var(--n700);margin-top:3px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}

/* sentiment trend */
.cc-trend{margin-bottom:14px;}
.cc-trend-lbl{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;
  color:var(--n400);margin-bottom:6px;}
.trend-dots{display:flex;align-items:center;gap:4px;}
.trend-dot{width:24px;height:24px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font-size:12px;border:2px solid transparent;transition:all .2s;}
.trend-dot.neutral{background:var(--n50);border-color:var(--n200);}
.trend-dot.slightly-neg{background:#fff8f0;border-color:#fed7aa;}
.trend-dot.neg{background:var(--warn-bg);border-color:#fcd34d;}
.trend-dot.very-neg{background:var(--err-bg);border-color:#fca5a5;}
.trend-dot.pos{background:var(--ok-bg);border-color:var(--ok-bd);}
.trend-arrow{color:var(--n300);font-size:8px;}

/* prior contacts */
.cc-prior{margin-bottom:14px;}
.cc-prior-lbl{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;
  color:var(--n400);margin-bottom:6px;}
.prior-chips{display:flex;gap:4px;flex-wrap:wrap;}
.prior-chip{width:28px;height:28px;border-radius:var(--r-sm);border:1.5px solid var(--n100);
  background:var(--n25);display:flex;align-items:center;justify-content:center;
  font-size:13px;cursor:pointer;transition:all .2s;position:relative;}
.prior-chip:hover{border-color:var(--p300);background:var(--p50);}
.prior-chip.esc{border-color:#fca5a5;background:var(--err-bg);}
.prior-chip.last{border-color:var(--ok-bd);background:var(--ok-bg);}

/* call controls */
.cc-controls{padding:12px 16px;border-top:1px solid var(--n100);flex-shrink:0;}
.cc-ctrl-row{display:flex;gap:8px;}
.cc-btn{flex:1;padding:9px 6px;border:1px solid var(--n200);border-radius:var(--r-md);
  background:var(--n0);font-size:11px;font-weight:600;cursor:pointer;
  display:flex;flex-direction:column;align-items:center;gap:3px;
  color:var(--n500);transition:all .18s;}
.cc-btn:hover{background:var(--n50);border-color:var(--n300);}
.cc-btn.end{border-color:#fca5a5;background:var(--err-bg);color:var(--err);}
.cc-btn.end:hover{background:#fecaca;}
.cc-btn.mute{border-color:var(--p100);background:var(--p50);color:var(--p600);}
.cc-btn i{font-size:14px;}

/* ══════════════════════════════════════
   MAIN AREA
══════════════════════════════════════ */
.main{flex:1;display:flex;flex-direction:column;overflow:hidden;min-width:0;}
.tab-bar{height:var(--tabbar-h);background:var(--n0);border-bottom:1px solid var(--n100);
  display:flex;align-items:stretch;flex-shrink:0;padding:0 4px;}
.m-tab{display:flex;align-items:center;gap:6px;padding:0 16px;
  font-size:12px;font-weight:500;cursor:pointer;color:var(--n400);
  border-bottom:2px solid transparent;white-space:nowrap;transition:all .18s;}
.m-tab:hover{color:var(--n600);}
.m-tab.active{color:var(--p500);border-bottom-color:var(--p500);font-weight:600;}
.tab-content{flex:1;overflow-y:auto;padding:16px 20px;}

/* Voice tab */
.conv-lbl{font-size:10px;font-weight:700;color:var(--n400);text-transform:uppercase;
  letter-spacing:.06em;margin-bottom:12px;display:flex;align-items:center;gap:6px;}
.connected-line{display:flex;align-items:center;gap:8px;padding:8px 12px;
  background:var(--ok-bg);border:1px solid var(--ok-bd);border-radius:var(--r-md);
  margin-bottom:12px;font-size:12px;color:var(--ok);font-weight:600;}
.int-note{background:var(--n0);border:1px solid var(--ok-bd);border-left:3px solid var(--ok);
  border-radius:var(--r-md);padding:12px 16px;margin-bottom:12px;box-shadow:var(--sh-xs);}
.note-tag{display:inline-flex;align-items:center;gap:5px;background:var(--ok-bg);
  border:1px solid var(--ok-bd);color:var(--ok);font-size:10px;font-weight:700;
  padding:2px 8px;border-radius:var(--r-xs);margin-bottom:8px;}
.note-body{font-size:12px;color:var(--n700);line-height:1.7;}
.note-body strong{color:var(--n800);font-weight:600;}
.snapshot{background:var(--n0);border:1px solid var(--n100);border-radius:var(--r-md);
  padding:12px 16px;margin-bottom:12px;box-shadow:var(--sh-xs);}
.snap-hdr{display:flex;align-items:center;gap:12px;margin-bottom:12px;}
.snap-av{width:36px;height:36px;border-radius:50%;background:var(--p50);color:var(--p600);
  font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;}
.snap-name{font-size:14px;font-weight:600;color:var(--n800);}
.snap-sub{font-size:11px;color:var(--n400);margin-top:1px;}
.snap-tags{display:flex;gap:4px;flex-wrap:wrap;margin-top:5px;}
.snap-tag{font-size:10px;padding:2px 7px;border-radius:var(--r-full);
  border:1px solid var(--n100);color:var(--n500);background:var(--n50);}
.snap-sec-lbl{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--n400);margin-bottom:6px;}
.snap-bullet{display:flex;align-items:flex-start;gap:6px;font-size:12px;color:var(--n700);padding:3px 0;line-height:1.5;}
.snap-bullet::before{content:"·";color:var(--p400);font-weight:700;flex-shrink:0;font-size:16px;line-height:1.1;}
.ai-lines{background:var(--n0);border:1px solid var(--n100);border-radius:var(--r-md);
  padding:12px 16px;box-shadow:var(--sh-xs);}
.ai-lines-hdr{display:flex;align-items:center;gap:8px;margin-bottom:10px;font-size:11px;font-weight:700;color:var(--n700);}
.ai-lines-hdr i{color:var(--p500);}
.ai-line{padding:9px 12px;border:1px solid var(--n100);border-radius:var(--r-sm);
  margin-bottom:8px;cursor:pointer;transition:all .18s;background:var(--n25);}
.ai-line:last-child{margin-bottom:0;}
.ai-line:hover{border-color:var(--p300);background:var(--p50);}
.ai-line-q{font-size:12px;color:var(--n800);line-height:1.5;margin-bottom:2px;}
.ai-line-hint{font-size:10px;color:var(--n400);font-style:italic;}

/* History tab */
.hist-wrap{display:flex;gap:16px;}
.hist-tl{width:36%;min-width:230px;}
.hist-tl-hdr{font-size:10px;font-weight:700;color:var(--n400);text-transform:uppercase;
  letter-spacing:.06em;margin-bottom:8px;display:flex;align-items:center;gap:5px;}
.risk-pill{display:inline-flex;align-items:center;gap:5px;padding:4px 12px;
  border-radius:var(--r-full);font-size:11px;font-weight:700;margin-bottom:12px;}
.tl-node{display:flex;gap:10px;padding:8px;border-radius:var(--r-sm);cursor:pointer;
  transition:all .18s;position:relative;margin-bottom:1px;}
.tl-node:hover{background:var(--n50);}
.tl-node.sel{background:var(--p50);outline:1.5px solid var(--p200);}
.tl-node:not(:last-child)::after{content:'';position:absolute;left:23px;top:38px;
  width:2px;height:calc(100% - 12px);background:var(--n100);z-index:0;}
.tl-ic{width:30px;height:30px;border-radius:50%;border:2px solid var(--n100);
  background:var(--n0);display:flex;align-items:center;justify-content:center;
  font-size:12px;flex-shrink:0;z-index:1;position:relative;}
.tl-body{flex:1;min-width:0;}
.tl-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:1px;}
.tl-ttl{font-size:11px;font-weight:600;color:var(--n700);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.tl-dt{font-size:9px;color:var(--n400);white-space:nowrap;margin-left:4px;flex-shrink:0;}
.tl-ag{font-size:10px;color:var(--n400);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-bottom:3px;}
.tl-foot{display:flex;gap:4px;align-items:center;flex-wrap:wrap;}
.tl-csat{font-size:9px;padding:1px 5px;border-radius:var(--r-full);font-weight:700;}
.c1{background:var(--err-bg);color:var(--err);}
.c2{background:var(--warn-bg);color:#856404;}
.c3{background:#fffde7;color:#795b00;}
.c4{background:var(--ok-bg);color:var(--ok);}
.c5{background:#e8f5e9;color:#1b5e20;}
.esc-tag{font-size:9px;background:var(--err-bg);color:var(--err);
  padding:1px 5px;border-radius:var(--r-xs);font-weight:700;}
.hist-brief{flex:1;display:flex;flex-direction:column;gap:10px;min-width:0;}
.brief-card{background:var(--n0);border:1px solid var(--n100);
  border-radius:var(--r-md);padding:12px 16px;box-shadow:var(--sh-xs);}
.brief-hdr{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;
  color:var(--n400);margin-bottom:10px;display:flex;align-items:center;gap:5px;}
.brief-hdr i{color:var(--p500);}
.risk-hero{display:flex;align-items:center;gap:16px;}
.risk-ring{width:72px;height:72px;position:relative;flex-shrink:0;}
.risk-ring svg{transform:rotate(-90deg);}
.risk-bg{fill:none;stroke:var(--n100);stroke-width:7;}
.risk-fg{fill:none;stroke-width:7;stroke-linecap:round;
  stroke-dasharray:201;stroke-dashoffset:201;transition:stroke-dashoffset 1.3s ease;}
.risk-in{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;}
.risk-num{font-size:17px;font-weight:700;line-height:1;}
.risk-den{font-size:9px;color:var(--n400);}
.risk-lbl{font-size:17px;font-weight:700;margin-bottom:4px;}
.risk-sc{font-size:12px;color:var(--n500);line-height:1.5;}
.pat-tbl{width:100%;border-collapse:collapse;}
.pat-tbl tr{border-bottom:1px solid var(--n50);}
.pat-tbl tr:last-child{border-bottom:none;}
.pat-tbl td{padding:6px 3px;font-size:11px;vertical-align:top;}
.pt-sev{width:18px;}.pt-lbl{font-weight:600;width:36%;padding-right:8px;color:var(--n700);}
.pt-desc{color:var(--n400);}
.act-item{display:flex;gap:8px;padding:8px 0;border-bottom:1px solid var(--n50);align-items:flex-start;}
.act-item:last-child{border-bottom:none;}
.act-num{width:20px;height:20px;border-radius:50%;background:var(--p500);color:#fff;
  font-size:10px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px;}
.act-pri{font-size:9px;font-weight:700;text-transform:uppercase;
  padding:2px 5px;border-radius:var(--r-xs);display:inline-block;margin-bottom:3px;}
.pri-critical{background:var(--err-bg);color:var(--err);}
.pri-high{background:var(--warn-bg);color:#92400e;}
.pri-medium{background:#fffde7;color:#795b00;}
.act-txt{font-size:12px;line-height:1.5;color:var(--n700);}

/* ── TRANSCRIPT PANEL ── */
.tr-panel{width:var(--tr-w);background:var(--n0);border-left:1px solid var(--n100);
  display:flex;flex-direction:column;flex-shrink:0;}
.tr-hdr{padding:8px 12px;background:var(--p500);
  display:flex;align-items:center;justify-content:space-between;flex-shrink:0;}
.tr-hdr-left .tr-lbl{font-size:9px;font-weight:700;text-transform:uppercase;
  letter-spacing:.08em;color:rgba(255,255,255,.5);}
.tr-hdr-left .tr-name{font-size:12px;font-weight:600;color:#fff;margin-top:1px;}
.tr-live{display:flex;align-items:center;gap:5px;font-size:10px;font-weight:700;color:#6ee2a0;}
.tr-live-dot{width:6px;height:6px;border-radius:50%;background:var(--ok);animation:pulse 1.5s infinite;}
.tr-body{flex:1;overflow-y:auto;padding:12px 10px;}
.bubble{margin-bottom:8px;}
.bubble-sp{font-size:9px;font-weight:700;color:var(--n300);margin-bottom:2px;
  text-transform:uppercase;letter-spacing:.05em;}
.bubble-txt{padding:8px 11px;border-radius:var(--r-md);font-size:11px;
  line-height:1.6;max-width:92%;white-space:pre-line;}
.b-cust .bubble-sp{color:var(--p400);}
.b-cust .bubble-txt{background:var(--p50);color:var(--n700);}
.b-agent .bubble-sp{color:var(--n400);}
.b-agent .bubble-txt{background:var(--n50);color:var(--n700);}
.b-sys .bubble-sp{color:var(--ok);}
.b-sys .bubble-txt{background:var(--ok-bg);color:#155724;font-style:italic;font-size:10px;}

/* ── DRAWER ── */
.overlay{position:fixed;inset:0;background:rgba(17,24,39,.3);z-index:200;
  opacity:0;pointer-events:none;transition:opacity .25s;}
.overlay.on{opacity:1;pointer-events:all;}
.drawer{position:fixed;right:0;top:0;bottom:0;width:400px;background:var(--n0);
  box-shadow:0 25px 50px #1f29372e;z-index:201;transform:translateX(100%);
  transition:transform .3s cubic-bezier(.4,0,.2,1);display:flex;flex-direction:column;}
.drawer.on{transform:translateX(0);}
.dr-hdr{padding:12px 16px;background:var(--p500);display:flex;align-items:center;gap:8px;flex-shrink:0;}
.dr-ic{font-size:18px;}
.dr-info h3{font-size:13px;font-weight:600;color:#fff;}
.dr-info p{font-size:10px;color:rgba(255,255,255,.5);}
.dr-close{margin-left:auto;width:26px;height:26px;border-radius:var(--r-sm);
  background:rgba(255,255,255,.1);color:#fff;border:none;cursor:pointer;
  display:flex;align-items:center;justify-content:center;font-size:12px;}
.dr-close:hover{background:rgba(255,255,255,.2);}
.dr-meta{padding:8px 16px;background:var(--n25);border-bottom:1px solid var(--n100);
  display:flex;gap:12px;flex-shrink:0;}
.dr-mi .dr-ml{font-size:9px;text-transform:uppercase;letter-spacing:.05em;color:var(--n400);font-weight:700;}
.dr-mi .dr-mv{font-size:12px;font-weight:600;margin-top:1px;color:var(--n700);}
.dr-body{flex:1;overflow-y:auto;padding:12px 16px;}
.dr-out{padding:10px 16px;border-top:1px solid var(--n100);flex-shrink:0;}
.dr-out-lbl{font-size:9px;text-transform:uppercase;letter-spacing:.05em;color:var(--n400);font-weight:700;margin-bottom:3px;}
.dr-out-txt{font-size:12px;line-height:1.5;color:var(--n700);}

/* case switcher dropdown */
.case-dd{position:fixed;top:48px;left:0;width:var(--left-w);background:var(--n0);
  border:1px solid var(--n100);border-top:none;border-radius:0 0 var(--r-md) var(--r-md);
  box-shadow:var(--sh-lg);z-index:50;display:none;}
.case-dd.open{display:block;}
.case-dd-item{padding:10px 14px;cursor:pointer;border-bottom:1px solid var(--n50);
  transition:background .15s;display:flex;align-items:center;gap:10px;}
.case-dd-item:last-child{border-bottom:none;}
.case-dd-item:hover{background:var(--n25);}
.case-dd-av{width:30px;height:30px;border-radius:50%;background:var(--p50);
  color:var(--p600);font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;}
.case-dd-name{font-size:12px;font-weight:600;color:var(--n700);}
.case-dd-sub{font-size:10px;color:var(--n400);}
.case-dd-risk{margin-left:auto;font-size:9px;font-weight:700;padding:2px 6px;
  border-radius:var(--r-full);background:var(--err-bg);color:var(--err);}

::-webkit-scrollbar{width:4px;}::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{background:var(--n200);border-radius:var(--r-full);}
</style>
</head>
<body>

<!-- HEADER -->
<header class="hdr">
  <div class="hdr-logo"><!--__LOGO__--><span class="hdr-logo-name">NiCE CXone</span></div>
  <div class="hdr-div"></div>
  <span class="hdr-prod">Agent Workspace</span>
  <div class="hdr-right">
    <div class="hdr-bell"><i class="fas fa-bell"></i><div class="hdr-bell-dot"></div></div>
    <div class="in-call"><div class="in-call-dot"></div><span>In a Call</span><span id="call-timer">00:00:00</span></div>
    <div class="hdr-av" id="hdr-av">SR</div>
  </div>
</header>

<!-- BODY -->
<div class="body">

  <!-- LEFT PANEL -->
  <div class="left">

    <!-- case switcher strip -->
    <div class="call-strip">
      <span class="call-strip-lbl">Active Call</span>
      <div class="call-strip-sel" onclick="toggleDD()">
        <span id="strip-name">—</span>
        <i class="fas fa-chevron-down" id="strip-chevron"></i>
      </div>
    </div>

    <!-- dropdown -->
    <div class="case-dd" id="case-dd"></div>

    <!-- call card -->
    <div class="call-card" id="call-card"></div>

    <!-- controls -->
    <div class="cc-controls">
      <div class="cc-ctrl-row">
        <button class="cc-btn mute"><i class="fas fa-microphone-slash"></i><span>Mute</span></button>
        <button class="cc-btn"><i class="fas fa-random"></i><span>Transfer</span></button>
        <button class="cc-btn"><i class="fas fa-pause"></i><span>Hold</span></button>
        <button class="cc-btn end"><i class="fas fa-phone-slash"></i><span>End Call</span></button>
      </div>
    </div>
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

let curKey=CASES[0]?.key, curTab='voice', callSec=0, ddOpen=false;

(function init(){
  buildDD();
  selectCase(curKey);
  setInterval(()=>{
    callSec++;
    const h=Math.floor(callSec/3600),m=Math.floor((callSec%3600)/60),s=callSec%60;
    const el=document.getElementById('call-timer');
    if(el) el.textContent=[h,m,s].map(x=>String(x).padStart(2,'0')).join(':');
  },1000);
  document.addEventListener('click',e=>{
    if(!e.target.closest('.call-strip') && !e.target.closest('.case-dd')) closeDD();
  });
})();

/* ── dropdown ── */
function buildDD(){
  document.getElementById('case-dd').innerHTML=CASES.map(c=>`
    <div class="case-dd-item" onclick="selectCase('${c.key}');closeDD()">
      <div class="case-dd-av">${c.init}</div>
      <div>
        <div class="case-dd-name">${c.name}</div>
        <div class="case-dd-sub">${c.iEmoji} ${c.industry} · ${c.ref}</div>
      </div>
      <div class="case-dd-risk">${c.score}</div>
    </div>`).join('');
}
function toggleDD(){
  ddOpen=!ddOpen;
  document.getElementById('case-dd').classList.toggle('open',ddOpen);
  document.getElementById('strip-chevron').style.transform=ddOpen?'rotate(180deg)':'';
}
function closeDD(){
  ddOpen=false;
  document.getElementById('case-dd').classList.remove('open');
  document.getElementById('strip-chevron').style.transform='';
}

/* ── select case ── */
function selectCase(key){
  curKey=key; curTab='voice'; callSec=0; closeDrawer();
  const c=CASES.find(x=>x.key===key); if(!c) return;
  document.getElementById('strip-name').textContent=c.name;
  document.getElementById('hdr-av').textContent=c.init;
  document.getElementById('tr-name').textContent=c.name;
  renderCallCard(c);
  renderTranscript(c);
  renderVoiceTab(c);
}

/* ── left panel call card ── */
function renderCallCard(c){
  const circ=120, offset=circ-(c.score/10)*circ;
  const trend=c.sentimentTrend.map((s,i)=>{
    const isLast=i===c.sentimentTrend.length-1;
    return `<div class="trend-dot ${s}" title="${s}">${sentEmoji(s)}</div>${i<c.sentimentTrend.length-1?'<div class="trend-arrow">›</div>':''}`;
  }).join('');
  const chips=c.nodes.map((n,i)=>`
    <div class="prior-chip${n.esc?' esc':''}${i===c.nodes.length-1?' last':''}"
         title="Contact ${n.seq} · ${n.chNm} · ${n.dt}"
         onclick="openDrawer(${i})">${n.icon}</div>`).join('');

  document.getElementById('call-card').innerHTML=`
    <div class="cc-av-row">
      <div class="cc-av">${c.init}</div>
      <div>
        <div class="cc-name">${c.name}</div>
        <div class="cc-sub">${c.iEmoji} ${c.industry} · ${c.ref}</div>
      </div>
      <div class="live-badge"><div class="live-dot"></div>LIVE</div>
    </div>

    <div class="cc-timer-row">
      <div>
        <div class="cc-timer" id="cc-timer-disp">00:00:00</div>
        <div class="cc-timer-lbl">Call Duration</div>
      </div>
    </div>

    <div class="cc-risk-row">
      <div class="cc-risk-ring">
        <svg width="44" height="44" viewBox="0 0 44 44">
          <circle class="rr-bg" cx="22" cy="22" r="19"/>
          <circle class="rr-fg" id="cc-score-fg" cx="22" cy="22" r="19" stroke="${c.col}"/>
        </svg>
        <div class="rr-in">
          <div class="rr-num" style="color:${c.col}">${c.score}</div>
          <div class="rr-den">/ 10</div>
        </div>
      </div>
      <div class="cc-risk-info">
        <div class="cc-risk-lbl" style="color:${c.col}">${c.label}</div>
        <div class="cc-risk-sub">${c.totalInts} prior contacts · ${c.patterns.filter(p=>p.sev==='🔴').length} critical patterns</div>
      </div>
    </div>

    <div class="cc-meta">
      <div class="cc-mi"><div class="cc-mi-lbl">Case Ref</div><div class="cc-mi-val">${c.ref}</div></div>
      <div class="cc-mi"><div class="cc-mi-lbl">Industry</div><div class="cc-mi-val">${c.iEmoji} ${c.industry}</div></div>
      <div class="cc-mi"><div class="cc-mi-lbl">Product</div><div class="cc-mi-val">${c.prod}</div></div>
      <div class="cc-mi"><div class="cc-mi-lbl">Status</div><div class="cc-mi-val">${c.status}</div></div>
    </div>

    <div class="cc-trend">
      <div class="cc-trend-lbl">Sentiment Trend (${c.nodes.length} contacts)</div>
      <div class="trend-dots">${trend}</div>
    </div>

    <div class="cc-prior">
      <div class="cc-prior-lbl">Prior Contacts — click to view transcript</div>
      <div class="prior-chips">${chips}</div>
    </div>`;

  // sync timer display
  const timerEl=document.getElementById('cc-timer-disp');
  if(timerEl){
    const orig=setInterval(()=>{
      const h=Math.floor(callSec/3600),m=Math.floor((callSec%3600)/60),s=callSec%60;
      timerEl.textContent=[h,m,s].map(x=>String(x).padStart(2,'0')).join(':');
    },1000);
  }

  // animate risk ring
  requestAnimationFrame(()=>{
    const fg=document.getElementById('cc-score-fg');
    if(fg){fg.style.strokeDasharray=circ;fg.style.strokeDashoffset=offset;}
  });
}

/* ── tab bar ── */
function renderTabBar(activeTab){
  document.getElementById('tab-bar').innerHTML=`
    <div class="m-tab${activeTab==='voice'?' active':''}" data-tab="voice" onclick="switchTab('voice')">
      <i class="fas fa-phone"></i>Voice
    </div>
    <div class="m-tab${activeTab==='history'?' active':''}" data-tab="history" onclick="switchTab('history')">
      <i class="fas fa-route"></i>Customer History
    </div>`;
}

function switchTab(tab){
  curTab=tab;
  const c=CASES.find(x=>x.key===curKey); if(!c) return;
  renderTabBar(tab);
  if(tab==='voice')   renderVoiceTab(c);
  if(tab==='history') renderHistoryTab(c);
}

/* ── voice tab ── */
function renderVoiceTab(c){
  renderTabBar('voice');
  const bullets=c.snapshotBullets.map(b=>`<div class="snap-bullet">${b}</div>`).join('');
  const lines=c.openingLines.map(l=>`
    <div class="ai-line">
      <div class="ai-line-q">${l.q}</div>
      <div class="ai-line-hint">— ${l.hint}</div>
    </div>`).join('');
  document.getElementById('tab-content').innerHTML=`
    <div class="conv-lbl"><i class="fas fa-comment-dots" style="color:var(--p400)"></i>Voice · New conversation</div>
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
            <span class="snap-tag" style="background:var(--err-bg);color:var(--err);border-color:#fca5a5">Risk ${c.score} ${c.label}</span>
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

/* ── history tab ── */
function renderHistoryTab(c){
  renderTabBar('history');
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
  const pats=c.patterns.map(p=>`<tr><td class="pt-sev">${p.sev}</td><td class="pt-lbl">${p.lbl}</td><td class="pt-desc">${p.desc}</td></tr>`).join('');
  const acts=c.actions.map((a,i)=>`
    <div class="act-item">
      <div class="act-num">${i+1}</div>
      <div><span class="act-pri pri-${a.pri.toLowerCase()}">${a.pri}</span><div class="act-txt">${a.txt}</div></div>
    </div>`).join('');
  const circ=201,offset=circ-(c.score/10)*circ;
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
                <circle class="risk-bg" cx="36" cy="36" r="32"/>
                <circle class="risk-fg" id="score-fg" cx="36" cy="36" r="32" stroke="${c.col}"/>
              </svg>
              <div class="risk-in">
                <div class="risk-num" style="color:${c.col}">${c.score}</div>
                <div class="risk-den">/ 10</div>
              </div>
            </div>
            <div>
              <div class="risk-lbl" style="color:${c.col}">${c.label}</div>
              <div class="risk-sc">${c.scenario}</div>
            </div>
          </div>
        </div>
        <div class="brief-card">
          <div class="brief-hdr"><i class="fas fa-search"></i>Root Cause</div>
          <div style="font-size:12px;line-height:1.7;color:var(--n600)">${c.rootCause||'Analysis in progress.'}</div>
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

/* ── transcript ── */
function renderTranscript(c){
  document.getElementById('tr-name').textContent=c.name;
  document.getElementById('tr-body').innerHTML=c.transcript.map(l=>{
    const cls=l.sp==='cust'?'b-cust':l.sp==='sys'?'b-sys':'b-agent';
    return `<div class="bubble ${cls}"><div class="bubble-sp">${l.nm}</div><div class="bubble-txt">${l.tx}</div></div>`;
  }).join('');
}

/* ── drawer ── */
function openDrawer(idx){
  const c=CASES.find(x=>x.key===curKey); if(!c) return;
  const n=c.nodes[idx];
  document.querySelectorAll('.tl-node,.prior-chip').forEach(el=>el.classList.remove('sel'));
  const nd=document.getElementById('hn'+idx); if(nd) nd.classList.add('sel');
  document.getElementById('dr-ic').textContent=n.icon;
  document.getElementById('dr-ttl').textContent=`Contact ${n.seq} — ${n.chNm}`;
  document.getElementById('dr-sub').textContent=`${n.dt} · ${n.ag}`;
  document.getElementById('dr-sent').textContent=`${n.sEmoji} ${SL[n.sent]||n.sent}`;
  document.getElementById('dr-csat').textContent=n.csat?`${n.csat}/5`:'—';
  document.getElementById('dr-dur').textContent=n.dur||'—';
  const ee=document.getElementById('dr-esc');
  ee.textContent=n.esc?'⚠️ Yes':'No'; ee.style.color=n.esc?'var(--err)':'inherit';
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
const SE={neutral:'😐','slightly-neg':'😕',neg:'😞','very-neg':'😡',pos:'😊'};
function sentEmoji(s){return SE[s]||'😐';}
</script>
</body>
</html>"""

if __name__ == "__main__":
    build()
