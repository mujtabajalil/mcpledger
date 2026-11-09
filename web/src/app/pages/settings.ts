import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Api, Members, Severity, errorText } from '../api';
import { EnrollSteps } from './enroll-steps';

declare global { interface Window { Paddle?: any } }

@Component({
  selector: 'sg-settings',
  imports: [FormsModule, EnrollSteps],
  template: `
    <div class="page">
      <div class="page-head"><div><h1>Settings</h1><p class="sub">{{ api.org()?.name }}</p></div></div>

      <nav class="jump">
        <a href="#policy">Policy</a><a href="#enroll">Enroll machines</a><a href="#alerts">Alerts</a><a href="#members">Members</a><a href="#billing">{{ api.org()?.edition?.mode === 'self_hosted' ? 'Edition' : 'Plan' }}</a>
      </nav>

      @if (api.org(); as o) {
        <section class="panel" id="policy">
          <header><h2>Policy</h2></header>
          <div class="body stack">
            <div>
              <h3>Mode</h3>
              <p class="muted small">Start in monitor mode while you review what your team already has. Switch to enforce once the inventory is approved.</p>
              <div class="choice">
                <label [class.on]="o.policy_mode === 'monitor'"><input type="radio" name="mode" [checked]="o.policy_mode === 'monitor'" (change)="setPolicy({ policy_mode: 'monitor' })" [disabled]="!api.isAdmin()">
                  <strong>Monitor</strong><span>Report everything. <code>mcpledger check</code> only fails on items you've blocked.</span></label>
                <label [class.on]="o.policy_mode === 'enforce'"><input type="radio" name="mode" [checked]="o.policy_mode === 'enforce'" (change)="setPolicy({ policy_mode: 'enforce' })" [disabled]="!api.isAdmin()">
                  <strong>Enforce</strong><span>Anything changed since approval fails the check too.</span></label>
              </div>
            </div>
            @if (o.policy_mode === 'enforce') {
              <div>
                <h3>Components nobody has reviewed yet</h3>
                <div class="segmented" style="margin-top:8px">
                  <button [class.on]="o.default_action === 'warn'" (click)="setPolicy({ default_action: 'warn' })" [disabled]="!api.isAdmin()">Warn</button>
                  <button [class.on]="o.default_action === 'block'" (click)="setPolicy({ default_action: 'block' })" [disabled]="!api.isAdmin()">Block until approved</button>
                </div>
                <p class="muted small" style="margin-top:6px">"Block until approved" is a strict allowlist: developers can only use what an admin approved.</p>
              </div>
            }
            @if (api.isAdmin()) {
              <label class="field" style="max-width:420px"><span>Organization name</span>
                <div class="row"><input type="text" [(ngModel)]="orgName"><button class="btn" (click)="setPolicy({ name: orgName })" [disabled]="orgName === o.name || !orgName.trim()">Rename</button></div></label>
            }
          </div>
        </section>

        <section class="panel" id="enroll">
          <header><h2>Enroll machines</h2><span class="spacer"></span>
            @if (api.isAdmin()) { <button class="btn small" (click)="rotate()">Rotate token</button> }</header>
          <div class="body">
            <sg-enroll-steps />
            <p class="faint small" style="margin-top:18px">For CI, set <code>MCPLEDGER_SERVER</code> and <code>MCPLEDGER_DEVICE_KEY</code> (from <code>~/.mcpledger/config.json</code> after enrolling a CI identity) and run <code>mcpledger check --project .</code>.</p>
          </div>
        </section>

        <section class="panel" id="alerts">
          <header><h2>Alerts</h2></header>
          <div class="body stack">
            @if (!o.plan_info.slack) {
              <div class="notice">Slack alerts are part of the Team plan. Alerts still appear on the Alerts page.</div>
            }
            <label class="field" style="max-width:620px"><span>Slack incoming webhook</span>
              <input type="url" [(ngModel)]="slackUrl" [placeholder]="o.slack_configured ? 'Connected. Paste a new URL to replace it' : 'https://hooks.slack.com/services/…'" [disabled]="!api.isAdmin() || !o.plan_info.slack">
              <small>In Slack: Apps, Incoming Webhooks, Add to a channel such as #security-alerts.</small></label>
            <div class="row">
              <button class="btn primary" (click)="saveSlack()" [disabled]="!api.isAdmin() || !o.plan_info.slack || !slackUrl.trim()">Connect Slack</button>
              @if (o.slack_configured) {
                <button class="btn" (click)="testSlack()">Send a test alert</button>
                <button class="btn danger" (click)="removeSlack()" [disabled]="!api.isAdmin()">Disconnect</button>
              }
            </div>
            <label class="field" style="max-width:320px"><span>Send alerts at or above</span>
              <select [ngModel]="o.alert_min_severity" (ngModelChange)="setPolicy({ alert_min_severity: $event })" [disabled]="!api.isAdmin()">
                @for (s of severities; track s) { <option [value]="s">{{ s }}</option> }
              </select>
              <small>Changes after approval are always high or critical.</small></label>
          </div>
        </section>

        <section class="panel" id="members">
          <header><h2>Members</h2></header>
          <div class="table-wrap"><table class="ledger">
            <thead><tr><th>Person</th><th>Role</th><th></th></tr></thead>
            <tbody>
              @for (m of members()?.members ?? []; track m.user_id) {
                <tr><td><strong>{{ m.name || m.email }}</strong><div class="faint small">{{ m.email }}</div></td>
                  <td>@if (api.isAdmin() && m.email !== api.me()?.user?.email) {
                      <select [ngModel]="m.role" (ngModelChange)="setRole(m.user_id, $event)" style="width:auto">
                        <option value="member">Member</option><option value="admin">Admin</option><option value="owner">Owner</option></select>
                    } @else { {{ m.role }} }</td>
                  <td style="text-align:right">@if (api.isAdmin() && m.role !== 'owner' && m.email !== api.me()?.user?.email) {
                    <button class="btn small danger" (click)="removeMember(m.user_id)">Remove</button> }</td></tr>
              }
              @for (i of members()?.invites ?? []; track i.id) {
                <tr><td>{{ i.email }}<div class="faint small">Invite pending</div></td><td>{{ i.role }}</td>
                  <td style="text-align:right">@if (api.isAdmin()) { <button class="btn small ghost" (click)="revokeInvite(i.id)">Cancel invite</button> }</td></tr>
              }
            </tbody>
          </table></div>
          @if (api.isAdmin()) {
            <div class="body stack" style="border-top:1px solid var(--rule)">
              <div class="row invite">
                <input type="email" [(ngModel)]="inviteEmail" placeholder="teammate@company.com" aria-label="Email to invite">
                <select [(ngModel)]="inviteRole" style="width:auto" aria-label="Role"><option value="member">Member</option><option value="admin">Admin</option></select>
                <button class="btn primary" (click)="invite()" [disabled]="!inviteEmail.trim()">Create invite link</button>
              </div>
              <p class="faint small">Members see the inventory. Admins approve, block, and change settings.</p>
              @if (inviteLink()) {
                <div class="cmd"><code>{{ inviteLink() }}</code><button class="btn small" (click)="api.copy(inviteLink()!, 'Invite link copied')">Copy</button></div>
                <p class="faint small">Send this link to {{ lastInvited }}. It works once.</p>
              }
            </div>
          }
        </section>

        @if (o.edition.mode === 'self_hosted') {
          <section class="panel" id="billing">
            <header><h2>Edition</h2><span class="faint small">Self-hosted · {{ o.plan_info.label }}</span></header>
            <div class="body stack">
              @switch (o.edition.license_status) {
                @case ('active') {
                  <p>Licensed to <strong>{{ o.edition.license?.customer }}</strong> for
                    {{ o.edition.license!.max_devices >= 1000000 ? 'unlimited' : o.edition.license?.max_devices }} machines, until {{ o.edition.license?.expires }}.</p>
                  <p class="faint small">License ID {{ o.edition.license?.license_id }}. Audit-log export and other Business features are on.</p>
                }
                @case ('expired') {
                  <div class="notice">Your Business license expired on {{ o.edition.license?.expires }}. This install is running the Community edition; nothing was deleted. Set a renewed key in <code>MCPLEDGER_LICENSE_KEY</code> and restart.</div>
                }
                @case ('invalid') {
                  <div class="error-box">The license key in <code>MCPLEDGER_LICENSE_KEY</code> isn't valid ({{ o.edition.license_error }}). Running the Community edition.</div>
                }
                @default {
                  <p>You're running the free <strong>Community edition</strong>: no machine limit, Slack alerts, approvals and drift detection included.</p>
                  <p class="muted small">A <strong>Business license</strong> adds audit-log CSV export for SOC 2 evidence, priority support, and SSO and longer retention when they ship.
                    Email <a href="mailto:licensing@mcpledger.dev">licensing&#64;mcpledger.dev</a>, then set the key as <code>MCPLEDGER_LICENSE_KEY</code> and restart.</p>
                }
              }
            </div>
          </section>
        } @else {
        <section class="panel" id="billing">
          <header><h2>Plan</h2><span class="faint small">Current: {{ o.plan_info.label }}{{ o.subscription_status ? ' (' + o.subscription_status + ')' : '' }}</span></header>
          <div class="plans">
            @for (p of planList; track p.key) {
              <div class="plan" [class.current]="o.plan === p.key">
                <h3>{{ p.name }}</h3>
                <p class="price">{{ p.price === 0 ? 'Free' : '$' + p.price }}<span>{{ p.price ? ' / month' : '' }}</span></p>
                <ul>@for (f of p.features; track f) { <li>{{ f }}</li> }</ul>
                @if (o.plan === p.key) { <span class="faint small">Your plan</span> }
                @else if (p.key !== 'free' && api.isAdmin()) {
                  <button class="btn primary" (click)="checkout(p.key)" [disabled]="!billing()?.paddle?.enabled">Upgrade to {{ p.name }}</button>
                }
              </div>
            }
          </div>
          @if (billing() && !billing().paddle.enabled) { <p class="faint small body">Checkout isn't configured on this server yet (set the PADDLE_* variables).</p> }
        </section>
        }
      }
    </div>
  `,
  styles: `
    .jump { display: flex; gap: 18px; margin-bottom: 18px; font-size: 14px; flex-wrap: wrap; }
    .panel { scroll-margin-top: 16px; }
    .choice { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; margin-top: 10px; }
    .choice label { border: 1px solid var(--rule-strong); border-radius: var(--r-md); padding: 12px 14px 12px 40px; position: relative; cursor: pointer; display: flex; flex-direction: column; gap: 2px; background: #fff; }
    .choice label.on { border-color: var(--gate); box-shadow: inset 0 0 0 1px var(--gate); background: #f4faf9; }
    .choice input { position: absolute; left: 14px; top: 14px; accent-color: var(--gate); }
    .choice span { font-size: 13.5px; color: var(--ink-soft); }
    .invite input[type=email] { max-width: 320px; }
    .plans { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
    .plan { padding: 20px; border-right: 1px solid var(--rule); display: flex; flex-direction: column; gap: 10px; }
    .plan:last-child { border-right: 0; }
    .plan.current { background: #f4faf9; }
    .price { font-size: 26px; font-weight: 800; letter-spacing: -0.02em; }
    .price span { font-size: 14px; font-weight: 500; color: var(--ink-soft); }
    .plan ul { margin: 0; padding-left: 18px; font-size: 14px; color: var(--ink-soft); flex: 1; }
    .plan .btn { align-self: flex-start; }
    @media (max-width: 760px) { .plan { border-right: 0; border-bottom: 1px solid var(--rule); } }
  `,
})
export class SettingsPage implements OnInit {
  api = inject(Api);
  members = signal<Members | null>(null);
  billing = signal<any>(null);
  inviteLink = signal<string | null>(null);
  slackUrl = ''; orgName = ''; inviteEmail = ''; inviteRole = 'member'; lastInvited = '';
  severities: Severity[] = ['info', 'low', 'medium', 'high', 'critical'];
  planList = [
    { key: 'free', name: 'Free', price: 0, features: ['Up to 3 machines', 'Inventory, findings and approvals', 'Drift alerts in the dashboard'] },
    { key: 'team', name: 'Team', price: 29, features: ['Up to 25 machines', 'Slack alerts', 'One year of history', 'Email support'] },
    { key: 'business', name: 'Business', price: 199, features: ['Unlimited machines', 'Audit log CSV export', 'Two years of history', 'SSO (on the roadmap)', 'Priority support'] },
  ];

