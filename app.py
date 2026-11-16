import calendar
import html
import os
import re
from datetime import date, datetime, time, timedelta

import importlib
import sys

import streamlit as st


# A long-running Streamlit server can keep older copies of the logic modules in memory
# after their files change (which causes errors like "unexpected keyword argument").
# Remember each file's modification time and reload the modules, in dependency order,
# whenever any of them differs, so the page always runs the latest code without a restart.
_LOGIC_MODULES = ("pawpal_system", "guardrails", "agent", "demo_data")


@st.cache_resource(show_spinner=False)
def _loaded_versions() -> dict:
    """Server-wide record of the file versions the loaded modules came from."""
    return {}


_mtimes = {
    name: os.path.getmtime(importlib.import_module(name).__file__) for name in _LOGIC_MODULES
}
if _loaded_versions().get("mtimes") != _mtimes:
    for _name in _LOGIC_MODULES:
        importlib.reload(sys.modules[_name])
    _loaded_versions()["mtimes"] = _mtimes
    st.session_state.pop("assistant_result", None)  # was built from the old classes

from agent import PawPalAgent, apply_proposal
from demo_data import build_demo_household
from logging_config import setup_logging
from pawpal_system import Owner, Pet, Scheduler, Task

setup_logging()

st.set_page_config(page_title="PawPal+ Family", page_icon="🐾", layout="wide")

SPECIES_EMOJI = {"dog": "🐶", "cat": "🐱", "other": "🐾"}
PRIORITY_COLOR = {"high": "#E5484D", "medium": "#F5A524", "low": "#2FB380"}
AVATAR_COLORS = ["#6C5CE7", "#00B8D9", "#F5A524", "#E5484D", "#2FB380", "#EC4899", "#3B82F6"]

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stApp { font-family: 'Inter', sans-serif; }
#MainMenu, footer { visibility: hidden; }
.block-container { padding-top: 2rem; max-width: 1150px; }

