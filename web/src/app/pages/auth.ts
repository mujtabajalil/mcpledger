import { Component, OnInit, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Api, errorText } from '../api';

const FRAME = `
  .auth { min-height: 100vh; display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr); }
  .form-side { display: flex; flex-direction: column; justify-content: center; padding: 48px clamp(24px, 6vw, 88px); }
  .form-side form { max-width: 380px; width: 100%; display: flex; flex-direction: column; gap: 16px; }
  .brand { display: flex; align-items: center; gap: 10px; font-weight: 800; font-size: 19px; color: var(--petrol); margin-bottom: 36px; letter-spacing: -0.02em; }
  .alt { margin-top: 8px; font-size: 14px; color: var(--ink-soft); }
  .story { background: var(--petrol); color: #d8e6e3; padding: 56px clamp(24px, 5vw, 72px); display: flex; flex-direction: column; justify-content: center; gap: 28px; }
  .story h2 { color: #fff; font-size: clamp(24px, 2.6vw, 34px); line-height: 1.15; font-weight: 800; max-width: 18ch; letter-spacing: -0.02em; }
  .story p { max-width: 46ch; font-size: 15.5px; line-height: 1.6; }
  .ledger-demo { font-family: var(--mono); font-size: 12.5px; border: 1px solid #34606b; border-radius: 8px; overflow: hidden; max-width: 460px; }
  .ledger-demo div { display: grid; grid-template-columns: 1fr auto; gap: 12px; padding: 9px 14px; border-top: 1px solid #2a5561; }
  .ledger-demo div:first-child { border-top: 0; }
  .ledger-demo .ok { color: #9fd9b5; } .ledger-demo .chg { color: #f0c46d; } .ledger-demo .blk { color: #f2a19a; }
  @media (max-width: 860px) { .auth { grid-template-columns: 1fr; } .story { display: none; } }
`;

const STORY = `
  <section class="story" aria-hidden="true">
    <h2>Every MCP server and agent skill on your team, accounted for.</h2>
    <p>MCPLedger inventories what each developer's Claude Code, Cursor, Codex and VS Code can load,
       lets you approve exact versions, and tells you the moment one changes after approval.</p>
    <div class="ledger-demo">
      <div><span>@modelcontextprotocol/server-github</span><span class="ok">approved</span></div>
      <div><span>mcp.linear.app/mcp</span><span class="ok">approved</span></div>
      <div><span>postmark-mcp</span><span class="chg">tools changed</span></div>
      <div><span>skill: invoice-helper</span><span class="blk">blocked</span></div>
    </div>
  </section>`;

const BRAND = `<div class="brand"><svg viewBox="0 0 32 32" width="28" height="28" aria-hidden="true"><rect width="32" height="32" rx="7" fill="#16343d"/><path d="M8 25V11l8-5 8 5v14" fill="none" stroke="#eef0ec" stroke-width="2.6" stroke-linejoin="round"/><path d="M12.5 25v-8h7v8" fill="none" stroke="#7fc8b8" stroke-width="2.6"/></svg>MCPLedger</div>`;

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
