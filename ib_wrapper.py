

"""
Interactive broker's API maintained with IB-INSYNC library

	This is async library, use asyncio to maintain coroutines
"""

# Importing built-in libraries
import asyncio
import pytz
import datetime as dt

# Importing third-party libraries
from ib_insync import *		# pip install ib_insync
import pandas as pd			# pip install pandas
#util.logToConsole('DEBUG')

class IBTWSAPI:

	def __init__(self, creds:dict):
		
		self.CREDS = creds

	def _create_contract(self, contract:str, symbol:str, exchange:str, expiry:str=..., strike:int=..., right:str=...):
		"""
		Creates contract object for api\n
		"""
		
		if contract == "stocks":
			return Stock(symbol=symbol, exchange=exchange, currency="USD")
		
		elif contract == "options":
			return Option(symbol=symbol, lastTradeDateOrContractMonth=expiry,exchange=exchange,currency="USD", strike=strike, right=right)
		
		elif contract == "futureContracts":
			return ContFuture(symbol=symbol, exchange=exchange, currency="USD")

	async def connect(self) -> bool:
		"""
		Connect the system with TWS account\n
		"""
		# try:
		host, port = self.CREDS['host'], self.CREDS['port']
		self.client = IB()
		self.client.connect(host=host, port=port, clientId=self.CREDS['client_id'], timeout=60)
		print("Connected")
		
		# except Exception as e:
		# 	print(e)
		# 	return False

	def is_connected(self) -> bool:
		"""
		Get the connection status\n
		"""
		return self.client.isConnected()

	def get_account_info(self):
		"""
		Returns connected account info\n
		"""
		account_info = self.client.accountSummary()
		return account_info

	def get_account_balance(self) -> float:
		"""
		Returns account balance\n
		"""
		for acc in self.get_account_info():
			if acc.tag == "AvailableFunds":
				return float(acc.value)
			
	async def get_positions(self):
		return self.client.positions()[0]

	async def get_open_orders(self):
		return self.client.reqOpenOrders()

	async def get_contract_info(self, contract:str, symbol:str, exchange: str) -> dict:
		"""
		Returns info of the contract\n
		"""
		# Creating contract
		c = self._create_contract(contract=contract, symbol=symbol, exchange=exchange)
		if contract in ["options"]:
			c.strike = ""
			c.lastTradeDateOrContractMonth = ""

		contract_info = self.client.reqContractDetails(contract=c)
		# print(contract_info)
		
		return {
				"contract_obj" : contract_info[0].contract,
				"expiry" : contract_info[0].contract.lastTradeDateOrContractMonth
			}

	async def get_expiries_and_strikes(self, technology: str, ticker: str) -> dict:
		"""
		"""
		# Creating contract
		if technology.lower() == "options":
			c = Option()
		else:
			c = FuturesOption()
		c.symbol = ticker
		c.strike = ""
		c.lastTradeDateOrContractMonth = ""
		print("Over here bro")
		contract_info = self.client.reqContractDetails(contract=c)
		# print(contract_info)

		ens = {}
		for contractDetails in contract_info:
			# print(contractDetails.contract.strike, contractDetails.contract.lastTradeDateOrContractMonth, contractDetails.contract.exchange, contractDetails.contract.symbol, contractDetails.contract.right)
			s_exp = contractDetails.contract.lastTradeDateOrContractMonth
			exp = dt.date(int(s_exp[:4]), int(s_exp[4:6]), int(s_exp[-2:]))
			strike = float(contractDetails.contract.strike)

			if exp not in ens: ens[exp] = []
			if strike not in ens[exp]: ens[exp].append(strike)
		current_datetime = dt.datetime.now(pytz.timezone("UTC"))
		return {k : sorted(ens[k]) for k in sorted(ens.keys()) if k > current_datetime.date()}

	async def fetch_strikes(self, symbol, exchange):
		spx = Index(symbol, 'CBOE')
		self.client.qualifyContracts(spx)
		self.client.reqMarketDataType(4)
		chains = self.client.reqSecDefOptParams(spx.symbol, '', spx.secType, spx.conId)
		chain = next(c for c in chains if c.tradingClass == 'SPX' and c.exchange == 'SMART')
		strikes = chain.strikes

		return strikes

	async def place_market_order(self, contract, qty, side):
		buy_order = MarketOrder(side, qty)
		buy_trade = self.client.placeOrder(contract, buy_order)
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
				await asyncio.sleep(1)
	async def current_price(self, symbol, exchange='CBOE'):
		spx_contract = Index(symbol, exchange)
		self.client.qualifyContracts(spx_contract)
		self.client.reqMarketDataType(4)

		market_data = self.client.reqMktData(spx_contract, '', snapshot=True)
		while util.isNan(market_data.last):
			await asyncio.sleep(0.1)

		if market_data.last > 0:
			return market_data.last
		else:
			print("Market data is not subscribed or unavailable for", symbol)
			return None

	async def get_option_chain(self, symbol:str, exp_list:list) -> dict:
		"""
		"""
		exps = {}
		df = pd.DataFrame(columns=['strike','kind','close','last'])
		self.client.reqMarketDataType(1)
		for i in exp_list:
			cds = self.client.reqContractDetails(Option(symbol, i, exchange='SMART'))
			# print(cds)
			options = [cd.contract for cd in cds]
			# print(options)
			l = []
			for x in options:
				# print(x)
				contract = Option(symbol, i, x.strike, x.right, "SMART", currency="USD")
				# print(contract)
				snapshot = self.client.reqMktData(contract, "", True, False)
				l.append([x.strike,x.right,snapshot])
				# print(snapshot)

			while util.isNan(snapshot.bid):
				self.client.sleep()
			for ii in l:
				df = df.append({'strike':ii[0],'kind':ii[1],'close':ii[2].close,'last':ii[2].last,'bid':ii[2].bid,'ask':ii[2].ask,'mid':(ii[2].bid+ii[2].ask)/2,'volume':ii[2].volume},ignore_index=True)
				exps[i] = df

		return exps

	async def get_candle_data(self, contract:str, symbol:str, timeframe:str, period:str='2d', exchange:str="SMART") -> pd.DataFrame:
		"""
		Returns candle data of a ticker\n
		"""
		_tf = {
			's':"sec",
			'm':"min",
			"h":"hour"
		}

		# Creating contract
		c = self._create_contract(contract=contract, symbol=symbol, exchange=exchange)

		# Parsing timeframe
		timeframe = timeframe[:-1] + ' ' + _tf[timeframe[-1]] + ('s' if timeframe[:-1] != '1' else '')
		
		# Parsing period
		period = ' '.join([i.upper() for i in period])

		data = self.client.reqHistoricalData(c, '', barSizeSetting=timeframe, durationStr=period, whatToShow='MIDPOINT', useRTH=True)
		df = pd.DataFrame([(
				{
					"datetime" : i.date,
					"open" : i.open,
					"high" : i.high,
					"low" : i.low,
					"close" : i.close,
				}
			) for i in data])
		df.set_index('datetime', inplace=True)
		return df

	async def place_order(
			self, 
			contract:str, 
			symbol:str, 
			side:str, 
			quantity:int, 
			order_type:str="MARKET", 
			price:float=..., 
			exchange:str="SMART",
		) -> dict:
		"""
		Places order in TWS account\n
		"""
		
		# Creating contract
		c = self._create_contract(contract=contract, symbol=symbol, exchange=exchange)

		# Parsing order type
		if order_type.upper() == "MARKET":
			order = MarketOrder(action=side.upper(), totalQuantity=quantity)
		elif order_type.upper() == "LIMIT":
			order = LimitOrder(action=side.upper(), totalQuantity=quantity, lmtPrice=price)
		elif order_type.upper() == "STOP":
			order = StopOrder(action=side.upper(), totalQuantity=quantity, stopPrice=price)

		order_info = self.client.placeOrder(contract=c, order=order)
		return order_info

	async def simple_order(self, c, order):
		return self.client.placeOrder(c, order)

	async def place_bracket_order(
			self, 
			symbol:str, 
			quantity:int, 
			price:float=...,
			stoploss:float=None, 
			targetprofit:float=None,
			expiry:str=None,
			strike:float=None,
			right:str=None,
			trailingpercent:float=False,
		) -> dict:
		"""
		Places a bracket order\n
		"""
		get_exit_side = "BUY"
		# Creating contract
		c = self._create_contract(contract="options", symbol=symbol, exchange="SMART", expiry=expiry, strike=strike, right=right)

		entry_order_info, stoploss_order_info, targetprofit_order_info = None, None, None

		parent_id = self.client.client.getReqId()
		
		# Entry order
		en_order = LimitOrder(action="SELL", totalQuantity=quantity, lmtPrice=price)
		en_order.orderId = parent_id
		en_order.transmit = False

		# Stoploss order
		if trailingpercent:
			sl_order = Order()
			sl_order.action = get_exit_side
			sl_order.totalQuantity = quantity
			sl_order.parentId = en_order.orderId
			sl_order.orderType = "TRAIL"
			sl_order.trailingPercent = trailingpercent
			# sl_order.trailStopPrice = stoploss
			sl_order.transmit = True
		elif stoploss:
			sl_order = StopOrder(action=get_exit_side, totalQuantity=quantity, stopPrice=stoploss)
			# sl_order.parentId = en_order.orderId
			sl_order.transmit = True

		# Targetprofit order
		# if targetprofit:
		# 	tp_order = LimitOrder(action=get_exit_side, totalQuantity=quantity, lmtPrice=targetprofit)
		# 	tp_order.parentId = en_order.orderId
		# 	tp_order.transmit = True

		entry_order_info = self.client.placeOrder(contract=c, order=en_order)
		self.client.sleep(1)
		if stoploss:
			stoploss_order_info = self.client.placeOrder(contract=c, order=sl_order)
			print("waiting for order to be placed")
			n = 0
			while True:  # Wait for up to 10 seconds
				# Wait for 1 second before checking the order status
				if entry_order_info.isDone():
					# Order was filled
					print("Order placed successfully")
					fill_price = entry_order_info.orderStatus.avgFillPrice
					print(stoploss_order_info)
					print("Fill price:", fill_price)
					x = fill_price
					return {
						"parent_id": parent_id,
						"entry": entry_order_info,
						"stoploss": stoploss_order_info,
						"targetprofit": targetprofit_order_info,
						"contract": c,
						"order": sl_order,
						"avgFill": x
					}
				else:
					print(f"Waiting... {n + 1} seconds")
					await asyncio.sleep(1)
		# self.client.sleep(1)
		# if targetprofit:
		# 	targetprofit_order_info = self.client.placeOrder(contract=c, order=tp_order)
	
	# async def modify_order(self, order_id:int, params = {}) -> None:
	# 	self.client.

	async def cancel_order(self, order_id:int) -> None:
		"""
		Cancel open order\n
		"""
		orders = self.client.reqOpenOrders()
		for order in orders:
			if order.orderId == order_id:
				self.client.cancelOrder(order=order)

	async def query_order(self, order_id:int) -> dict:
		"""
		Queries order\n
		"""

		all_orders = self.client.openOrders() + [i.order for i in self.client.reqCompletedOrders(True)]
		
		for order in all_orders:
			print(order)
			if order.permId == order_id:
				return order

	# async def modify_trailing_stop_percent(self, order_id, new_trailing_percent):
	# 	# Get the existing order
	# 	trades = self.client.trades()
	# 	target_trade = next((t for t in trades if t.order.orderId == order_id), None)
	#
	# 	if not target_trade:
	# 		raise ValueError(f"Order with ID {order_id} not found")
	#
	# 	# Create a new order with modified trailing percent
	# 	modified_order = target_trade.order
	# 	modified_order.trailingPercent = new_trailing_percent
	#
	# 	# Submit the modification
	# 	self.client.placeOrder(target_trade.contract, modified_order)
	#
	# 	await self.client.sleep(10)
	#
	# 	return modified_order

	async def connect_app(self, app) -> None:
		"""
		Connect main app with api\n
		"""
		self.app = app

	async def get_latest_premium_price(self, symbol, expiry, strike, right, exchange="CBOE"):

		# Create the option contract
		option_contract = Option(
			symbol=symbol,
			lastTradeDateOrContractMonth=expiry,
			strike=strike,
			right=right,
			exchange=exchange,
		)

		# Qualify the contract
		self.client.qualifyContracts(option_contract)

		# Request market data
		market_data = self.client.reqMktData(option_contract, '', snapshot=True)

		self.client.reqMarketDataType(4)
		while util.isNan(market_data.last):
			await asyncio.sleep(10)

		# Extract relevant prices
		premium_price = {
			"bid": market_data.bid,
			"ask": market_data.ask,
			"last": market_data.last,
			"mid": (market_data.bid + market_data.ask) / 2 if market_data.bid and market_data.ask else None
		}
		return premium_price

	async def modify_option_trail_percent(self, trade, new_trailing_percent=0.14):
		"""
        Asynchronously modify the trailing percentage for an option order

        Args:
            ib: IB instance that is already connected
            trade: Existing trade object
            new_trailing_percent: New trailing percentage value (default 0.14)

        Returns:
            Modified order object
        """
		# Create modified order maintaining all original parameters
		modified_order = Order(
			orderId=trade.order.orderId,
			action=trade.order.action,
			totalQuantity=trade.order.totalQuantity,
			orderType='TRAIL',
			tif=trade.order.tif,
			ocaGroup=trade.order.ocaGroup,
			ocaType=trade.order.ocaType,
			parentId=trade.order.parentId,
			displaySize=trade.order.displaySize,
			trailStopPrice=trade.order.trailStopPrice,
			trailingPercent=new_trailing_percent,  # Modified trailing percent
			openClose=trade.order.openClose,
			account=trade.order.account,
			clearingIntent=trade.order.clearingIntent,
			dontUseAutoPriceForHedge=trade.order.dontUseAutoPriceForHedge
		)

		# Cancel existing order
		self.client.cancelOrder(trade.order)

		# Wait a brief moment to ensure cancellation is processed
		self.client.sleep(0.2)

		# Place new order with modified trailing percent
		new_trade = self.client.placeOrder(trade.contract, modified_order)

		self.client.sleep(10)

		return new_trade

	# Example usage:
	"""
	import asyncio

	async def main():
	    ib = IB()
	    await ib.connectAsync('127.0.0.1', 7497, clientId=12)

	    try:
	        # Get existing trade
	        trades = ib.trades()
	        target_trade = next((t for t in trades 
	                           if t.order.orderId == 210 
	                           and t.contract.symbol == 'SPX'), None)

	        if target_trade:
	            modified_trade = await modify_option_trail_percent(ib, target_trade)
	            print(f"Trail modified successfully. New trailing percent: {modified_trade.order.trailingPercent}")
	        else:
	            print("Target trade not found")

	    except Exception as e:
	        print(f"Error: {e}")
	    finally:
	        await ib.disconnectAsync()

	# Run the async function
	asyncio.run(main())
	"""