  async ngOnInit() {
    this.orgName = this.api.org()?.name ?? '';
    await this.api.refreshOrg();
    const [m, b] = await Promise.all([this.api.get<Members>('/api/org/members'), this.api.get<any>('/api/billing')]);
    this.members.set(m); this.billing.set(b);
    const frag = location.hash.slice(1);
    if (frag) setTimeout(() => document.getElementById(frag)?.scrollIntoView(), 50);
  }

  private async run(fn: () => Promise<any>, done?: string) {
    try { const r = await fn(); if (done) this.api.notify(done); return r; }
    catch (e) { this.api.notify(errorText(e)); return null; }
  }

  async setPolicy(body: any) {
    const o = await this.run(() => this.api.patch('/api/org/policy', body), 'Saved');
    if (o) this.api.org.set(o);
  }
  async rotate() {
    const o = await this.run(() => this.api.post('/api/org/enroll-token/rotate'), 'New token created. Enrolled machines keep working.');
    if (o) this.api.org.set(o);
  }
  async saveSlack() {
    const o = await this.run(() => this.api.put('/api/org/slack', { slack_webhook_url: this.slackUrl.trim() }), 'Slack connected');
    if (o) { this.api.org.set(o); this.slackUrl = ''; }
  }
  async removeSlack() {
    const o = await this.run(() => this.api.put('/api/org/slack', { slack_webhook_url: null }), 'Slack disconnected');
    if (o) this.api.org.set(o);
  }
  testSlack() { this.run(() => this.api.post('/api/org/slack/test'), 'Test alert sent'); }

