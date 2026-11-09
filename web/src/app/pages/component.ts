import { Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Api, ComponentDetail, Tool, Version, errorText } from '../api';
import { AgoPipe, ClientPipe, DiffLine, Fingerprint, SevBadge, StatusBadge, lineDiff } from '../shared';

interface ToolChange { name: string; change: 'added' | 'removed' | 'changed'; diff: DiffLine[]; schemaChanged: boolean }
interface FileChange { path: string; change: 'added' | 'removed' | 'changed'; diff: DiffLine[] | null }

@Component({
  selector: 'sg-component',
  imports: [FormsModule, RouterLink, AgoPipe, ClientPipe, Fingerprint, SevBadge, StatusBadge],
  template: `
    <div class="page">
      <a routerLink="/inventory" class="small crumb">Inventory</a>
      @if (error()) { <div class="error-box">{{ error() }}</div> }
      @if (c(); as c) {
        <div class="page-head">
          <div>
            <div class="row title"><h1>{{ c.name }}</h1><sg-status [value]="c.status" /></div>
            <p class="sub"><code>{{ c.identity }}</code> · {{ c.kind === 'skill' ? 'Agent skill' : 'MCP server' }} · first seen {{ c.first_seen_at | ago }}</p>
          </div>
          @if (api.isAdmin()) {
            <div class="row">
              @if (c.status === 'blocked') {
                <button class="btn" (click)="unblock()" [disabled]="busy()">Unblock</button>
              } @else {
                <button class="btn danger" (click)="mode.set('block')">Block</button>
              }
            </div>
          }
        </div>

        @if (c.status === 'blocked') {
          <div class="banner blocked">Blocked{{ c.blocked_reason ? ': ' + c.blocked_reason : '' }}.
            Developers see this reason, <code>mcpledger check</code> fails, and <code>mcpledger fix --yes</code> removes it.</div>
        } @else if (c.status === 'drift') {
          <div class="banner drift">Some machines run a version you haven't approved. Compare it with the approved version below,
            then approve it or block the component.</div>
        } @else if (c.status === 'pending') {
          <div class="banner pending">Not reviewed yet. Check the findings and {{ c.kind === 'skill' ? 'files' : 'tool definitions' }}, then approve the version you trust.</div>
        }

        @if (mode() === 'block') {
          <section class="panel decide">
            <div class="body stack">
              <label class="field"><span>Reason developers will see</span>
                <input type="text" [(ngModel)]="note" placeholder="e.g. Sends repository contents to a third-party server"></label>
              <div class="row"><button class="btn solid-danger" (click)="block()" [disabled]="busy()">Block everywhere</button>
                <button class="btn ghost" (click)="mode.set('')">Cancel</button></div>
            </div>
          </section>
        }

        <section class="panel">
          <header><h2>Versions</h2><span class="faint small">Each fingerprint is one exact {{ c.kind === 'skill' ? 'set of files' : 'launch config and tool list' }}. Approving pins it.</span></header>
          <div class="table-wrap"><table class="ledger">
            <thead><tr><th>Fingerprint</th><th>Version</th><th>Risk</th><th class="num">Machines</th><th>First seen</th><th></th></tr></thead>
            <tbody>
              @for (v of c.versions; track v.id) {
                <tr class="clickable" [class.sel]="v.id === selected()?.id" (click)="selectedId.set(v.id)">
                  <td><sg-print [hash]="v.fingerprint" /></td>
                  <td>{{ v.version_label }}
                    @if (v.approved) { <div class="ok small">Approved by {{ v.approved_by }}</div> }
                    @else if (v.trusted) { <div class="ok small">Matches an approved version</div> }</td>
                  <td><sg-sev [value]="v.max_severity" /></td>
                  <td class="num">{{ v.installs }}</td>
                  <td class="faint small">{{ v.first_seen_at | ago }}</td>
                  <td class="actions">
                    @if (api.isAdmin() && c.status !== 'blocked') {
                      @if (v.approved) {
                        <button class="btn small" (click)="revoke(v); $event.stopPropagation()" [disabled]="busy()">Revoke</button>
                      } @else if (!v.trusted) {
                        <button class="btn small approve" (click)="approve(v); $event.stopPropagation()" [disabled]="busy()">Approve</button>
                      }
                    }
                  </td>
                </tr>
              }
            </tbody>
          </table></div>
        </section>

        @if (selected(); as v) {
          @if (baseline() && baseline()!.id !== v.id && !v.trusted) {
            <section class="panel">
              <header><h2>What changed since approval</h2>
                <span class="row small faint"><sg-print [hash]="baseline()!.fingerprint" [compact]="true" /> to <sg-print [hash]="v.fingerprint" [compact]="true" /></span></header>
              <div class="body stack">
                @if (configChanges().length) {
                  <div><h3>Launch config</h3>
                    <ul class="changes">@for (ch of configChanges(); track ch) { <li>{{ ch }}</li> }</ul></div>
                }
                @for (t of toolChanges(); track t.name) {
                  <div class="change">
                    <h3><code>{{ t.name }}</code> <span class="pill {{ t.change }}">{{ t.change }}</span>
                      @if (t.schemaChanged) { <span class="faint small">input schema changed</span> }</h3>
                    @if (t.diff.length) { <pre class="diff">@for (l of t.diff; track $index) {<span class="{{ l.kind }}">{{ l.kind === 'add' ? '+ ' : l.kind === 'del' ? '- ' : '  ' }}{{ l.text }}</span>}</pre> }
                  </div>
                }
                @for (f of fileChanges(); track f.path) {
                  <div class="change">
                    <h3><code>{{ f.path }}</code> <span class="pill {{ f.change }}">{{ f.change }}</span></h3>
                    @if (f.diff) { <pre class="diff">@for (l of f.diff; track $index) {<span class="{{ l.kind }}">{{ l.kind === 'add' ? '+ ' : l.kind === 'del' ? '- ' : '  ' }}{{ l.text }}</span>}</pre> } @else if (f.change === 'changed') { <p class="faint small">Contents weren't uploaded (machine used <code>--hashes-only</code>).</p> }
                  </div>
                }
                @if (!configChanges().length && !toolChanges().length && !fileChanges().length) {
                  <p class="muted">Only the tool list was recorded on one side, so there's nothing to compare line by line.</p>
                }
              </div>
            </section>
          }

          <section class="panel">
            <header><h2>Findings</h2><span class="faint small">Static checks for prompt injection, hidden text, exfiltration and risky config.</span></header>
            @if (v.findings.length === 0) { <div class="empty"><p>No findings for this version.</p></div> }
            @else {
              <ul class="findings">
                @for (f of v.findings; track f.rule + f.location) {
                  <li>
                    <div class="row"><sg-sev [value]="f.severity" /><strong>{{ f.title }}</strong><span class="faint small">{{ f.rule }} · {{ f.location }}</span></div>
                    <p class="muted small">{{ f.detail }}</p>
                    @if (f.evidence) { <code class="evidence">{{ f.evidence }}</code> }
                  </li>
                }
              </ul>
            }
          </section>

          <div class="split">
            <section class="panel">
              @if (c.kind === 'mcp_server') {
                <header><h2>Tools</h2><span class="faint small">{{ v.snapshot.tools ? v.snapshot.tools.length + ' advertised' : 'Not recorded' }}</span></header>
                @if (v.snapshot.tools) {
                  <ul class="tools">
                    @for (t of v.snapshot.tools; track t.name) {
                      <li><code>{{ t.name }}</code><p class="small">{{ t.description || 'No description' }}</p></li>
                    } @empty { <li class="faint">This server advertises no tools.</li> }
                  </ul>
                } @else {
                  <div class="empty small"><p>Run <code>mcpledger scan --introspect</code> on a machine with this server to record its tools.
                    Without them, MCPLedger can't detect a server that changes its behaviour while keeping the same version.</p></div>
                }
              } @else {
                <header><h2>Files</h2><span class="faint small">{{ v.snapshot.files.length }} files</span></header>
                <ul class="tools">
                  @for (f of v.snapshot.files; track f.path) {
                    <li><code>{{ f.path }}</code> <span class="faint small">{{ f.size }} bytes</span>
                      @if (f.path.toLowerCase().endsWith('skill.md') && f.content) { <pre class="file">{{ f.content }}</pre> }</li>
                  }
                </ul>
              }
            </section>

            <section class="panel">
              <header><h2>Configuration</h2></header>
              <div class="body">
                @if (c.kind === 'mcp_server') {
                  <dl class="facts">
                    <dt>Transport</dt><dd>{{ v.snapshot.transport }}</dd>
                    @if (v.snapshot.url) { <dt>URL</dt><dd><code>{{ v.snapshot.url }}</code></dd> }
                    @if (v.snapshot.command) { <dt>Command</dt><dd><code>{{ v.snapshot.command }} {{ v.snapshot.args.join(' ') }}</code></dd> }
                    @if (v.snapshot.package) { <dt>Package</dt><dd>{{ v.snapshot.package.ecosystem }} · {{ v.snapshot.package.name }}@{{ v.snapshot.package.version || 'unpinned' }}</dd> }
                    <dt>Env vars</dt><dd>{{ v.snapshot.env_keys.length ? v.snapshot.env_keys.join(', ') : 'none' }}</dd>
                    @if (v.snapshot.header_keys.length) { <dt>Headers</dt><dd>{{ v.snapshot.header_keys.join(', ') }}</dd> }
                    @if (v.snapshot.inline_secret_keys.length) { <dt>Literal secrets</dt><dd class="bad">{{ v.snapshot.inline_secret_keys.join(', ') }} <span class="faint">(values never leave the machine)</span></dd> }
                  </dl>
                } @else {
                  <dl class="facts">
                    <dt>Name</dt><dd>{{ v.snapshot.name }}</dd>
                    <dt>Description</dt><dd>{{ v.snapshot.description || 'none' }}</dd>
                  </dl>
                }
              </div>
            </section>
          </div>
        }

        <section class="panel">
          <header><h2>Installed on</h2></header>
          @if (c.installs.length === 0) { <div class="empty"><p>Not currently installed on any reporting machine.</p></div> }
          @else {
            <div class="table-wrap"><table class="ledger">
              <thead><tr><th>Machine</th><th>App</th><th class="hide-sm">Where</th><th>Version</th></tr></thead>
              <tbody>
                @for (i of c.installs; track i.device_id + i.location) {
                  <tr>
                    <td><strong>{{ i.hostname }}</strong><div class="faint small">{{ i.owner }}</div></td>
                    <td>{{ i.client | client }}<div class="faint small">{{ i.scope }} · as "{{ i.local_name }}"</div></td>
                    <td class="hide-sm"><code class="small">{{ i.location.split('::')[0] }}</code></td>
                    <td><sg-print [hash]="fpOf(i.version_id)" [compact]="true" />
                      <div class="small" [class.ok]="i.trusted" [class.bad]="!i.trusted">{{ i.trusted ? 'approved' : (c.status === 'blocked' ? 'blocked' : 'not approved') }}</div></td>
                  </tr>
                }
              </tbody>
            </table></div>
          }
        </section>
      } @else if (!error()) { <p class="faint">Loading…</p> }
    </div>
  `,
  styles: `
    .crumb { display: inline-block; margin-bottom: 10px; }
    .title { gap: 14px; }
    .banner { border-radius: var(--r-md); padding: 12px 16px; margin-bottom: 20px; font-size: 14.5px; border-left: 4px solid; }
    .banner.blocked { background: var(--block-tint); border-color: var(--block); }
    .banner.drift { background: var(--drift-tint); border-color: var(--drift); }
    .banner.pending { background: var(--pending-tint); border-color: var(--pending); }
    .decide { border-color: var(--block); }
    tr.sel td { background: var(--gate-tint) !important; }
    td.actions { text-align: right; white-space: nowrap; }
    .ok { color: var(--ok); } .bad { color: var(--block); }
    .findings, .tools, .changes { list-style: none; margin: 0; padding: 0; }
    .findings li, .tools li { padding: 14px 20px; border-bottom: 1px solid var(--rule); }
    .findings li:last-child, .tools li:last-child { border-bottom: 0; }
    .findings p { margin-top: 4px; max-width: 80ch; }
    .evidence { display: block; margin-top: 8px; background: #f2f4f0; padding: 6px 10px; border-radius: var(--r-sm); white-space: pre-wrap; word-break: break-word; }
    .tools p { margin-top: 4px; color: var(--ink-soft); white-space: pre-wrap; max-width: 80ch; }
    .changes li { padding: 4px 0; }
    .split { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr); gap: 20px; margin-top: 20px; align-items: start; }
    .split .panel + .panel { margin-top: 0; }
    .split + .panel { margin-top: 20px; }
    pre.diff, pre.file { font-family: var(--mono); font-size: 12.5px; background: #f6f7f4; border: 1px solid var(--rule); border-radius: var(--r-sm);
      padding: 10px 12px; overflow-x: auto; white-space: pre-wrap; word-break: break-word; margin: 8px 0 0; max-height: 420px; overflow-y: auto; }
    pre.diff .add { background: #dff0e4; color: #1d5a35; display: block; }
    pre.diff .del { background: #f8e1de; color: #8e1b14; display: block; text-decoration: line-through; text-decoration-color: rgba(142,27,20,.35); }
    pre.diff .same { color: var(--ink-soft); display: block; }
    .change h3 { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .pill { font-size: 11.5px; font-weight: 700; padding: 1px 8px; border-radius: 999px; }
    .pill.added { background: var(--ok-tint); color: var(--ok); }
    .pill.removed { background: var(--block-tint); color: var(--block); }
    .pill.changed { background: var(--drift-tint); color: var(--drift); }
    @media (max-width: 980px) { .split { grid-template-columns: 1fr; } .split .panel + .panel { margin-top: 20px; } }
  `,
})
export class ComponentPage implements OnInit {
  api = inject(Api);
  id = input.required<string>();
  c = signal<ComponentDetail | null>(null);
  error = signal('');
  busy = signal(false);
  mode = signal<'' | 'block'>('');
  selectedId = signal<string | null>(null);
  note = '';

