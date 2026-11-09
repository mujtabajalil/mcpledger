import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Api, ComponentRow, Overview, errorText } from '../api';
import { AgoPipe, Avatar, ClientPipe, CLIENT_LABEL, Icon, SevBadge, StatusBadge } from '../shared';
import { EnrollSteps } from './enroll-steps';

const SEV_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
const TICKS = 14;

interface Kpi { label: string; icon: string; value: string; note: string; trend: 'up' | 'down' | 'flat'; tone: 'good' | 'bad' | 'neutral'; fill: number; color: string; link: string }
interface Bar { label: string; count: number; x: number; top: number; hi: boolean }

// Chart geometry (SVG user units).
const CH = { w: 720, h: 300, left: 46, right: 12, top: 70, base: 258, cap: 12 };

@Component({
  selector: 'sg-overview',
  imports: [FormsModule, RouterLink, AgoPipe, Avatar, ClientPipe, Icon, SevBadge, StatusBadge, EnrollSteps],
  template: `
    <div class="page">
      <div class="page-head">
        <div>
          <h1>Overview</h1>
          <p class="sub">{{ data() ? headline() : 'Know every MCP server and agent skill your team runs.' }}</p>
        </div>
        <div class="tools">
          <a routerLink="/alerts" class="bell" [class.has]="(data()?.open_alerts ?? 0) > 0" aria-label="Alerts"><sg-icon name="alerts" /></a>
          <form class="search" (ngSubmit)="search()" role="search">
            <input type="search" name="q" [(ngModel)]="q" placeholder="Search servers and skills" aria-label="Search inventory">
          </form>
          <a routerLink="/settings" fragment="enroll" class="btn primary"><sg-icon name="plus" [size]="16" [stroke]="2" />Enroll machine</a>
        </div>
      </div>

      @if (error()) { <div class="error-box">{{ error() }}</div> }
      @if (data(); as d) {
        @if (d.devices === 0) {
          <section class="panel">
            <header><h2><sg-icon name="devices" [size]="16" />Enroll your first machine</h2></header>
            <div class="body">
              <p class="muted intro">MCPLedger learns what's installed from the <code>mcpledger</code> CLI. Run these on any developer laptop
                (yours is a good start). It takes about a minute and changes nothing on the machine.</p>
              <sg-enroll-steps />
            </div>
          </section>
        } @else {
          <div class="kpis">
            @for (k of kpis(); track k.label) {
              <a class="panel kpi" [routerLink]="k.link">
                <header><h2>{{ k.label }}</h2><span class="spacer"></span><sg-icon [name]="k.icon" [size]="17" /></header>
                <div class="inner">
                  <div>
                    <div class="num-xl">{{ k.value }}</div>
                    <p class="delta" [class]="'delta ' + k.tone">
                      @if (k.trend !== 'flat') { <sg-icon [name]="k.trend === 'up' ? 'arrow-up' : 'arrow-down'" [size]="14" [stroke]="2" /> }
                      {{ k.note }}</p>
                  </div>
                  <div class="meter" role="img" [attr.aria-label]="k.label + ': ' + k.value">
                    @for (t of ticks; track $index) {
                      <i [style.height.%]="30 + t * 5.4" [style.background]="$index < k.fill ? k.color : null"></i>
                    }
                  </div>
                </div>
              </a>
            }
          </div>

          <div class="mid">
            <section class="panel chart">
              <header>
                <h2><sg-icon name="chart" [size]="16" />Components by AI tool</h2><span class="spacer"></span>
                <span class="faint small">{{ bars().length }} {{ bars().length === 1 ? 'tool' : 'tools' }} · {{ d.installs }} installs</span>
              </header>
              <div class="body">
                <div class="row lead">
                  <span class="big">{{ d.components }}</span>
                  <span class="chip">{{ d.mcp_servers }} MCP {{ d.mcp_servers === 1 ? 'server' : 'servers' }}</span>
                  <span class="chip amber">{{ d.skills }} {{ d.skills === 1 ? 'skill' : 'skills' }}</span>
                  <span class="muted">across {{ d.devices }} {{ d.devices === 1 ? 'machine' : 'machines' }}</span>
                </div>
                <svg [attr.viewBox]="'0 0 ' + ch.w + ' ' + ch.h" class="bars" role="img" [attr.aria-label]="chartLabel()">
                  <defs>
                    <linearGradient id="hiL" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#a9b2f5"/><stop offset="1" stop-color="#4350d8"/></linearGradient>
                    <linearGradient id="hiR" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8a95ee"/><stop offset="1" stop-color="#3540c4"/></linearGradient>
                    <linearGradient id="loL" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f0f0ee"/><stop offset="1" stop-color="#e9e9e7"/></linearGradient>
                    <linearGradient id="loR" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e8e8e6"/><stop offset="1" stop-color="#e0e0de"/></linearGradient>
                  </defs>
                  @for (t of yTicks(); track t.v) {
                    <line [attr.x1]="ch.left" [attr.x2]="ch.w - ch.right" [attr.y1]="t.y" [attr.y2]="t.y" class="grid" />
                    <text [attr.x]="ch.left - 12" [attr.y]="t.y + 4" class="ylab">{{ t.v }}</text>
                  }
                  @for (b of bars(); track b.label) {
                    <g [class.hi]="b.hi">
                      <path [attr.d]="face(b, 'l')" [attr.fill]="b.hi ? 'url(#hiL)' : 'url(#loL)'" />
                      <path [attr.d]="face(b, 'r')" [attr.fill]="b.hi ? 'url(#hiR)' : 'url(#loR)'" />
                      <path [attr.d]="face(b, 't')" [attr.fill]="b.hi ? '#c9cff9' : '#f6f6f5'" class="top" />
                      <text [attr.x]="b.x" [attr.y]="ch.base + 32" class="xlab">{{ b.label }}</text>
                      @if (b.hi) {
                        <g [attr.transform]="'translate(' + b.x + ' ' + (b.top - ch.cap - 14) + ')'">
                          <rect x="-34" y="-30" width="68" height="28" rx="8" class="tip" />
                          <text y="-11" class="tiptext">{{ b.count }} {{ b.count === 1 ? 'item' : 'items' }}</text>
                          <path d="M-5 -2 0 3 5 -2z" class="tip" />
                        </g>
                      }
                      <title>{{ b.label }}: {{ b.count }}</title>
                    </g>
                  }
                </svg>
              </div>
            </section>

            <section class="panel risk">
              <header>
                <h2><sg-icon name="shield" [size]="16" />Risk to review</h2><span class="spacer"></span>
                <span class="chip plain">{{ d.open_alerts }} open {{ d.open_alerts === 1 ? 'alert' : 'alerts' }}</span>
              </header>
              <div class="body">
                <div class="big">{{ d.risky.length }}</div>
                <p class="muted">High or critical findings that aren't blocked yet.</p>
                <ul class="risky">
                  @for (r of d.risky; track r.id) {
                    <li>
                      <div><a [routerLink]="['/inventory', r.id]">{{ r.name }}</a>
                        <span class="faint small">{{ r.kind === 'skill' ? 'Skill' : 'MCP server' }} · {{ r.installs }} {{ r.installs === 1 ? 'install' : 'installs' }}</span></div>
                      <sg-sev [value]="r.max_severity" />
                    </li>
                  } @empty {
                    <li class="clear"><sg-icon name="check" [size]="18" />Nothing high-risk is running unblocked.</li>
                  }
                </ul>
                <a routerLink="/alerts" class="cta">Review open alerts <sg-icon name="arrow-right" [size]="16" /></a>
              </div>
            </section>
          </div>

          <div class="low">
            <section class="panel">
              <header><h2><sg-icon name="inbox" [size]="16" />Waiting on a decision</h2><span class="spacer"></span>
                <a routerLink="/inventory" class="small">View all <sg-icon name="arrow-right" [size]="14" /></a></header>
              @if (queue().length === 0) {
                <div class="empty"><h3>Nothing waiting</h3><p>New servers, skills and changes will show up here.</p></div>
              } @else {
                <div class="table-wrap"><table class="ledger">
                  <thead><tr><th>Component</th><th>Status</th><th>Risk</th><th class="num hide-sm">Machines</th><th class="hide-sm">Last seen</th><th aria-label="Open"></th></tr></thead>
                  <tbody>
                    @for (c of queue(); track c.id) {
                      <tr class="clickable" (click)="open(c.id)">
                        <td><div class="who"><sg-avatar [name]="c.name" [kind]="c.kind" />
                          <div><a [routerLink]="['/inventory', c.id]" (click)="$event.stopPropagation()"><strong>{{ c.name }}</strong></a>
                          <div class="faint small">{{ c.kind === 'skill' ? 'Skill' : 'MCP server' }} in
                            @for (cl of c.clients; track cl; let last = $last) { {{ cl | client }}{{ last ? '' : ', ' }} }</div></div></div></td>
                        <td><sg-status [value]="c.status" /></td>
                        <td><sg-sev [value]="c.max_severity" /></td>
                        <td class="num hide-sm">{{ c.devices }}</td>
                        <td class="hide-sm faint small nowrap">{{ c.last_seen_at | ago }}</td>
                        <td class="go"><sg-icon name="chevron" [size]="16" /></td>
                      </tr>
                    }
                  </tbody>
                </table></div>
              }
            </section>

            <section class="panel">
              <header><h2><sg-icon name="activity" [size]="16" />Latest activity</h2><span class="spacer"></span>
                <a routerLink="/alerts" class="small">All alerts <sg-icon name="arrow-right" [size]="14" /></a></header>
              <ol class="feed">
                @for (e of d.recent_events; track e.id) {
                  <li [class]="'s-' + e.severity">
                    @if (e.component_id) { <a [routerLink]="['/inventory', e.component_id]">{{ e.title }}</a> } @else { <span>{{ e.title }}</span> }
                    <span class="faint small">{{ e.created_at | ago }}</span>
                  </li>
                } @empty { <li class="faint">No activity yet.</li> }
              </ol>
            </section>
          </div>
        }
      } @else if (!error()) { <p class="faint">Loading…</p> }
    </div>
  `,
  styles: `
    .tools { display: flex; align-items: center; gap: 10px; }
    .search input { width: 280px; }
    .bell { position: relative; width: 40px; height: 40px; display: grid; place-items: center; border-radius: 10px; color: var(--ink-soft); }
    .bell:hover { background: var(--well); color: var(--ink); }
    .bell.has::after { content: ""; position: absolute; top: 9px; right: 10px; width: 7px; height: 7px; border-radius: 50%; background: var(--block); box-shadow: 0 0 0 2px var(--canvas); }
    .intro { margin-bottom: 22px; max-width: 72ch; }

    .kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; margin-bottom: 20px; }
    .kpis .panel + .panel { margin-top: 0; }
    .kpi { text-decoration: none; color: inherit; transition: border-color .15s, box-shadow .15s; }
    .kpi:hover { border-color: var(--rule-strong); box-shadow: 0 4px 16px rgba(24,24,27,.06); color: inherit; }
    .kpi > header { color: var(--ink-faint); }
    .kpi .inner { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; padding: 26px 16px 16px; min-height: 128px; }
    .delta { display: flex; align-items: center; gap: 4px; margin-top: 10px; font-size: 13px; color: var(--ink-soft); white-space: nowrap; }
    .delta.good { color: var(--ok); } .delta.bad { color: var(--block); }
    .meter { display: flex; align-items: flex-end; gap: 2px; height: 44px; flex: none; }
    .meter i { display: block; width: 3px; border-radius: 2px; background: #e8e8e6; }

    .mid { display: grid; grid-template-columns: minmax(0, 1.75fr) minmax(0, 1fr); gap: 20px; align-items: stretch; }
    .mid .panel + .panel, .low .panel + .panel { margin-top: 0; }
    .mid .panel { display: flex; flex-direction: column; }
    .mid .panel > .body { flex: 1; }
    .lead { gap: 10px; margin-bottom: 6px; }
    .big { font-size: 26px; font-weight: 600; letter-spacing: -0.03em; font-variant-numeric: tabular-nums; }
    .chip { font-size: 12.5px; font-weight: 500; color: #3f48b8; background: var(--gate-tint); border-radius: 7px; padding: 3px 8px; }
    .chip.amber { color: #9a5208; background: var(--drift-tint); }
    .chip.plain { color: var(--ink); background: var(--paper); border: 1px solid var(--rule-strong); box-shadow: var(--shadow-xs); }
    .bars { width: 100%; height: auto; display: block; margin-top: 4px; }
    .bars .grid { stroke: var(--rule); stroke-width: 1; }
    .bars .ylab { font-size: 11.5px; fill: var(--ink-faint); text-anchor: end; font-variant-numeric: tabular-nums; }
    .bars .xlab { font-size: 13px; fill: var(--ink-soft); text-anchor: middle; }
    .bars .top { stroke: rgba(255,255,255,.9); stroke-width: 1; }
    .bars .tip { fill: #18181b; }
    .bars .tiptext { fill: #fff; font-size: 12.5px; font-weight: 600; text-anchor: middle; }

    .risk .body { display: flex; flex-direction: column; }
    .risk .big { font-size: 26px; }
    .risky { list-style: none; margin: 16px 0; padding: 0; border-top: 1px solid var(--rule); flex: 1; }
    .risky li { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 13px 0; border-bottom: 1px solid var(--rule); }
    .risky li:last-child { border-bottom: 0; }
    .risky li > div { display: flex; flex-direction: column; min-width: 0; }
    .risky a { font-weight: 500; text-decoration: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .risky .clear { color: var(--ok); justify-content: flex-start; gap: 8px; }
    .cta { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border: 1px solid var(--rule-strong); border-radius: 10px;
      background: var(--well); color: var(--ink-soft); text-decoration: none; font-size: 14px; }
    .cta:hover { background: var(--paper); color: var(--ink); }

    .low { display: grid; grid-template-columns: minmax(0, 1.75fr) minmax(0, 1fr); gap: 20px; margin-top: 20px; align-items: start; }
    .who { display: flex; align-items: center; gap: 12px; }
    td.go { color: var(--ink-faint); width: 1%; }
    .nowrap { white-space: nowrap; }
    .feed { list-style: none; margin: 0; padding: 8px 0; }
    .feed li { padding: 10px 20px 10px 34px; position: relative; display: flex; flex-direction: column; font-size: 14px; }
    .feed li::before { content: ""; position: absolute; left: 18px; top: 17px; width: 7px; height: 7px; border-radius: 50%; background: var(--sev-info); }
    .feed li.s-critical::before, .feed li.s-high::before { background: var(--block); }
    .feed li.s-medium::before { background: var(--drift); }
    .feed li.s-low::before { background: var(--sev-low); }
    .feed a { color: var(--ink); font-weight: 500; text-decoration: none; }
    .feed a:hover { color: var(--gate); }
    header a.small { display: inline-flex; align-items: center; gap: 4px; }

    @media (max-width: 1180px) { .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
    @media (max-width: 980px) { .mid, .low { grid-template-columns: minmax(0, 1fr); } .search input { width: 200px; } }
    @media (max-width: 560px) { .kpis { grid-template-columns: minmax(0, 1fr); } .tools { width: 100%; } .search { flex: 1; } .search input { width: 100%; } }
  `,
})
export class OverviewPage implements OnInit {
  private api = inject(Api);
  private router = inject(Router);
  data = signal<Overview | null>(null);
  rows = signal<ComponentRow[]>([]);
  error = signal('');
  q = '';
  ch = CH;
  ticks = Array.from({ length: TICKS }, (_, i) => i);

