import { Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { Api } from './api';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet],
  template: `
    <router-outlet />
    @if (api.toast(); as t) { <div class="toast" role="status">{{ t }}</div> }
  `,
})
export class App {
  api = inject(Api);
}
