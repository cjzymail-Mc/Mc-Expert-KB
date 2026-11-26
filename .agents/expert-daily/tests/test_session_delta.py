"""Integration cases using throwaway Codex-format SQLite and rollout data."""
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import uuid
from datetime import datetime as RealTime
from pathlib import Path
from unittest.mock import patch

prior_bytecode = sys.dont_write_bytecode
sys.dont_write_bytecode = True
stage = Path(__file__).resolve().parent
target = stage.parent / 'session-delta.py'
module_spec = importlib.util.spec_from_file_location('delta', target)
delta = importlib.util.module_from_spec(module_spec)
try:
    module_spec.loader.exec_module(delta)
finally:
    sys.dont_write_bytecode = prior_bytecode


def stamp(when):
    return RealTime.fromisoformat('2026-11-' + when).astimezone()


def ms(when):
    return int(stamp(when).timestamp() * 1000)


class Clock(RealTime):
    current = stamp('24T17:00:00')

    @classmethod
    def now(cls, tz=None):
        return cls.current if tz is None else cls.current.astimezone(tz)


delta.datetime = Clock


class Data:
    def __init__(self, folder):
        self.home = folder / '.codex'
        self.home.mkdir()
        self.skills = folder/'kb'/'.agents'/'skills'
        self.skills.mkdir(parents=True)
        os.environ.update(CODEX_HOME=str(self.home), USERPROFILE=str(folder), HOME=str(folder))
        self.state = sqlite3.connect(self.home / 'state_5.sqlite')
        self.state.executescript('''CREATE TABLE threads(id TEXT PRIMARY KEY, rollout_path TEXT,
          agent_role TEXT, agent_path TEXT, created_at INTEGER, updated_at INTEGER,
          model_provider TEXT DEFAULT 'openai', model TEXT DEFAULT 'gpt-6.2-sol');''')
        self.project = sqlite3.connect(self.home / 'thread_history_1.sqlite')
        self.project.executescript('''CREATE TABLE thread_items(thread_id TEXT,turn_id TEXT,
          item_id TEXT,rollout_ordinal INTEGER,created_at_ms INTEGER,item_json TEXT,
          item_type TEXT,updated_at_ordinal INTEGER,started_at_ms INTEGER,completed_at_ms INTEGER,
          PRIMARY KEY (thread_id, turn_id, item_id));''')

    def role_state(self, name):
        skill = self.skills/name
        skill.mkdir(exist_ok=True)
        (skill/'daily-task.ps1').touch()
        return skill/'.local'/'unit-host'/'unit-user'

    def thread(self, n, start, end, role=None):
        uid = str(uuid.UUID(int=n))
        file = self.home/'sessions'/('rollout-' + uid + '.jsonl')
        file.parent.mkdir(exist_ok=True)
        self.state.execute('INSERT INTO threads(id,rollout_path,agent_role,agent_path,created_at,updated_at) VALUES(?,?,?,?,?,?)',
                           (uid, str(file), role, '/root/' + (role or ''), ms(start)//1000, ms(end)//1000))
        self.state.commit()
        return uid, file

    def reg(self, uid, role, when):
        sub = self.role_state(role)/'sessions'
        sub.mkdir(parents=True, exist_ok=True)
        (sub/(str(uuid.uuid4())+'.json')).write_text(json.dumps(dict(session=uid,expert=role,
              firstSeen=stamp(when).isoformat(),lastSeen=stamp(when).isoformat(),
              date=stamp(when).date().isoformat(),project='fixture',codexHome=str(self.home))), encoding='utf-8')

    def msg(self, uid, when, turn, who, txt):
        t = 'userMessage' if who == 'user' else 'agentMessage'
        b = dict(type=t, content=[dict(type='text',text=txt)]) if who=='user' else dict(type=t,text=txt,phase='final_answer')
        self.project.execute('INSERT INTO thread_items VALUES(?,?,?,?,?,?,?,?,?,?)',
            (uid,turn,str(uuid.uuid4()),ms(when),ms(when),json.dumps(b),t,ms(when),None,None))
        self.project.commit()

    def rollout(self, path, rows):
        with path.open('a',encoding='utf-8') as out:
            for when,ty,p in rows:
                out.write(json.dumps(dict(timestamp=stamp(when).isoformat(),type=ty,payload=p))+'\n')

    def run(self, role, when):
        Clock.current=stamp(when)
        delta.collect(role,self.role_state(role))

    def evidence(self, role):
        return [json.loads(p.read_text(encoding='utf-8'))['evidence'] for p in (self.role_state(role)/'pending').glob('*.json')]


def check(key, ok):
    if not ok:
        raise AssertionError(key)
    print('PASS', key)


def test_session_delta():
    with patch.dict(os.environ), tempfile.TemporaryDirectory() as td:
        d=Data(Path(td))
        alpha,beta='alpha-advisor','beta-advisor'
        u,f=d.thread(1,'24T12:00:00','25T01:00:00')
        d.msg(u,'24T12:00:01','old','user','OLD_UNRELATED')
        d.msg(u,'24T16:50:00','t1','user','$alpha-advisor A_REQUEST')
        d.reg(u,alpha,'24T16:50:05')
        d.run(alpha,'24T17:00:00')
        a1='\n'.join(d.evidence(alpha))
        check('explicit call included and old task excluded', 'A_REQUEST' in a1 and 'OLD_UNRELATED' not in a1)
        d.msg(u,'24T17:30:00','t1','assistant','A_FINAL_DELIVERED_LATE')
        d.msg(u,'24T18:01:00','t2','user','$beta-advisor B_PRIVATE_QUERY')
        d.reg(u,beta,'24T18:01:01')
        d.msg(u,'24T18:02:00','t2','assistant','B_PRIVATE_RESULT')
        d.run(alpha,'25T17:00:00')
        d.run(beta,'25T17:00:00')
        a2='\n'.join(d.evidence(alpha)); b2='\n'.join(d.evidence(beta))
        check('delayed answer from after cutoff collected with A context','A_FINAL_DELIVERED_LATE' in a2 and any('A_REQUEST' in x and 'A_FINAL_DELIVERED_LATE' in x for x in d.evidence(alpha)))
        check('two experts in one parent thread: B content excluded from A','B_PRIVATE_QUERY' not in a2 and 'B_PRIVATE_RESULT' not in a2)
        check('A content excluded from B','A_REQUEST' not in b2 and 'A_FINAL_DELIVERED_LATE' not in b2)
        check('B first invocation active','B_PRIVATE_QUERY' in b2)
        num=len(d.evidence(alpha))
        d.run(alpha,'25T18:00:00')
        check('second same-day run is idempotent',num==len(d.evidence(alpha)))

        child='other-expert'
        u2,f2=d.thread(2,'25T10:01:00','25T10:06:00',child)
        d.rollout(f2,[
            ('25T10:01:00','session_meta',{'id':u2,'forked_from_id':u,'parent_thread_id':u}),
            ('25T10:01:00','session_meta',{'id':u}),
            ('25T10:01:00','turn_context',{'turn_id':'inherited'}),
            ('25T10:01:00','response_item',{'type':'message','role':'user','content':[{'type':'input_text','text':'PRIVATE_PARENT_HISTORY'}]}),
            ('25T10:01:01','event_msg',{'type':'thread_settings_applied','thread_id':u2}),
            ('25T10:01:01','turn_context',{'turn_id':'child-turn'}),
            ('25T10:01:01','response_item',{'type':'agent_message','author':'/root','recipient':'/root/'+child,'content':[{'type':'input_text','text':'Message Type: NEW_TASK\nTask name: /root/other-expert\nSender: /root\nPayload:\nACTUAL_CHILD_HANDOFF'}]}),
            ('25T10:06:00','response_item',{'type':'message','role':'assistant','phase':'final_answer','content':[{'type':'output_text','text':'ACTUAL_CHILD_ANSWER'}]})])
        d.run(child,'25T17:00:00')
        out='\n'.join(d.evidence(child))
        check('direct call excludes inherited parent history','PRIVATE_PARENT_HISTORY' not in out)
        check('direct call includes actual handoff','ACTUAL_CHILD_HANDOFF' in out)
        check('direct call includes actual final answer','ACTUAL_CHILD_ANSWER' in out)

        # On current Codex, the text block can contain only the envelope. The parent
        # has the plaintext dispatch arguments. Unrelated parent requests must stay out.
        host,hostfile=d.thread(6,'25T10:01:00','25T10:06:00')
        crypt='opaque-advisor'
        opaque,opaque_file=d.thread(7,'25T10:02:00','25T10:06:00',crypt)
        d.rollout(hostfile,[
            ('25T10:01:00','response_item',{'type':'message','role':'user','content':[{'type':'input_text','text':'NEVER_COPY_PARENT_BODY'}]}),
            ('25T10:01:59','response_item',{'type':'function_call','name':'spawn_agent','namespace':'collaboration',
                                           'arguments':json.dumps(dict(task_name=crypt,agent_type=crypt,message='MATCHED_DISPATCH_ONLY'))}),
            ('25T10:02:00','response_item',{'type':'function_call','name':'spawn_agent','namespace':'collaboration',
                                           'arguments':json.dumps(dict(task_name='different',agent_type=crypt,message='UNRELATED_DISPATCH'))})])
        d.rollout(opaque_file,[
            ('25T10:02:00','session_meta',{'id':opaque,'parent_thread_id':host,'forked_from_id':host}),
            ('25T10:02:00','turn_context',{'turn_id':'child-turn'}),
            ('25T10:02:01','response_item',{'type':'agent_message','author':'/root','recipient':'/root/'+crypt,
                'content':[{'type':'input_text','text':'Message Type: NEW_TASK\nPayload:\n'},{'type':'encrypted_content','encrypted_content':'opaque-fixture'}]})])
        d.run(crypt,'25T17:00:00')
        opaque_out='\n'.join(d.evidence(crypt))
        check('opaque child receives only its own matched dispatch',
              'MATCHED_DISPATCH_ONLY' in opaque_out and 'NEVER_COPY_PARENT_BODY' not in opaque_out and 'UNRELATED_DISPATCH' not in opaque_out)

        for n, prefix, source in [(70, 'expert_auto_', 'automatic'), (71, 'expert_named_', 'explicit')]:
            role = 'tagged-advisor-' + str(n)
            uid, role_file = d.thread(n, '25T11:00:00', '25T11:05:00', role)
            task = prefix + 'sample'
            recipient = '/root/' + task
            d.state.execute('UPDATE threads SET agent_path=? WHERE id=?', (recipient,uid))
            d.state.commit()
            cipher = 'gAAAAA' + 'a'*100
            d.rollout(hostfile, [('25T11:00:01', 'response_item', {'type':'function_call', 'name':'spawn_agent',
                'namespace':'collaboration', 'arguments':json.dumps(dict(task_name=task,agent_type=role,message=cipher))})])
            handoff = {'type':'agent_message','author':'/root','recipient':recipient,
                       'content':[{'type':'input_text','text':'Message Type: NEW_TASK\nPayload:\n'}]}
            d.rollout(role_file, [('25T11:00:00','session_meta',{'id':uid,'parent_thread_id':host,'forked_from_id':host}),
                                  ('25T11:00:01','turn_context',{'turn_id':'first'}),
                                  ('25T11:00:02','response_item',handoff),
                                  ('25T11:05:00','turn_context',{'turn_id':'revision'}),
                                  ('25T11:05:00','response_item',handoff)])
            d.run(role,'25T17:00:00')
            records=[delta.read(x) for x in (d.role_state(role)/'pending').glob('*.json')]
            check('opaque dispatch and continuation: '+source,
                  any(r.get('invocationSources')==[source,'continued'] for r in records)
                  and all(cipher not in r['evidence'] for r in records))

        delayed='delayed-advisor'
        ud,fd=d.thread(3,'24T16:56:00','24T16:59:00',delayed)
        d.rollout(fd,[
            ('24T16:56:00','session_meta',{'id':ud,'parent_thread_id':host,'forked_from_id':host}),
            ('24T16:56:01','event_msg',{'type':'thread_settings_applied','thread_id':ud})])
        d.run(delayed,'24T17:00:00')
        d.msg(ud,'24T16:59:00','projected-late','assistant','LATE_PROJECTION_BEFORE_CUTOFF')
        d.run(delayed,'26T17:00:00')
        check('direct call missed before cutoff recovers late projection after missed day',
              'LATE_PROJECTION_BEFORE_CUTOFF' in '\n'.join(d.evidence(delayed)))

        orphan='projection-only-advisor'
        ux,_=d.thread(8,'25T12:00:00','25T12:05:00',orphan)
        d.msg(ux,'25T12:01:00','replayed-parent','user','DO_NOT_LEARN_INHERITED_PARENT_REQUEST')
        d.msg(ux,'25T12:02:00','unattributed','assistant','DO_NOT_LEARN_UNVERIFIED_ANSWER')
        with patch.object(delta,'query_messages',side_effect=AssertionError('unattributed child history read')):
            d.run(orphan,'25T17:00:00')
            d.run(orphan,'25T18:00:00')
        orphan_out=d.evidence(orphan)
        check('no rollout for child: record its invocation once without reading unverified messages',
              len(orphan_out)==1 and '本次已登记调用' in orphan_out[0] and 'DO_NOT_LEARN' not in orphan_out[0])

        mixed='mixed-advisor'
        um,fm=d.thread(4,'24T16:00:00','24T16:15:00')
        d.reg(um,mixed,'24T16:00:01');d.msg(um,'24T16:00:00','pm','user','$mixed-advisor PARTIAL_DB_REQUEST')
        d.rollout(fm,[('24T16:00:00','turn_context',{'turn_id':'pm'}),
            ('24T16:00:00','event_msg',{'type':'user_message','message':'$mixed-advisor PARTIAL_DB_REQUEST'}),
            ('24T16:15:00','event_msg',{'type':'agent_message','phase':'final_answer','message':'ROLLOUT_ONLY_FINAL'})])
        d.run(mixed,'26T17:00:00')
        check('partially projected thread recovers rollout-only outcome',
              'ROLLOUT_ONLY_FINAL' in '\n'.join(d.evidence(mixed)))
        late='overnight-advisor'
        un,_=d.thread(5,'24T23:51:00','25T08:01:00')
        d.reg(un,late,'24T23:55:01')
        d.msg(un,'24T23:55:00','night-task','user','$overnight-advisor CHECK_LATE_REQUEST')
        d.run(late,'24T23:59:00')
        d.msg(un,'25T08:00:00','night-task','assistant','SAME_TURN_OVERNIGHT_RESULT')
        d.msg(un,'25T08:01:00','unrelated','user','PRIVATE_UNREGISTERED_NEW_DAY')
        d.run(late,'25T17:00:00')
        contexts=d.evidence(late)
        check('overnight answer carries its own request without other material',
              any('CHECK_LATE_REQUEST' in c and 'SAME_TURN_OVERNIGHT_RESULT' in c for c in contexts)
              and not any('PRIVATE_UNREGISTERED_NEW_DAY' in c for c in contexts))
        check('credential values in quoted key-value data are redacted',
              'SECRET-TEXT-FIXTURE' not in delta.clean('{"api_key": "SECRET-TEXT-FIXTURE"}'))
        external = 'other-provider'
        uid, _ = d.thread(12,'25T14:00:00','25T14:05:00',external)
        d.state.execute("UPDATE threads SET model_provider='openrouter' WHERE id=?", (uid,))
        d.state.commit()
        d.reg(uid,external,'25T14:01:00')
        with patch.object(delta, 'query_messages', side_effect=AssertionError('foreign thread read')):
            d.run(external,'25T17:00:00')
        check('alternative provider in native home is excluded', not d.evidence(external))
        d.state.execute("UPDATE threads SET model_provider='openai',model='glm-5.3' WHERE id=?", (uid,))
        d.state.commit()
        check('mislabelled GLM thread cannot create manual feedback', not delta.native_thread(d.home, uid))
        alt_home = Path(td)/'.codex-glm'
        alt_home.mkdir()
        old = 'old-glm-receipt'
        reg = d.role_state(old)/'sessions'
        reg.mkdir(parents=True)
        (reg/'glm.json').write_text(json.dumps(dict(session=u,expert=old,firstSeen=stamp('24T16:50:05').isoformat(),codexHome=str(alt_home))), encoding='utf-8')
        with patch.object(delta, 'direct_calls', wraps=delta.direct_calls) as discover:
            d.run(old,'25T17:00:00')
            check('legacy receipt cannot add another home to nightly discovery',
                  not d.evidence(old) and [c.args[0] for c in discover.call_args_list]==[d.home])
        switch='mixed-runtime'
        um, fm=d.thread(14,'25T09:00:00','25T10:00:00')
        d.reg(um,switch,'25T09:00:02')
        d.msg(um,'25T09:00:01','other','user','$mixed-runtime FOREIGN_TURN_ONLY')
        d.msg(um,'25T09:10:00','native','user','$mixed-runtime OPENAI_TURN_ONLY')
        d.msg(um,'25T09:11:00','unknown','assistant','UNATTRIBUTED_MODEL')
        d.rollout(fm,[('25T09:00:00','turn_context',{'turn_id':'other','model':'glm-5.3'}),
                      ('25T09:09:59','turn_context',{'turn_id':'native','model':'gpt-6.2-sol'})])
        d.run(switch,'25T17:00:00')
        extracted=' '.join(d.evidence(switch))
        check('mixed window keeps the attributable native turn only', 'OPENAI_TURN_ONLY' in extracted and 'FOREIGN_TURN_ONLY' not in extracted and 'UNATTRIBUTED_MODEL' not in extracted)
        last_foreign='native-then-foreign'
        uf, ff = d.thread(15,'25T12:00:00','25T13:00:00')
        d.state.execute("UPDATE threads SET model='glm-5.3' WHERE id=?", (uf,))
        d.state.commit()
        d.reg(uf,last_foreign,'25T12:00:02')
        d.msg(uf,'25T12:00:01','first-native','user','$native-then-foreign FIRST_NATIVE')
        d.msg(uf,'25T12:10:00','later-glm','assistant','LATER_GLM')
        d.rollout(ff,[('25T12:00:00','turn_context',{'turn_id':'first-native','model':'gpt-6.2-sol'}),
                      ('25T12:09:59','turn_context',{'turn_id':'later-glm','model':'glm-5.3'})])
        d.run(last_foreign,'25T17:00:00')
        extracted = ' '.join(d.evidence(last_foreign))
        check('later model switch preserves earlier verified native evidence', 'FIRST_NATIVE' in extracted and 'LATER_GLM' not in extracted)
        foreign_use='foreign-only-call'
        uu, fu = d.thread(16,'25T12:00:00','25T14:00:00')
        d.reg(uu,foreign_use,'25T12:00:02')
        d.msg(uu,'25T12:00:01','glm-invocation','user','$foreign-only-call FOREIGN_INVOCATION')
        d.msg(uu,'25T13:00:01','unrelated-native','user','UNRELATED_NATIVE_WORK')
        d.rollout(fu,[('25T12:00:00','turn_context',{'turn_id':'glm-invocation','model':'glm-5.3'}),
                      ('25T13:00:00','turn_context',{'turn_id':'unrelated-native','model':'gpt-6.2-sol'})])
        d.run(foreign_use,'25T17:00:00')
        check('foreign invocation cannot claim later unrelated native work', not d.evidence(foreign_use))
        d.project.close(); d.state.close()


if __name__ == "__main__":
    test_session_delta()
