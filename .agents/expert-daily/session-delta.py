"""Collect new evidence only for explicitly registered expert days or actual named-role calls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import uuid
from contextlib import closing
from datetime import datetime, time, timedelta

DAY = timedelta(days=1)
UUID = re.compile(r'^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$', re.I)
MACHINE_TEXT = re.compile(r'^\s*(?:<(?:skill|environment_context|system|permissions|instructions|subagent_|turn_aborted|goal_context|INSTRUCTIONS)\b|# AGENTS\.md instructions for|This is a continuation of|Message Type:)', re.I)
SECRETS = re.compile(r'(?i)(?:sk-(?:proj-)?[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{14,}|Bearer\s+[A-Za-z0-9._~+/=-]{8,}|(?:token|api[_ -]?key|password|密码|密钥|secret)["\']?\s*[:=：]\s*["\']?[^\s,，;"\']{2,})')
MENTION = re.compile(r'(?<![\w$])\$\s*([a-z][a-z0-9]*(?:-[a-z0-9]+)*)\b', re.I)
LOCAL_PATH = re.compile(r'(?:[A-Za-z]:[\\/]|\\\\[^\\\s]+\\)[^\r\n"<>|]*')
FILE_FIELDS = ('feedback', 'subject', 'outcome', 'evidence')


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f'.{path.name}.{uuid.uuid4().hex}.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    os.replace(tmp, path)


def digest(*values):
    return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode()).hexdigest()


def ms(value):
    return int(value.timestamp() * 1000)


def local_day(value):
    return datetime.fromtimestamp(value / 1000).date()


def midnight(date):
    return ms(datetime.combine(date, time.min))


def db_file(home, stem):
    versions = [(int(p.stem.rsplit('_', 1)[1]), p) for p in home.glob(stem + '_*.sqlite')
                if p.stem.rsplit('_', 1)[1].isdigit()]
    return max(versions)[1] if versions else None


def connect(path):
    return sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=10)


def native_model(model):
    return bool(re.match(r'^(?:gpt(?:-|$)|chatgpt(?:-|$)|codex(?:-|$)|o\d+(?:-|$))', (model or '').lower()))


def openai_thread_model(home, thread):
    """Use the local thread index as origin evidence before reading conversation text."""
    db = db_file(home, 'state')
    if not db or not UUID.fullmatch(thread or ''):
        return None
    with closing(connect(db)) as conn:
        fields = {r[1] for r in conn.execute('PRAGMA table_info(threads)')}
        if not {'model_provider', 'model'} <= fields:
            return None
        row = conn.execute('SELECT model_provider, model FROM threads WHERE id=?', (thread,)).fetchone()
    return row[1] if row and row[0] == 'openai' else None


def native_thread(home, thread):
    return native_model(openai_thread_model(home, thread))


def clean(text):
    if not isinstance(text, str) or MACHINE_TEXT.match(text) or re.fullmatch(r'gAAAAA[A-Za-z0-9_=-]{60,}', text.strip()):
        return ''
    # Never turn a pasted environment, agent policy, code listing or secret into a learning rule.
    text = re.split(r'<(?:environment_context|skill|subagent_notification|system-reminder)\b', text, 1, re.I)[0]
    text = re.sub(r'\x60{3}[\s\S]*?(?:\x60{3}|$)', '〔代码略〕', text)
    text = re.sub(r'-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?(?:-----END [^-]*PRIVATE KEY-----|$)', '〔已隐去〕', text)
    text = re.sub(r'https?://\S+', '〔链接〕', text)
    text = LOCAL_PATH.sub('〔本机位置〕', text)
    text = SECRETS.sub('〔已隐去〕', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text if len(text) <= 1300 else text[:900] + ' … ' + text[-360:]


def query_messages(home, thread, start, end):
    db = db_file(home, 'thread_history')
    if not db:
        return []
    with closing(connect(db)) as conn:
        rows = conn.execute("""SELECT item_json,created_at_ms,turn_id FROM thread_items
            WHERE thread_id=? AND item_type IN ('userMessage','agentMessage')
            AND created_at_ms>=? AND created_at_ms<? ORDER BY created_at_ms,rollout_ordinal""",
                            (thread, start, end))
        result = []
        for js, timestamp, turn in rows:
            item = json.loads(js)
            if item['type'] == 'userMessage':
                t = ' '.join(b.get('text', '') for b in item.get('content', []) if b.get('type') == 'text')
                role = 'request'
            elif item.get('phase') in (None, 'final_answer', 'final'):
                t, role = item.get('text', ''), 'response'
            else:
                continue
            if t := clean(t):
                result.append((timestamp, role, t, turn))
    return result


def find_rollout(home, thread):
    db = db_file(home, 'state')
    if db:
        with closing(connect(db)) as conn:
            row = conn.execute('SELECT rollout_path FROM threads WHERE id=?', (thread,)).fetchone()
        if row and row[0]:
            path = Path(row[0])
            for p in (path, Path(str(path) + '.zst')):
                if p.is_file() and thread in p.name:
                    return p
    for folder in ('sessions', 'archived_sessions'):
        for path in (home / folder).rglob(f'*{thread}.jsonl*'):
            if path.name.endswith(('.jsonl', '.jsonl.zst')):
                return path
    return None


def read_rollout(path):
    if path.suffix != '.zst':
        return path.read_bytes()
    try:
        from compression import zstd
        return zstd.decompress(path.read_bytes())
    except ImportError:
        # Node 24 is shipped on this machine; no dependency installation is needed.
        js = "process.stdout.write(require('node:zlib').zstdDecompressSync(require('node:fs').readFileSync(process.argv[1])))"
        return subprocess.run(['node', '-e', js, str(path)], stdout=subprocess.PIPE, check=True).stdout


def delivered_prompts(home, parent, child, envelopes):
    """Match opaque inbound envelopes to the actual dispatch. Never import parent conversation text."""
    if not child[1] or not native_thread(home, parent):
        return []
    result = []
    db = db_file(home, 'thread_history')
    lo, hi = min(x[0] for x in envelopes)-120_000, max(x[0] for x in envelopes)+1000
    candidates = []
    if db:
        with closing(connect(db)) as conn:
            for stamp, js in conn.execute("""SELECT created_at_ms,item_json FROM thread_items
                    WHERE thread_id=? AND item_type='collabAgentToolCall' AND created_at_ms BETWEEN ? AND ?""",
                    (parent,lo,hi)):
                item = json.loads(js)
                if child[0] in (item.get('receiverThreadIds') or []) and item.get('prompt'):
                    candidates.append((stamp,item['prompt']))
    path = find_rollout(home, parent)
    if path:
        lines = read_rollout(path).splitlines()
        _, nonnative_turns = classify_turns(lines)
        if nonnative_turns:
            # Parent dispatch projections have no reliable model tag of their own.
            # For a mixed parent, use the child's attributable messages instead.
            return []
        for line in lines:
            # Skip tool outputs, parent user messages, images and unrelated event types.
            if not any(k in line for k in (b'spawn_agent',b'followup_task',b'send_message')):
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            args = obj.get('payload', {})
            tool = args.get('name')
            if (obj.get('type') != 'response_item' or args.get('type') != 'function_call' or
                    tool not in ('spawn_agent','followup_task','send_message') or args.get('namespace') not in ('collaboration',None)):
                continue
            stamp = ms(datetime.fromisoformat(obj['timestamp'].replace('Z','+00:00')))
            if not lo <= stamp <= hi:
                continue
            try:
                fields = json.loads(args['arguments'])
            except (ValueError,KeyError,TypeError):
                continue
            if tool == 'spawn_agent' and fields.get('agent_type') != child[2]:
                continue
            target = fields.get('task_name' if tool=='spawn_agent' else 'target')
            if target not in (child[0],child[1],child[1].rsplit('/',1)[-1]):
                continue
            if fields.get('message'):
                candidates.append((stamp,fields['message']))
    for stamp, turn in envelopes:
        near = [(abs(t-stamp),i,msg) for i,(t,msg) in enumerate(candidates) if -1000 <= stamp-t <= 120_000]
        if near:
            _,idx,msg = min(near)
            if text := clean(msg):
                result.append((stamp,'request',text,turn))
            candidates.pop(idx)
    return result


def classify_turns(lines):
    native, foreign = set(), set()
    for line in lines:
        if b'"turn_context"' not in line[:160]:
            continue
        try:
            item = json.loads(line)
        except ValueError:
            continue
        ctx = item.get('payload') or {}
        if item.get('type') != 'turn_context':
            continue
        turn_id = ctx.get('turn_id') or ''
        if ctx.get('model_provider', 'openai') != 'openai' or (ctx.get('model') and not native_model(ctx['model'])):
            foreign.add(turn_id)
        elif turn_id and native_model(ctx.get('model')):
            native.add(turn_id)
    return native - foreign, foreign


def legacy_messages(path, start, end, child=None, home=None, require_tag=False):
    rows = []
    turn = ''
    child_started = None
    inherited_turns = set()
    opaque = []
    route_origin = None
    if child and child[1]:
        task = child[1].rsplit('/', 1)[-1]
        if task.startswith('expert_auto_'):
            route_origin = 'automatic'
        elif task.startswith('expert_named_'):
            route_origin = 'explicit'
    first_delivery = True
    parent = None
    data = read_rollout(path)
    lines = data.splitlines()
    native_turns, foreign = classify_turns(lines)
    for line in lines:
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            if not data.endswith((b'\r', b'\n')) and data.endswith(line):
                break  # The active writer can be in the middle of the last JSON record.
            raise
        payload = obj.get('payload', {})
        if not obj.get('timestamp'):
            continue
        stamp = ms(datetime.fromisoformat(obj['timestamp'].replace('Z', '+00:00')))
        typ, kind = obj.get('type'), payload.get('type')
        if child and typ == 'session_meta':
            if payload.get('id') == child[0]:
                parent = payload.get('parent_thread_id') or payload.get('forked_from_id')
                child_started = None if payload.get('forked_from_id') or payload.get('parent_thread_id') else stamp
            elif payload.get('id'):
                child_started = None  # A second session_meta starts the replay of the parent's history.
            continue
        if typ == 'turn_context' or (typ == 'event_msg' and kind == 'task_started'):
            turn = payload.get('turn_id') or turn
            continue
        if child and typ == 'event_msg' and kind == 'thread_settings_applied' and payload.get('thread_id') == child[0]:
            if child_started is None:
                child_started = stamp
            continue
        if child and typ == 'response_item' and kind == 'agent_message':
            if child[1] and payload.get('recipient') != child[1]:
                continue
            raw = '\n'.join(b.get('text', '') for b in payload.get('content', []) if isinstance(b, dict))
            if not raw.startswith(('Message Type: NEW_TASK','Message Type: MESSAGE')) or 'Payload:' not in raw:
                continue
            if child_started is None:
                child_started = stamp
            t, role = raw.partition('Payload:')[2].strip(), 'request'
            if not t and start <= stamp < end:
                opaque.append((stamp,turn))
            # Delivered envelopes retain recipient metadata even if the prompt is opaque.
            # Only new, opt-in task paths carry a source; older direct calls stay unclassified.
            if route_origin and not t:
                source = route_origin if first_delivery else 'continued'
                t = f'[expert-route {source}]'
            first_delivery = False
        elif typ == 'event_msg' and kind in ('user_message', 'agent_message'):
            role = 'request' if kind == 'user_message' else 'response'
            t = payload.get('message', '')
            if role == 'response' and payload.get('phase') == 'commentary':
                continue
        elif typ == 'response_item' and kind == 'message' and payload.get('role') in ('assistant', 'user'):
            role = 'request' if payload['role'] == 'user' else 'response'
            if payload.get('phase') == 'commentary':
                continue
            t = ' '.join(b.get('text', '') for b in payload.get('content', []) if isinstance(b, dict))
        else:
            continue
        if child and child_started is None:
            if turn:
                inherited_turns.add(turn)
            continue
        if not start <= stamp < end:
            continue
        if t := clean(t):
            rows.append((stamp, role, t, turn))
    if opaque and home:
        rows.extend(delivered_prompts(home, parent, child, opaque))
    return rows, child_started, inherited_turns, (native_turns if foreign or require_tag else None)


def registered_windows(local, default_home, expert):
    windows = []
    for p in sorted((local / 'sessions').glob('*.json')):
        try:
            rec = read(p)
            session = str(rec.get('session') or '').lower()
            if not UUID.fullmatch(session) or rec.get('expert', expert) != expert:
                continue
            date = datetime.fromisoformat(str(rec.get('date') or rec['firstSeen'])[:10]).date()
            first = ms(datetime.fromisoformat(rec['firstSeen'].replace('Z', '+00:00')))
            home = Path(rec.get('codexHome') or default_home)
            if home.resolve() != default_home.resolve():
                continue
            marks = tuple(ms(datetime.fromisoformat(m.replace('Z','+00:00'))) for m in rec.get('calledAt') or ())
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            print(f'Unreadable invocation file {p.name}: {type(exc).__name__}', file=sys.stderr)
            continue
        windows.append((home, session, date, max(midnight(date), first), 'parent', marks or (first,)))
    return windows


def direct_calls(home, expert, floor, now):
    db = db_file(home, 'state')
    if not db:
        return []
    with closing(connect(db)) as conn:
        fields = {r[1] for r in conn.execute('PRAGMA table_info(threads)')}
        if not {'agent_role','id','created_at','updated_at'} <= fields:
            return []
        agent_path = 'agent_path' if 'agent_path' in fields else 'NULL'
        rows = conn.execute(f"""SELECT id, created_at, updated_at, {agent_path} FROM threads
            WHERE agent_role=? AND updated_at>=? AND created_at<?""", (expert, floor // 1000, now // 1000 + 1))
        result = []
        for thread, created, updated, path in rows:
            start = max(created * 1000, floor)
            date = local_day(start)
            while date <= local_day(min(now, updated * 1000 + 999)):
                result.append((home, thread, date, max(midnight(date), start), 'child', (path, local_day(created*1000) == date)))
                date += DAY
    return result


def queue_record(local, expert, uid, role, texts):
    record_id = digest('chat-evidence-v1', expert, uid, role, texts)
    if any((local / d / (record_id + '.json')).exists() for d in ('pending', 'processed')):
        return
    fields = (
        '请从下列本次调用的对话摘录中判断有无可复用的纠偏。'
        if role == 'parent' else '专家本次直接调用的交接和答复。交接是主 agent 的描述，不能据此确立用户长期偏好。',
        '本次专家协作（' + expert + '）',
        '结合摘录中的请求及答复核查。没有新经验或与本专家无关时可直接结案。明确冲突再留待核对。',
        '\n'.join(texts))
    record = dict(id=record_id, historySource='native-codex', **dict(zip(FILE_FIELDS, fields)))
    if role == 'child':
        # A tag at the start of a delivered handoff describes routing, not user preference.
        sources = []
        for line in texts:
            tag = re.match(r'^交接者：\[expert-route (automatic|explicit|continued)\](?:\s|$)', line)
            if tag and tag[1] not in sources:
                sources.append(tag[1])
        if sources:
            record['invocationSources'] = sources
            record['feedback'] += ' 本批专家交接标明的调度来源：' + '、'.join(sources) + '。'
    save(local / 'pending' / (record_id + '.json'), record)


def parent_scope(rows, expert, first, marks, names):
    """Resolve actual mentions at the user request, even when the skill registers moments later."""
    boundary = sorted(marks)
    idx, active = 0, set()
    explicit_turns = {}
    prior = next((r for r in reversed(rows) if r[0] <= first and r[1] == 'request'), None)
    if prior and (not prior[3] or not any(r[3] == prior[3] and r[0] >= first for r in rows)):
        if expert not in MENTION.findall(prior[2]):
            prior = None
    selected = []
    for row in rows:
        stamp, kind, text, turn = row
        while idx < len(boundary) and boundary[idx][0] <= stamp:
            point, name = boundary[idx]
            idx += 1
            if point and name not in active:
                active = {name}
        if kind == 'request':
            called = set(MENTION.findall(text)) & names
            if called:
                active = called
                if turn:
                    explicit_turns[turn] = called
        owners = explicit_turns.get(turn, active)
        if stamp < first:
            if row == prior and (expert in owners or not owners):
                selected.append(row)
        elif expert in owners:
            selected.append(row)
    return selected


def parent_marks(local, expert, default_home):
    # Sibling skill directories are authoritative for a shared parent thread's handoffs.
    if local.parent.parent.name == '.local':
        skills = local.parents[3]
        siblings = [(d.name, d/'.local'/local.parent.name/local.name) for d in skills.iterdir()
                    if d.is_dir() and (d/'daily-task.ps1').is_file()]
    else:
        siblings = []
    siblings = [(n, d) for n, d in siblings if n != expert] + [(expert, local)]
    names = {n for n, _ in siblings}
    windows, marks = [], {}
    for name, state in siblings:
        for window in registered_windows(state, default_home, name):
            home, thread, date, first, _, points = window
            key = (home.resolve(), thread, date)
            marks.setdefault(key, set()).update((point, name) for point in points)
            if name == expert:
                windows.append(window)
    return windows, marks, names


def collect_window(local, expert, home, thread, date, first, role, detail, now, marks, names):
    day_end = midnight(date + DAY)
    end = min(now, midnight(date + 2*DAY) if role == 'parent' else day_end)
    key = digest(str(home.resolve()).casefold(), thread, date.isoformat(), role)
    cursor = local / 'history-cursors' / (key + '.json')
    previous = read(cursor) if cursor.is_file() else {}
    if previous.get('closed') or end <= first:
        return
    model = openai_thread_model(home, thread)
    if not model:
        return
    # Read the current day again until settled, so late projection writes cannot be lost.
    start = max(midnight(date), first - (15 * 60 * 1000 if role == 'parent' else 0))
    path = find_rollout(home, thread)
    # SQLite can project a fork's inherited parent turns under the child ID.
    # Without a rollout boundary we can attest only that the named expert was called.
    if not path and not native_model(model):
        return
    rows = query_messages(home, thread, start, end) if role == 'parent' or path is not None else []
    if path:
        extra, gate, inherited, allowed_turns = legacy_messages(path, start, end, (thread,detail[0],expert) if role == 'child' else None, home, require_tag=not native_model(model))
        if role == 'child':
            # Projected messages can also contain inherited turns with rewritten timestamps.
            rows = [r for r in rows if gate is not None and r[0] >= gate and r[3] not in inherited]
        rows = sorted(rows + extra, key=lambda r: r[0])
        if allowed_turns is not None:
            native_rows = [r for r in rows if r[3] in allowed_turns]
            if role == 'parent':
                # Untagged receipt times cannot establish which runtime invoked a skill
                # in a mixed thread. Keep the verified request turn and its answers.
                invoked = {r[3] for r in native_rows if r[1] == 'request' and expert in MENTION.findall(r[2])}
                native_rows = [r for r in native_rows if r[3] in invoked]
            if not native_rows:
                return
            rows = native_rows
    elif role == 'parent' and not db_file(home, 'thread_history'):
        raise RuntimeError(f'No readable history for registered {expert} session {thread[:8]}')
    waiting = False
    if role == 'parent':
        selected = parent_scope([r for r in rows if r[0] < day_end], expert, first,
                                marks.get((home.resolve(),thread,date), ()), names)
        # A late-night invocation can finish after midnight. Retain only the same
        # turn's answer, without claiming unrelated work from the following day.
        if selected and selected[-1][1] == 'request' and selected[-1][3]:
            replies = [r for r in rows if r[0] >= day_end and r[1] == 'response' and r[3] == selected[-1][3]]
            waiting = not replies
            selected.extend(replies)
        rows = selected
    seen = set(previous.get('seen', []))
    new = []
    in_batch = set()
    for stamp, kind, text, turn in rows:
        # Legacy logs can serialize one utterance both as an event and a response item.
        ident = digest(turn, kind, text)
        if ident in seen or ident in in_batch:
            continue
        in_batch.add(ident)
        who = ('用户' if role == 'parent' else '交接者') if kind == 'request' else '助手答复'
        new.append((ident, who + '：' + text, turn))
    # A continued turn can complete after 17:00. Carry the request forward with a new response.
    excerpt = []
    if (new and new[0][1].startswith('助手答复') and previous.get('lastRequest')
            and new[0][2] and new[0][2] == previous.get('lastRequestTurn')):
        excerpt.append('上次已读的请求（仅供对照）：' + previous['lastRequest'])
    for _, line, _ in new:
        excerpt.append(line)
        if sum(map(len, excerpt)) >= 6500:
            queue_record(local, expert, key, role, excerpt)
            excerpt = []
    if excerpt:
        queue_record(local, expert, key, role, excerpt)
    if (role == 'parent' or detail[1]) and not seen and not new and not previous.get('checked'):
        queue_record(local, expert, key, role, ['本次已登记调用，当前未取得可供判断的纠偏或结果。'])
    requests = [(line, turn) for _, line, turn in new if line.startswith(('用户：', '交接者：'))]
    request, request_turn = requests[-1] if requests else (previous.get('lastRequest'), previous.get('lastRequestTurn'))
    settle = midnight(date + 2*DAY) if waiting else day_end
    save(cursor, {'seen': sorted(seen | in_batch), 'lastRequest': request, 'lastRequestTurn': request_turn,
                  'checked': True, 'closed': now >= settle + 2 * 3600 * 1000})


def collect(expert, local):
    now = ms(datetime.now())
    default_home = Path.home() / '.codex'
    registered, marks, names = parent_marks(local, expert, default_home)
    mark = local / 'discovery.json'
    today = midnight(local_day(now))
    # On first installation discover today's direct calls. On later runs include missed days.
    floor = min(today, midnight(local_day(read(mark)['through']))) if mark.is_file() else today
    calls = list(registered)
    calls.extend(direct_calls(default_home, expert, floor, now))
    for args in dict.fromkeys(calls):
        collect_window(local, expert, *args, now, marks, names)
    save(mark, {'through': now})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-native-session', metavar='ID')
    parser.add_argument('--expert')
    parser.add_argument('--local-dir', type=Path)
    args = parser.parse_args()
    if args.check_native_session:
        raise SystemExit(0 if native_thread(Path.home() / '.codex', args.check_native_session) else 3)
    if not (args.expert and args.local_dir):
        parser.error('collection requires --expert and --local-dir')
    collect(args.expert, args.local_dir)

