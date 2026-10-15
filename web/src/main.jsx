import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

async function api(path, data) {
  const response = await fetch('/api/' + path, data === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'The local request failed.');
  return result;
}

function SourcePath({ context }) {
  if (!context) return null;
  const decision = context.decisions[0];
  const source = context.sources.find(s => s.id === decision?.path.at(-1));
  const rows = [
    { title: context.task, kind: 'Task', id: context.task_id },
    ...context.dependencies.filter(d => decision?.path.includes(d.id)).map(d => ({ title: d.name, kind: 'Dependency', id: d.id })),
    ...(decision ? [{ title: decision.text, kind: 'Decision · ' + decision.state, id: decision.id }] : []),
    ...(source ? [{ title: source.title + (source.uri.endsWith('#section-2') ? ' · §2' : ''), kind: 'Source', id: source.id }] : []),
  ];
  return <section className="source-section" aria-labelledby="path-title">
    <h2 id="path-title">The path behind the answer</h2>
    <ol className="path-list">{rows.map((row, i) => <li key={row.id}>
      <span className="path-number" aria-hidden="true">{i + 1}</span>
      <div><div className="path-title">{row.title}</div><div className="muted path-kind">{row.kind}<span className="record-id">{row.id}</span></div></div>
    </li>)}</ol>
    {source && <blockquote className="excerpt"><div className="small-label">SOURCE EXCERPT</div><p>{source.excerpt}</p></blockquote>}
    <p className="caption muted">Graph revision {context.revision} · Source path read from FalkorDB</p>
  </section>;
}

function AgentDraft({ title, answer, trace, stale = false }) {
  if (!answer) return null;
  return <section className={'draft ' + (stale ? 'stale' : '')}>
    <h3>{title}</h3>{stale && <p className="pink">Earlier graph revision. Trace again before using this answer.</p>}
    <p className="draft-answer">{answer}</p>
    {trace?.length > 0 && <details><summary>Inspect agent activity</summary><ol className="activity">{trace.map((step, i) => <li key={i}>
      {step.tool === 'get_task_context' ? 'Read live task context' : step.tool === 'propose_relay' ? 'Saved a pending relay proposal' : 'Read the approved relay'}
      <code>{step.tool}</code>
    </li>)}</ol></details>}
  </section>;
}

function PolicyEditor({ busy, perform, onSaved }) {
  const [open, setOpen] = useState(false);
  const [state, setState] = useState('cleared');
  const [text, setText] = useState('Policy amendment: the recovery drill evidence has been accepted. Review remains incomplete.');
  return <section className="policy">
    <div className="policy-row"><span>Policy amendment</span><button className="secondary small" disabled={busy} onClick={() => setOpen(!open)} aria-expanded={open}>Update decision</button></div>
    {open && <form className="policy-form" onSubmit={e => { e.preventDefault(); perform('Saving policy amendment…', async () => { await api('decision', { state, text }); setOpen(false); await onSaved(); }); }}>
      <label htmlFor="decision-state">Decision state</label><select id="decision-state" value={state} onChange={e => setState(e.target.value)}><option value="cleared">Cleared</option><option value="blocking">Blocking</option></select>
      <label htmlFor="policy-text">Source amendment</label><textarea id="policy-text" value={text} onChange={e => setText(e.target.value)} required maxLength={2000}/>
      <p className="caption muted">Saving creates a new source version. Existing relay context becomes outdated.</p>
      <button className="primary" disabled={busy || !text.trim()}>Save amendment</button>
    </form>}
  </section>;
}

