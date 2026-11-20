import json, sys, os, collections, datetime, glob
SRC = r"C:\Users\Yuhan Zhao\.claude\projects\c--Github-phaethon"
OUT = sys.argv[1]
SESS = sys.argv[2:]

def ts(s):
    return datetime.datetime.fromisoformat(s.replace('Z', '+00:00'))

def text_of(content):
    if isinstance(content, str):
        return content
    out = []
    for b in content:
        if b.get('type') == 'text':
            out.append(b['text'])
    return '\n'.join(out)

def trunc(s, n):
    s = s if isinstance(s, str) else json.dumps(s, ensure_ascii=False)
    return s if len(s) <= n else s[:n] + f'...[+{len(s)-n}]'

def condense(path, out_md, out_stats, label):
    lines = []; stats = collections.Counter(); tools = collections.Counter()
    usage = collections.Counter(); models = collections.Counter(); efforts = collections.Counter()
    first = last = None; asks = []; agents = []; compactions = 0; user_turns = 0; cost = None
    recs = [json.loads(l) for l in open(path, encoding='utf-8')]
    fullids = set(); ctx_max = 0; gaps = []; prev = None; seen_ids = set()
    for d in recs:
        t = d.get('type')
        if t == 'cost-state':
            cost = {k: v for k, v in d.items() if k not in ('sessionId', 'type')}
        if 'timestamp' in d and t in ('user', 'assistant'):
            x = ts(d['timestamp']); first = first or x; last = x
            if prev and (x - prev).total_seconds() > 600: gaps.append((str(prev)[11:19], round((x - prev).total_seconds() / 60)))
            prev = x
        if t == 'assistant':
            m = d['message']; models[m.get('model')] += 1; efforts[d.get('effort')] += 1
            u = m.get('usage') or {}
            mid = m.get('id')
            if mid not in seen_ids:
                seen_ids.add(mid)
                for k in ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'output_tokens'):
                    usage[k] += u.get(k, 0)
                usage['thinking_tokens'] += (u.get('output_tokens_details') or {}).get('thinking_tokens', 0)
                stats['api_calls'] += 1
            stats['assistant_msgs'] += 1
            ctx_max = max(ctx_max, u.get('input_tokens', 0) + u.get('cache_creation_input_tokens', 0) + u.get('cache_read_input_tokens', 0))
            tstamp = d.get('timestamp', '')[11:19]
            for b in m['content']:
                bt = b.get('type')
                if bt == 'text' and b['text'].strip():
                    lines.append(f"\n**A [{tstamp}]**: {b['text'].strip()}\n")
                elif bt == 'thinking':
                    stats['thinking_blocks'] += 1
                elif bt == 'tool_use':
                    name = b['name']; tools[name] += 1; inp = b.get('input', {})
                    if name in ('AskUserQuestion', 'Agent', 'Skill'): fullids.add(b.get('id'))
                    if name == 'AskUserQuestion':
                        asks.append((tstamp, inp))
                        lines.append(f"\n**A [{tstamp}] ASKUSERQUESTION**:\n```json\n{json.dumps(inp, ensure_ascii=False, indent=1)}\n```\n")
                    elif name == 'Agent':
                        agents.append((tstamp, inp))
                        lines.append(f"\n**A [{tstamp}] AGENT({inp.get('subagent_type')}, {inp.get('description')})**:\n```\n{inp.get('prompt', '')}\n```\n")
                    elif name == 'Skill':
                        lines.append(f"\n**A [{tstamp}] SKILL** {inp}\n")
                    elif name in ('Bash', 'PowerShell'):
                        lines.append(f"- [{tstamp}] {name}: `{trunc(inp.get('command', ''), 300)}`  ({inp.get('description', '')})")
                    elif name in ('Read', 'Glob', 'Grep'):
                        lines.append(f"- [{tstamp}] {name}: {trunc(inp, 200)}")
                    elif name in ('Edit', 'Write'):
                        lines.append(f"- [{tstamp}] {name}: {inp.get('file_path')} (old {len(inp.get('old_string', ''))}c new {len(inp.get('new_string', inp.get('content', '')))}c)")
                    else:
                        lines.append(f"- [{tstamp}] {name}: {trunc(inp, 300)}")
        elif t == 'user':
            m = d.get('message', {}); c = m.get('content')
            tstamp = d.get('timestamp', '')[11:19]
            if isinstance(c, list) and any(b.get('type') == 'tool_result' for b in c):
                for b in c:
                    if b.get('type') == 'tool_result':
                        cc = b.get('content')
                        s = cc if isinstance(cc, str) else ' '.join(x.get('text', '') for x in cc if isinstance(x, dict))
                        stats['tool_result_chars'] += len(s)
                        if b.get('is_error'):
                            stats['tool_errors'] += 1; lines.append(f"  - ERR: {trunc(s, 400)}")
                        elif b.get('tool_use_id') in fullids:
                            lines.append("  - RESULT (full):\n```\n" + trunc(s, 12000) + "\n```")
                        else:
                            lines.append(f"  - -> {trunc(s, 250)}")
            else:
                txt = text_of(c or '')
                if d.get('isCompactSummary') or 'This session is being continued from a previous conversation' in txt:
                    compactions += 1
                    lines.append(f"\n## [{tstamp}] COMPACTION SUMMARY\n{trunc(txt, 6000)}\n")
                elif 'agent-message' in txt[:300]:
                    lines.append(f"\n### [{tstamp}] AGENT HAND-BACK\n{trunc(txt, 20000)}\n")
                elif d.get('isMeta'):
                    lines.append(f"\n*(meta [{tstamp}])*: {trunc(txt, 300)}\n")
                else:
                    user_turns += 1
                    lines.append(f"\n## USER [{tstamp}]\n{trunc(txt, 5000)}\n")
    dur = (last - first).total_seconds() / 3600 if first and last else 0
    st = {'label': label, 'first': str(first), 'last': str(last), 'hours': round(dur, 2), 'user_turns': user_turns,
          'compactions': compactions, 'assistant_msgs': stats['assistant_msgs'], 'api_calls': stats['api_calls'], 'thinking_blocks': stats['thinking_blocks'],
          'tool_errors': stats['tool_errors'], 'tool_result_chars': stats['tool_result_chars'], 'tools': dict(tools),
          'usage': dict(usage), 'models': dict(models), 'efforts': dict(efforts), 'asks': len(asks), 'ctx_max': ctx_max, 'idle_gaps_min': gaps,
          'agents': [(t, i.get('subagent_type'), i.get('description')) for t, i in agents], 'cost': cost}
    hl = [l for l in lines if not l.startswith('- [') and not l.startswith('  - ')]
    with open(out_md.replace('.md', '.highlights.md'), 'w', encoding='utf-8') as f:
        f.write(f"# {label} highlights\n" + '\n'.join(hl))
    with open(out_md, 'w', encoding='utf-8') as f:
        f.write(f"# {label}\n\n```json\n{json.dumps(st, indent=1, default=str)}\n```\n\n" + '\n'.join(lines))
    with open(out_stats, 'w', encoding='utf-8') as f:
        json.dump(st, f, indent=1, default=str)
    return st

