import { Component, OnInit, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Api, errorText } from '../api';

const FRAME = `
  .auth { min-height: 100vh; display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr); padding: 10px; gap: 10px; }
  .form-side { display: flex; flex-direction: column; justify-content: center; padding: 48px clamp(24px, 6vw, 88px); }
  .form-side form { max-width: 380px; width: 100%; display: flex; flex-direction: column; gap: 16px; }
  .form-side h1 { font-size: 28px; letter-spacing: -0.03em; }
  .form-side .btn.primary { padding: 11px 14px; margin-top: 4px; }
  .brand { display: flex; align-items: center; gap: 11px; font-weight: 700; font-size: 19px; color: var(--ink); margin-bottom: 40px; letter-spacing: -0.03em; }
  .brand .mark { width: 36px; height: 36px; border-radius: 10px; background: #18181b; display: grid; place-items: center; box-shadow: inset 0 1px 0 rgba(255,255,255,.12), 0 1px 2px rgba(0,0,0,.2); }
  .alt { margin-top: 8px; font-size: 14px; color: var(--ink-soft); }
  .story { background: var(--canvas); border: 1px solid var(--rule-strong); border-radius: 22px; padding: 56px clamp(24px, 5vw, 72px);
    display: flex; flex-direction: column; justify-content: center; gap: 26px; box-shadow: 0 8px 24px rgba(24,24,27,.04); }
  .story h2 { font-size: clamp(26px, 2.7vw, 36px); line-height: 1.12; font-weight: 600; max-width: 18ch; letter-spacing: -0.035em; }
  .story p { max-width: 46ch; font-size: 16px; line-height: 1.6; color: var(--ink-soft); }
  .ledger-demo { max-width: 480px; background: var(--well); border: 1px solid var(--rule); border-radius: 18px; padding: 5px; }
  .ledger-demo .cap { font-size: 13px; color: var(--ink-faint); padding: 8px 12px 10px; }
  .ledger-demo .rows { background: var(--paper); border: 1px solid var(--rule); border-radius: 12px; box-shadow: var(--shadow-xs); }
  .ledger-demo .r { display: grid; grid-template-columns: 1fr auto; gap: 12px; align-items: center; padding: 12px 14px; border-top: 1px solid var(--rule); font-size: 14px; }
  .ledger-demo .r:first-child { border-top: 0; }
  .ledger-demo .r span:first-child { font-family: var(--mono); font-size: 12.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  @media (max-width: 860px) { .auth { grid-template-columns: 1fr; } .story { display: none; } }
`;

const STORY = `
  <section class="story" aria-hidden="true">
    <h2>Every MCP server and agent skill on your team, accounted for.</h2>
    <p>MCPLedger inventories what each developer's Claude Code, Cursor, Codex and VS Code can load,
       lets you approve exact versions, and tells you the moment one changes after approval.</p>
    <div class="ledger-demo">
      <div class="cap">Inventory</div>
      <div class="rows">
        <div class="r"><span>@modelcontextprotocol/server-github</span><span class="status approved">Approved</span></div>
        <div class="r"><span>mcp.linear.app/mcp</span><span class="status approved">Approved</span></div>
        <div class="r"><span>postmark-mcp</span><span class="status drift">Tools changed</span></div>
        <div class="r"><span>skill: invoice-helper</span><span class="status blocked">Blocked</span></div>
      </div>
    </div>
  </section>`;

const BRAND = `<div class="brand"><span class="mark"><svg viewBox="0 0 32 32" width="22" height="22" aria-hidden="true"><path d="M8 25V11l8-5 8 5v14" fill="none" stroke="#fff" stroke-width="2.8" stroke-linejoin="round"/><path d="M12.5 25v-8h7v8" fill="none" stroke="#9ad8ca" stroke-width="2.8"/></svg></span>MCPLedger</div>`;

@Component({
  selector: 'sg-login',
  imports: [FormsModule, RouterLink],
  template: `
    <div class="auth">
      <section class="form-side">
        ${BRAND}
        <form (ngSubmit)="submit()">
          <h1>Sign in</h1>
          @if (error()) { <div class="error-box" role="alert">{{ error() }}</div> }
          <label class="field"><span>Work email</span><input type="email" name="email" [(ngModel)]="email" autocomplete="email" required></label>
          <label class="field"><span>Password</span><input type="password" name="password" [(ngModel)]="password" autocomplete="current-password" required></label>
          <button class="btn primary" [disabled]="busy()">{{ busy() ? 'Signing in…' : 'Sign in' }}</button>
          <p class="alt">New to MCPLedger? <a routerLink="/signup">Create your team</a></p>
        </form>
      </section>
      ${STORY}
    </div>`,
  styles: FRAME,
})
export class LoginPage {
  private api = inject(Api);
  private router = inject(Router);
  email = ''; password = '';
  busy = signal(false); error = signal('');

