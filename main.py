import creds
from ib_wrapper import IBWrapper
from ib_insync import *
import time
import threading


class Strategy:

    def __init__(self):
        self.broker = IBWrapper(creds.port)
        self.strikes = None
        self.otm_closest_call = None
        self.otm_closest_put = None
        self.date = creds.date

    def main(self):
        print("Started Bot")
        self.strikes = self.broker.fetch_strikes(creds.instrument, creds.exchange)
        current_price = self.broker.current_price("SPX", "CBOE")
        # self.place_hedge_orders()
        self.place_atm_call_order(0.15)
        # self.place_atm_put_order(0.15)

    def place_hedge_orders(self):
        current_price = self.broker.current_price("SPX", "CBOE")
        otm_call_strike = round(current_price + 10, 1)
        otm_put_strike = round(current_price - 10, 1)

        self.closest_call = min(self.strikes, key=lambda x: abs(x - otm_call_strike))
        self.otm_closest_put = min(self.strikes, key=lambda x: abs(x - otm_put_strike))

        spx_contract = Option(
            symbol=creds.instrument,
            lastTradeDateOrContractMonth=self.date,
            strike=self.closest_call,
            right='C',
            exchange=creds.exchange
        )
        self.broker.place_market_order(contract=spx_contract, qty=1, side="BUY")

        spx_contract = Option(
            symbol=creds.instrument,
            lastTradeDateOrContractMonth=self.date,
            strike=self.otm_closest_put,
            right='P',
            exchange=creds.exchange
        )
        self.broker.place_market_order(contract=spx_contract, qty=1, side="BUY")

    def close_open_hedges(self, close_put=True, close_call=True):
        if close_call:
            spx_contract = Option(
                symbol=creds.instrument,
                lastTradeDateOrContractMonth=self.date,
                strike=self.closest_call,
                right='C',
                exchange=creds.exchange
            )
            self.broker.place_market_order(contract=spx_contract, qty=1, side="SELL")
        if close_put:
            spx_contract = Option(
                symbol=creds.instrument,
                lastTradeDateOrContractMonth=self.date,
                strike=self.otm_closest_put,
                right='P',
                exchange=creds.exchange
            )
            self.broker.place_market_order(contract=spx_contract, qty=1, side="SELL")

    def place_atm_call_order(self, sl):
        current_price = self.broker.current_price("SPX", "CBOE")

        closest_current_price = min(self.strikes, key=lambda x: abs(x - current_price))

        spx_contract = Option(
            symbol=creds.instrument,
            lastTradeDateOrContractMonth=self.date,
            strike=closest_current_price,
            right='C',
            exchange=creds.exchange
        )
        _, fill_price = self.broker.place_market_order(contract=spx_contract, qty=1, side="SELL")

        stop_loss_price = fill_price * (1 + sl)

        def monitor_stop_loss():
            while True:
                latest_premium = self.broker.get_option_premium_price(contract=spx_contract)

                print(f"Monitoring... Current Price: {latest_premium}, Stop-Loss Price: {stop_loss_price}")

                if latest_premium >= stop_loss_price:
                    print("STOP-LOSS TRIGGERED: BUYING CALL POSITION")
                    sell_order = MarketOrder('BUY', 1)
                    sell_trade = self.broker.place_market_order(spx_contract, sell_order)

                    while sell_trade.orderStatus.status != 'Filled':
                        print(f"Waiting for BUY Order to Fill: Status - {sell_trade.orderStatus.status}")
                        time.sleep(3)

                    print("Buy Order Filled, Position Closed")
                    self.close_open_hedges(close_put=False, close_call=True)
                    break
                else:
                    time.sleep(10)

        stop_loss_thread = threading.Thread(target=monitor_stop_loss)
        stop_loss_thread.start()

    def place_atm_put_order(self, sl):
        current_price = self.broker.current_price("SPX", "CBOE")

        closest_current_price = min(self.strikes, key=lambda x: abs(x - current_price))

        spx_contract = Option(
            symbol=creds.instrument,
            lastTradeDateOrContractMonth=self.date,
            strike=closest_current_price,
            right='P',
            exchange=creds.exchange
        )
        _, fill_price = self.broker.place_market_order(contract=spx_contract, qty=1, side="SELL")

        stop_loss_price = fill_price * (1 - sl)

        def monitor_stop_loss():
            while True:
                latest_premium = self.broker.get_option_premium_price(contract=spx_contract)

                print(f"Monitoring... Current Price: {latest_premium}, Stop-Loss Price: {stop_loss_price}")

                if latest_premium >= stop_loss_price:
                    print("STOP-LOSS TRIGGERED: BUYING CALL POSITION")
                    sell_order = MarketOrder('BUY', 1)
                    sell_trade = self.broker.place_market_order(spx_contract, sell_order)

                    while sell_trade.orderStatus.status != 'Filled':
                        print(f"Waiting for BUY Order to Fill: Status - {sell_trade.orderStatus.status}")
                        time.sleep(3)

                    print("Buy Order Filled, Position Closed")
                    self.close_open_hedges(close_put=True, close_call=False)
                    break
                else:
                    time.sleep(10)

        stop_loss_thread = threading.Thread(target=monitor_stop_loss)
        stop_loss_thread.start()


s = Strategy()
s.main()
