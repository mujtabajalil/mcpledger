import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { Api } from '../api';
import { Icon } from '../shared';

@Component({
  selector: 'sg-shell',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, Icon],
  template: `
    <div class="layout">
      <aside>
        <a routerLink="/overview" class="brand" aria-label="MCPLedger overview">
          <span class="mark"><svg viewBox="0 0 32 32" width="22" height="22" aria-hidden="true"><path d="M8 25V11l8-5 8 5v14" fill="none" stroke="#fff" stroke-width="2.8" stroke-linejoin="round"/><path d="M12.5 25v-8h7v8" fill="none" stroke="#9ad8ca" stroke-width="2.8"/></svg></span>
          <span class="word">MCPLedger</span>
        </a>

        @if (api.me()?.orgs?.length! > 1) {
          <select class="org-switch" [value]="api.org()?.id" (change)="api.switchOrg($any($event.target).value)" aria-label="Organization">
            @for (o of api.me()!.orgs; track o.id) { <option [value]="o.id">{{ o.name }}</option> }
          </select>
        } @else {
          <div class="org-name">{{ api.org()?.name }}</div>
        }

        <nav aria-label="Main">
          <p class="group">Monitor</p>
          <a routerLink="/overview" routerLinkActive="on"><sg-icon name="overview" />Overview</a>
          <a routerLink="/inventory" routerLinkActive="on"><sg-icon name="inventory" />Inventory</a>
          <a routerLink="/alerts" routerLinkActive="on"><sg-icon name="alerts" />Alerts
            @if (openAlerts() > 0) { <b class="count" [attr.aria-label]="openAlerts() + ' open'">{{ openAlerts() }}</b> }
          </a>
          <a routerLink="/devices" routerLinkActive="on"><sg-icon name="devices" />Devices
            <span class="meta">{{ api.org()?.device_count }}</span></a>

          <p class="group">Govern</p>
          <a routerLink="/audit" routerLinkActive="on"><sg-icon name="audit" />Audit log</a>
          <a routerLink="/settings" routerLinkActive="on"><sg-icon name="settings" />Settings</a>
          <a href="https://github.com/mujtabajalil/mcpledger#readme" target="_blank" rel="noopener"><sg-icon name="docs" />Docs
            <sg-icon class="meta" name="external" [size]="14" /></a>
        </nav>

        <div class="mode" [class.enforce]="enforcing()">
          <span class="dot"></span>
          <div>
            <strong>{{ enforcing() ? 'Enforcing' : 'Monitoring' }}</strong>
            <span>@if (enforcing()) { Blocked items fail <code>check</code> } @else { Nothing is blocked yet }</span>
          </div>
        </div>

        <div class="me">
          <span class="initials" aria-hidden="true">{{ initials() }}</span>
          <div class="who">
            <strong>{{ displayName() }}</strong>
            <span [title]="api.me()?.user?.email">{{ api.me()?.user?.email }}</span>
          </div>
          <button class="out" (click)="api.logout()" title="Sign out" aria-label="Sign out"><sg-icon name="logout" [size]="17" /></button>
        </div>
      </aside>
      <main><router-outlet /></main>
    </div>
  `,
  styles: `
    .layout { display: grid; grid-template-columns: 260px minmax(0, 1fr); min-height: 100vh; }
    aside { display: flex; flex-direction: column; padding: 22px 14px 14px 16px; position: sticky; top: 0; height: 100vh; overflow-y: auto; }
    .brand { display: flex; align-items: center; gap: 11px; color: var(--ink); text-decoration: none; padding: 0 6px; }
    .mark { width: 36px; height: 36px; border-radius: 10px; background: #18181b; display: grid; place-items: center;
      box-shadow: inset 0 1px 0 rgba(255,255,255,.12), 0 1px 2px rgba(0,0,0,.2); }
    .word { font-weight: 700; font-size: 19px; letter-spacing: -0.03em; }
    .org-name, .org-switch { margin: 16px 6px 0; font-size: 13px; color: var(--ink-soft); padding-bottom: 16px; border-bottom: 1px solid var(--rule-strong); }
    .org-switch { width: auto; padding: 6px 10px; border-bottom: 1px solid var(--rule-strong); margin-bottom: 0; }
    nav { display: flex; flex-direction: column; gap: 2px; margin-top: 6px; }
    .group { font-size: 11.5px; font-weight: 500; text-transform: uppercase; letter-spacing: .06em; color: var(--ink-faint); margin: 18px 10px 6px; }
    nav a { color: #3f3f46; text-decoration: none; padding: 8px 10px; border-radius: 10px; font-size: 15px; font-weight: 450;
      display: flex; align-items: center; gap: 11px; border: 1px solid transparent; transition: background .12s, color .12s; }
    nav a sg-icon { color: #71717a; }
    nav a:hover { background: rgba(24, 24, 27, .045); color: var(--ink); }
    nav a.on { background: var(--paper); color: var(--ink); font-weight: 500; border-color: var(--rule-strong); box-shadow: var(--shadow-sm); }
    nav a.on sg-icon { color: var(--ink); }
    .count { margin-left: auto; background: var(--block); color: #fff; font-size: 11.5px; font-weight: 600; border-radius: 999px; min-width: 20px; text-align: center; padding: 0 6px; line-height: 19px; }
    .meta { margin-left: auto; color: var(--ink-faint); font-size: 13.5px; font-variant-numeric: tabular-nums; }
    .mode { margin-top: auto; display: flex; gap: 10px; align-items: flex-start; padding: 12px; border-radius: 12px; font-size: 12.5px; color: var(--ink-soft); }
    .mode strong { display: block; color: var(--ink); font-size: 13px; font-weight: 600; }
    .mode .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--ink-faint); margin-top: 5px; box-shadow: 0 0 0 3px rgba(138,138,146,.18); flex: none; }
    .mode.enforce .dot { background: var(--ok); box-shadow: 0 0 0 3px rgba(23,128,61,.18); }
    .me { margin-top: 10px; display: flex; align-items: center; gap: 10px; padding: 10px; background: var(--paper); border: 1px solid var(--rule-strong); border-radius: 14px; box-shadow: var(--shadow-sm); }
    .initials { width: 36px; height: 36px; border-radius: 10px; background: linear-gradient(135deg, #e0e3fb, #f6e7d4); color: #3f3f46; display: grid; place-items: center; font-size: 13px; font-weight: 600; flex: none; }
    .who { min-width: 0; flex: 1; display: flex; flex-direction: column; line-height: 1.25; }
    .who strong { font-size: 14px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .who span { font-size: 12.5px; color: var(--ink-faint); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .out { border: 0; background: transparent; color: var(--ink-faint); padding: 6px; border-radius: 8px; cursor: pointer; display: grid; }
    .out:hover { background: var(--well); color: var(--ink); }
    main { min-width: 0; margin: 10px 10px 10px 0; background: var(--canvas); border: 1px solid var(--rule-strong); border-radius: 22px;
      box-shadow: 0 1px 3px rgba(24,24,27,.04), 0 8px 24px rgba(24,24,27,.04); min-height: calc(100vh - 20px); }
    @media (max-width: 860px) {
      .layout { grid-template-columns: minmax(0, 1fr); }
      aside { position: static; height: auto; flex-direction: row; flex-wrap: wrap; align-items: center; gap: 8px; padding: 12px 16px; }
      .org-name, .org-switch, .mode, .group, .who, .meta { display: none; }
      nav { flex-direction: row; overflow-x: auto; width: 100%; order: 3; margin: 0; }
      nav a { white-space: nowrap; padding: 6px 10px; }
      .me { margin: 0 0 0 auto; padding: 4px; border-radius: 12px; }
      .initials { width: 30px; height: 30px; }
      main { margin: 0 8px 8px; min-height: auto; border-radius: 18px; }
    }
  `,
})
export class Shell implements OnInit {
  api = inject(Api);
  openAlerts = signal(0);
  enforcing = computed(() => this.api.org()?.policy_mode === 'enforce');
  displayName = computed(() => {
    const u = this.api.me()?.user;
    if (!u) return '';
    if (u.name) return u.name;
    const local = u.email.split('@')[0];
    return local.charAt(0).toUpperCase() + local.slice(1);
  });
  initials = computed(() => this.displayName().split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase());

  async ngOnInit() {
    try {
      const ev = await this.api.get<any[]>('/api/events', { unacked: true, limit: 200 });
      this.openAlerts.set(ev.filter(e => ['medium', 'high', 'critical'].includes(e.severity)).length);
    } catch { /* non-critical */ }
  }
}
