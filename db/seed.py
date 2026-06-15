"""
seed.py — reads the four source Word files and populates customer_journey_forensics.db
Run from the project root: python3 db/seed.py
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "customer_journey_forensics.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


# ---------------------------------------------------------------------------
# Data extracted from the four .docx files
# ---------------------------------------------------------------------------

CHANNELS = [
    ("CH-VOICE-01",   "Phone Call",              "VOICE"),
    ("CH-EMAIL-01",   "Email",                   "EMAIL"),
    ("CH-CHAT-BOT",   "Chatbot",                 "CHAT"),
    ("CH-CHAT-LIVE",  "Live Chat",               "CHAT"),
    ("CH-WA-01",      "WhatsApp",                "DIGITAL"),
    ("CH-PORTAL-01",  "Portal / Self-Service",   "DIGITAL"),
    ("CH-SOCIAL-01",  "Social Media",            "DIGITAL"),
    ("CH-SMS-01",     "SMS",                     "DIGITAL"),
    ("CH-CALLBACK-01","Callback",                "VOICE"),
    ("CH-AUTO-01",    "Automated Notification",  "DIGITAL"),
    ("CH-APP-01",     "Mobile App",              "DIGITAL"),
]

AGENTS = [
    # Healthcare
    ("AG-HC-1011", "Rachel Kim",                          None,          "Member Authorization Team",      "Human"),
    ("AG-HC-1027", "Michael Torres",                      None,          "Member Authorization Team",      "Human"),
    ("AG-HC-1033", "Sandra Patel",                        None,          "Member Authorization Team",      "Human"),
    ("AG-HC-2001", "David Osei",                          None,          "Escalation Desk",                "Human"),
    ("AG-HC-3001", "Dr. Lisa Chen",                       None,          "Clinical Resolution Team",       "Human"),
    ("AG-HC-1044", "Christine Walsh",                     None,          "Pharmacy Benefits Team",         "Human"),
    ("AG-HC-1052", "James Bradley",                       None,          "Provider Authorization Team",    "Human"),
    ("AG-HC-1067", "Patricia Lee",                        None,          "Pharmacy Benefits Team",         "Human"),
    ("AG-HC-1074", "Kevin Morris",                        None,          "Digital Member Care",            "Human"),
    ("AG-HC-2008", "Maria Gonzalez",                      None,          "Clinical Escalation Team",       "Human"),
    ("AG-HC-3005", "Dr. Amanda Foster",                   None,          "Clinical Operations",            "Human"),
    ("AG-HC-BOT",  "CareFirst Bot",                       None,          "Virtual Member Assistant",       "Bot"),
    ("AG-HC-PORTAL","Portal System",                      None,          "Member Portal",                  "System"),
    # ISP
    ("AG-ISP-2201", "Marcus Webb",                        None,          "Tier 1 Tech Support",            "Human"),
    ("AG-ISP-2214", "Priya Nair",                         None,          "Tier 1 Tech Support",            "Human"),
    ("AG-ISP-2238", "Jordan Ellis",                       None,          "Digital Support Team",           "Human"),
    ("AG-ISP-2251", "Diane Forsyth",                      None,          "Tier 1 Tech Support",            "Human"),
    ("AG-ISP-2263", "Tyler Brooks",                       None,          "Social Media Response Team",     "Human"),
    ("AG-ISP-3001", "Samantha Cruz",                      None,          "Priority Resolution Team",       "Human"),
    ("AG-ISP-APP",  "StreamLine App System",              None,          "My StreamLine App",              "System"),
    ("AG-ISP-2290", "Liam Foster",                        None,          "Installations Team",             "Human"),
    ("AG-ISP-2305", "Rosa Whitfield",                     None,          "Installations Team",             "Human"),
    ("AG-ISP-2317", "Nathan Cole",                        None,          "Digital Support Team",           "Human"),
    ("AG-ISP-2329", "Isabel Reyes",                       None,          "Digital Member Care",            "Human"),
    # Banking
    ("AG-BNK-1041", "Sophie Brennan",                     None,          "Card Services Team",             "Human"),
    ("AG-BNK-1058", "Marcus Webb",                        None,          "Card Services Team",             "Human"),
    ("AG-BNK-1067", "Priya Nair",                         None,          "Digital Support Team",           "Human"),
    ("AG-BNK-3002", "Catherine Holt",                     None,          "Client Retention Team",          "Human"),
    ("AG-BNK-1072", "Tom Aldridge",                       None,          "Payments Team",                  "Human"),
    ("AG-BNK-1085", "Fiona Marsh",                        None,          "Payments Team",                  "Human"),
    ("AG-BNK-1091", "James Okafor",                       None,          "Digital Support Team",           "Human"),
    ("AG-BNK-4001", "Richard Osei",                       None,          "Compliance Resolution Team",     "Human"),
    ("AG-BNK-APP",  "App System",                         None,          "Mobile Banking App",             "System"),
    ("AG-BNK-AUTO", "System",                             None,          "Automated Payments Notification","System"),
    # Insurance
    ("AG-1023",     "Sarah Collins",                      "TEAM-POLICY", "Policy Services",                "Human"),
    ("AG-2088",     "David Chen",                         "TEAM-DIGITAL","Digital Care",                   "Human"),
    ("AG-INS-KEVIN","Kevin Moore",                        None,          "Billing Support",                "Human"),
    ("AG-INS-DAN",  "Daniel Ross",                        None,          "Escalation Desk",                "Human"),
    ("AG-INS-LAURA","Laura Bennett",                      None,          "Customer Resolution",            "Human"),
    ("BOT-001",     "SafeLife Assistant",                 "TEAM-DIGITAL","Digital Support",                "Bot"),
    ("SYS-001",     "Unassigned",                         "TEAM-POLICY", "Policy Services",                "System"),
    ("AG-INS-SAR2", "James Thompson",                     None,          "Claims Team",                    "Human"),
    ("AG-INS-UND",  "Patricia Hughes",                    None,          "Underwriting Team",              "Human"),
    ("AG-INS-ESC",  "Rachel Foster",                      None,          "Escalation Desk",                "Human"),
    ("AG-INS-SUP",  "Michael Davis",                      None,          "Supervisor Team",                "Human"),
    ("AG-INS-MGR",  "Jennifer Walsh",                     None,          "Customer Resolution",            "Human"),
    ("AG-INS-BOT2", "InsureBot",                          None,          "Digital Support",                "Bot"),
    ("AG-INS-WA1",  "Thomas Brown",                       None,          "Digital Care",                   "Human"),
    ("AG-INS-WA2",  "Amanda Clarke",                      None,          "Digital Care",                   "Human"),
    ("AG-INS-ESC2", "Steven Morris",                      None,          "Escalation Desk",                "Human"),
    ("AG-INS-MGR2", "Catherine Reed",                     None,          "Customer Resolution",            "Human"),
]

CUSTOMERS = [
    # Healthcare
    ("CUST-HC-10021", "Jennifer Martinez", "Healthcare", "PPO Premium",  None, "PPO — Premium Family Plan", "ACC-HC-10021", "MBR-774412",  None),
    ("CUST-HC-20044", "Robert Nguyen",     "Healthcare", "HMO Silver",   None, "HMO — Individual Silver Plan","ACC-HC-20044","MBR-882231",  None),
    # ISP
    ("CUST-ISP-30017","Emily Carter",      "ISP",        None,           None, "Ultra Fiber 500 — Residential","ACC-SL-994421",None,         None),
    ("CUST-ISP-40083","Emily Hartwell",    "ISP",        None,           None, "Fiber Home 250 — New Connection","ACC-SL-771290",None,        None),
    # Banking
    ("CUST-BNK-20045","David Kowalski",    "Banking",    "Gold Member",  7,    "Visa Platinum Credit Card",  "ACC-774-992-11",None,         None),
    ("CUST-BNK-30087","Elena Vasquez",     "Banking",    "Silver Member",4,    "Business Banking",           "ACC-881-447-22",None,         None),
    # Insurance
    ("CUST-45821",    "Michael Johnson",   "Insurance",  None,           None, "Auto Insurance",             None,           None,          "POL-784512"),
    ("CUST-88241",    "Sarah Williams",    "Insurance",  None,           None, "Home Insurance",             None,           None,          "HOM-661234"),
    ("CUST-INS-30001","James Patterson",   "Insurance",  None,           None, "Life Insurance",             None,           None,          "LIF-445521"),
    ("CUST-INS-40001","Anna Rodriguez",    "Insurance",  None,           None, "Auto Insurance",             None,           None,          "AUT-338812"),
    ("CUST-INS-50001","David Kim",         "Insurance",  None,           None, "Home Insurance",             None,           None,          "HOM-992241"),
    ("CUST-INS-60001","Lisa Thompson",     "Insurance",  None,           None, "Auto Insurance",             None,           None,          "AUT-771190"),
]

JOURNEY_SESSIONS = [
    # Healthcare — Scenario A
    (
        "MC-AUTH-HC-220891", "CUST-HC-10021", "TENANT-HC-001", "Healthcare",
        "The Prior Authorization That Blocked Treatment",
        "AUTH-HC-220891", "Prior Authorization",
        "2026-06-02T10:15:00Z", "2026-06-18T18:48:00Z", 7,
        9.5, "CRITICAL RISK", "Resolved",
        "Prior authorization request was received but never assigned to a clinical reviewer. "
        "The system lacked automatic escalation triggers for time-sensitive medical cases. "
        "An agent promise of expedited review was not backed by any system action. "
        "No proactive outbound communication process existed."
    ),
    # Healthcare — Scenario C
    (
        "MC-STP-HC-334421", "CUST-HC-20044", "TENANT-HC-001", "Healthcare",
        "The Prescription That Couldn't Be Filled",
        "STP-HC-334421", "Step Therapy Exception",
        "2026-07-01T14:20:00Z", "2026-07-10T14:22:00Z", 7,
        9.3, "CRITICAL RISK", "Resolved",
        "Step therapy exception request was misrouted to the standard prior authorization queue at first contact. "
        "Two separate agents promised 24-hour callbacks which were not fulfilled. "
        "No system trigger existed to detect a patient approaching medication exhaustion."
    ),
    # ISP — Scenario A
    (
        "MC-TKT-ISP-884401", "CUST-ISP-30017", "TENANT-ISP-001", "ISP",
        "The Connection That Never Got Fixed",
        "TKT-ISP-884401", "Speed Issue",
        "2026-09-01T09:20:00Z", "2026-09-14T10:44:00Z", 7,
        9.1, "CRITICAL RISK", "Escalated",
        "Speed fault was caused by a signal-level issue that remote resets could not address. "
        "The first ticket was prematurely closed without verification. "
        "No auto-escalation rule existed for tickets unresolved after 5 days. "
        "Three callback promises were made with no tracking or enforcement mechanism."
    ),
    # ISP — Scenario B
    (
        "MC-ORD-SL-552018", "CUST-ISP-40083", "TENANT-ISP-001", "ISP",
        "The Technician Who Never Showed Up",
        "ORD-SL-552018", "New Installation",
        "2026-09-05T14:00:00Z", "2026-09-15T09:00:00Z", 5,
        9.4, "CRITICAL RISK", "Escalated",
        "StreamLine accepted a new installation order for a multi-dwelling unit without completing "
        "a pre-sale infrastructure survey, making the promised service delivery impossible from the outset. "
        "Four separate callback and escalation promises were made by different agents across different channels "
        "with no centralised tracking or enforcement."
    ),
    # Banking — Scenario A
    (
        "MC-CARD-BNK-7731", "CUST-BNK-20045", "TENANT-BNK-001", "Banking",
        "The Credit Card That Kept Getting Blocked",
        "ACC-774-992-11", "Card Block",
        "2026-05-01T09:10:00Z", "2026-06-03T11:22:00Z", 7,
        8.2, "HIGH CHURN RISK", "Resolved",
        "The automated fraud detection rule flagged a known merchant as suspicious on every billing cycle. "
        "Agents were not shown interaction history at the start of each call, so each contact was handled in isolation. "
        "The correct resolution path was never taken because no system logic prompted it."
    ),
    # Banking — Scenario B
    (
        "MC-TRF-BNK-447221", "CUST-BNK-30087", "TENANT-BNK-001", "Banking",
        "The International Transfer That Nobody Fixed",
        "TRF-BNK-990041", "SEPA Transfer Block",
        "2026-04-07T13:15:00Z", "2026-05-08T10:55:00Z", 7,
        9.1, "CRITICAL CHURN RISK", "Resolved",
        "A new AML compliance rule triggered on a regular, legitimate SEPA transfer. "
        "Payments agents had no visibility into the compliance hold reason, leading to repeated incorrect attribution "
        "to the receiving bank. The first resolution cleared the individual transfer but did not apply a standing exception."
    ),
    # Insurance — Scenario 1
    (
        "MC-POL-784512", "CUST-45821", "TENANT-INS-001", "Insurance",
        "The Never-Ending Policy Cancellation",
        "POL-784512", "Policy Cancellation",
        "2026-04-01T09:12:00Z", "2026-04-18T00:00:00Z", 7,
        9.2, "HIGH RISK", "Resolved",
        "No owner was assigned to the cancellation request. The request remained pending across multiple teams, "
        "resulting in a broken promise, additional premium deduction, repeated contacts, and eventual escalation."
    ),
    # Insurance — Scenario 2
    (
        "MC-CLM-772191", "CUST-88241", "TENANT-INS-001", "Insurance",
        "The Claim Nobody Owned",
        "CLM-772191", "Home Insurance Claim",
        "2026-05-01T09:05:00Z", "2026-05-18T00:00:00Z", 7,
        9.0, "HIGH RISK", "Resolved",
        "Multiple departments involved with no single owner assigned. "
        "Claims team and Underwriting team each pointed to the other. "
        "Repeated storytelling required and conflicting information provided across contacts."
    ),
    # Insurance — Scenario 3
    (
        "MC-LIF-445521", "CUST-INS-30001", "TENANT-INS-001", "Insurance",
        "The Policy Update That Was Never Applied",
        "LIF-445521", "Policy Update",
        "2026-06-01T00:00:00Z", "2026-06-18T00:00:00Z", 7,
        8.8, "HIGH RISK", "Resolved",
        "Customer submitted a beneficiary update request that was not processed. "
        "Multiple follow-up contacts yielded conflicting statuses. "
        "Escalation required before the update was finally applied."
    ),
    # Insurance — Scenario 4
    (
        "MC-AUT-338812", "CUST-INS-40001", "TENANT-INS-001", "Insurance",
        "The Premium That Wouldn't Stop",
        "AUT-338812", "Billing Dispute",
        "2026-07-01T00:00:00Z", "2026-07-18T00:00:00Z", 7,
        9.1, "CRITICAL RISK", "Resolved",
        "Customer cancelled policy but premium continued to be deducted. "
        "Billing system not updated after cancellation confirmation. "
        "Multiple contacts required before refund and stop of payments was confirmed."
    ),
    # Insurance — Scenario 5
    (
        "MC-HOM-992241", "CUST-INS-50001", "TENANT-INS-001", "Insurance",
        "The Renewal Campaign That Never Stopped",
        "HOM-992241", "Marketing Opt-Out",
        "2026-08-01T00:00:00Z", "2026-08-18T00:00:00Z", 7,
        7.5, "MEDIUM RISK", "Resolved",
        "Customer submitted opt-out request for renewal marketing communications. "
        "Emails, SMS and WhatsApp messages continued after confirmed opt-out. "
        "Compliance team intervention required to suppress all channels."
    ),
    # Insurance — Scenario 6
    (
        "MC-AUT-771190", "CUST-INS-60001", "TENANT-INS-001", "Insurance",
        "The Accident Claim Escalation Spiral",
        "AUT-771190", "Auto Insurance Claim",
        "2026-09-01T00:00:00Z", "2026-09-18T00:00:00Z", 7,
        9.4, "CRITICAL RISK", "Resolved",
        "Accident claim submitted but assessor not assigned for 8 days. "
        "Customer received no proactive updates and conflicting repair timeline information. "
        "Escalation spiral required executive manager intervention before claim was progressed."
    ),
]

INTERACTIONS = [
    # ── Healthcare Scenario A ──────────────────────────────────────────────
    ("CNT-HC-10001","MC-AUTH-HC-220891","TENANT-HC-001","2026-06-02T10:15:00Z","2026-06-02T10:26:00Z",None,
     "VOICE","INBOUND","CH-VOICE-01","SK-VOICE-01","Member Services — Authorization",
     "AG-HC-1011","Pending Review",660,"Neutral",3,0,0,1,None,None,None,None,None,
     "memberId=MBR-774412 | authNumber=AUTH-HC-220891 | requestType=Prior Authorization",
     "Rachel: Thank you for calling CareFirst Member Services. How can I help you today?\n"
     "Jennifer: Hi. My doctor submitted a prior authorization for a cardiology referral a few days ago. I just want to confirm you received it.\n"
     "Rachel: I can see an authorization request on file. Reference number AUTH-HC-220891.\n"
     "Jennifer: Great. When can I expect a decision? My appointment is scheduled for June 18th.\n"
     "Rachel: Authorizations are typically reviewed within 5 to 7 business days.",
     "Authorization confirmed as received. Standard timeline communicated. No urgency flag raised."),

    ("CNT-HC-10002","MC-AUTH-HC-220891","TENANT-HC-001","2026-06-05T14:30:00Z",None,None,
     "DIGITAL — SELF SERVICE","INBOUND","CH-PORTAL-01",None,"Member Portal",
     "AG-HC-PORTAL","Self Service — No Resolution",None,"Slightly Negative",None,0,0,2,None,None,None,None,None,
     "memberId=MBR-774412 | authNumber=AUTH-HC-220891 | portalAction=Status Check",
     "Jennifer: Logged into member portal. Navigated to: My Authorizations > View Status.\n"
     "Portal: Authorization AUTH-HC-220891 — Status: PENDING REVIEW.\n"
     "Jennifer: Clicked View Details — no additional information available.",
     "Portal shows Pending Review with no timeline or contact option. No further action available to patient."),

    ("CNT-HC-10003","MC-AUTH-HC-220891","TENANT-HC-001","2026-06-09T11:00:00Z","2026-06-09T11:18:00Z",None,
     "VOICE","INBOUND","CH-VOICE-01",None,"Member Services — Authorization",
     "AG-HC-1027","Follow Up Required",1080,"Negative",2,0,0,3,None,None,None,None,None,
     "memberId=MBR-774412",
     "Jennifer: It's been a week and my authorization is still showing pending. My appointment is in nine days.\n"
     "Michael: I can see the request is still in review. Let me check if it has been assigned to a clinical reviewer.\n"
     "Jennifer: Has it?\nMichael: I don't see an assigned reviewer at this time.\n"
     "Michael: I can request an expedited review. You should receive an update within 48 hours.",
     "Urgent flag requested by agent. Promise made: update within 48 hours. No action confirmed in system."),

    ("CNT-HC-10004","MC-AUTH-HC-220891","TENANT-HC-001","2026-06-12T09:05:00Z",None,None,
     "EMAIL","INBOUND","CH-EMAIL-01",None,"Member Services — Written Complaints",
     None,"Follow-Up Request",None,"Very Negative",None,0,0,4,None,None,
     "jennifer.martinez@email.com","complaints@carefirst.com",
     "memberId=MBR-774412 | authNumber=AUTH-HC-220891",
     "Subject: No Update on Prior Authorization — Appointment in 6 Days\n"
     "I was promised an update within 48 hours when I called on June 9th. I have received nothing. "
     "My specialist appointment is scheduled for June 18th and I cannot attend without authorization.",
     "Email received and logged. No response sent within SLA. Authorization still unassigned."),

    ("CNT-HC-10005","MC-AUTH-HC-220891","TENANT-HC-001","2026-06-18T15:45:00Z","2026-06-18T16:08:00Z",None,
     "VOICE","INBOUND","CH-VOICE-01",None,"Member Services — Authorization",
     "AG-HC-1033","Complaint — Missed Appointment",1380,"Very Negative",1,0,1,5,None,None,None,None,None,
     "memberId=MBR-774412",
     "Jennifer: My appointment was today. The hospital turned me away because the authorization was not approved.\n"
     "Sandra: I am very sorry to hear that, Mrs. Martinez. Let me review your file.\n"
     "Jennifer: This is a cardiac referral. My doctor saw something concerning on my ECG.\n"
     "Sandra: I sincerely apologize. I will escalate this immediately.",
     "Appointment missed. Medical treatment delayed. Escalation flag raised. Supervisor review requested."),

    ("CNT-HC-10006","MC-AUTH-HC-220891","TENANT-HC-001","2026-06-18T16:10:00Z",None,None,
     "VOICE","INBOUND","CH-VOICE-01",None,"Escalation Desk",
     "AG-HC-2001","Clinical Review — Emergency Escalation",1200,"Very Negative",1,0,1,6,None,None,None,None,None,
     "memberId=MBR-774412",
     "David: Mrs. Martinez, I understand you have been escalated to our resolution team. I have reviewed your full case.\n"
     "Jennifer: This is a heart condition. This is not a routine referral.\n"
     "David: I am initiating an emergency clinical review right now.",
     "Emergency clinical review initiated. Manager callback promised within 2 hours."),

    ("CNT-HC-10007","MC-AUTH-HC-220891","TENANT-HC-001","2026-06-18T18:30:00Z","2026-06-18T18:48:00Z",None,
     "VOICE","OUTBOUND","CH-CALLBACK-01",None,"Clinical Resolution Team",
     "AG-HC-3001","Resolved",1080,"Positive",4,0,0,7,None,None,None,None,None,
     "memberId=MBR-774412",
     "Dr. Chen: Mrs. Martinez, I am the Clinical Operations Manager. I have personally reviewed your authorization and it has been fully approved.\n"
     "Jennifer: Finally. It has been nineteen days.\n"
     "Dr. Chen: We have already contacted Riverside Heart Center. Your appointment has been rescheduled for June 22nd.",
     "Authorization approved. Appointment rescheduled June 22nd. Cancellation fees waived. Case resolved."),

    # ── Healthcare Scenario C ──────────────────────────────────────────────
    ("CNT-HC-20001","MC-STP-HC-334421","TENANT-HC-001","2026-07-01T14:20:00Z","2026-07-01T14:35:00Z",None,
     "VOICE","INBOUND","CH-VOICE-01",None,"Pharmacy Benefits — Member Services",
     "AG-HC-1044","Information Provided — Incorrect",900,"Slightly Negative",2,0,0,1,None,None,None,None,None,
     "memberId=MBR-882231 | medication=Ozempic 1mg | rejectionCode=ST-PRIOR-AUTH",
     "Robert: I just tried to fill my prescription at the pharmacy and they said my insurance rejected it.\n"
     "Christine: It appears your plan requires step therapy for this medication.\n"
     "Christine: Your doctor can submit an exception request on your behalf.",
     "Patient given incorrect process information — step therapy exception routed through wrong channel."),

    ("CNT-HC-20002","MC-STP-HC-334421","TENANT-HC-001","2026-07-03T10:00:00Z","2026-07-03T10:22:00Z",None,
     "VOICE","INBOUND","CH-VOICE-01",None,"Provider Services — Prior Authorization",
     "AG-HC-1052","Routed Incorrectly",1320,"Negative",2,1,0,2,None,None,None,None,None,
     "memberId=MBR-882231 | requestType=Step Therapy Exception",
     "Dr. Shaw's Office: I'd like to submit a step therapy exception request for Ozempic 1mg.\n"
     "James: I will submit this to our pharmacy benefits team for review.\n"
     "James: The team will be in touch within 24 hours.",
     "Exception request submitted but routed to standard Prior Authorization queue. 24-hour callback promised."),

    ("CNT-HC-20003","MC-STP-HC-334421","TENANT-HC-001","2026-07-05T18:00:00Z","2026-07-05T18:08:00Z",None,
     "CHAT — SELF SERVICE","INBOUND","CH-CHAT-BOT",None,"Virtual Member Assistant",
     "AG-HC-BOT","Self Service Failed",480,"Negative",None,0,0,3,None,None,None,None,None,
     "memberId=MBR-882231",
     "Robert: I want to check the status of my prescription exception request.\n"
     "Bot: I do not see any open exception requests on file.\n"
     "Robert: That cannot be right. My doctor called two days ago.\n"
     "Bot: I am unable to locate pending exception requests. Please contact Member Services.",
     "Chatbot cannot locate exception request — confirms routing error from Interaction 2. No agent available."),

    ("CNT-HC-20004","MC-STP-HC-334421","TENANT-HC-001","2026-07-07T11:30:00Z","2026-07-07T11:52:00Z",None,
     "VOICE","INBOUND","CH-VOICE-01",None,"Pharmacy Benefits Team",
     "AG-HC-1067","Follow Up Required — Urgent",1320,"Very Negative",1,0,0,4,None,None,None,None,None,
     "memberId=MBR-882231",
     "Robert: I submitted an exception request four days ago. I have less than three days of medication left.\n"
     "Patricia: I see the request is in our standard prior authorization queue. It doesn't appear to have been routed as a step therapy exception.\n"
     "Patricia: I am going to re-route this to the correct team right now and flag it as urgent.",
     "Routing error identified and corrected. Second 24-hour callback promise made. Urgency flag added."),

    ("CNT-HC-20005","MC-STP-HC-334421","TENANT-HC-001","2026-07-09T08:15:00Z",None,None,
     "DIGITAL — WHATSAPP","INBOUND","CH-WA-01",None,"Digital Member Care",
     "AG-HC-1074","Emergency Escalation",960,"Very Negative",1,0,1,5,None,None,None,None,None,
     "memberId=MBR-882231",
     "Robert: I have run out of my diabetes medication. I have been waiting nine days.\n"
     "Kevin: Mr. Nguyen, I am very concerned to hear this. Let me review your case immediately.\n"
     "Kevin: I am treating this as a medical emergency.",
     "Medical emergency flagged. Patient without medication. Emergency clinical escalation initiated."),

    ("CNT-HC-20006","MC-STP-HC-334421","TENANT-HC-001","2026-07-09T09:00:00Z","2026-07-09T09:28:00Z",None,
     "VOICE","INBOUND","CH-VOICE-01",None,"Clinical Escalation Team",
     "AG-HC-2008","Emergency Review — Pending Clinical Approval",1680,"Very Negative",1,0,1,6,None,None,None,None,None,
     "memberId=MBR-882231",
     "Maria: I am issuing an emergency temporary authorization right now so you can pick up a 7-day supply today.\n"
     "Robert: Thank you. I really needed to hear that.",
     "Emergency temporary authorization issued for 7-day supply. Full exception escalated to Chief Pharmacy Officer."),

    ("CNT-HC-20007","MC-STP-HC-334421","TENANT-HC-001","2026-07-10T14:00:00Z","2026-07-10T14:22:00Z",None,
     "VOICE","OUTBOUND","CH-CALLBACK-01",None,"Clinical Operations",
     "AG-HC-3005","Resolved",1320,"Positive",4,0,0,7,None,None,None,None,None,
     "memberId=MBR-882231",
     "Dr. Foster: Your full exception has now been approved. Ozempic 1mg is now an approved medication on your plan for 12 months.\n"
     "Robert: That is a relief. This has been a very stressful two weeks.",
     "Full step therapy exception approved for 12 months. Co-pay waived for 90-day supply. Case resolved."),

    # ── ISP Scenario A ─────────────────────────────────────────────────────
    ("CNT-ISP-30001","MC-TKT-ISP-884401","TENANT-ISP-001","2026-09-01T09:20:00Z","2026-09-01T09:34:00Z",None,
     "VOICE","INBOUND","CH-VOICE-01",None,"Technical Support — Internet",
     "AG-ISP-2201","Remote Test Completed — Ticket Closed",840,"Slightly Negative",3,0,0,1,None,None,None,None,None,
     "accountId=ACC-SL-994421 | planSpeed=500Mbps | reportedSpeed=12Mbps | ticketType=Speed Issue",
     "Emily: My internet has been really slow since yesterday evening. I'm paying for 500 Mbps and I'm getting about 12.\n"
     "Marcus: The diagnostic is showing some signal fluctuation. I'm going to reset your router remotely.\n"
     "Marcus: Your ticket number is TKT-ISP-884401.",
     "Remote reset performed. Ticket logged. Ticket prematurely closed as Resolved — no follow-up scheduled."),

    ("CNT-ISP-30002","MC-TKT-ISP-884401","TENANT-ISP-001","2026-09-03T14:10:00Z","2026-09-03T14:28:00Z",None,
     "VOICE","INBOUND","CH-VOICE-01",None,"Technical Support — Internet",
     "AG-ISP-2214","Router Reset — Monitoring Requested",1080,"Negative",2,0,0,2,None,None,None,None,None,
     "accountId=ACC-SL-994421 | priorTicket=TKT-ISP-884401 | repeatContact=TRUE",
     "Emily: I called two days ago about my internet speed. It's still slow — if anything it's gotten worse.\n"
     "Priya: I can see the ticket from the 1st. It's showing as resolved.\n"
     "Emily: It is not resolved.",
     "Second remote reset applied. Monitoring flag added — no automated escalation trigger configured."),

    ("CNT-ISP-30003","MC-TKT-ISP-884401","TENANT-ISP-001","2026-09-06T19:45:00Z","2026-09-06T19:52:00Z",None,
     "DIGITAL — SELF SERVICE","INBOUND","CH-APP-01",None,"My StreamLine App",
     "AG-ISP-APP","Self Service — No Resolution",None,"Negative",None,0,0,3,None,None,None,None,None,
     "accountId=ACC-SL-994421 | appAction=Ticket Status Check",
     "Emily: Opened My StreamLine app. Navigated to: Support > My Tickets.\n"
     "App: TKT-ISP-884401 — Status: RESOLVED.\n"
     "Emily: Tapped Reopen Ticket — option greyed out.\n"
     "App speed test: 9.4 Mbps download / 1.2 Mbps upload.",
     "App shows ticket as Resolved despite ongoing fault. Speed test confirms 9.4 Mbps. No ability to reopen."),

    ("CNT-ISP-30004","MC-TKT-ISP-884401","TENANT-ISP-001","2026-09-08T11:05:00Z","2026-09-08T11:29:00Z",None,
     "CHAT — LIVE AGENT","INBOUND","CH-CHAT-LIVE",None,"Technical Support — Chat",
     "AG-ISP-2238","Technician Visit Scheduled",1440,"Negative",2,0,0,4,None,None,None,None,None,
     "accountId=ACC-SL-994421 | repeatContact=TRUE",
     "Emily: My ticket TKT-ISP-884401 is marked resolved but my internet is still at under 10 Mbps.\n"
     "Jordan: I agree a technician visit is the right next step. I can book that for you now.\n"
     "Jordan: The earliest slot I have is September 12th, between 8am and 1pm.",
     "Technician visit booked for September 12th. No escalation to Tier 2 despite 3 contacts."),

    ("CNT-ISP-30005","MC-TKT-ISP-884401","TENANT-ISP-001","2026-09-12T14:55:00Z","2026-09-12T15:18:00Z",None,
     "VOICE","INBOUND","CH-VOICE-01",None,"Technical Support — Internet",
     "AG-ISP-2251","Complaint — Technician No Access",1380,"Very Negative",1,0,1,5,None,None,None,None,None,
     "accountId=ACC-SL-994421 | techVisit=TECH-SL-44821 | outcome=NoEntry",
     "Emily: I had a technician booked for today. I was home all morning. Nobody came.\n"
     "Diane: I can see the technician marked the visit as No Access — Customer Not Home.\n"
     "Emily: I was home. I did not leave the house.",
     "Technician marked job closed as No Access without attempting contact. Complaint logged."),

    ("CNT-ISP-30006","MC-TKT-ISP-884401","TENANT-ISP-001","2026-09-14T08:30:00Z","2026-09-14T09:05:00Z",None,
     "DIGITAL — SOCIAL MEDIA","INBOUND","CH-SOCIAL-01",None,"Social Media — Customer Care",
     "AG-ISP-2263","Escalation — Supervisor Assigned",2100,"Very Negative",1,0,1,6,None,None,None,None,None,
     "accountId=ACC-SL-994421 | platform=Twitter/X | sentimentScore=-0.89",
     "@StreamLineBB 14 days of internet under 10 Mbps on a 500 Mbps plan. Two resets. A technician who didn't show up.\n"
     "Tyler: Hi Emily, we are very sorry to see this. We've sent you a DM.",
     "Public post generated reputational exposure. Escalated to Priority Resolution supervisor."),

    ("CNT-ISP-30007","MC-TKT-ISP-884401","TENANT-ISP-001","2026-09-14T10:15:00Z","2026-09-14T10:44:00Z",None,
     "VOICE","OUTBOUND","CH-CALLBACK-01",None,"Priority Resolution — Supervisor",
     "AG-ISP-3001","Field Fault Escalated — Second Technician Dispatched",1740,"Slightly Negative",3,0,1,7,None,None,None,None,None,
     "accountId=ACC-SL-994421 | priorityFlag=TRUE",
     "Samantha: Hello, is this Emily Carter? I'm Samantha Cruz, Priority Resolution supervisor at StreamLine.\n"
     "Samantha: I'm booking a priority technician for September 17th — a dedicated slot, 10am to 11am.\n"
     "Samantha: I'm applying a credit of 50% of your monthly bill for the period September 1st to the date of resolution.",
     "Priority technician booked September 17th. Bill credit of 50% applied. Cancellation threat noted."),

    # ── ISP Scenario B ─────────────────────────────────────────────────────
    ("CNT-ISP-40001","MC-ORD-SL-552018","TENANT-ISP-001","2026-09-05T14:00:00Z","2026-09-05T14:19:00Z",None,
     "VOICE","INBOUND","CH-VOICE-01",None,"New Installations — Customer Services",
     "AG-ISP-2290","Appointment Rescheduled — No Notice Given",1140,"Negative",2,0,0,1,None,None,None,None,None,
     "accountId=ACC-SL-771290 | orderId=ORD-SL-552018 | installDate=2026-09-05 | techStatus=Reassigned",
     "Emily: My installation was booked for today and nobody has come.\n"
     "Liam: It looks like the technician assigned to your area was reallocated this morning.\n"
     "Emily: Why wasn't I told?\nLiam: I can rebook for September 9th.",
     "Appointment missed due to unnotified technician reallocation. Rescheduled to September 9th."),

    ("CNT-ISP-40002","MC-ORD-SL-552018","TENANT-ISP-001","2026-09-09T13:10:00Z","2026-09-09T13:35:00Z",None,
     "VOICE","INBOUND","CH-VOICE-01",None,"New Installations — Customer Services",
     "AG-ISP-2305","Infrastructure Issue — Field Engineering Required",1500,"Very Negative",1,0,1,2,None,None,None,None,None,
     "accountId=ACC-SL-771290 | outcome=InfrastructureFault",
     "Emily: The technician came this morning but left without installing anything. He said the building doesn't have the right cabling infrastructure.\n"
     "Rosa: I need to escalate this to our field engineering team. They'll need to survey the building.\n"
     "Rosa: I'd expect a survey within 48 hours.",
     "Infrastructure fault identified at address. Field engineering survey requested. 48-hour survey timeline promised."),

    ("CNT-ISP-40003","MC-ORD-SL-552018","TENANT-ISP-001","2026-09-10T10:25:00Z","2026-09-10T10:50:00Z",None,
     "CHAT — LIVE AGENT","INBOUND","CH-CHAT-LIVE",None,"New Installations — Chat",
     "AG-ISP-2317","Engineering Survey — Unconfirmed",1500,"Very Negative",1,0,0,3,None,None,None,None,None,
     "accountId=ACC-SL-771290 | surveyStatus=NotScheduled",
     "Emily: I was told a field engineering survey would happen within 48 hours. I've received no contact.\n"
     "Nathan: I can see the referral is in the engineering queue. I don't have a confirmed booking date yet.",
     "Engineering survey still not scheduled 24+ hours after promise. Urgent flag re-raised."),

    ("CNT-ISP-40004","MC-ORD-SL-552018","TENANT-ISP-001","2026-09-14T16:40:00Z","2026-09-14T17:05:00Z",None,
     "DIGITAL — WHATSAPP","INBOUND","CH-WA-01",None,"Digital Care — WhatsApp",
     "AG-ISP-2329","Conflicting Information — Escalation Required",1500,"Very Negative",1,0,1,4,None,None,None,None,None,
     "accountId=ACC-SL-771290 | daysSinceOrder=16 | connectionStatus=NotInstalled",
     "Emily: It has been 9 days since my installation should have happened. I still have no internet.\n"
     "Isabel: I can see a survey was completed on September 13th.\n"
     "Emily: Nobody came to my apartment. Nobody contacted me.",
     "External survey completed without customer notification. Cabling upgrade confirmed but no ETA."),

    ("CNT-ISP-40005","MC-ORD-SL-552018","TENANT-ISP-001","2026-09-15T09:00:00Z",None,None,
     "EMAIL","INBOUND","CH-EMAIL-01",None,"Customer Relations — Complaints",
     None,"Formal Complaint Received — Case Manager Assigned",None,"Very Negative",None,0,1,5,None,None,
     "emily.hartwell@email.com","complaints@streamline.com",
     "accountId=ACC-SL-771290",
     "Subject: Formal Complaint — Order ORD-SL-552018 — 14 Days Without Service\n"
     "My installation was originally booked for September 5th. It is now September 15th and I still have no internet service.",
     "Formal complaint received. Case manager assigned. No confirmed installation date available."),

    # ── Banking Scenario A ─────────────────────────────────────────────────
    ("CNT-BNK-20001","MC-CARD-BNK-7731","TENANT-BNK-001","2026-05-01T09:10:00Z","2026-05-01T09:24:00Z",None,
     "VOICE","INBOUND","CH-VOICE-01",None,"Card Services — Block & Unblock",
     "AG-BNK-1041","Card Unblocked",840,"Slightly Negative",3,0,0,1,None,None,None,None,None,
     "accountId=ACC-774-992-11 | cardLast4=7731 | blockReason=FraudRule-FX-Recur | merchantId=STRM-EU-4421",
     "David: My credit card has been blocked. I tried to pay for my Netflix subscription.\n"
     "Sophie: I can see the card was blocked by our automated fraud detection system.\n"
     "Sophie: I'll unblock the card for you now.",
     "Card unblocked. Recurring foreign merchant not whitelisted. No investigation triggered."),

    ("CNT-BNK-20002","MC-CARD-BNK-7731","TENANT-BNK-001","2026-05-03T18:45:00Z",None,None,
     "DIGITAL — SELF SERVICE","INBOUND","CH-APP-01",None,"Mobile Banking App",
     "AG-BNK-APP","Self Service — No Resolution",None,"Neutral",None,0,0,2,None,None,None,None,None,
     "accountId=ACC-774-992-11 | cardLast4=7731 | action=StatusCheck",
     "David: Logged into NorthPoint mobile app. Navigated to: Cards > Card 7731 > Status.\n"
     "App: Card Status: ACTIVE.\n"
     "David: Tapped Notifications Settings — no option to whitelist merchants.",
     "Self-service provides no resolution path. No block history visible."),

    ("CNT-BNK-20003","MC-CARD-BNK-7731","TENANT-BNK-001","2026-05-15T08:30:00Z","2026-05-15T08:51:00Z",None,
     "VOICE","INBOUND","CH-VOICE-01",None,"Card Services — Block & Unblock",
     "AG-BNK-1058","Card Unblocked",1260,"Negative",2,0,0,3,None,None,None,None,None,
     "accountId=ACC-774-992-11 | cardLast4=7731 | blockReason=FraudRule-FX-Recur | priorContacts=1",
     "David: My card has been blocked again. This is the second time in two weeks.\n"
     "Marcus: I can see the card has been blocked due to a foreign recurring transaction.\n"
     "David: Can someone actually fix this permanently?\nMarcus: I'll unblock the card and add a note to your file.",
     "Card unblocked a second time. No interaction history carried forward. Root cause still unresolved."),

    ("CNT-BNK-20004","MC-CARD-BNK-7731","TENANT-BNK-001","2026-05-17T14:10:00Z","2026-05-17T14:28:00Z",None,
     "DIGITAL — LIVE CHAT","INBOUND","CH-CHAT-LIVE",None,"Digital Support — Card Queries",
     "AG-BNK-1067","Advisory — No Action Taken",1080,"Negative",2,0,0,4,None,None,None,None,None,
     "accountId=ACC-774-992-11 | contactReason=FraudPrevention",
     "David: My card keeps getting blocked by your fraud system. How do I stop it from happening a third time?\n"
     "Priya: Unfortunately I am not able to modify fraud detection rules from this channel. You would need to call Card Services.\n"
     "David: I've already called Card Services twice. They just unblock it and nothing changes.",
     "Chat agent could not modify fraud rules. Customer directed back to phone — the channel that already failed twice."),

    ("CNT-BNK-20005","MC-CARD-BNK-7731","TENANT-BNK-001","2026-05-29T19:05:00Z","2026-05-29T19:42:00Z",None,
     "VOICE","INBOUND","CH-VOICE-01",None,"Card Services — International",
     "AG-BNK-1041","Card Unblocked — Transferred",2220,"Very Negative",1,1,0,5,None,None,None,None,None,
     "accountId=ACC-774-992-11 | customerLocation=Abroad | priorContacts=3",
     "David: My card has been blocked for the third time. I am currently in Germany and I cannot pay for anything.\n"
     "Sophie: I will unblock the card immediately. I am also going to transfer you to our Fraud Rules team.\n"
     "Agent 2: I can submit a whitelist request for that merchant.",
     "Card unblocked via temporary override. Merchant whitelist request submitted. Customer abroad for 37 minutes with no card."),

    ("CNT-BNK-20006","MC-CARD-BNK-7731","TENANT-BNK-001","2026-05-31T10:20:00Z",None,None,
     "EMAIL","INBOUND","CH-EMAIL-01",None,"Customer Relations — Written Complaints",
     None,"Complaint Logged",None,"Very Negative",None,0,1,6,None,None,
     "david.kowalski@email.com","complaints@northpointbank.com",
     "accountId=ACC-774-992-11",
     "Subject: Formal Complaint — Repeated Card Blocks and Complete Lack of Resolution\n"
     "This is the third time in 30 days that your automated fraud system has blocked my card for an identical reason.",
     "Formal complaint logged. Churn risk elevated to HIGH. Case assigned to Senior Relationship Manager."),

    ("CNT-BNK-20007","MC-CARD-BNK-7731","TENANT-BNK-001","2026-06-03T11:00:00Z","2026-06-03T11:22:00Z",None,
     "VOICE","OUTBOUND","CH-CALLBACK-01",None,"Client Retention Team",
     "AG-BNK-3002","Resolved — Whitelist Confirmed, Goodwill Gesture Offered",1320,"Positive",4,0,0,7,None,None,None,None,None,
     "accountId=ACC-774-992-11",
     "Catherine: I can confirm that the Netflix merchant whitelist has now been permanently applied to your card.\n"
     "Catherine: I'd like to offer you a waiver of your annual card fee this year.",
     "Merchant permanently whitelisted. Annual fee waived. Travel insurance upgrade issued. Churn risk reduced."),

    # ── Banking Scenario B ─────────────────────────────────────────────────
    ("CNT-BNK-30001","MC-TRF-BNK-447221","TENANT-BNK-001","2026-04-07T13:15:00Z","2026-04-07T13:29:00Z",None,
     "VOICE","INBOUND","CH-VOICE-01",None,"Payments — International Transfers",
     "AG-BNK-1072","Advised — Third Party Issue",840,"Neutral",3,0,0,1,None,None,None,None,None,
     "accountId=ACC-881-447-22 | transferRef=TRF-BNK-990041 | amount=EUR4200 | blockReason=AML-Screening-Pending",
     "Elena: I submitted an international SEPA transfer yesterday for EUR 4,200. It still shows as pending.\n"
     "Tom: It looks like EuroBank may have placed a hold on the incoming transfer. I'd suggest contacting them directly.",
     "Transfer incorrectly attributed to receiving bank. AML screening root cause not identified."),

    ("CNT-BNK-30002","MC-TRF-BNK-447221","TENANT-BNK-001","2026-04-09T10:05:00Z","2026-04-09T10:24:00Z",None,
     "VOICE","INBOUND","CH-VOICE-01",None,"Payments — International Transfers",
     "AG-BNK-1085","Advised — Third Party Issue",1140,"Negative",2,0,0,2,None,None,None,None,None,
     "accountId=ACC-881-447-22 | priorContacts=1 | eurobankConfirmation=NoIssue",
     "Elena: I called EuroBank. They confirmed there is no issue on their side. The issue is with you.\n"
     "Fiona: I can see it is still pending. The system shows a third-party hold.\n"
     "Elena: I am asking why my transfer has been blocked for three days and nobody can tell me why.",
     "Same incorrect diagnosis repeated. Internal review promised but no escalation ticket raised."),

    ("CNT-BNK-30003","MC-TRF-BNK-447221","TENANT-BNK-001","2026-04-10T15:40:00Z","2026-04-10T16:02:00Z",None,
     "DIGITAL — LIVE CHAT","INBOUND","CH-CHAT-LIVE",None,"Digital Support — Payments",
     "AG-BNK-1091","Escalated — Callback Promised",1320,"Very Negative",1,0,1,3,None,None,None,None,None,
     "accountId=ACC-881-447-22",
     "Elena: I have a blocked SEPA transfer that has been stuck for four days. I have called twice.\n"
     "James: The system is showing a compliance screening flag. This may actually be on our side.\n"
     "James: I'm going to escalate this formally now — reference ESC-BNK-4421.",
     "Compliance flag correctly identified on third contact. Escalation ticket ESC-BNK-4421 raised."),

    ("CNT-BNK-30004","MC-TRF-BNK-447221","TENANT-BNK-001","2026-04-14T09:30:00Z",None,None,
     "EMAIL","INBOUND","CH-EMAIL-01",None,"Customer Relations — Written Complaints",
     None,"Complaint Logged",None,"Very Negative",None,0,1,4,None,None,
     "elena.vasquez@email.com","complaints@northpointbank.com",
     "accountId=ACC-881-447-22 | escalationRef=ESC-BNK-4421",
     "Subject: No Callback — Escalation ESC-BNK-4421 — Transfer Still Blocked Day 7\n"
     "I was promised a callback within 24 hours on April 10th. It is now April 14th. I have received nothing.",
     "Complaint formally lodged. Ombudsman threat raised. Churn risk elevated to CRITICAL."),

    ("CNT-BNK-30005","MC-TRF-BNK-447221","TENANT-BNK-001","2026-04-16T07:55:00Z",None,None,
     "DIGITAL — AUTO NOTIFICATION","OUTBOUND","CH-AUTO-01",None,"Automated Payments Notification",
     "AG-BNK-AUTO","Transfer Processed — Auto Notification Sent",None,"Neutral",None,0,0,5,None,None,None,None,None,
     "transferRef=TRF-BNK-990041",
     "System: AML screening on TRF-BNK-990041 cleared.\n"
     "System: Auto-notification sent: Your transfer of EUR 4,200 has been processed.",
     "Transfer resolved silently. Customer notified by automated message only. No explanation of root cause."),

    ("CNT-BNK-30006","MC-TRF-BNK-447221","TENANT-BNK-001","2026-05-07T11:20:00Z","2026-05-07T12:05:00Z",None,
     "VOICE","INBOUND","CH-VOICE-01",None,"Payments — International Transfers",
     "AG-BNK-1072","Transferred — Compliance Team",2700,"Very Negative",1,1,1,6,None,None,None,None,None,
     "accountId=ACC-881-447-22 | transferRef=TRF-BNK-990078 | churnRisk=CRITICAL",
     "Elena: My monthly transfer to EuroBank has been blocked again. Same amount — EUR 4,200.\n"
     "Tom: I'm going to transfer you directly to our Compliance team.\n"
     "Niamh: I'm applying a temporary override today and I'll have a permanent compliance exception submitted before end of day.",
     "Temporary override applied. Permanent AML exception submitted. Churn risk remains CRITICAL."),

    ("CNT-BNK-30007","MC-TRF-BNK-447221","TENANT-BNK-001","2026-05-08T10:30:00Z","2026-05-08T10:55:00Z",None,
     "VOICE","OUTBOUND","CH-CALLBACK-01",None,"Compliance Resolution Team",
     "AG-BNK-4001","Resolved — Permanent Exception Applied, Retention Offer Made",1500,"Positive",4,0,0,7,None,None,None,None,None,
     "accountId=ACC-881-447-22",
     "Richard: A permanent compliance exception has been registered for your regular EUR 4,200 SEPA transfer to EuroBank AG.\n"
     "Elena: I'll stay for now.\nRichard: I'm also arranging a complimentary upgrade to our Business Premium account tier.",
     "Permanent AML exception applied. Business Premium upgrade offered. Churn risk LOW. Case resolved."),

    # ── Insurance Scenario 1 ───────────────────────────────────────────────
    ("CNT-10001","MC-POL-784512","TENANT-INS-001","2026-04-01T09:12:00Z","2026-04-01T09:15:00Z","2026-04-01T09:15:08Z",
     "EMAIL","INBOUND","CH-EMAIL-01","SK-EMAIL-01","Policy Administration",
     "SYS-001","Pending Review",None,"Neutral",None,0,0,1,"EMAIL-10001",None,None,
     "michael.johnson@email.com","cancellations@safelife.com",
     "policyNumber=POL-784512 | requestType=Cancellation",
     "Subject: Request to Cancel Auto Insurance Policy\n"
     "I recently sold my vehicle and would like to cancel my auto insurance policy effective immediately.",
     "No response received."),

    ("CNT-10002","MC-POL-784512","TENANT-INS-001","2026-04-04T10:30:00Z","2026-04-04T10:36:00Z","2026-04-04T10:36:04Z",
     "CHAT","INBOUND","CH-CHAT-BOT","SK-BOT-01","Virtual Assistant",
     "BOT-001","Self Service Failed",360,"Slightly Negative",None,0,0,2,"CHAT-10002","RECORDED","REDACTED",
     "michael_johnson_webchat","SafeLifeBot",
     "policyNumber=POL-784512 | requestType=Cancellation Status",
     "Customer: I sent a cancellation request four days ago but haven't heard back.\n"
     "Bot: I cannot process cancellation requests.\nCustomer: Has anyone reviewed my email?\n"
     "Bot: I am unable to answer that question.",
     "Customer forced to switch channels."),

    ("CNT-10003","MC-POL-784512","TENANT-INS-001","2026-04-06T14:00:00Z","2026-04-06T14:11:00Z","2026-04-06T14:12:02Z",
     "VOICE","INBOUND","CH-VOICE-01","SK-VOICE-01","Policy Services",
     "AG-1023","Follow Up Required",660,"Neutral",3,0,0,3,"REC-10003","RECORDED","REDACTED",
     "+1-617-555-9182","+1-800-555-2000",None,None,
     "policyNumber=POL-784512 | requestType=Cancellation",
     "Sarah: Thank you for calling SafeLife Insurance.\n"
     "Michael: I emailed six days ago requesting cancellation. Nobody responded.\n"
     "Sarah: The retention team needs to process it. Within 48 hours.",
     "Promise made. No cancellation performed. No follow-up sent."),

    ("CNT-10004","MC-POL-784512","TENANT-INS-001","2026-04-10T16:15:00Z","2026-04-10T16:24:00Z","2026-04-10T16:24:06Z",
     "DIGITAL","INBOUND","CH-WA-01","SK-WA-01","Digital Support",
     "AG-2088","Escalated",540,"Negative",2,0,1,4,"WA-10004","RECORDED","REDACTED",
     "Michael Johnson","SafeLife WhatsApp",
     "policyNumber=POL-784512 | escalationTicket=ESC-44281",
     "Michael: I was promised cancellation within 48 hours.\n"
     "David: I don't see a completed cancellation request.\n"
     "David: Escalation ticket created. Ticket Number: ESC-44281",
     "Escalation ticket created. Customer sentiment becomes negative."),

    ("CNT-10005","MC-POL-784512","TENANT-INS-001","2026-04-13T09:00:00Z","2026-04-13T09:13:00Z",None,
     "VOICE","INBOUND","CH-VOICE-01",None,"Billing Support",
     "AG-INS-KEVIN","Billing Complaint",780,"Very Negative",1,1,1,5,None,None,None,None,None,
     "policyNumber=POL-784512",
     "Michael: I requested cancellation almost two weeks ago. You charged me another premium today.\n"
     "Kevin: The cancellation request still appears pending.\n"
     "Michael: I want to speak with a supervisor.",
     "Billing dispute created. Transferred to Escalation Team."),

    ("CNT-10006","MC-POL-784512","TENANT-INS-001","2026-04-15T11:00:00Z","2026-04-15T11:17:00Z",None,
     "VOICE","INBOUND","CH-VOICE-01",None,"Escalation Desk",
     "AG-INS-DAN","Supervisor Review Requested",1020,"Very Negative",1,0,1,6,None,None,None,None,None,
     "policyNumber=POL-784512",
     "Daniel: I understand your issue has been escalated.\n"
     "Michael: I've contacted your company five times. Nobody owns this problem.\n"
     "Daniel: I will escalate directly to a manager.",
     "Manager callback scheduled."),

    ("CNT-10007","MC-POL-784512","TENANT-INS-001","2026-04-18T14:00:00Z","2026-04-18T14:07:00Z",None,
     "VOICE","OUTBOUND","CH-CALLBACK-01",None,"Customer Resolution",
     "AG-INS-LAURA","Resolved",420,"Positive",5,0,0,7,None,None,None,None,None,
     "policyNumber=POL-784512",
     "Laura: Your policy has now been cancelled. A refund is being processed for the premium charged after your cancellation request.\n"
     "Michael: Finally.\nLaura: We apologize for the inconvenience.",
     "Policy cancelled. Refund issued. Case resolved. Customer retained."),

    # ── Insurance Scenario 2 ───────────────────────────────────────────────
    ("CNT-20001","MC-CLM-772191","TENANT-INS-001","2026-05-01T09:05:00Z","2026-05-01T09:10:00Z","2026-05-01T09:10:06Z",
     "CHAT","INBOUND","CH-CHAT-BOT","SK-BOT-01","Virtual Assistant",
     "BOT-001","Self Service Failed",300,"Slightly Negative",None,0,0,1,"CHAT-20001","RECORDED","REDACTED",
     None,None,None,None,
     "claimNumber=CLM-772191 | policyNumber=HOM-661234",
     "Customer: I need to check the status of my water damage claim.\nBot: I can help with claims.\n"
     "Customer: My claim number is CLM-772191.\nBot: Your claim is under review. No further information available.",
     "Bot unable to provide claim status. Customer directed to live agent."),

    ("CNT-20002","MC-CLM-772191","TENANT-INS-001","2026-05-03T10:00:00Z","2026-05-03T10:20:00Z",None,
     "CHAT","INBOUND","CH-CHAT-LIVE",None,"Claims Team",
     "AG-INS-SAR2","Under Review — No Timeline",1200,"Neutral",3,0,0,2,None,None,None,None,None,
     "claimNumber=CLM-772191",
     "Sarah: My home insurance claim for water damage has been submitted. Nobody can tell me when it will be reviewed.\n"
     "Agent: Your claim is currently under review by the Claims team. I can't give you a specific timeline.",
     "Claim confirmed under review but no timeline or owner provided."),

    ("CNT-20003","MC-CLM-772191","TENANT-INS-001","2026-05-05T14:00:00Z","2026-05-05T14:25:00Z",None,
     "VOICE","INBOUND","CH-VOICE-01",None,"Claims Team",
     "AG-INS-SAR2","Ownership Dispute — Underwriting",1500,"Negative",2,1,0,3,None,None,None,None,None,
     "claimNumber=CLM-772191",
     "Sarah: Can you tell me who owns my claim?\n"
     "Agent: The Claims team is reviewing it but Underwriting needs to assess the damage value.\n"
     "Sarah: So who do I call for an update?",
     "Claims team says Underwriting owns assessment. Customer transferred."),

    ("CNT-20004","MC-CLM-772191","TENANT-INS-001","2026-05-08T09:00:00Z","2026-05-08T09:22:00Z",None,
     "VOICE","INBOUND","CH-VOICE-01",None,"Underwriting Team",
     "AG-INS-UND","Ownership Dispute — Claims",1320,"Very Negative",1,1,0,4,None,None,None,None,None,
     "claimNumber=CLM-772191",
     "Sarah: Underwriting said Claims owns my case. Claims said Underwriting owns it.\n"
     "Patricia: I can see the claim. The final approval is with the Claims team.\n"
     "Sarah: This is going in circles.",
     "Underwriting says Claims owns final approval. Customer experiencing circular ownership confusion."),

    ("CNT-20005","MC-CLM-772191","TENANT-INS-001","2026-05-11T08:00:00Z",None,None,
     "EMAIL","INBOUND","CH-EMAIL-01",None,"Customer Relations — Written Complaints",
     None,"Complaint Logged",None,"Very Negative",None,0,1,5,None,None,
     "sarah.williams@email.com","complaints@safelife.com",
     "claimNumber=CLM-772191",
     "Subject: Formal Complaint — Claim CLM-772191 — No Owner, Conflicting Information\n"
     "I submitted my water damage claim 10 days ago. I have spoken to four different agents. Nobody owns this claim.",
     "Formal complaint received. Claim value $8,500. Escalation desk assigned."),

    ("CNT-20006","MC-CLM-772191","TENANT-INS-001","2026-05-14T10:00:00Z","2026-05-14T10:22:00Z",None,
     "VOICE","INBOUND","CH-VOICE-01",None,"Escalation Desk",
     "AG-INS-ESC","Supervisor Review Requested",1320,"Very Negative",1,0,1,6,None,None,None,None,None,
     "claimNumber=CLM-772191",
     "Rachel: I understand your claim has been through several departments without resolution.\n"
     "Sarah: I've spoken to four people. Nobody takes ownership.\n"
     "Rachel: I am assigning a dedicated claim handler to your case right now.",
     "Dedicated claim handler assigned. Escalation desk takes ownership."),

    ("CNT-20007","MC-CLM-772191","TENANT-INS-001","2026-05-18T11:00:00Z","2026-05-18T11:30:00Z",None,
     "VOICE","OUTBOUND","CH-CALLBACK-01",None,"Supervisor Team",
     "AG-INS-SUP","Resolved",1800,"Positive",5,0,0,7,None,None,None,None,None,
     "claimNumber=CLM-772191",
     "Michael: Mrs Williams, I am your dedicated claim supervisor. Your water damage claim has been approved for $8,500.\n"
     "Sarah: Finally. Thank you.\nMichael: Payment will be processed within 3 business days.",
     "Claim approved for $8,500. Payment processing initiated. Case resolved."),
]

FAILURE_PATTERNS = [
    # Healthcare A
    ("MC-AUTH-HC-220891","CRITICAL","SLA Breach","Authorization exceeded review timeline by 14+ days"),
    ("MC-AUTH-HC-220891","CRITICAL","Broken Promise","Agent promised 48-hour expedited review. No action taken."),
    ("MC-AUTH-HC-220891","CRITICAL","Medical Urgency Ignored","Cardiac referral not flagged as clinically time-sensitive"),
    ("MC-AUTH-HC-220891","CRITICAL","Repeat Contact","Patient contacted insurer 5 times across 5 channels"),
    ("MC-AUTH-HC-220891","WARNING","Channel Switching","Phone, Portal, Email before escalation"),
    ("MC-AUTH-HC-220891","WARNING","No Proactive Communication","Zero outbound updates across 17 days"),
    ("MC-AUTH-HC-220891","WARNING","Treatment Delay","Missed specialist appointment due to authorization failure"),
    ("MC-AUTH-HC-220891","WARNING","Ownership Gap","Request sat unassigned in queue with no reviewer"),
    # Healthcare C
    ("MC-STP-HC-334421","CRITICAL","Routing Failure","Exception request sent to wrong team at first contact"),
    ("MC-STP-HC-334421","CRITICAL","Broken Promise","24-hour callback promised twice, never delivered"),
    ("MC-STP-HC-334421","CRITICAL","Medical Impact","Patient without critical medication for 5 days"),
    ("MC-STP-HC-334421","CRITICAL","Incorrect Information","First agent gave wrong process guidance"),
    ("MC-STP-HC-334421","WARNING","Repeat Contact","Patient contacted insurer 5 times across 5 channels"),
    ("MC-STP-HC-334421","WARNING","Escalation Spiral","Required Chief Pharmacy Officer intervention"),
    ("MC-STP-HC-334421","WARNING","Channel Switching","Phone, Bot, WhatsApp, Escalation before resolution"),
    ("MC-STP-HC-334421","WARNING","Sentiment Deterioration","Neutral at start, critical distress by Day 9"),
    # ISP A
    ("MC-TKT-ISP-884401","CRITICAL","Premature Ticket Closure","Ticket marked Resolved twice despite ongoing speed fault"),
    ("MC-TKT-ISP-884401","CRITICAL","Field Visit Failure","Technician closed job as No Access without attempting contact"),
    ("MC-TKT-ISP-884401","CRITICAL","Broken Promise","Callback promised three times across journey, never delivered"),
    ("MC-TKT-ISP-884401","CRITICAL","Repeat Contact","5 contacts across 5 channels before escalation"),
    ("MC-TKT-ISP-884401","WARNING","No Tier 2 Escalation","Persistent fault never escalated despite 7+ days unresolved"),
    ("MC-TKT-ISP-884401","WARNING","Reputational Risk","Customer took issue public on Twitter/X before internal resolution"),
    ("MC-TKT-ISP-884401","WARNING","Channel Switching","Phone, App, Chat, Social Media forced by lack of resolution"),
    ("MC-TKT-ISP-884401","WARNING","Network Root Cause Unidentified","External line fault suspected but not confirmed or repaired"),
    # ISP B
    ("MC-ORD-SL-552018","CRITICAL","Pre-Sale Infrastructure Failure","Address not surveyed before service sold, installation impossible"),
    ("MC-ORD-SL-552018","CRITICAL","Unnotified Appointment Miss","First technician reassigned with no customer notification"),
    ("MC-ORD-SL-552018","CRITICAL","Broken Promise","Survey and callback promised four times; none completed on time"),
    ("MC-ORD-SL-552018","CRITICAL","Customer Left Without Service","14+ days without internet, previous ISP cancelled"),
    ("MC-ORD-SL-552018","WARNING","Survey Result Not Communicated","Outcome of external survey not sent to customer for 6 days"),
    ("MC-ORD-SL-552018","WARNING","No Interim Solution Offered","No mobile data or bridge solution provided during 2-week outage"),
    ("MC-ORD-SL-552018","WARNING","Channel Switching","Phone, Chat, WhatsApp, Email before formal escalation"),
    ("MC-ORD-SL-552018","WARNING","Churn Risk","Customer explicitly threatening cancellation and formal regulator complaint"),
    # Banking A
    ("MC-CARD-BNK-7731","CRITICAL","Recurring Failure","Identical block triggered 3 times with no systemic fix between contacts"),
    ("MC-CARD-BNK-7731","CRITICAL","Context Loss","Agents had no visibility into previous interactions on the same issue"),
    ("MC-CARD-BNK-7731","CRITICAL","Wrong Escalation Path","Customer needed Fraud Rules team from Call 1; reached them on Call 3"),
    ("MC-CARD-BNK-7731","CRITICAL","Customer Abroad With No Working Card","High-severity impact caused by known unresolved issue"),
    ("MC-CARD-BNK-7731","WARNING","Repeat Contact","5 contacts across 4 channels for one underlying issue"),
    ("MC-CARD-BNK-7731","WARNING","Channel Dead-End","Live chat could not take action, directed customer back to failed channel"),
    ("MC-CARD-BNK-7731","WARNING","No Proactive Alert","System did not notify customer before card blocked payment"),
    # Banking B
    ("MC-TRF-BNK-447221","CRITICAL","Wrong Diagnosis Repeated","Agent incorrectly blamed receiving bank on two consecutive contacts"),
    ("MC-TRF-BNK-447221","CRITICAL","Broken Promise","Callback promised at escalation. Not received for 4 days."),
    ("MC-TRF-BNK-447221","CRITICAL","Incomplete Fix","First resolution cleared individual transfer only, left AML rule active"),
    ("MC-TRF-BNK-447221","CRITICAL","Silent Resolution","Transfer processed with no explanation, apology, or prevention plan"),
    ("MC-TRF-BNK-447221","CRITICAL","Full Cycle Repeated","Identical issue, identical wrong diagnosis, identical escalation path one month later"),
    ("MC-TRF-BNK-447221","WARNING","Compliance Visibility Gap","Payments agents cannot see compliance hold reasons"),
    ("MC-TRF-BNK-447221","WARNING","Escalation Ticket Auto-Closed","System closed escalation without human confirmation of root cause fix"),
    ("MC-TRF-BNK-447221","WARNING","Context Loss Between Channels","Each agent started from scratch despite 3+ previous contacts on same issue"),
    # Insurance 1
    ("MC-POL-784512","CRITICAL","Broken Promise","Cancellation promised within 48 hours — not actioned"),
    ("MC-POL-784512","CRITICAL","Repeat Contact","Customer contacted company 5 times before resolution"),
    ("MC-POL-784512","CRITICAL","Financial Impact","Premium deducted despite active cancellation request"),
    ("MC-POL-784512","CRITICAL","Ownership Gap","No owner assigned to the cancellation request"),
    ("MC-POL-784512","WARNING","Channel Switching","Email, Chatbot, Voice, WhatsApp before escalation"),
    ("MC-POL-784512","WARNING","Escalation Risk","Supervisor and manager intervention required"),
    ("MC-POL-784512","WARNING","Sentiment Deterioration","Neutral at first contact, Very Negative by interaction 5"),
    # Insurance 2
    ("MC-CLM-772191","CRITICAL","Ownership Gap","No single owner assigned across Claims and Underwriting teams"),
    ("MC-CLM-772191","CRITICAL","Conflicting Information","Claims and Underwriting each blamed the other for ownership"),
    ("MC-CLM-772191","CRITICAL","Repeat Contact","Customer spoke to 4 agents across multiple channels"),
    ("MC-CLM-772191","WARNING","Channel Switching","Chatbot, Chat, Voice, Email before escalation"),
    ("MC-CLM-772191","WARNING","No Timeline Provided","$8,500 claim with no processing timeline communicated"),
    ("MC-CLM-772191","WARNING","Escalation Required","Escalation desk required to assign dedicated handler"),
]

RECOMMENDED_ACTIONS = [
    # Healthcare A
    ("MC-AUTH-HC-220891","High","Auto-flag authorizations with appointment dates within 10 days as clinically urgent"),
    ("MC-AUTH-HC-220891","High","Trigger supervisor alert when authorization exceeds 5 days with no assigned reviewer"),
    ("MC-AUTH-HC-220891","Medium","Send proactive status updates to member every 3 days while authorization is pending"),
    ("MC-AUTH-HC-220891","Medium","Detect broken promise pattern: flag when promised action not completed within stated timeframe"),
    # Healthcare C
    ("MC-STP-HC-334421","High","Auto-detect step therapy exception requests and route directly to specialist queue"),
    ("MC-STP-HC-334421","High","Flag cases where medication supply window is under 7 days as medical urgency"),
    ("MC-STP-HC-334421","High","Trigger alert when promised callback is not completed within stated timeframe"),
    ("MC-STP-HC-334421","Medium","Enable emergency temporary authorization workflow for critical medications"),
    # ISP A
    ("MC-TKT-ISP-884401","High","Auto-escalate to Tier 2 when same fault ticket is reopened or unresolved for more than 5 days"),
    ("MC-TKT-ISP-884401","High","Block technician job closure as No Access without photo evidence or customer phone contact record"),
    ("MC-TKT-ISP-884401","High","Trigger supervisor alert when promised callback is not completed within stated timeframe"),
    ("MC-TKT-ISP-884401","High","Auto-flag accounts where measured speed falls below 10% of contracted speed for 48+ hours"),
    ("MC-TKT-ISP-884401","Medium","Disable Resolved ticket status when in-app speed test shows performance below threshold"),
    ("MC-TKT-ISP-884401","Medium","Proactively contact customer if line diagnostic shows ongoing packet loss after a remote reset"),
    # ISP B
    ("MC-ORD-SL-552018","High","Mandate infrastructure pre-survey for all multi-dwelling new connection orders"),
    ("MC-ORD-SL-552018","High","Auto-notify customer with 24-hour advance notice when technician appointment is changed or cancelled"),
    ("MC-ORD-SL-552018","High","Trigger senior case manager assignment when installation order has been open for more than 7 days"),
    ("MC-ORD-SL-552018","High","Send automated customer update within 24 hours of any engineering survey outcome"),
    ("MC-ORD-SL-552018","Medium","Create interim connectivity policy: offer mobile broadband bridge for customers with installation delays over 5 days"),
    ("MC-ORD-SL-552018","Medium","Detect promise-tracking gap: log callback commitments with owner name and SLA, alert supervisor on breach"),
    # Banking A
    ("MC-CARD-BNK-7731","Critical","Auto-flag accounts where the same block reason recurs within 30 days — route directly to Fraud Rules team"),
    ("MC-CARD-BNK-7731","Critical","Surface full interaction history on every inbound contact screen"),
    ("MC-CARD-BNK-7731","High","Prompt agents to submit merchant whitelist when block reason is FraudRule-FX-Recur and merchant appears in 12+ months of history"),
    ("MC-CARD-BNK-7731","High","Enable proactive SMS/push alert before card block is applied, for known low-risk recurring payments"),
    ("MC-CARD-BNK-7731","Medium","Add merchant whitelist self-service option to mobile app for customers with 12+ months transaction history"),
    # Banking B
    ("MC-TRF-BNK-447221","Critical","Expose compliance hold reason codes to Payments agent interface — eliminate incorrect third-party blame diagnosis"),
    ("MC-TRF-BNK-447221","Critical","Require human agent confirmation before closing escalation tickets"),
    ("MC-TRF-BNK-447221","Critical","When compliance review clears a transfer, auto-trigger review for standing exception on recurring payment patterns"),
    ("MC-TRF-BNK-447221","High","Implement recurrence detection: same AML rule + same account within 90 days routes directly to Compliance team"),
    ("MC-TRF-BNK-447221","High","When a compliance hold resolves, send proactive explanation message — not just automated transfer confirmation"),
    ("MC-TRF-BNK-447221","Medium","Display full cross-channel contact history summary on agent screen at start of each interaction"),
    # Insurance 1
    ("MC-POL-784512","High","Assign a named owner to every cancellation request within 1 hour of receipt"),
    ("MC-POL-784512","High","Auto-trigger billing freeze when a cancellation request is logged"),
    ("MC-POL-784512","High","Send confirmation email to customer within 24 hours of any cancellation request"),
    ("MC-POL-784512","Medium","Flag promises made by agents and alert supervisor if not actioned within the stated timeframe"),
    # Insurance 2
    ("MC-CLM-772191","High","Assign a dedicated claim owner at point of submission for all claims above $5,000"),
    ("MC-CLM-772191","High","Send proactive claim status updates every 3 days until resolution"),
    ("MC-CLM-772191","High","Define and document ownership boundary between Claims and Underwriting in agent tooling"),
    ("MC-CLM-772191","Medium","Enable customer-facing claim tracker with named owner and expected resolution date"),
]


# ---------------------------------------------------------------------------
# Database build
# ---------------------------------------------------------------------------

def flag(v):
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, str):
        return 1 if v.upper() == "TRUE" else 0
    return v if v is not None else 0


def build_db():
    db_path = os.path.abspath(DB_PATH)
    if os.path.exists(db_path):
        os.remove(db_path)

    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")

    with open(SCHEMA_PATH) as f:
        con.executescript(f.read())

    # channels
    con.executemany(
        "INSERT INTO channels VALUES (?,?,?)", CHANNELS)

    # agents
    con.executemany(
        "INSERT INTO agents VALUES (?,?,?,?,?)", AGENTS)

    # customers
    con.executemany(
        "INSERT INTO customers VALUES (?,?,?,?,?,?,?,?,?)", CUSTOMERS)

    # journey_sessions
    con.executemany(
        """INSERT INTO journey_sessions VALUES
           (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        JOURNEY_SESSIONS)

    def _fix_row(row):
        """Ensure every interaction row has exactly 29 values.
        Layout: 19 fixed fields | 7 middle fields | 3 tail fields (business_data, transcript, outcome)
        Middle fields: recording_id, recording_status, redaction_status, ani, dnis, from_address, to_address
        """
        r = list(row)
        prefix, suffix, mid = r[:19], r[-3:], r[19:-3]
        if len(mid) == 5:
            mid = mid + [None, None]        # append from_address, to_address
        elif len(mid) == 4:
            mid = mid[:2] + [None, None, None] + mid[2:]  # insert redaction, ani, dnis
        # len 7 = already correct (rows with explicit ani/dnis/from/to)
        return prefix + mid + suffix

    for row in INTERACTIONS:
        con.execute(
            "INSERT INTO interactions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            _fix_row(row)
        )

    # failure_patterns
    con.executemany(
        "INSERT INTO failure_patterns (master_contact_id,severity,pattern_type,pattern_description) VALUES (?,?,?,?)",
        FAILURE_PATTERNS)

    # recommended_actions
    con.executemany(
        "INSERT INTO recommended_actions (master_contact_id,priority,action_text) VALUES (?,?,?)",
        RECOMMENDED_ACTIONS)

    con.commit()

    # Row counts
    print("Database built:", db_path)
    print()
    for table in ["customers","agents","channels","journey_sessions","interactions","failure_patterns","recommended_actions"]:
        n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:<25} {n:>4} rows")

    con.close()


if __name__ == "__main__":
    build_db()
