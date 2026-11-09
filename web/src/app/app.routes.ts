import { inject } from '@angular/core';
import { CanActivateFn, Router, Routes } from '@angular/router';
import { Api } from './api';
import { Shell } from './pages/shell';
import { LoginPage, SignupPage, InvitePage } from './pages/auth';
import { OverviewPage } from './pages/overview';
import { InventoryPage } from './pages/inventory';
import { ComponentPage } from './pages/component';
import { DevicesPage } from './pages/devices';
import { AlertsPage } from './pages/alerts';
import { AuditPage } from './pages/audit';
import { SettingsPage } from './pages/settings';

const signedIn: CanActivateFn = async () => {
  const api = inject(Api);
  if (api.me() || (await api.loadSession())) return true;
  return inject(Router).parseUrl('/login');
};

const signedOut: CanActivateFn = async () => {
  const api = inject(Api);
  if (api.me() || (await api.loadSession())) return inject(Router).parseUrl('/overview');
  return true;
};

export const routes: Routes = [
  { path: 'login', component: LoginPage, canActivate: [signedOut], title: 'Sign in · MCPLedger' },
  { path: 'signup', component: SignupPage, canActivate: [signedOut], title: 'Create your team · MCPLedger' },
  { path: 'invite/:token', component: InvitePage, title: 'Join your team · MCPLedger' },
  {
    path: '',
    component: Shell,
    canActivate: [signedIn],
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'overview' },
      { path: 'overview', component: OverviewPage, title: 'Overview · MCPLedger' },
      { path: 'inventory', component: InventoryPage, title: 'Inventory · MCPLedger' },
      { path: 'inventory/:id', component: ComponentPage, title: 'Component · MCPLedger' },
      { path: 'devices', component: DevicesPage, title: 'Devices · MCPLedger' },
      { path: 'alerts', component: AlertsPage, title: 'Alerts · MCPLedger' },
      { path: 'audit', component: AuditPage, title: 'Audit log · MCPLedger' },
      { path: 'settings', component: SettingsPage, title: 'Settings · MCPLedger' },
    ],
  },
  { path: '**', redirectTo: '' },
];