.hero {
  background: linear-gradient(135deg, #6C5CE7 0%, #8E7BFF 55%, #00B8D9 130%);
  color: #fff; border-radius: 22px; padding: 28px 32px; margin-bottom: 20px;
  box-shadow: 0 12px 30px rgba(108, 92, 231, .25);
}
.hero h1 { color:#fff; font-size: 2rem; font-weight: 800; margin:0; letter-spacing:-.02em; padding:0; }
.hero p { color: rgba(255,255,255,.88); margin: 6px 0 0; font-size: 1rem; }

.stat {
  background:#fff; border-radius:16px; padding:16px 18px;
  border:1px solid #ECEEF4; box-shadow: 0 2px 8px rgba(20,25,50,.04);
}
.stat .label { color:#7A8194; font-size:.78rem; font-weight:600; text-transform:uppercase; letter-spacing:.06em; }
.stat .value { font-size:1.9rem; font-weight:800; color:#1F2430; line-height:1.2; }

.task-title { font-weight:700; font-size:1.02rem; color:#1F2430; }
.task-done .task-title { text-decoration: line-through; color:#9AA1B2; }
.meta { color:#7A8194; font-size:.85rem; margin-top:2px; }
.pill {
  display:inline-block; padding:2px 10px; border-radius:999px; font-size:.75rem;
  font-weight:600; margin-right:6px; background:#F0F1F7; color:#4A5165;
}
.avatar {
  display:inline-flex; align-items:center; justify-content:center; width:26px; height:26px;
  border-radius:50%; color:#fff; font-weight:700; font-size:.78rem; margin-right:6px; vertical-align:middle;
}
.timechip {
  font-weight:800; font-size:1.05rem; color:#6C5CE7; background:#EFEDFF;
  border-radius:12px; padding:8px 10px; text-align:center; min-width:64px;
}
.section-title { font-size:1.15rem; font-weight:800; margin: 6px 0 10px; color:#1F2430; }

div[data-testid="stVerticalBlockBorderWrapper"] { border-radius:16px; }
.stButton > button, .stFormSubmitButton > button { border-radius:12px; font-weight:600; }
section[data-testid="stSidebar"] { border-right:1px solid #ECEEF4; }
.stTabs [data-baseweb="tab-list"] { gap:6px; }
.stTabs [data-baseweb="tab"] { border-radius:10px; padding:8px 16px; font-weight:600; }
</style>
""",
    unsafe_allow_html=True,
)


st.markdown(
    """
<style>
.stApp {
  background:
    radial-gradient(900px 400px at 100% -10%, #E9E4FF 0%, transparent 60%),
    radial-gradient(700px 400px at -10% 10%, #D9F5FB 0%, transparent 55%),
    #F6F7FB;
}
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #FFFFFF 0%, #F3F0FF 100%);
}
.brand { display:flex; align-items:center; gap:10px; font-weight:800; font-size:1.35rem; letter-spacing:-.02em; color:#1F2430; margin-bottom:6px;}
.brand .logo { width:38px; height:38px; border-radius:12px; display:flex; align-items:center; justify-content:center;
  background:linear-gradient(135deg,#6C5CE7,#00B8D9); box-shadow:0 6px 14px rgba(108,92,231,.35); font-size:1.2rem;}

/* hero */
.hero { position:relative; overflow:hidden; padding:30px 34px 26px; border-radius:26px;
  background: linear-gradient(120deg,#5B4BDB 0%,#7C6CF5 50%,#19B8D8 120%); }
.hero::after { content:"🐾"; position:absolute; right:26px; top:-8px; font-size:9rem; opacity:.12; transform:rotate(-14deg);}
.hero::before { content:""; position:absolute; width:260px; height:260px; border-radius:50%; right:-60px; bottom:-120px;
  background:rgba(255,255,255,.12); }
.hero .eyebrow { text-transform:uppercase; letter-spacing:.14em; font-size:.72rem; font-weight:700; opacity:.8; margin-bottom:6px;}
.hero .row { display:flex; align-items:center; gap:18px; margin-top:16px; flex-wrap:wrap; position:relative; z-index:1;}
.hero .faces { display:flex; }
.hero .faces .avatar { width:38px; height:38px; font-size:1rem; margin:0 -8px 0 0; border:3px solid rgba(255,255,255,.9); box-shadow:0 4px 10px rgba(0,0,0,.15);}
.hero .faces .petface { width:38px; height:38px; border-radius:50%; background:#fff; display:flex; align-items:center;
  justify-content:center; font-size:1.2rem; margin-right:-8px; border:3px solid rgba(255,255,255,.9);}
.progress-wrap { flex:1; min-width:220px; max-width:380px; }
.progress-label { font-size:.82rem; font-weight:600; display:flex; justify-content:space-between; margin-bottom:6px; opacity:.95;}
.progress-bar { height:10px; border-radius:99px; background:rgba(255,255,255,.28); overflow:hidden;}
.progress-bar > span { display:block; height:100%; border-radius:99px; background:#fff; transition:width .6s ease;}

/* stat cards */
.stat { position:relative; overflow:hidden; border:none; padding:18px 20px;
  box-shadow:0 8px 24px rgba(40,40,90,.07); transition:transform .2s ease, box-shadow .2s ease;}
.stat:hover { transform:translateY(-3px); box-shadow:0 14px 30px rgba(40,40,90,.12);}
.stat .icon { width:40px; height:40px; border-radius:12px; display:flex; align-items:center; justify-content:center; font-size:1.2rem; margin-bottom:10px;}

/* task cards */
div[data-testid="stVerticalBlockBorderWrapper"]:has(.card-marker) {
  background:#fff; border:1px solid #ECEEF4; box-shadow:0 4px 14px rgba(40,40,90,.05);
  transition:transform .18s ease, box-shadow .18s ease; border-left-width:5px;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.card-marker):hover { transform:translateY(-2px); box-shadow:0 12px 26px rgba(40,40,90,.10);}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.prio-high) { border-left-color:#E5484D; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(.prio-medium) { border-left-color:#F5A524; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(.prio-low) { border-left-color:#2FB380; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(.is-done) { opacity:.7; }
.card-marker { display:none; }
.timechip { background:linear-gradient(135deg,#EFEDFF,#E3F7FC); }

/* pet cards */
.petcard { border-radius:20px; padding:20px; color:#1F2430; margin-bottom:14px; position:relative; overflow:hidden;
  box-shadow:0 8px 22px rgba(40,40,90,.08); transition:transform .2s ease;}
.petcard:hover { transform:translateY(-4px) rotate(-.4deg);}
.petcard .big { font-size:3rem; line-height:1; }
.petcard .name { font-weight:800; font-size:1.25rem; margin-top:8px;}
.petcard.dog { background:linear-gradient(135deg,#FFF1D6,#FFE0B2);}
.petcard.cat { background:linear-gradient(135deg,#EDE7FF,#D9D0FF);}
.petcard.other { background:linear-gradient(135deg,#DDF7EE,#C5EFE0);}
.petcard .mini { height:7px; border-radius:99px; background:rgba(0,0,0,.08); margin-top:12px; overflow:hidden;}
.petcard .mini > span { display:block; height:100%; background:rgba(31,36,48,.55); border-radius:99px;}

/* icon buttons: Done pill, subtle round delete, ghost remove */
[class*="st-key-done_"] button {
  background:#E7F8F1; color:#178A64; border:1px solid #C6EEDD; border-radius:999px; height:38px; min-height:38px;
  font-weight:700; padding:0 14px; white-space:nowrap; width:100%;
  display:flex; flex-wrap:nowrap; align-items:center; justify-content:center; gap:6px;
}
[class*="st-key-done_"] button p { margin:0; white-space:nowrap; font-size:.9rem; }
[class*="st-key-done_"] button span { margin:0 !important; font-size:1.15rem; }
.done-pill { display:flex; align-items:center; justify-content:center; gap:6px; height:38px; border-radius:999px;
  background:#F0F1F7; color:#7A8194; font-weight:700; font-size:.88rem; white-space:nowrap; }
[class*="st-key-done_"] button:hover { background:#D3F3E5; color:#0F7A57; border-color:#9FE0C3; }
/* after a click the button keeps focus: make focus/active look like the resting state */
[class*="st-key-done_"] button:focus:not(:hover),
[class*="st-key-done_"] button:active:not(:hover),
[class*="st-key-done_"] button:focus-visible:not(:hover) {
  background:#E7F8F1 !important; color:#178A64 !important; border-color:#C6EEDD !important;
  box-shadow:none !important; outline:none !important;
}
[class*="st-key-done_"] button:focus, [class*="st-key-done_"] button:active { outline:none !important; box-shadow:none !important; }
[class*="st-key-del_"] button:focus:not(:hover), [class*="st-key-rm_"] button:focus:not(:hover) {
  background:#F4F5FA !important; color:#9AA1B2 !important; box-shadow:none !important; outline:none !important;
}
[class*="st-key-del_"] button, [class*="st-key-rm_"] button {
  width:38px; min-width:38px; height:38px; min-height:38px; padding:0; border-radius:50%;
  background:#F4F5FA; border:none; color:#9AA1B2; box-shadow:none;
  display:flex; align-items:center; justify-content:center;
}
[class*="st-key-del_"] button:hover, [class*="st-key-rm_"] button:hover { background:#FDECEC; color:#E5484D !important; transform:scale(1.08);}
[class*="st-key-del_"] button p, [class*="st-key-rm_"] button p { display:none; }
[class*="st-key-del_"] button span, [class*="st-key-rm_"] button span { margin:0 !important; }
[class*="st-key-rm_"] button { width:28px; min-width:28px; height:28px; min-height:28px; }
div[data-testid="stPopover"] > button {
  background:rgba(255,255,255,.7); border:1px solid rgba(0,0,0,.08); color:#5B6275; border-radius:12px; font-weight:600;
}
div[data-testid="stPopover"] > button:hover { background:#FDECEC; color:#E5484D; border-color:#F6C5C7;}

/* calendar */
.cal { display:grid; grid-template-columns:repeat(7,minmax(0,1fr)); gap:8px; }
.cal-h { text-align:center; font-weight:700; color:#7A8194; font-size:.75rem; text-transform:uppercase; letter-spacing:.08em; padding:4px 0; }
.cal-d { min-height:108px; background:#fff; border:1px solid #ECEEF4; border-radius:14px; padding:8px; position:relative;
  box-shadow:0 2px 8px rgba(40,40,90,.04); overflow:hidden; }
.cal-d.off { opacity:.38; }
.cal-d.today { border:2px solid #6C5CE7; background:#F7F5FF; }
.cal-d.sel { box-shadow:0 0 0 3px rgba(108,92,231,.3); }
.cal-n { font-weight:800; font-size:.85rem; color:#1F2430; }
.cal-d.today .cal-n { background:#6C5CE7; color:#fff; border-radius:50%; width:24px; height:24px; display:inline-flex;
  align-items:center; justify-content:center; }
.cal-cnt { position:absolute; top:8px; right:8px; font-size:.68rem; font-weight:700; color:#7A8194; background:#F0F1F7;
  border-radius:99px; padding:1px 7px; }
.chip { font-size:.7rem; font-weight:600; padding:2px 7px; border-radius:7px; margin-top:4px; overflow:hidden;
  text-overflow:ellipsis; white-space:nowrap; }
.chip.done { text-decoration:line-through; opacity:.5; }
.more { font-size:.7rem; color:#7A8194; margin-top:4px; font-weight:600; }
.cal-title { font-size:1.5rem; font-weight:800; text-align:center; color:#1F2430; letter-spacing:-.01em; }
@media (max-width: 760px) { .cal-d { min-height:58px; padding:5px; } .chip, .more { display:none; } .cal { gap:4px; } }

/* assistant suggestion chips */
[class*="st-key-sugg_"] button { border-radius:999px; background:#fff; border:1px solid #DAD6FF; color:#4C3FC4;
  font-weight:600; font-size:.85rem; min-height:40px; box-shadow:0 2px 8px rgba(108,92,231,.08); }
[class*="st-key-sugg_"] button:hover { background:#EFEDFF; border-color:#6C5CE7; color:#4C3FC4; transform:translateY(-1px); }

/* empty state */
.empty { text-align:center; padding:36px 10px; color:#7A8194; }
.empty .e { font-size:3rem; }
.empty b { color:#1F2430; font-size:1.05rem; display:block; margin:6px 0 2px;}

/* tabs as pills */
.stTabs [data-baseweb="tab-list"] { background:#fff; padding:6px; border-radius:16px; border:1px solid #ECEEF4;
  box-shadow:0 4px 14px rgba(40,40,90,.05); width:fit-content; }
.stTabs [data-baseweb="tab"] { height:auto; background:transparent; }
.stTabs [aria-selected="true"] { background:linear-gradient(135deg,#6C5CE7,#8E7BFF); color:#fff !important; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display:none; }
button[kind="primary"], .stFormSubmitButton > button[kind="primaryFormSubmit"] {
  background:linear-gradient(135deg,#6C5CE7,#8E7BFF); border:none; box-shadow:0 6px 16px rgba(108,92,231,.35);}
button[kind="primary"]:hover { filter:brightness(1.07); transform:translateY(-1px);}
.stButton > button:not([kind="primary"]):hover { border-color:#6C5CE7; color:#6C5CE7; }
.stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] > div, .stTimeInput input {
  border-radius:12px !important; }
</style>
""",
    unsafe_allow_html=True,
)


def clock(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"


def avatar(name: str | None) -> str:
    """Round colored initial for a family member (grey ? when unassigned)."""
    if not name:
        return '<span class="avatar" style="background:#B8BECC">?</span>'
    color = AVATAR_COLORS[sum(map(ord, name)) % len(AVATAR_COLORS)]
    return f'<span class="avatar" style="background:{color}">{name[0].upper()}</span>'


def flash(message: str, icon: str = "✅") -> None:
    """Queue a toast notification to show after the next rerun (st.toast right before
    st.rerun() can get lost, so we show it on the fresh page instead)."""
    st.session_state.flash = (message, icon)


def _rebuild_household(old) -> Owner:
    """Copy a household created by an older version of the code into the current classes.

    Streamlit keeps objects in session_state across code edits, so an open browser tab
    can hold an Owner that lacks newer methods and fields. Rebuilding keeps its data.
    """
    family = Owner(
        name=getattr(old, "name", "My Family"),
        available_minutes=getattr(old, "available_minutes", 120),
        members=list(getattr(old, "members", [])),
    )
    for old_pet in getattr(old, "pets", []):
        pet = Pet(name=old_pet.name, species=old_pet.species)
        for t in old_pet.tasks:
            pet.add_task(Task(
                title=t.title, duration_minutes=t.duration_minutes, priority=t.priority,
                frequency=t.frequency, time=t.time, completed=t.completed,
                due_date=getattr(t, "due_date", None), assigned_to=getattr(t, "assigned_to", None),
                added_by=getattr(t, "added_by", None), completed_on=getattr(t, "completed_on", None),
            ))
        family.add_pet(pet)
    return family


# Streamlit reruns this script on every click, so the household lives in session_state.
if "family" not in st.session_state:
    st.session_state.family = Owner(name="My Family", available_minutes=120)
elif not (type(st.session_state.family) is Owner and hasattr(st.session_state.family, "tasks_on")
          and all(type(p) is Pet and all(type(t) is Task and hasattr(t, "completed_on") for t in p.tasks)
                  for p in st.session_state.family.pets)):
    st.session_state.family = _rebuild_household(st.session_state.family)
family: Owner = st.session_state.family
scheduler = Scheduler(family)
pet_of = {id(t): pet for pet in family.pets for t in pet.tasks}
if "flash" in st.session_state:
    _msg, _icon = st.session_state.pop("flash")
    st.toast(_msg, icon=_icon)

# ---------------------------------------------------------------- Sidebar
with st.sidebar:
    st.markdown('<div class="brand"><div class="logo">🐾</div>PawPal+</div>', unsafe_allow_html=True)
    family.name = st.text_input("Family name", value=family.name)
    family.available_minutes = int(
        st.number_input("Care time available today (min)", 1, 1440, family.available_minutes, step=15)
    )
    st.divider()

    st.markdown("**🏠 Family members**")
    with st.form("add_member", clear_on_submit=True, border=False):
        new_member = st.text_input("Add a member", placeholder="e.g. Ana", label_visibility="collapsed")
        if st.form_submit_button("＋ Add member", use_container_width=True):
            try:
                family.add_member(new_member)
                st.session_state.current_member = new_member.strip()
                flash(f"{new_member.strip()} joined the family", "👋")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    for m in list(family.members):
        c1, c2 = st.columns([5, 1], vertical_alignment="center")
        c1.markdown(f"{avatar(m)} {m}", unsafe_allow_html=True)
        if c2.button("", key=f"rm_{m}", icon=":material/close:", help=f"Remove {m} (their tasks become unassigned)"):
            family.remove_member(m)
            flash(f"Removed {m}", "🗑️")
            st.rerun()

    current = None
    if family.members:
        st.divider()
        if st.session_state.get("current_member") not in family.members:
            st.session_state.current_member = family.members[0]
        current = st.selectbox("I'm using the app as", family.members, key="current_member")

# ---------------------------------------------------------------- Header + stats
today = datetime.now()
all_tasks = family.get_all_tasks()
# "Today" only: daily tasks reset each morning, finished one-off tasks never come back,
# and tasks due in the future don't count until their day arrives.
pending_tasks = [t for t in all_tasks if t.is_due()]
done_count = sum(1 for t in all_tasks if t.done_on())
today_total = len(pending_tasks) + done_count
pct = round(100 * done_count / today_total) if today_total else 0
hour = today.hour
greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
faces = "".join(avatar(m) for m in family.members) + "".join(
    f'<span class="petface">{SPECIES_EMOJI.get(p.species, "🐾")}</span>' for p in family.pets
)
st.markdown(
    f"""<div class="hero">
    <div class="eyebrow">{today:%A, %B %d}</div>
    <h1>{greeting}, {family.name} 👋</h1>
    <p>Everyone's pet care, in one place.</p>
    <div class="row">
      <div class="faces">{faces}</div>
      <div class="progress-wrap">
        <div class="progress-label"><span>Care progress</span><span>{done_count}/{today_total} done today · {pct}%</span></div>
        <div class="progress-bar"><span style="width:{pct}%"></span></div>
      </div>
    </div></div>""",
    unsafe_allow_html=True,
)

if not family.members:
    st.markdown(
        '<div class="empty"><div class="e">🏠</div><b>Welcome to PawPal+</b>'
        "Add the first family member in the sidebar, or try a ready-made family.</div>",
        unsafe_allow_html=True,
    )
    _, demo_col, _ = st.columns([1, 1, 1])
    if demo_col.button("Load demo family", type="primary", icon=":material/auto_awesome:",
                       use_container_width=True):
        st.session_state.family = build_demo_household()
        flash("Loaded the Rivera family: 3 members, 2 pets and a week of tasks", "✨")
        st.rerun()
    st.stop()

conflicts = scheduler.detect_conflicts()
STAT_STYLES = [("🏠", "#EFEDFF"), ("🐾", "#FFF1D6"), ("📝", "#E3F7FC"), ("✅", "#DDF7EE")]
for col, label, value, (icon, bg) in zip(
    st.columns(4),
    ["Family members", "Pets", "To do today", "Done today"],
    [len(family.members), len(family.pets), len(pending_tasks), done_count],
    STAT_STYLES,
):
    col.markdown(
        f'<div class="stat"><div class="icon" style="background:{bg}">{icon}</div>'
        f'<div class="label">{label}</div><div class="value">{value}</div></div>',
        unsafe_allow_html=True,
    )
st.write("")

tab_today, tab_cal, tab_add, tab_pets, tab_plan, tab_ai = st.tabs(
    ["📋 Today", "📅 Calendar", "➕ Add task", "🐕 Pets", "🗓️ Day plan", "🤖 Assistant"]
)

# ---------------------------------------------------------------- Tasks
with tab_today:
    f1, f2, f3 = st.columns(3)
    pet_choice = f1.selectbox("Pet", ["All pets"] + [p.name for p in family.pets])
    member_choice = f2.selectbox("Assigned to", ["Everyone", "Me"] + family.members)
    status_choice = f3.selectbox("Status", ["To do", "Done today", "Upcoming", "All"])

    member_filter = {"Everyone": None, "Me": current}.get(member_choice, member_choice)
    shown = family.filter_tasks(
        pet_name=None if pet_choice == "All pets" else pet_choice,
        member=member_filter,
    )
    status_test = {
        "To do": lambda t: t.is_due(),
        "Done today": lambda t: t.done_on(),
        "Upcoming": lambda t: t.is_upcoming(),
        "All": lambda t: t.is_due() or t.done_on() or t.is_upcoming(),
    }[status_choice]
    shown = scheduler.sort_by_time([t for t in shown if status_test(t)])

    if conflicts:
        with st.expander(f"⚠️ {len(conflicts)} scheduling conflict(s)", expanded=True):
            for message in conflicts:
                st.warning(message)
            st.caption("The same person can't do two things at once. Reassign one task, change its time, or shorten it.")

    if not shown:
        st.markdown(
            '<div class="empty"><div class="e">🦴</div><b>Nothing here yet</b>'
            "Nothing to show for this filter. Use <i>Add task</i> to give your pets something to look forward to.</div>",
            unsafe_allow_html=True,
        )
    for i, t in enumerate(shown):
        pet = pet_of[id(t)]
        with st.container(border=True):
            st.markdown(
                f'<span class="card-marker prio-{t.priority} {"is-done" if t.completed else ""}"></span>',
                unsafe_allow_html=True,
            )
            c_time, c_main, c_btn, c_del = st.columns([1.2, 6.6, 2.0, 0.6], vertical_alignment="center", gap="small")
            c_time.markdown(f'<div class="timechip">{t.time or "Any"}</div>', unsafe_allow_html=True)
            who = t.assigned_to
            added = f" · added by {t.added_by}" if t.added_by and t.added_by != who else ""
            due = f" · due {t.due_date:%a %b %d}" if t.is_upcoming() else (
                " · overdue" if t.is_due() and t.due_date else "")
            color = PRIORITY_COLOR[t.priority]
            c_main.markdown(
                f"""<div class="{'task-done' if t.completed else ''}">
                <div class="task-title">{SPECIES_EMOJI.get(pet.species, '🐾')} {pet.name} — {t.title}</div>
                <div class="meta">
                  <span class="pill" style="background:{color}22;color:{color}">{t.priority}</span>
                  <span class="pill">{t.duration_minutes} min</span>
                  <span class="pill">{t.frequency}</span>
                  {avatar(who)}{who or 'Anyone'}{added}{due}
                </div></div>""",
                unsafe_allow_html=True,
            )
            if t.completed:
                c_btn.markdown('<div class="done-pill">✔ Completed</div>', unsafe_allow_html=True)
            elif c_btn.button("Done", key=f"done_{i}_{id(t)}", icon=":material/check_circle:", use_container_width=True):
                nxt = pet.mark_task_complete(t.title)
                flash(
                    f"Done! Next '{t.title}' on {nxt.due_date:%a %b %d}." if nxt else f"Done! '{t.title}' won't repeat.",
                    "✅",
                )
                st.rerun()
            if c_del.button("", key=f"del_{i}_{id(t)}", icon=":material/delete:", help="Delete this task"):
                pet.tasks[:] = [x for x in pet.tasks if x is not t]
                flash(f"Deleted '{t.title}' for {pet.name}", "🗑️")
                st.rerun()

# ---------------------------------------------------------------- Calendar
def _cal_set_month(delta: int | None) -> None:
    """Move the visible month; None jumps back to today."""
    if delta is None:
        st.session_state.cal_month = date.today().replace(day=1)
        st.session_state.cal_day = date.today()
        return
    month = st.session_state.cal_month
    index = month.year * 12 + month.month - 1 + delta
    st.session_state.cal_month = date(index // 12, index % 12 + 1, 1)


with tab_cal:
    st.session_state.setdefault("cal_month", date.today().replace(day=1))
    st.session_state.setdefault("cal_day", date.today())
    month_start: date = st.session_state.cal_month

    n1, n2, n3, n4 = st.columns([1, 4, 1, 1.4], vertical_alignment="center")
    n1.button("", key="cal_prev", icon=":material/chevron_left:", on_click=_cal_set_month, args=(-1,),
              use_container_width=True)
    n2.markdown(f'<div class="cal-title">{month_start:%B %Y}</div>', unsafe_allow_html=True)
    n3.button("", key="cal_next", icon=":material/chevron_right:", on_click=_cal_set_month, args=(1,),
              use_container_width=True)
    n4.button("Today", key="cal_today", icon=":material/today:", on_click=_cal_set_month, args=(None,),
              use_container_width=True)

    cal_member = st.selectbox("Show tasks for", ["Everyone", "Me"] + family.members, key="cal_member")
    cal_filter = {"Everyone": None, "Me": current}.get(cal_member, cal_member)

    def day_items(day: date):
        items = [(p, t) for p, t in family.tasks_on(day) if cal_filter is None or t.assigned_to == cal_filter]
        return sorted(items, key=lambda it: (it[1].time is None, it[1].time or "", it[0].name))

    selected: date = st.session_state.cal_day
    weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(month_start.year, month_start.month)
    cells = "".join(f'<div class="cal-h">{d}</div>' for d in ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"])
    for week in weeks:
        for day in week:
            items = day_items(day)
            classes = ["cal-d"]
            if day.month != month_start.month:
                classes.append("off")
            if day == date.today():
                classes.append("today")
            if day == selected:
                classes.append("sel")
            chips = ""
            for pet, t in items[:3]:
                color = PRIORITY_COLOR[t.priority]
                label = html.escape(f"{t.time + ' ' if t.time else ''}{pet.name}: {t.title}")
                chips += (f'<div class="chip{" done" if t.completed else ""}" '
                          f'style="background:{color}22;color:{color}">{label}</div>')
            more = f'<div class="more">+{len(items) - 3} more</div>' if len(items) > 3 else ""
            cnt = f'<span class="cal-cnt">{len(items)}</span>' if items else ""
            cells += f'<div class="{" ".join(classes)}"><span class="cal-n">{day.day}</span>{cnt}{chips}{more}</div>'
    st.markdown(f'<div class="cal">{cells}</div>', unsafe_allow_html=True)

    st.write("")
    picked_day = st.date_input("Look at a day", key="cal_day")
    items = day_items(picked_day)
    heading = "Today" if picked_day == date.today() else f"{picked_day:%A, %B %d}"
    st.markdown(f'<div class="section-title">{heading} · {len(items)} task(s)</div>', unsafe_allow_html=True)
    if not items:
        st.markdown('<div class="empty"><div class="e">🌤️</div><b>Nothing planned</b>A free day!</div>',
                    unsafe_allow_html=True)
    for pet, t in items:
        with st.container(border=True):
            st.markdown(
                f'<span class="card-marker prio-{t.priority} {"is-done" if t.completed else ""}"></span>',
                unsafe_allow_html=True,
            )
            c1, c2, c3 = st.columns([1.2, 7.4, 2], vertical_alignment="center")
            c1.markdown(f'<div class="timechip">{t.time or "Any"}</div>', unsafe_allow_html=True)
            c2.markdown(
                f"""<div class="{'task-done' if t.completed else ''}">
                <div class="task-title">{SPECIES_EMOJI.get(pet.species, '🐾')} {html.escape(pet.name)} — {html.escape(t.title)}</div>
                <div class="meta"><span class="pill">{t.duration_minutes} min</span><span class="pill">{t.frequency}</span>
                {avatar(t.assigned_to)}{html.escape(t.assigned_to or 'Anyone')}</div></div>""",
                unsafe_allow_html=True,
            )
            c3.markdown(
                f'<div class="done-pill">{"✔ Done" if t.completed else "Planned"}</div>', unsafe_allow_html=True
            )

# ---------------------------------------------------------------- Add task
with tab_add:
    if not family.pets:
        st.info("Add a pet in the **Pets** tab first.")
    else:
        st.markdown('<div class="section-title">New care task</div>', unsafe_allow_html=True)
        with st.form("add_task_form", clear_on_submit=True):
            a1, a2 = st.columns(2)
            task_pet = a1.selectbox("Pet", [p.name for p in family.pets])
            task_title = a2.text_input("What needs doing?", value="Morning walk")
            b1, b2, b3 = st.columns(3)
            duration = b1.number_input("Duration (min)", 1, 240, 20)
            priority = b2.selectbox("Priority", ["low", "medium", "high"], index=1)
            frequency = b3.selectbox("Repeats", ["daily", "weekly", "once"])
            d1, d2, d3 = st.columns(3, vertical_alignment="bottom")
            use_time = d1.checkbox("Set a specific time")
            picked = d2.time_input("Time", value=time(8, 0))
            assignee = d3.selectbox(
                "Assign to", ["Anyone"] + family.members,
                index=(family.members.index(current) + 1) if current else 0,
            )
            submitted = st.form_submit_button("Add task", type="primary")

        if submitted:
            if not task_title.strip():
                st.error("Please describe the task.")
            else:
                pet = next(p for p in family.pets if p.name == task_pet)
                pet.add_task(Task(
                    title=task_title.strip(), duration_minutes=int(duration), priority=priority,
                    frequency=frequency, time=picked.strftime("%H:%M") if use_time else None,
                    assigned_to=None if assignee == "Anyone" else assignee, added_by=current,
                ))
                flash(f"Added '{task_title.strip()}' for {pet.name}", "🐾")
                st.rerun()

        st.divider()
        s1, s2 = st.columns(2)
        slot_len = s1.number_input("Need a free slot? Task length (min)", 1, 240, 20, key="slot_len")
        slot_for = s2.selectbox(
            "For", ["Everyone"] + family.members,
            index=(family.members.index(current) + 1) if current else 0, key="slot_for",
        )
        if st.button("Find next free slot"):
            slot = scheduler.find_next_available_slot(
                int(slot_len), member=None if slot_for == "Everyone" else slot_for
            )
            if slot is not None:
                st.success(f"Next free slot: **{clock(slot)}**")
            else:
                st.warning("Nothing fits today.")

# ---------------------------------------------------------------- Pets
with tab_pets:
    st.markdown('<div class="section-title">Family pets</div>', unsafe_allow_html=True)
    with st.form("add_pet_form", clear_on_submit=True):
        p1, p2, p3 = st.columns([3, 2, 1.2], vertical_alignment="bottom")
        pet_name = p1.text_input("Pet name")
        species = p2.selectbox("Species", ["dog", "cat", "other"])
        add_pet_clicked = p3.form_submit_button("Add pet", type="primary", use_container_width=True)
    if add_pet_clicked:
        if not pet_name.strip():
            st.error("Please enter a pet name.")
        elif any(p.name.lower() == pet_name.strip().lower() for p in family.pets):
            st.error("That pet is already in the family.")
        else:
            family.add_pet(Pet(name=pet_name.strip(), species=species))
            flash(f"Welcome to the family, {pet_name.strip()}!", "🐾")
            st.rerun()

    if not family.pets:
        st.markdown(
            '<div class="empty"><div class="e">🐶🐱</div><b>No pets yet</b>Add your first family pet above.</div>',
            unsafe_allow_html=True,
        )
    cols = st.columns(3)
    for idx, pet in enumerate(family.pets):
        pending = sum(1 for t in pet.tasks if t.is_due())
        done_today = sum(1 for t in pet.tasks if t.done_on())
        total = pending + done_today
        ppct = round(100 * done_today / total) if total else 0
        kind = pet.species if pet.species in SPECIES_EMOJI else "other"
        with cols[idx % 3]:
          st.markdown(
            f"""<div class="petcard {kind}"><div class="big">{SPECIES_EMOJI.get(pet.species, '🐾')}</div>
            <div class="name">{pet.name}</div>
            <div class="meta">{pet.species.title()} · {pending} to do · {done_today} done today</div>
            <div class="mini"><span style="width:{ppct}%"></span></div></div>""",
            unsafe_allow_html=True,
          )
          with st.popover(f"Remove {pet.name}", icon=":material/delete:", use_container_width=True):
            st.write(f"Delete **{pet.name}** and its {len(pet.tasks)} task(s)? This can't be undone.")
            if st.button("Yes, delete", key=f"delpet_{pet.name}", type="primary", icon=":material/delete_forever:"):
                family.remove_pet(pet.name)
                flash(f"Removed {pet.name}", "🗑️")
                st.rerun()

# ---------------------------------------------------------------- Day plan
with tab_plan:
    st.markdown('<div class="section-title">Smart day plan</div>', unsafe_allow_html=True)
    st.caption(f"Highest priority first, within {family.available_minutes} minutes of family care time.")
    if st.button("Generate plan", type="primary"):
        if not pending_tasks:
            st.warning("No pending tasks to plan.")
        else:
            plan = scheduler.generate_plan()
            for t, start in plan.scheduled_tasks:
                with st.container(border=True):
                    st.markdown(f'<span class="card-marker prio-{t.priority}"></span>', unsafe_allow_html=True)
                    c1, c2 = st.columns([1.6, 8], vertical_alignment="center")
                    c1.markdown(
                        f'<div class="timechip">{clock(start)}–{clock(start + t.duration_minutes)}</div>',
                        unsafe_allow_html=True,
                    )
                    c2.markdown(
                        f'<div class="task-title">{pet_of[id(t)].name} — {t.title}</div>'
                        f'<div class="meta">{avatar(t.assigned_to)}{t.assigned_to or "Anyone"} · {t.priority} priority</div>',
                        unsafe_allow_html=True,
                    )
            st.success(f"Scheduled {len(plan.scheduled_tasks)} task(s) · {plan.total_minutes} min total")
            for t, reason in plan.skipped_tasks:
                st.warning(f"Skipped '{t.title}' ({pet_of[id(t)].name}): {reason}")

# ---------------------------------------------------------------- Assistant
with tab_ai:
    st.markdown('<div class="section-title">PawPal Assistant</div>', unsafe_allow_html=True)
    act_directly = st.toggle(
        "Let the assistant make changes for me", value=True, key="ai_direct",
        help="On: it adds pets, adds tasks and marks tasks done itself, like a family member. "
             "Off: it only suggests tasks and you approve each one. It can never delete anything.",
    )
    st.caption(
        "Try: “Add a puppy named Milo”, “Add a 20 minute walk for Rex at 7:30 every day, assigned to Ana”, "
        "or “Mark Rex's morning walk as done”. Care advice comes from the PawPal guide, not a vet."
        if act_directly else
        "Care advice grounded in the PawPal guide. It proposes tasks; nothing is added until you approve. Not veterinary advice."
    )
    if not os.environ.get("GEMINI_API_KEY"):
        st.info("Set GEMINI_API_KEY (environment variable or a `.env` line) and restart to enable the assistant.")
    else:
        # Suggested prompts built from this family's real pets, members and tasks
        suggestions: list[tuple[str, str]] = []
        first_pet = family.pets[0] if family.pets else None
        if first_pet is None:
            suggestions.append(("🐶 Add my first pet", "Add a dog named Buddy to my family"))
        else:
            if act_directly:
                suggestions.append((f"🗓️ Plan a routine for {first_pet.name}",
                                    f"Plan a daily care routine for {first_pet.name} and add the tasks to my schedule"))
            else:
                suggestions.append((f"🗓️ Routine for {first_pet.name}",
                                    f"What should I do daily for {first_pet.name}?"))
            suggestions.append((f"🍽️ How often to feed {first_pet.name}?",
                                f"How often should I feed my {first_pet.species}?"))
            suggestions.append((f"🛁 Grooming for {first_pet.name}",
                                f"How often should I groom my {first_pet.species}?"))
            if act_directly and family.members:
                suggestions.append((f"👤 Walk for {family.members[0]}",
                                    f"Add a 20 minute walk for {first_pet.name} at 07:30 every day, "
                                    f"assigned to {family.members[0]}"))
            todo = next(((p, t) for p in family.pets for t in p.tasks if t.is_due()), None)
            if act_directly and todo:
                suggestions.append((f"✅ Mark “{todo[1].title}” done",
                                    f"Mark {todo[0].name}'s {todo[1].title} as done"))
            suggestions.append(("⏰ Next free slot", "When is the next free 30 minute slot in my pet schedule?"))
            suggestions.append(("⚠️ Check conflicts", "Do I have any conflicts in my pet schedule?"))
        if act_directly:
            suggestions.append(("🐱 Add a new pet", "Add a cat named Luna to my family"))

        st.markdown('<div class="meta" style="margin:4px 0 6px">💡 Not sure what to ask? Tap one:</div>',
                    unsafe_allow_html=True)
        chosen = None
        chip_cols = st.columns(3)
        for i, (label, prompt_text) in enumerate(suggestions[:6]):
            if chip_cols[i % 3].button(label, key=f"sugg_{i}", use_container_width=True):
                chosen = prompt_text

        question = st.text_input("Or type your own", placeholder="What should I do daily for my beagle?")
        asked = st.button("Ask", type="primary") and bool(question)
        prompt = chosen or (question if asked else None)
        if prompt:
            with st.spinner("Thinking..."):
                st.session_state.assistant_result = PawPalAgent(family, auto_apply=act_directly, show_sources=False).ask(prompt)
            if st.session_state.assistant_result.actions:
                flash(f"Assistant made {len(st.session_state.assistant_result.actions)} change(s)", "🤖")
                st.rerun()  # refresh the counts, calendar and lists above
        result = st.session_state.get("assistant_result")
        if result:
            # Hide the "Sources: ..." line, even on an answer saved before sources were turned off
            shown_answer = re.sub(r"\s*Sources:.*\Z", "", result.answer, flags=re.S).strip()
            (st.warning if result.refused or result.error else st.info)(shown_answer or result.answer)
            for action in result.actions:
                st.success(action, icon="✅")
            for i, proposal in enumerate(list(result.proposals)):
                label = (f"**{proposal['pet']}: {proposal['title']}** · {proposal['duration_minutes']} min · "
                         f"{proposal['priority']} · {proposal.get('time') or 'any time'} · {proposal['frequency']}")
                with st.container(border=True):
                    c1, c2, c3 = st.columns([6, 1.2, 1.2], vertical_alignment="center")
                    c1.markdown(label)
                    if c2.button("Approve", key=f"approve_{i}_{label}", type="primary"):
                        try:
                            task = apply_proposal(family, proposal)
                            task.added_by = current
                            result.proposals.remove(proposal)
                            st.rerun()
                        except ValueError as exc:
                            st.error(f"Could not add: {exc}")
                    if c3.button("Reject", key=f"reject_{i}_{label}"):
                        result.proposals.remove(proposal)
                        st.rerun()
