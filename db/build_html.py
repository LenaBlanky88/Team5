"""
build_html.py
Reads customer_journey_forensics.db and writes journey-analyzer.html
with all scenario data sourced from the database.
Run from project root: python3 db/build_html.py
"""
import sqlite3, json, re, os, sys

DB_PATH = "customer_journey_forensics.db"
TEMPLATE = "journey-analyzer.html"
OUT = "journey-analyzer.html"

# ── helpers ──────────────────────────────────────────────────────────────────

CHANNEL_ICON = {
    "Phone Call": "📞",   "Email": "📧",      "Chatbot": "🤖",
    "Live Chat": "💬",    "WhatsApp": "💬",   "Callback": "📲",
    "Portal / Self-Service": "🖥️", "Social Media": "🌐",
    "Mobile App": "📱",   "Automated Notification": "🔔",
}
CHANNEL_KEY = {
    "Phone Call": "voice",  "Email": "email",  "Chatbot": "chat",
    "Live Chat": "livechat","WhatsApp": "whatsapp","Callback": "callback",
    "Portal / Self-Service": "portal","Social Media": "social",
    "Mobile App": "mobile", "Automated Notification": "auto",
}
SENT_EMOJI = {
    "Neutral": "😐", "Slightly Negative": "😕", "Negative": "😞",
    "Very Negative": "😡", "Positive": "😊",
}
SENT_KEY = {
    "Neutral": "neutral","Slightly Negative": "slightly-neg",
    "Negative": "neg","Very Negative": "very-neg","Positive": "pos",
}

def parse_transcript(raw, cust_first, agent_name):
    """Turn flat transcript text into bubble objects."""
    if not raw:
        return [{"sp":"sys","nm":"System","tx":"No transcript available."}]
    lines = [l.strip() for l in raw.strip().split("\n") if l.strip()]
    bubbles = []
    for line in lines:
        if ":" in line:
            speaker, _, text = line.partition(":")
            speaker = speaker.strip()
            text = text.strip()
            if not text:
                continue
            # Classify speaker role
            lower_sp = speaker.lower()
            if any(w in lower_sp for w in ["customer","member","michael","james","david","jennifer",
                                            "robert","emily","sarah","anna","lisa","elena"]):
                sp = "cust"
            elif any(w in lower_sp for w in ["bot","system","ivr","portal","auto","notification"]):
                sp = "sys"
            else:
                sp = "agent"
            bubbles.append({"sp": sp, "nm": speaker, "tx": text})
        else:
            bubbles.append({"sp": "sys", "nm": "System", "tx": line})
    return bubbles if bubbles else [{"sp":"sys","nm":"System","tx":raw[:200]}]


def fmt_dur(secs):
    if not secs:
        return None
    m, s = divmod(secs, 60)
    return f"{m} min {s} sec" if s else f"{m} min"

def risk_color(score):
    if score >= 9.0:
        return "#DC3545"
    if score >= 7.5:
        return "#FD7E14"
    return "#FFC107"

def initials(name):
    parts = name.split()
    return (parts[0][0] + parts[-1][0]).upper() if len(parts) >= 2 else name[:2].upper()

def industry_prod(industry, plan_type, policy_number, account_number, member_id):
    ref = policy_number or account_number or member_id or "N/A"
    prod_map = {
        "Insurance": "Insurance", "Healthcare": "Health Insurance",
        "Banking": "Banking", "ISP": "Broadband / ISP",
    }
    return prod_map.get(industry, industry), ref

# ── main ─────────────────────────────────────────────────────────────────────

