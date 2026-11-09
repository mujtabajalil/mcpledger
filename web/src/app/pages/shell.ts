import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { Api } from '../api';

@Component({
  selector: 'sg-shell',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <div class="layout">
      <aside>
        <a routerLink="/overview" class="brand" aria-label="MCPLedger overview">
          <svg viewBox="0 0 32 32" width="26" height="26" aria-hidden="true"><path d="M8 25V11l8-5 8 5v14" fill="none" stroke="#eef0ec" stroke-width="2.6" stroke-linejoin="round"/><path d="M12.5 25v-8h7v8" fill="none" stroke="#7fc8b8" stroke-width="2.6"/></svg>
          <span>MCPLedger</span>
        </a>

        @if (api.me()?.orgs?.length! > 1) {
          <select class="org-switch" [value]="api.org()?.id" (change)="api.switchOrg($any($event.target).value)" aria-label="Organization">
            @for (o of api.me()!.orgs; track o.id) { <option [value]="o.id">{{ o.name }}</option> }
          </select>
        } @else {
          <div class="org-name">{{ api.org()?.name }}</div>
        }

        <nav>
          <a routerLink="/overview" routerLinkActive="on">Overview</a>
          <a routerLink="/inventory" routerLinkActive="on">Inventory</a>
          <a routerLink="/alerts" routerLinkActive="on">Alerts
            @if (openAlerts() > 0) { <b class="count">{{ openAlerts() }}</b> }
          </a>
          <a routerLink="/devices" routerLinkActive="on">Devices</a>
          <a routerLink="/audit" routerLinkActive="on">Audit log</a>
          <a routerLink="/settings" routerLinkActive="on">Settings</a>
        </nav>

        <div class="mode" [class.enforce]="api.org()?.policy_mode === 'enforce'">
          @if (api.org()?.policy_mode === 'enforce') {
            <strong>Enforcing</strong><span>Blocked items fail <code>mcpledger check</code></span>
          } @else {
            <strong>Monitoring</strong><span>Nothing is blocked yet</span>
          }
        </div>

        <div class="me">
          <span class="email" [title]="api.me()?.user?.email">{{ api.me()?.user?.email }}</span>
          <button class="link" (click)="api.logout()">Sign out</button>
        </div>
      </aside>
      <main><router-outlet /></main>
    </div>
  `,
  styles: `
    .layout { display: grid; grid-template-columns: 232px 1fr; min-height: 100vh; }
    aside { background: var(--petrol); color: #d8e6e3; display: flex; flex-direction: column; padding: 20px 14px; position: sticky; top: 0; height: 100vh; }
    .brand { display: flex; align-items: center; gap: 10px; color: #fff; text-decoration: none; font-weight: 800; font-size: 18px; padding: 0 8px; letter-spacing: -0.02em; }
    .org-name, .org-switch { margin: 18px 8px 14px; font-size: 13px; color: #a9c2bd; }
    .org-switch { width: auto; background: var(--petrol-2); color: #fff; border-color: #34606b; padding: 6px 8px; }
    nav { display: flex; flex-direction: column; gap: 2px; }
    nav a { color: #d8e6e3; text-decoration: none; padding: 8px 10px; border-radius: 6px; font-weight: 500; display: flex; align-items: center; }
    nav a:hover { background: var(--petrol-2); color: #fff; }
    nav a.on { background: #eef0ec; color: var(--petrol); font-weight: 700; }
    .count { margin-left: auto; background: var(--drift); color: #fff; font-size: 11.5px; border-radius: 999px; padding: 0 7px; line-height: 18px; }
    nav a.on .count { background: var(--block); }
    .mode { margin-top: auto; border: 1px solid #34606b; border-radius: 8px; padding: 10px 12px; font-size: 12.5px; display: flex; flex-direction: column; gap: 2px; }
    .mode strong { color: #fff; font-size: 13px; }
    .mode.enforce { border-color: #7fc8b8; }
    .mode code { color: #bfe3da; }
    .me { margin-top: 14px; padding: 0 8px; display: flex; align-items: center; gap: 8px; font-size: 12.5px; }
    .email { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; color: #a9c2bd; }
    .link { background: none; border: 0; color: #fff; font: inherit; font-weight: 600; cursor: pointer; padding: 0; text-decoration: underline; text-underline-offset: 2px; }
    main { min-width: 0; }
    @media (max-width: 860px) {
      .layout { grid-template-columns: 1fr; }
      aside { position: static; height: auto; flex-direction: row; flex-wrap: wrap; align-items: center; gap: 8px; padding: 12px 16px; }
      .org-name, .org-switch, .mode { display: none; }
      nav { flex-direction: row; overflow-x: auto; width: 100%; order: 3; }
      nav a { white-space: nowrap; padding: 6px 10px; }
      .me { margin: 0 0 0 auto; }
      .email { display: none; }
    }
  `,
})
export class Shell implements OnInit {
  api = inject(Api);
  openAlerts = signal(0);

  async ngOnInit() {
    try {
      const ev = await this.api.get<any[]>('/api/events', { unacked: true, limit: 200 });
      this.openAlerts.set(ev.filter(e => ['medium', 'high', 'critical'].includes(e.severity)).length);
    } catch { /* non-critical */ }
  }
}