  selected = computed(() => {
    const c = this.c();
    if (!c) return null;
    return c.versions.find(v => v.id === this.selectedId())
      ?? c.versions.find(v => !v.trusted && v.installs > 0) ?? c.versions[0];
  });
  baseline = computed(() => {
    const c = this.c();
    if (!c) return null;
    const approved = c.versions.filter(v => v.approved);
    const sel = this.selected();
    return approved.find(a => a.launch_hash === sel?.launch_hash) ?? approved[0] ?? null;
  });

  configChanges = computed(() => {
    const a = this.baseline()?.snapshot, b = this.selected()?.snapshot;
    if (!a || !b || this.c()?.kind !== 'mcp_server') return [];
    const out: string[] = [];
    const cmd = (s: any) => [s.command, ...(s.args ?? [])].filter(Boolean).join(' ');
    if (cmd(a) !== cmd(b)) out.push(`Command: ${cmd(a) || 'none'}  to  ${cmd(b) || 'none'}`);
    if (a.url !== b.url) out.push(`URL: ${a.url ?? 'none'}  to  ${b.url ?? 'none'}`);
    const added = (b.env_keys ?? []).filter((k: string) => !(a.env_keys ?? []).includes(k));
    const removed = (a.env_keys ?? []).filter((k: string) => !(b.env_keys ?? []).includes(k));
    if (added.length) out.push(`New env vars: ${added.join(', ')}`);
    if (removed.length) out.push(`Removed env vars: ${removed.join(', ')}`);
    return out;
  });

