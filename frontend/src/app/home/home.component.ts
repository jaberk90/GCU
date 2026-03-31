/**
 * HomeComponent — US-1, FR-1, FR-2
 * Entry point: ticker input, validation, route to dashboard.
 */
import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { FormControl, Validators } from '@angular/forms';

@Component({
  selector: 'app-home',
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.scss']
})
export class HomeComponent {

  tickerCtrl = new FormControl('', [
    Validators.required,
    Validators.pattern(/^[A-Za-z]{1,10}$/)
  ]);

  errorMessage = '';

  constructor(private router: Router) {}

  /** US-1 task 1-4: validate input and route to dashboard */
  onAnalyze(): void {
    this.errorMessage = '';
    const raw = (this.tickerCtrl.value || '').trim().toUpperCase();

    if (!raw) {
      this.errorMessage = 'Please enter a stock symbol before analyzing.';
      this.tickerCtrl.markAsTouched();
      return;
    }

    if (this.tickerCtrl.invalid) {
      this.errorMessage = `"${raw}" is not a valid ticker format. Use 1–10 letters only (e.g. AAPL).`;
      return;
    }

    // Route to dashboard with symbol as query param
    this.router.navigate(['/dashboard'], { queryParams: { symbol: raw } });
  }

  onKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Enter') this.onAnalyze();
  }
}