  async submit() {
    this.busy.set(true); this.error.set('');
    try {
      await this.api.post('/api/auth/login', { email: this.email, password: this.password });
      await this.api.loadSession();
      this.router.navigateByUrl('/overview');
    } catch (e) { this.error.set(errorText(e)); } finally { this.busy.set(false); }
  }
}

@Component({
  selector: 'sg-signup',
  imports: [FormsModule, RouterLink],
  template: `
    <div class="auth">
      <section class="form-side">
        ${BRAND}
        <form (ngSubmit)="submit()">
          <h1>Create your team</h1>
          <p class="muted">Free for up to 3 developers. No card needed.</p>
          @if (error()) { <div class="error-box" role="alert">{{ error() }}</div> }
          <label class="field"><span>Your name</span><input type="text" name="name" [(ngModel)]="name" autocomplete="name"></label>
          <label class="field"><span>Work email</span><input type="email" name="email" [(ngModel)]="email" autocomplete="email" required></label>
          <label class="field"><span>Team or company name</span><input type="text" name="org" [(ngModel)]="orgName" placeholder="Acme Engineering"></label>
          <label class="field"><span>Password</span><input type="password" name="password" [(ngModel)]="password" autocomplete="new-password" minlength="10" required>
            <small>At least 10 characters.</small></label>
          <button class="btn primary" [disabled]="busy()">{{ busy() ? 'Creating…' : 'Create team' }}</button>
          <p class="alt">Already have an account? <a routerLink="/login">Sign in</a></p>
        </form>
      </section>
      ${STORY}
    </div>`,
  styles: FRAME,
})
export class SignupPage {
  private api = inject(Api);
  private router = inject(Router);
  name = ''; email = ''; orgName = ''; password = '';
  busy = signal(false); error = signal('');

  async submit() {
    this.busy.set(true); this.error.set('');
    try {
      await this.api.post('/api/auth/signup', { name: this.name, email: this.email, org_name: this.orgName || null, password: this.password });
      await this.api.loadSession();
      this.router.navigateByUrl('/overview');
    } catch (e) { this.error.set(errorText(e)); } finally { this.busy.set(false); }
  }
}

@Component({
  selector: 'sg-invite',
  imports: [FormsModule, RouterLink],
  template: `
    <div class="auth">
      <section class="form-side">
        ${BRAND}
        @if (loadError()) {
          <div class="stack" style="max-width:380px">
            <h1>This invite can't be used</h1>
            <p class="muted">{{ loadError() }}. Ask your admin for a new invite link.</p>
            <a class="btn" routerLink="/login">Go to sign in</a>
          </div>
        } @else if (info()) {
          <form (ngSubmit)="submit()">
            <h1>Join {{ info().org_name }}</h1>
            <p class="muted">{{ info().invited_by }} invited {{ info().email }}.</p>
            @if (error()) { <div class="error-box" role="alert">{{ error() }}</div> }
            @if (signedIn()) {
              <button class="btn primary" [disabled]="busy()">Join {{ info().org_name }}</button>
            } @else if (info().has_account) {
              <p>You already have an account. <a [routerLink]="'/login'">Sign in</a>, then open this link again.</p>
            } @else {
              <label class="field"><span>Your name</span><input type="text" name="name" [(ngModel)]="name"></label>
              <label class="field"><span>Choose a password</span><input type="password" name="password" [(ngModel)]="password" minlength="10" required>
                <small>At least 10 characters.</small></label>
              <button class="btn primary" [disabled]="busy()">Create account and join</button>
            }
          </form>
        }
      </section>
      ${STORY}
    </div>`,
  styles: FRAME,
})
export class InvitePage implements OnInit {
  private api = inject(Api);
  private router = inject(Router);
  token = input.required<string>();
  info = signal<any>(null); loadError = signal(''); error = signal('');
  signedIn = signal(false); busy = signal(false);
  name = ''; password = '';

  async ngOnInit() {
    try { this.info.set(await this.api.get(`/api/auth/invite/${this.token()}`)); }
    catch (e) { this.loadError.set(errorText(e)); }
    this.signedIn.set(await this.api.loadSession());
  }

  async submit() {
    this.busy.set(true); this.error.set('');
    try {
      if (this.signedIn()) {
        const r: any = await this.api.post(`/api/auth/invite/${this.token()}/accept`);
        try { localStorage.setItem('ml_org', r.org_id); } catch { /* ignore */ }
      } else {
        await this.api.post('/api/auth/signup', { email: this.info().email, name: this.name, password: this.password, invite_token: this.token() });
      }
      await this.api.loadSession();
      this.router.navigateByUrl('/overview');
    } catch (e) { this.error.set(errorText(e)); } finally { this.busy.set(false); }
  }
}