function RelayPanel({ relay, relays, onSelect, busy, perform, refresh, specialist, setSpecialist }) {
  const status = !relay ? 'No relay prepared' : relay.stale ? 'Context changed · trace again' : relay.status === 'approved' ? 'Approved by you' : 'Awaiting your approval';
  const packet = relay?.packet;
  return <aside className="handoff" aria-labelledby="handoff-title">
    <h2 id="handoff-title">Next handoff</h2><p className="recipient">Review specialist</p>
    <p className="muted intro">Selected context, sources and permissions travel together.</p>
    <div className="relay-box">
      <h3>Release review</h3><p className="pink relay-status" aria-live="polite">{status}</p>
      <p className="permissions muted">Read selected context · Propose work</p>
      {packet && <details className="packet"><summary>Inspect context packet</summary>
        <p>{packet.purpose}</p><p><strong>Recipient:</strong> {packet.recipient}</p>
        <p><strong>Task:</strong> {packet.task}</p><p><strong>Expected result:</strong> {packet.expected_result}</p>
        <p><strong>Return route:</strong> {packet.return_route}</p>
        <p><strong>Sources:</strong> {packet.context.sources.map(s => s.id).join(', ')}</p>
        <p><strong>Selected dependencies:</strong> {packet.context.dependencies.map(d => d.name).join('; ')}</p>
        <p className="caption muted">Snapshot revision {relay.revision} · {relay.id.slice(0, 8)}</p>
      </details>}
      <button className="primary" disabled={busy || !relay || relay.stale || relay.status !== 'pending'} onClick={() => perform('Approving selected relay…', async () => { await api('approve', { relay_id: relay.id, human_confirmed: true }); await refresh(); })}>Approve relay</button>
      <button className="secondary" disabled={busy || !relay || relay.stale || relay.status !== 'approved'} onClick={() => perform('Specialist is reading the approved context…', async () => { const result = await api('resume', { relay_id: relay.id, recipient: packet.recipient }); setSpecialist(result); await refresh(); })}>Resume as specialist</button>
      <p className="caption muted approval-note">Only you can approve a relay.</p>
    </div>
    <PolicyEditor busy={busy} perform={perform} onSaved={refresh}/>
    <AgentDraft title="Specialist draft · fresh session" answer={specialist?.answer} stale={specialist && (specialist.relay_id !== relay?.id || relay?.stale)}/>
    {relays.length > 0 && <section className="history"><h3>Relay history</h3><ul>{relays.map(r => <li key={r.id}><button className={r.id === relay?.id ? 'history-item selected' : 'history-item'} onClick={() => { onSelect(r.id); setSpecialist(null); }} disabled={busy}><span>{r.id.slice(0, 8)}</span><span>{r.stale ? 'Outdated' : r.status === 'approved' ? 'Approved' : 'Pending'}</span></button></li>)}</ul></section>}
  </aside>;
}

function App() {
  const [state, setState] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [question, setQuestion] = useState('What is blocking the Lantern release?');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [answer, setAnswer] = useState(null);
  const [specialist, setSpecialist] = useState(null);
  async function refresh() { const next = await api('state'); setState(next); return next; }
  useEffect(() => { refresh().catch(e => setError(e.message)); }, []);
  async function perform(message, work) { setError(''); setBusy(message); try { await work(); } catch (e) { setError(e.message); await refresh().catch(() => {}); } finally { setBusy(''); } }
  const relays = state?.relays || [];
  const relay = relays.find(r => r.id === selectedId) || relays[0];
  const persisted = state?.runs.find(r => r.kind === 'coordinator');
  const currentAnswer = answer || (persisted ? { answer: persisted.answer, context: { revision: persisted.revision }, tool_trace: persisted.trace } : null);
  return <>
    <header className="app-header"><span className="wordmark">Agent Office</span><span className="room-title">Command Room</span><span className="model-label">Local · Qwen3 4B</span></header>
    <div className="shell"><nav className="project-rail" aria-label="Project"><div className="small-label">LANTERN PROJECT</div><div className="rail-active" aria-current="page">Release relay</div><p className="rail-note">Fictional workspace</p><p className="rail-version">v{state?.version || '0.2.1'} / Local prototype</p></nav>
      <main className="workspace"><div className="investigation"><h1>Good work needs context.</h1><p className="subtitle">Trace a task. Prepare the next handoff. Stay in control.</p>
        <form className="ask-form" onSubmit={e => { e.preventDefault(); perform('Tracing live context with the local model…', async () => { const result = await api('ask', { question }); setAnswer(result); setSelectedId(result.relay.id); setSpecialist(null); await refresh(); }); }}>
          <label className="small-label" htmlFor="question">ASK THE OFFICE</label>
          <textarea id="question" value={question} onChange={e => setQuestion(e.target.value)} required maxLength={2000} disabled={!!busy}/>
          <div className="ask-actions"><button className="primary" disabled={!!busy || !state || !question.trim()}>Trace context</button><span className="caption muted">Answers use the live FalkorDB graph.</span></div>
        </form>
        {busy && <p className="working" role="status"><span className="working-dot"/>{busy}</p>}
        {error && <div className="error" role="alert"><p>{error}</p>{!state && <button className="secondary small" onClick={() => perform('Reconnecting…', refresh)}>Retry connection</button>}</div>}
        <SourcePath context={state?.context}/>
        <AgentDraft title="Coordinator draft" answer={currentAnswer?.answer} trace={currentAnswer?.tool_trace} stale={currentAnswer && currentAnswer.context.revision !== state?.context.revision}/>
      </div>
      <RelayPanel relay={relay} relays={relays} onSelect={setSelectedId} busy={!!busy} perform={perform} refresh={refresh} specialist={specialist} setSpecialist={setSpecialist}/>
    </main></div>
  </>;
}

createRoot(document.getElementById('root')).render(<App/>);
