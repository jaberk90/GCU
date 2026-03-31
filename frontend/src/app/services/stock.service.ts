/**
 * StockService — FR-1, FR-2, FR-4, FR-5, FR-6, FR-9
 * Client-side service for all backend API calls.
 * API keys never stored here — backend handles auth.
 */
import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { environment } from '../../environments/environment';

@Injectable({ providedIn: 'root' })
export class StockService {

  private baseUrl = environment.apiUrl; // e.g. http://localhost:5000/api/v1

  constructor(private http: HttpClient) {}

  /** FR-2: Validate ticker format via backend */
  validate(symbol: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/validate`, { symbol })
      .pipe(catchError(this.handleError));
  }

  /** FR-1, FR-4, FR-5: Full technical + fundamental analysis */
  analyze(symbol: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/analyze`, { symbol })
      .pipe(catchError(this.handleError));
  }

  /** FR-6: Forecast view — ARIMA + LSTM */
  predict(symbol: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/predict`, { symbol })
      .pipe(catchError(this.handleError));
  }

  private handleError(error: HttpErrorResponse): Observable<never> {
    const msg = error.error?.error || 'An unexpected error occurred. Please try again.';
    return throwError(() => new Error(msg));
  }
}
