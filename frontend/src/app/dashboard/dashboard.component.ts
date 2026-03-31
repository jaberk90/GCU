/**
 * DashboardComponent — US-2, US-3, US-4, US-5, US-6, FR-4, FR-5, FR-6, FR-10
 * Main results view: Summary, Technical tab, Fundamental tab, Prediction tab.
 */
import { Component, OnInit, OnDestroy } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { StockService } from '../services/stock.service';

@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss']
})
export class DashboardComponent implements OnInit {

  symbol = '';
  activeTab: 'technical' | 'fundamental' | 'prediction' = 'technical';

  loading = false;
  loadingPredict = false;
  error = '';
  analysisData: any = null;
  predictionData: any = null;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private stockSvc: StockService
  ) {}

  ngOnInit(): void {
    this.route.queryParams.subscribe(params => {
      const sym = (params['symbol'] || '').toUpperCase();
      if (!sym) {
        this.router.navigate(['/']);
        return;
      }
      this.symbol = sym;
      this.loadAnalysis();
    });
  }

  loadAnalysis(): void {
    this.loading = true;
    this.error = '';
    this.analysisData = null;

    this.stockSvc.analyze(this.symbol).subscribe({
      next: data => {
        this.analysisData = data;
        this.loading = false;
      },
      error: (err: Error) => {
        this.error = err.message;
        this.loading = false;
      }
    });
  }

  loadPrediction(): void {
    if (this.predictionData || this.loadingPredict) return;
    this.loadingPredict = true;

    this.stockSvc.predict(this.symbol).subscribe({
      next: data => {
        this.predictionData = data;
        this.loadingPredict = false;
      },
      error: (err: Error) => {
        this.predictionData = { error: err.message };
        this.loadingPredict = false;
      }
    });
  }

  switchTab(tab: 'technical' | 'fundamental' | 'prediction'): void {
    this.activeTab = tab;
    if (tab === 'prediction') this.loadPrediction();
  }

  goHome(): void {
    this.router.navigate(['/']);
  }

  // ── Formatting helpers ──────────────────────────────────────────────────────

  fmt(n: any, dec = 2): string {
    if (n == null || isNaN(Number(n))) return '—';
    return Number(n).toFixed(dec);
  }

  fmtB(n: any): string {
    const v = Number(n);
    if (!v || isNaN(v)) return '—';
    if (Math.abs(v) >= 1e12) return (v / 1e12).toFixed(2) + 'T';
    if (Math.abs(v) >= 1e9)  return (v / 1e9).toFixed(2)  + 'B';
    if (Math.abs(v) >= 1e6)  return (v / 1e6).toFixed(2)  + 'M';
    return v.toLocaleString();
  }

  isPos(n: any): boolean { return Number(n) >= 0; }
  recClass(action: string): string {
    return (action || '').toLowerCase();
  }
}