  async invite() {
    const r: any = await this.run(() => this.api.post('/api/org/invites', { email: this.inviteEmail.trim(), role: this.inviteRole }));
    if (r) { this.inviteLink.set(r.link); this.lastInvited = r.email; this.inviteEmail = ''; this.members.set(await this.api.get<Members>('/api/org/members')); }
  }
  async revokeInvite(id: string) { await this.run(() => this.api.delete(`/api/org/invites/${id}`), 'Invite cancelled'); this.members.set(await this.api.get<Members>('/api/org/members')); }
  async setRole(userId: string, role: string) { await this.run(() => this.api.patch(`/api/org/members/${userId}`, { role }), 'Role updated'); this.members.set(await this.api.get<Members>('/api/org/members')); }
  async removeMember(userId: string) { await this.run(() => this.api.delete(`/api/org/members/${userId}`), 'Member removed'); this.members.set(await this.api.get<Members>('/api/org/members')); }

  async checkout(plan: 'team' | 'business' | string) {
    const b = this.billing();
    if (!b?.paddle?.enabled) return;
    await loadPaddle();
    const P = window.Paddle;
    if (b.paddle.environment === 'sandbox') P.Environment.set('sandbox');
    P.Initialize({
      token: b.paddle.client_token,
      eventCallback: async (ev: any) => {
        if (ev?.name === 'checkout.completed') {
          this.api.notify('Payment received. Updating your plan…');
          for (let i = 0; i < 10; i++) { await new Promise(r => setTimeout(r, 2000)); await this.api.refreshOrg(); if (this.api.org()?.plan === plan) break; }
        }
      },
    });
    P.Checkout.open({ items: [{ priceId: b.paddle.prices[plan], quantity: 1 }], customer: { email: b.customer_email }, customData: { org_id: b.org_id } });
  }
}

function loadPaddle(): Promise<void> {
  if (window.Paddle) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = 'https://cdn.paddle.com/paddle/v2/paddle.js';
    s.onload = () => resolve();
    s.onerror = () => reject(new Error('Could not load checkout'));
    document.head.appendChild(s);
  });
}