  queue = computed(() =>
    this.rows()
      .filter(r => r.status === 'pending' || r.status === 'drift')
      .sort((a, b) => (a.status === 'drift' ? 0 : 1) - (b.status === 'drift' ? 0 : 1)
        || (SEV_ORDER[a.max_severity ?? 'info'] ?? 5) - (SEV_ORDER[b.max_severity ?? 'info'] ?? 5)
        || b.devices - a.devices)
      .slice(0, 8));

  headline = computed(() => {
    const d = this.data();
    if (!d) return '';
    const p = d.status_counts.pending, ch = d.status_counts.drift, b = d.status_counts.blocked;
    const parts: string[] = [];
    if (ch) parts.push(`${ch} changed since approval`);
    if (p) parts.push(`${p} ${p === 1 ? 'needs' : 'need'} review`);
    const stale = d.stale_devices ? ` ${d.stale_devices} ${d.stale_devices === 1 ? "machine hasn't" : "machines haven't"} reported in a week.` : '';
    if (!parts.length) return (b ? `Everything else is approved. ${b} blocked.` : 'Everything installed is approved.') + stale;
    const s = parts.join(', ');
    return s.charAt(0).toUpperCase() + s.slice(1) + '.' + stale;
  });

  kpis = computed<Kpi[]>(() => {
    const d = this.data();
    if (!d) return [];
    const total = Math.max(d.components, 1);
    const frac = (n: number, of: number) => Math.round((n / Math.max(of, 1)) * TICKS);
    const sc = d.status_counts;
    const approvedPct = Math.round((sc.approved / total) * 100);
    const fresh = d.devices - d.stale_devices;
    return [
      { label: 'Needs review', icon: 'inbox', value: String(sc.pending), link: '/inventory',
        note: sc.pending ? `of ${d.components} components` : 'nothing new to review', trend: 'flat', tone: 'neutral',
        fill: frac(sc.pending, total), color: '#71717a' },
      { label: 'Changed since approval', icon: 'compare', value: String(sc.drift), link: '/inventory',
        note: sc.drift ? 'need re-approval' : 'no drift', trend: sc.drift ? 'up' : 'flat', tone: sc.drift ? 'bad' : 'good',
        fill: frac(sc.drift, total), color: '#e0912f' },
      { label: 'Approved', icon: 'check', value: `${approvedPct}%`, link: '/inventory',
        note: `${sc.approved} of ${d.components} pinned`, trend: approvedPct >= 50 ? 'up' : 'down', tone: approvedPct >= 50 ? 'good' : 'bad',
        fill: frac(sc.approved, total), color: '#2f9e5b' },
      { label: 'Machines reporting', icon: 'devices', value: String(d.devices), link: '/devices',
        note: d.stale_devices ? `${d.stale_devices} quiet for 7+ days` : 'all reported this week',
        trend: d.stale_devices ? 'down' : 'up', tone: d.stale_devices ? 'bad' : 'good',
        fill: frac(fresh, d.devices), color: '#5b67de' },
    ];
  });