  toolChanges = computed<ToolChange[]>(() => {
    const a: Tool[] | null = this.baseline()?.snapshot?.tools ?? null;
    const b: Tool[] | null = this.selected()?.snapshot?.tools ?? null;
    if (!a || !b) return [];
    const am = new Map(a.map(t => [t.name, t])), bm = new Map(b.map(t => [t.name, t]));
    const out: ToolChange[] = [];
    for (const [name, t] of bm) {
      const old = am.get(name);
      if (!old) out.push({ name, change: 'added', diff: lineDiff('', t.description).filter(l => l.text), schemaChanged: false });
      else {
        const schemaChanged = JSON.stringify(old.inputSchema) !== JSON.stringify(t.inputSchema);
        if (old.description !== t.description || schemaChanged)
          out.push({ name, change: 'changed', diff: old.description !== t.description ? lineDiff(old.description, t.description) : [], schemaChanged });
      }
    }
    for (const name of am.keys()) if (!bm.has(name)) out.push({ name, change: 'removed', diff: [], schemaChanged: false });
    return out;
  });

  fileChanges = computed<FileChange[]>(() => {
    if (this.c()?.kind !== 'skill') return [];
    const a: any[] = this.baseline()?.snapshot?.files ?? [], b: any[] = this.selected()?.snapshot?.files ?? [];
    const am = new Map(a.map(f => [f.path, f])), bm = new Map(b.map(f => [f.path, f]));
    const out: FileChange[] = [];
    for (const [path, f] of bm) {
      const old = am.get(path);
      if (!old) out.push({ path, change: 'added', diff: f.content != null ? lineDiff('', f.content).filter(l => l.text) : null });
      else if (old.sha256 !== f.sha256)
        out.push({ path, change: 'changed', diff: old.content != null && f.content != null ? lineDiff(old.content, f.content) : null });
    }
    for (const path of am.keys()) if (!bm.has(path)) out.push({ path, change: 'removed', diff: null });
    return out;
  });

  async ngOnInit() { await this.load(); }

  async load() {
    try { this.c.set(await this.api.get<ComponentDetail>(`/api/components/${this.id()}`)); }
    catch (e) { this.error.set(errorText(e)); }
  }

  fpOf(versionId: string) { return this.c()?.versions.find(v => v.id === versionId)?.fingerprint ?? ''; }

  private async act(path: string, body: any, done: string) {
    this.busy.set(true);
    try {
      this.c.set(await this.api.post<ComponentDetail>(`/api/components/${this.id()}/${path}`, body));
      this.api.notify(done);
      this.mode.set(''); this.note = '';
    } catch (e) { this.api.notify(errorText(e)); }
    finally { this.busy.set(false); }
  }

  approve(v: Version) { this.act('approve', { version_id: v.id }, 'Version approved'); }
  revoke(v: Version) { this.act('revoke-version', { version_id: v.id }, 'Approval revoked'); }
  block() { this.act('block', { note: this.note || null }, 'Blocked'); }
  unblock() { this.act('unblock', {}, 'Unblocked'); }
}
