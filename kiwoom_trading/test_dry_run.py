"""
모의투자 + DRY_RUN 모드에서 data_feed / account / signals 동작 확인.
실제 API 호출이 필요한 함수는 mock 응답으로 대체해 단독 실행 가능하게 함.

실행:
  python -m kiwoom_trading.test_dry_run
"""
import json
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd

from .signals import generate_signals, Signal, adapt_pipeline_output
from . import config


# ── 샘플 full_result.csv 데이터 ──────────────────────────────
SAMPLE_ROWS = [
    {
        "code": "005930", "name": "삼성전자", "sector": "전기전자",
        "prob_up": 0.72, "prob_down": 0.28, "pred_ret5d": 0.025,
        "pred_price5d": 77000, "grade": "A+", "Close": 75000,
        "bounce_score": 65, "rsi14": 55.0, "macd_cross": 1,
    },
    {
        "code": "000660", "name": "SK하이닉스", "sector": "전기전자",
        "prob_up": 0.61, "prob_down": 0.39, "pred_ret5d": 0.018,
        "pred_price5d": 185000, "grade": "A", "Close": 181800,
        "bounce_score": 40, "rsi14": 48.0, "macd_cross": 0,
    },
    {
        "code": "051910", "name": "LG화학", "sector": "화학",
        "prob_up": 0.30, "prob_down": 0.70, "pred_ret5d": -0.015,
        "pred_price5d": 295000, "grade": "D", "Close": 300000,
        "bounce_score": 10, "rsi14": 38.0, "macd_cross": 0,
    },
]


class TestConfig(unittest.TestCase):
    def test_trading_mode_mock(self):
        self.assertEqual(config.TRADING_MODE, "mock",
                         "TRADING_MODE 기본값은 'mock' 이어야 합니다")

    def test_dry_run_true(self):
        self.assertTrue(config.DRY_RUN,
                        "DRY_RUN 기본값은 True 이어야 합니다")

    def test_base_url_mock(self):
        self.assertIn("mockapi", config.BASE_URL,
                      "mock 모드 BASE_URL 에 'mockapi' 가 포함되어야 합니다")


class TestSignals(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame(SAMPLE_ROWS)

    def test_adapt_ok(self):
        out = adapt_pipeline_output(self.df)
        self.assertEqual(out["code"].iloc[0], "005930")
        self.assertAlmostEqual(out["prob_up"].iloc[0], 0.72)

    def test_code_zero_padded(self):
        df2 = self.df.copy()
        df2.loc[0, "code"] = "5930"       # 패딩 없는 경우
        out = adapt_pipeline_output(df2)
        self.assertEqual(out["code"].iloc[0], "005930")

    def test_generate_signals_buy(self):
        signals = generate_signals(self.df)
        buy = [s for s in signals if s.action == "BUY"]
        codes = [s.code for s in buy]
        self.assertIn("005930", codes, "삼성전자는 BUY 시그널이어야 합니다")
        self.assertIn("000660", codes, "SK하이닉스는 BUY 시그널이어야 합니다")

    def test_generate_signals_sell(self):
        signals = generate_signals(self.df)
        sell = [s for s in signals if s.action == "SELL"]
        codes = [s.code for s in sell]
        self.assertIn("051910", codes, "LG화학은 SELL 시그널이어야 합니다")

    def test_buy_sorted_by_prob(self):
        signals = generate_signals(self.df)
        buy = [s for s in signals if s.action == "BUY"]
        probs = [s.prob_up for s in buy]
        self.assertEqual(probs, sorted(probs, reverse=True),
                         "BUY 시그널은 prob_up 내림차순이어야 합니다")

    def test_signal_fields(self):
        signals = generate_signals(self.df)
        s = signals[0]
        self.assertIsInstance(s.code, str)
        self.assertIsInstance(s.prob_up, float)
        self.assertIsInstance(s.current_price, float)


class TestDataFeedMock(unittest.TestCase):
    """실제 API 호출 없이 mock 응답으로 data_feed 함수 확인."""

    @patch("kiwoom_trading.kiwoom_client.post")
    def test_get_current_price(self, mock_post):
        mock_post.return_value = {
            "return_code": 0,
            "return_msg": "정상",
            "body": {
                "stk_cd": "005930",
                "stck_prpr": "75000",
                "prdy_vrss": "500",
                "prdy_ctrt": "0.67",
            },
        }
        from .data_feed import get_current_price
        result = get_current_price("005930")
        self.assertEqual(result["stk_cd"], "005930")
        self.assertEqual(result["stck_prpr"], "75000")

    @patch("kiwoom_trading.kiwoom_client.post")
    def test_get_daily_chart(self, mock_post):
        mock_post.return_value = {
            "return_code": 0,
            "return_msg": "정상",
            "cont_yn": "N",
            "body": [
                {
                    "stck_bsop_date": "20240501",
                    "stck_oprc": "74000",
                    "stck_hgpr": "75500",
                    "stck_lwpr": "73500",
                    "stck_clpr": "75000",
                    "acml_vol":  "12345678",
                }
            ],
        }
        from .data_feed import get_daily_chart
        rows = get_daily_chart("005930")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["stck_clpr"], "75000")


class TestAccountMock(unittest.TestCase):
    """실제 API 호출 없이 mock 응답으로 account 함수 확인."""

    @patch("kiwoom_trading.kiwoom_client.post")
    def test_get_deposit(self, mock_post):
        mock_post.return_value = {
            "return_code": 0,
            "return_msg": "정상",
            "body": {
                "dnca_tot_amt":  "10000000",
                "ord_psbl_cash": "8000000",
            },
        }
        from .account import get_deposit
        dep = get_deposit()
        self.assertEqual(dep["ord_psbl_cash"], "8000000")

    @patch("kiwoom_trading.kiwoom_client.post")
    def test_get_positions(self, mock_post):
        mock_post.return_value = {
            "return_code": 0,
            "return_msg": "정상",
            "cont_yn": "N",
            "body": [
                {
                    "stk_cd":      "005930",
                    "stk_nm":      "삼성전자",
                    "hldg_qty":    "10",
                    "pchs_avg_pric": "70000",
                    "evlu_amt":    "750000",
                    "evlu_pfls_amt": "50000",
                }
            ],
        }
        from .account import get_positions
        pos = get_positions()
        self.assertEqual(len(pos), 1)
        self.assertEqual(pos[0]["stk_cd"], "005930")


if __name__ == "__main__":
    print(f"\n설정 확인: TRADING_MODE={config.TRADING_MODE}, "
          f"DRY_RUN={config.DRY_RUN}, BASE_URL={config.BASE_URL}\n")
    unittest.main(verbosity=2)
