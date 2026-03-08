/**
 * 내 지갑 타입 정의
 * 백엔드 GET /api/wallet/balance 응답과 1:1 대응
 */

export interface WalletAsset {
  currency: string         // "BTC", "USDT", "ETH"
  amount: number           // 보유 수량
  usd_value: number        // USD 환산 가치
  krw_value: number        // KRW 환산 가치
  pct_of_total: number     // 전체 대비 비중 (%)
  current_price_usd: number  // 현재 단가 (USD)
  change_24h_pct: number   // 24시간 변동률 (%)
}

export interface WalletBalance {
  total_usd: number        // 전체 자산 USD
  total_krw: number        // 전체 자산 KRW
  cash_usd: number         // USDT 잔고 (현금)
  coin_value_usd: number   // 코인 총 가치 (USDT 제외)
  asset_count: number      // 보유 자산 종류 수
  mode: 'paper' | 'live'  // 트레이딩 모드
  fx_rate: number          // USD/KRW 환율
  updated_at: string       // 업데이트 시각 (ISO)
  assets: WalletAsset[]
}
