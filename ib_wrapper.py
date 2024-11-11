from ib_insync import IB, Stock, Forex, util, MarketOrder, LimitOrder, Index
from datetime import datetime
import random
import pytz
import time

timeZ_Ny = pytz.timezone('America/New_York')


class IBWrapper:
    def __init__(self, port):
        self.ib = IB()
        self.connect(port)

    def connect(self, port):
        self.ib = self.login(port)
        self.ib.reqMarketDataType(4)

    def disconnect(self):
        self.ib.disconnect()

    def get_account_balance(self):
        """
        Get the account balance information.
        """
        account_balance = self.ib.accountValues()
        for av in account_balance:
            if av.tag == 'AvailableFunds':
                print("Account Balance:-", float(av.value))
                return float(av.value)

    def get_account_summary(self):
        return self.ib.accountSummary()

    def get_positions(self):
        return self.ib.positions()

    def place_limit_order_at_bid_ask(self, contract, qty, side):
        """
        Place a limit order at the bid or ask price.

        :param contract: The contract object to trade.
        :param qty: Quantity of the order.
        :param side: 'BUY' for buying at the bid price, 'SELL' for selling at the ask price.
        """
        # Request market data
        market_data = self.ib.reqMktData(contract, '', False, False)
        self.ib.sleep(2)  # Wait a bit for the market data to be populated

        if side.upper() == 'BUY':
            # Place buy limit order at the bid price
            price = market_data.bid
            if price <= 0:  # If no bid price is available, use the last price
                price = market_data.last
        elif side.upper() == 'SELL':
            # Place sell limit order at the ask price
            price = market_data.ask
            if price <= 0:  # If no ask price is available, use the last price
                price = market_data.last
        else:
            print("Invalid side specified. Must be 'BUY' or 'SELL'.")
            return None, 0

        if price <= 0:
            print("Could not determine a valid price for the limit order.")
            return None, 0

        # Create and place the limit order
        limit_order = LimitOrder(side, qty, price)
        print(f"Placing limit order for {qty} of {contract.symbol} at {price} {side}")
        limit_trade = self.ib.placeOrder(contract, limit_order)

        # Wait for the order to be transmitted
        self.ib.sleep(1)

        return limit_trade, price

    def place_market_order(self, contract, qty, side):
        buy_order = MarketOrder(side, qty)
        buy_trade = self.ib.placeOrder(contract, buy_order)
        print("waiting for order to be placed")
        n = 0
        while True:  # Wait for up to 10 seconds
            # Wait for 1 second before checking the order status
            if buy_trade.isDone():
                # Order was filled
                print("Order placed successfully")
                fill_price = buy_trade.orderStatus.avgFillPrice
                print("Fill price:", fill_price)
                return buy_trade, fill_price
            else:
                print(f"Waiting... {n + 1} seconds")
                self.ib.sleep(1)

    def close_all_positions(self):
        print("closing all positions")
        positions = self.ib.positions()
        for position in positions:
            contract = position.contract
            [contract] = self.ib.qualifyContracts(contract)
            size = position.position
            if size > 0:  # Long position
                order = MarketOrder('SELL', abs(size))
            else:  # Short position
                order = MarketOrder('BUY', abs(size))
            trade = self.ib.placeOrder(contract, order)
            print(trade)

    def login(self, port=7497):
        print("trying to login")
        while True:
            try:
                random_id = random.randint(0, 9999)
                ib = IB()
                ibs = ib.connect('127.0.0.1', port, clientId=random_id)
                print(datetime.now(timeZ_Ny), " : ", "connected ")
                return ibs
            except Exception as e:
                print(e)
                print(datetime.now(timeZ_Ny), " : ", "retrying to login in 60 seconds")
                time.sleep(65)
                pass

    def is_connected(self):
        if self.ib.isConnected():
            print(datetime.now(timeZ_Ny), " : ", "connected")
        else:
            self.ib = self.login()

    def get_historical_data(self, contract, duration='1 D', size='1 min'):
        """
        endDateTime: Can be set to '' to indicate the current time,
                or it can be given as a datetime.date or datetime.datetime,
                or it can be given as a string in 'yyyyMMdd HH:mm:ss' format.
                If no timezone is given then the TWS login timezone is used.
            durationStr: Time span of all the bars. Examples:
                '60 S', '30 D', '13 W', '6 M', '10 Y'.
            barSizeSetting: Time period of one bar. Must be one of:
                '1 secs', '5 secs', '10 secs' 15 secs', '30 secs',
                '1 min', '2 mins', '3 mins', '5 mins', '10 mins', '15 mins',
                '20 mins', '30 mins',
                '1 hour', '2 hours', '3 hours', '4 hours', '8 hours',
                '1 day', '1 week', '1 month'.
            whatToShow: Specifies the source for constructing bars.
                Must be one of:
                'TRADES', 'MIDPOINT', 'BID', 'ASK', 'BID_ASK',
                'ADJUSTED_LAST', 'HISTORICAL_VOLATILITY',
                'OPTION_IMPLIED_VOLATILITY', 'REBATE_RATE', 'FEE_RATE',
                'YIELD_BID', 'YIELD_ASK', 'YIELD_BID_ASK', 'YIELD_LAST'.
                For 'SCHEDULE' use :meth:.reqHistoricalSchedule.
        """
        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime='',
            durationStr=duration,
            barSizeSetting=size,
            whatToShow='TRADES',
            useRTH=True
        )
        return bars

    @staticmethod
    def get_random():
        random_id = random.randint(0, 9999)
        return random_id

    def current_price(self, symbol, exchange='CBOE'):
        spx_contract = Index(symbol, exchange)
        self.ib.qualifyContracts(spx_contract)

        market_data = self.ib.reqMktData(spx_contract, '', False, False)
        self.ib.sleep(2)

        if market_data.last > 0:
            return market_data.last
        else:
            print("Market data is not subscribed or unavailable for", symbol)
            return None

    def fetch_strikes(self, symbol, exchange):
        spx = Index(symbol, 'CBOE')
        self.ib.qualifyContracts(spx)
        self.ib.reqMarketDataType(4)
        chains = self.ib.reqSecDefOptParams(spx.symbol, '', spx.secType, spx.conId)
        chain = next(c for c in chains if c.tradingClass == 'SPX' and c.exchange == 'SMART')
        strikes = chain.strikes

        return strikes

    def get_option_premium_price(self, contract):
        market_data = self.ib.reqMktData(contract, "", False, False)
        self.ib.sleep(2)

        premium_price = market_data.last if market_data.last else (market_data.bid + market_data.ask) / 2
        return premium_price