def build():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found. Run db/seed.py first.")
        sys.exit(1)

    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    sessions = db.execute("""
        SELECT js.master_contact_id, js.scenario_title, js.case_reference_id,
               js.industry, js.risk_score, js.risk_label, js.total_interactions,
               js.root_cause,
               c.customer_name, c.customer_id, c.plan_type,
               c.account_number, c.member_id, c.policy_number
        FROM journey_sessions js JOIN customers c ON js.customer_id = c.customer_id
        ORDER BY js.risk_score DESC
    """).fetchall()

    S = {}
    for s in sessions:
        key = s['master_contact_id']
        ints = db.execute("""
            SELECT i.interaction_sequence, i.media_type, i.overall_sentiment,
                   i.csat, i.escalation_flag, i.duration_seconds,
                   i.transcript, i.outcome, i.start_time,
                   ch.channel_name, a.agent_name
            FROM interactions i
            LEFT JOIN channels ch ON i.channel_id = ch.channel_id
            LEFT JOIN agents a ON i.agent_id = a.agent_id
            WHERE i.master_contact_id = ?
            ORDER BY i.interaction_sequence
        """, (key,)).fetchall()

        if not ints:
            continue  # skip sessions with no interaction data

        fps = db.execute("""
            SELECT severity, pattern_type, pattern_description
            FROM failure_patterns WHERE master_contact_id = ?
            ORDER BY CASE severity WHEN 'CRITICAL' THEN 1 ELSE 2 END
        """, (key,)).fetchall()

        acts = db.execute("""
            SELECT priority, action_text FROM recommended_actions
            WHERE master_contact_id = ?
            ORDER BY CASE priority WHEN 'Critical' THEN 1 WHEN 'High' THEN 2
                     WHEN 'Medium' THEN 3 ELSE 4 END
        """, (key,)).fetchall()

        prod, ref = industry_prod(s['industry'], s['plan_type'],
                                  s['policy_number'], s['account_number'], s['member_id'])
        ref = s['case_reference_id'] or ref

        # Build interaction list
        int_list = []
        for it in ints:
            ch_name = it['channel_name'] or it['media_type']
            icon = CHANNEL_ICON.get(ch_name, "📋")
            ch_key = CHANNEL_KEY.get(ch_name, "voice")
            sent_raw = it['overall_sentiment'] or "Neutral"
            sent_emoji = SENT_EMOJI.get(sent_raw, "😐")
            sent_key = SENT_KEY.get(sent_raw, "neutral")
            ag = it['agent_name'] or "Unassigned"
            dt = str(it['start_time'])[:10] if it['start_time'] else "—"
            lines = parse_transcript(it['transcript'], s['customer_name'], ag)
            int_list.append({
                "seq": it['interaction_sequence'],
                "ch": ch_key,
                "icon": icon,
                "chNm": ch_name,
                "ttl": f"{ch_name} — Interaction {it['interaction_sequence']}",
                "dt": dt,
                "ag": ag,
                "sent": sent_key,
                "sEmoji": sent_emoji,
                "csat": it['csat'],
                "esc": bool(it['escalation_flag']),
                "dur": fmt_dur(it['duration_seconds']),
                "lines": lines,
                "out": it['outcome'] or "—",
            })

        # Build failure pattern list
        pat_list = []
        for fp in fps:
            sev_icon = "🔴" if fp['severity'] == "CRITICAL" else "🟠"
            pat_list.append({
                "sev": sev_icon,
                "lbl": fp['pattern_type'],
                "desc": fp['pattern_description'],
            })

        # Build actions list
        act_list = [{"pri": a['priority'], "txt": a['action_text']} for a in acts]

        score = float(s['risk_score']) if s['risk_score'] else 7.0
        label = s['risk_label'] or "HIGH RISK"
        col = risk_color(score)

        # Build summary from root_cause
        root = s['root_cause'] or ""
        summary = (s['scenario_title'] or "") + ". " + root[:200] if root else s['scenario_title'] or ""

        first_ch = int_list[0]['ch'] if int_list else "voice"
        ch_display_map = {
            "voice":"📞 Inbound Voice Call","email":"📧 Inbound Email",
            "chat":"🤖 Chat Session","livechat":"💬 Live Chat",
            "whatsapp":"💬 WhatsApp","portal":"🖥️ Self-Service Portal",
            "callback":"📲 Agent Callback","social":"🌐 Social Media",
            "mobile":"📱 Mobile App","auto":"🔔 Notification",
        }
        ch_display = ch_display_map.get(first_ch, "📞 Inbound Contact")

        S[key] = {
            "cust": {
                "name": s['customer_name'],
                "id": s['customer_id'],
                "init": initials(s['customer_name']),
                "policy": ref,
                "prod": prod,
                "ch": ch_display,
            },
            "score": score,
            "label": label,
            "ints": int_list,
            "an": {
                "score": score,
                "label": label,
                "col": col,
                "sum": summary,
                "root": root,
                "pats": pat_list,
                "acts": act_list,
            },
        }

    db.close()

    # ── patch HTML ────────────────────────────────────────────────────────────
    with open(TEMPLATE, "r") as f:
        html = f.read()

    js_data = json.dumps(S, indent=2, ensure_ascii=False)

    # Build dynamic scenario button bar from DB sessions
    btn_lines = []
    industry_emoji = {"Insurance":"📋","Healthcare":"🏥","Banking":"🏦","ISP":"📡"}
    for s_raw in sessions:
        key = s_raw['master_contact_id']
        if key not in S:
            continue
        ind = s_raw['industry']
        emoji = industry_emoji.get(ind, "📋")
        name = s_raw['customer_name'].split()[0]  # first name
        short = (s_raw['scenario_title'] or "")[:35]
        btn_lines.append(
            f'  <button class="scen-btn" data-key="{key}" '
            f'onclick="loadScenario(\'{key}\')">'
            f'{emoji} {name} — {short}</button>'
        )
    buttons_html = "\n".join(btn_lines)

    # Replace static S object
    html = re.sub(
        r'const S = \{.*?\};',
        f'const S = {js_data};',
        html,
        flags=re.DOTALL,
    )

    # Replace scenario button bar (between the scen-lbl span and the reset button)
    html = re.sub(
        r'(<span class="scen-lbl">.*?</span>)\s*'
        r'(<button class="scen-btn.*?</button>\s*)+'
        r'(<button class="reset-btn")',
        r'\1\n' + buttons_html + r'\n  \3',
        html,
        flags=re.DOTALL,
    )

    # Update loadScenario boot call to use first DB key
    first_key = list(S.keys())[0] if S else "MC-POL-784512"
    html = re.sub(
        r"boot\(\);",
        f"boot('{first_key}');",
        html,
    )
    # Update boot() function to accept key
    html = re.sub(
        r"function boot\(\) \{",
        "function boot(k) {",
        html,
    )
    html = re.sub(
        r"loadScenario\('johnson'\);",
        "loadScenario(k || Object.keys(S)[0]);",
        html,
    )

    with open(OUT, "w") as f:
        f.write(html)

    print(f"✓ Written {OUT} with {len(S)} DB-sourced scenarios:")
    for k, v in S.items():
        print(f"  {k}: {v['cust']['name']} | {len(v['ints'])} ints | risk={v['score']}")

if __name__ == "__main__":
    build()