  private clientCounts = computed(() => {
    const counts = new Map<string, number>();
    for (const r of this.rows()) for (const c of new Set(r.clients)) counts.set(c, (counts.get(c) ?? 0) + 1);
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);
  });

  private yMax = computed(() => {
    const m = Math.max(1, ...this.clientCounts().map(([, n]) => n));
    const step = Math.max(1, Math.ceil(m / 4));
    return step * 4;
  });

  yTicks = computed(() => {
    const max = this.yMax();
    return [0, 1, 2, 3, 4].map(i => {
      const v = (max / 4) * i;
      return { v, y: CH.base - ((CH.base - CH.top) * v) / max };
    });
  });

  bars = computed<Bar[]>(() => {
    const entries = this.clientCounts();
    const max = this.yMax();
    const slot = (CH.w - CH.left - CH.right) / Math.max(entries.length, 1);
    const top = Math.max(...entries.map(([, n]) => n));
    let marked = false;
    return entries.map(([client, n], i) => {
      const hi = !marked && n === top;
      if (hi) marked = true;
      return { label: CLIENT_LABEL[client] ?? client, count: n, x: CH.left + slot * (i + 0.5),
        top: CH.base - ((CH.base - CH.top) * n) / max, hi };
    });
  });

  chartLabel = computed(() => 'Components by AI tool: ' + this.bars().map(b => `${b.label} ${b.count}`).join(', '));

  /** One face of an isometric column: left, right or the diamond top. */
  face(b: Bar, side: 'l' | 'r' | 't'): string {
    const slot = (CH.w - CH.left - CH.right) / Math.max(this.bars().length, 1);
    const hw = Math.min(46, slot * 0.36), c = CH.cap, x = b.x, t = b.top, base = CH.base;
    if (side === 'l') return `M${x - hw} ${t} L${x} ${t + c} L${x} ${base} L${x - hw} ${base - c} Z`;
    if (side === 'r') return `M${x} ${t + c} L${x + hw} ${t} L${x + hw} ${base - c} L${x} ${base} Z`;
    return `M${x - hw} ${t} L${x} ${t - c} L${x + hw} ${t} L${x} ${t + c} Z`;
  }

  async ngOnInit() {
    try {
      const [d, rows] = await Promise.all([
        this.api.get<Overview>('/api/org/overview'),
        this.api.get<ComponentRow[]>('/api/components'),
      ]);
      this.data.set(d); this.rows.set(rows);
    } catch (e) { this.error.set(errorText(e)); }
  }

  search() { this.router.navigate(['/inventory'], { queryParams: { q: this.q.trim() || null } }); }
  open(id: string) { this.router.navigate(['/inventory', id]); }
}