async def main():
    CONTRACTS = ["Stocks", "Options", "FutureContract", "FutureContractOptions"]

    creds = {
        "host": "0.0.0.0",
        "port": 4001,
        "client_id": 2,
    }

    api = IBTWSAPI(creds=creds)
    await api.connect()  # Note the use of 'await' here

    print("Connected")
    
    # Now that the connection is established, you can call other methods
    positions = await api.get_positions()
    print(positions)


# if __name__ == "__main__":
#     asyncio.run(main())
"""
if __name__ == "__main__":

	CONTRACTS = ["Stocks", "Options", "FutureContract", "FutureContractOptions"]

	creds = {
		"host" : "0.0.0.0",
		"port" : 4001,
		"client_id" : 2,
	}

	api = IBTWSAPI(creds=creds)
	api.connect()
	print("connected")
	positions=api.get_positions()
	print(positions)
"""
	# NOTE Get the connection status of the api client
	# is_connected_to_tws = api.is_connected()
	# print(is_connected_to_tws)

	# NOTE Get account info
	# account_info = api.get_account_info()
	# print(account_info)
	# [print(i) for i in account_info]

	# NOTE Get account balance
	# balance = api.get_account_balance()
	# print(balance)

	# NOTE Get contract info
	# contract = CONTRACTS[1]
	# symbol = "AAPL"
	# exchange = "SMART"
	# contract_info = api.get_contract_info(contract=contract, symbol=symbol, exchange=exchange)
	# print(contract_info)

	# NOTE Get expiries and strikes

	#technology = CONTRACTS[3]
	#ticker = "CL"
	#ens = api.get_expiries_and_strikes(technology=technology, ticker=ticker)
	#print(ens)

	# NOTE Get candle data
	# contract = CONTRACTS[2]
	# symbol = "ES"
	# timeframe = "5m"
	# period = "2d"
	# exchange = "GLOBEX"
	# df = api.get_candle_data(contract=contract, symbol=symbol, timeframe=timeframe, period=period, exchange=exchange)
	# print(df)
	
	# NOTE Get options chain
	# symbol = "AAPL"
	# exp_list = [20221012]
	# chain = api.get_option_chain(symbol=symbol, exp_list=exp_list)
	# print(chain)

	# NOTE Place order
	# contract = CONTRACTS[0]
	# symbol = "AAPL"
	# side = "buy"
	# quantity = 1
	# order_type = "MARKET"
	# price = None
	# exchange = "SMART"
	# order_info = api.place_order(contract=contract, symbol=symbol, side=side, quantity=quantity, order_type=order_type, price=price, exchange=exchange)
	# print(order_info)

	# NOTE Place bracket order
	# contract = CONTRACTS[0]
	# symbol = "AAPL"
	# side = "buy"
	# quantity = 1
	# order_type = "MARKET"
	# price = None
	# exchange = "SMART"
	# stoploss = 139.0
	# targetprofit = None
	# orders_info = api.place_bracket_order(contract=contract, symbol=symbol, side=side, quantity=quantity, order_type=order_type, price=price, exchange=exchange, stoploss=stoploss, targetprofit=targetprofit)
	# print(orders_info)

	# NOTE Cancel order
	# order_id = 124
	# api.cancel_order(order_id=order_id)

	# NOTE Query_order
	# order_id = 1248689
	# order_info = api.query_order(order_id=order_id)
	# print(order_info)