for sid in SESS:
    base = os.path.join(SRC, sid + '.jsonl'); od = os.path.join(OUT, sid[:8]); os.makedirs(od, exist_ok=True)
    st = condense(base, os.path.join(od, 'main.md'), os.path.join(od, 'main.stats.json'), sid)
    print(sid[:8], st['hours'], 'h', 'turns', st['user_turns'], 'compact', st['compactions'], 'asks', st['asks'],
          'agents', len(st['agents']), 'out_tok', st['usage'].get('output_tokens'), 'cache_read', st['usage'].get('cache_read_input_tokens'))
    for ag in sorted(glob.glob(os.path.join(SRC, sid, 'subagents', 'agent-*.jsonl'))):
        aid = os.path.basename(ag)[:-6]
        mp = ag[:-6] + '.meta.json'
        meta = json.load(open(mp, encoding='utf-8')) if os.path.exists(mp) else {}
        st2 = condense(ag, os.path.join(od, aid + '.md'), os.path.join(od, aid + '.stats.json'), f"{sid[:8]}/{aid} {json.dumps(meta)[:300]}")
        print('   ', aid, st2['hours'], 'h', 'msgs', st2['assistant_msgs'], 'out', st2['usage'].get('output_tokens'),
              'cache_read', st2['usage'].get('cache_read_input_tokens'), meta.get('description') or meta.get('agentType') or '')
