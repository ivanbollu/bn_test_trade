from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException
import time
import logging
import pandas as pd

# ====================== 1. Basic Configuration ======================
# Replace with your API keys
API_KEY = "8IRAEyYeSeChN3wYPFZFS8f7xLzK4xwLn1uM3Vhdb7RhMBrkGRuTf61BZCRwH4Xh"
SECRET_KEY = "qCJEZniuc6Rsy9XzDFC2DJn9iY8cFtSvPwQbsbJmuqH5JQ4z3AJ9fb94RM6vhOFG"

# Trading Configuration
SYMBOL = "BTCUSDT"          # Trading pair (BTC/USDT)
BASE_ASSET = "USDT"         # Base asset
QUANTITY = 0.01             # Order quantity per trade (minimum trading unit for BTCUSDT is 0.01)
LEVERAGE = 1                # No leverage for spot trading (modify this if using futures)
RISK_RATIO = 0.01           # Risk ratio (single order amount does not exceed 1% of account USDT balance)

# Logging Configuration (for troubleshooting)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ====================== 2. Initialize Binance Client ======================
def init_binance_client():
    """Initialize Binance client (supports spot/futures, spot by default)"""
    client = Client(API_KEY, SECRET_KEY, testnet=True)
    # Test connection
    try:
        client.get_account()
        logger.info("Binance API connection successful!")
        return client
    except Exception as e:
        logger.error(f"API connection failed: {e}")
        raise SystemExit(1)

# ====================== 3. Parse Trading Signals ======================
def get_trade_signal(client):
    """
    Get trading signal based on 20-day Moving Average (MA20)
    
    Strategy:
        - BUY: When price crosses above MA20 (bullish breakout)
        - SELL: When price crosses below MA20 (bearish breakdown)
        - HOLD: When price stays on the same side of MA20
    
    :param client: Binance client instance
    :return: "BUY" | "SELL" | "HOLD"
    """
    try:
        # Get 30 days of historical data to calculate MA20
        klines = client.get_historical_klines(
            symbol=SYMBOL,
            interval=Client.KLINE_INTERVAL_1DAY,
            start_str="30 days ago UTC"
        )
        
        if len(klines) < 21:
            logger.warning("Insufficient historical data for MA20 calculation")
            return "HOLD"
        
        # Convert to DataFrame
        df = pd.DataFrame(klines, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_av', 'trades', 'tb_base_av', 
            'tb_quote_av', 'ignore'
        ])
        
        # Convert close price to float
        df['close'] = df['close'].astype(float)
        
        # Calculate 20-day Moving Average
        df['ma20'] = df['close'].rolling(window=20).mean()
        
        # Get latest data
        current_price = df['close'].iloc[-1]
        current_ma20 = df['ma20'].iloc[-1]
        prev_price = df['close'].iloc[-2]
        prev_ma20 = df['ma20'].iloc[-2]
        
        logger.info(f"Current Price: {current_price:.2f}, MA20: {current_ma20:.2f}")
        logger.info(f"Previous Price: {prev_price:.2f}, Previous MA20: {prev_ma20:.2f}")
        
        # Check for crossover signals
        # BUY: Price was below MA20, now above MA20 (golden cross)
        if prev_price <= prev_ma20 and current_price > current_ma20:
            logger.info("📈 BUY Signal: Price crossed ABOVE MA20")
            return "BUY"
        
        # SELL: Price was above MA20, now below MA20 (death cross)
        elif prev_price >= prev_ma20 and current_price < current_ma20:
            logger.info("📉 SELL Signal: Price crossed BELOW MA20")
            return "SELL"
        
        # HOLD: No crossover detected
        else:
            if current_price > current_ma20:
                logger.info("✅ Holding LONG position (Price > MA20)")
            else:
                logger.info("❌ Holding SHORT position (Price < MA20)")
            return "HOLD"
            
    except Exception as e:
        logger.error(f"Failed to calculate MA20 signal: {e}")
        return "HOLD"

# ====================== 3.1 Minute Price Increase Signal ======================
def get_minute_price_increase_signal(client):
    """
    Check if current price increased by 0.1% compared to 1 minute ago
    Strategy:
        - BUY: If current price > price_1min_ago * 1.001
        - HOLD: Otherwise
    :param client: Binance client instance
    :return: "BUY" | "HOLD"
    """
    try:
        # Get current market price
        ticker = client.get_symbol_ticker(symbol=SYMBOL)
        current_price = float(ticker["price"])

        # Get 1-minute klines to get the close price from 1 minute ago
        klines = client.get_historical_klines(
            symbol=SYMBOL,
            interval=Client.KLINE_INTERVAL_1MINUTE,
            limit=2  # Get last 2 candles
        )

        if len(klines) < 2:
            logger.warning("Insufficient minute data for price increase check")
            return "HOLD"

        # The previous candle's close price (1 minute ago)
        prev_price = float(klines[-2][4])  # close price of previous candle

        logger.info(f"Minute price check - Current: {current_price:.2f}, 1 min ago: {prev_price:.2f}, Change: {(current_price/prev_price - 1)*100:.4f}%")

        # Check if price increased by 0.1%
        if current_price > prev_price * 1.001:
            logger.info("📈 Minute BUY Signal: Price increased > 0.1% in 1 minute")
            return "BUY"
        else:
            return "HOLD"

    except Exception as e:
        logger.error(f"Failed to calculate minute price increase signal: {e}")
        return "HOLD"

# ====================== 4. Account Balance & Risk Control ======================
def get_balance(client, asset):
    """Get available balance of the specified asset"""
    account_info = client.get_account()
    for balance in account_info["balances"]:
        if balance["asset"] == asset:
            return float(balance["free"])
    return 0.0

def calculate_safe_quantity(client):
    """Calculate safe order quantity based on risk control rules"""
    usdt_balance = get_balance(client, BASE_ASSET)
    max_trade_usdt = usdt_balance * RISK_RATIO  # Maximum trade amount per order
    # Get latest price and calculate purchasable quantity (quantity = amount / price)
    ticker = client.get_symbol_ticker(symbol=SYMBOL)
    latest_price = float(ticker["price"])
    safe_quantity = max_trade_usdt / latest_price
    # Round down to the minimum trading unit (0.01)
    safe_quantity = round(safe_quantity // 0.01 * 0.01, 2)
    # Ensure quantity is not less than the minimum trading unit
    return max(safe_quantity, 0.01)

# ====================== 5. Core Trading Logic ======================
def place_order(client, side, quantity):
    """
    Place order function
    :param side: Order direction (Client.SIDE_BUY / Client.SIDE_SELL)
    :param quantity: Order quantity
    :return: Order information / None
    """
    # Binance BTCUSDT minimum trading quantity is 0.00001
    if quantity < 0.00001:
        logger.warning(f"Order quantity {quantity} is less than minimum trading unit (0.00001), skipping order placement")
        return None
    # Round quantity to 5 decimal places to match Binance precision
    quantity = round(quantity, 5)

    try:
        # Market order (suitable for signal trading, fast execution)
        order = client.create_order(
            symbol=SYMBOL,
            side=side,
            type=Client.ORDER_TYPE_MARKET,
            quantity=quantity
        )
        logger.info(f"{side} order successful: {order}")
        return order
    except BinanceAPIException as e:
        logger.error(f"API error: {e}")
    except BinanceOrderException as e:
        logger.error(f"Order error: {e}")
    except Exception as e:
        logger.error(f"Unknown order error: {e}")
    return None

def close_all_position(client):
    """Close all positions (sell all held BTCUSDT)"""
    btc_balance = get_balance(client, "BTC")  # Get available BTC balance
    if btc_balance < 0.01:
        logger.info("No BTC positions held, no need to close positions")
        return None
    # Sell all holdings (market order)
    return place_order(client, Client.SIDE_SELL, round(btc_balance, 2))

# ====================== 6. Main Loop (Monitor Signals + Execute Trades) ======================
def main():
    client = init_binance_client()
    logger.info("Start monitoring trading signals...")
    
    # Initial balance report
    initial_usdt = get_balance(client, BASE_ASSET)
    logger.info(f"Initial USDT balance: {initial_usdt}")
    
    minute_count = 0
    while True:
        try:
            # 1. Check minute price increase signal (every minute)
            minute_signal = get_minute_price_increase_signal(client)
            logger.info(f"Minute price signal: {minute_signal}")

            if minute_signal == "BUY":
                # Buy fixed quantity 0.001 BTC
                buy_quantity = 0.001
                # Check if we have enough USDT balance
                usdt_balance = get_balance(client, BASE_ASSET)
                ticker = client.get_symbol_ticker(symbol=SYMBOL)
                latest_price = float(ticker["price"])
                required_usdt = buy_quantity * latest_price
                if usdt_balance >= required_usdt:
                    logger.info(f"Executing minute BUY: {buy_quantity} BTC at price {latest_price:.2f}")
                    place_order(client, Client.SIDE_BUY, buy_quantity)
                else:
                    logger.warning(f"Insufficient USDT balance for minute BUY. Need {required_usdt:.2f} USDT, have {usdt_balance:.2f}")

            # 2. Check MA20 signal every 5 minutes
            if minute_count % 5 == 0:
                signal = get_trade_signal(client)
                logger.info(f"MA20 signal: {signal}")

                # Execute trade based on signal
                if signal == "BUY":
                    # Calculate safe order quantity (replace fixed QUANTITY)
                    safe_qty = calculate_safe_quantity(client)
                    logger.info(f"Safe order quantity after risk control: {safe_qty}")
                    if safe_qty > 0:
                        place_order(client, Client.SIDE_BUY, safe_qty)

                elif signal == "SELL":
                    # Close all positions (sell all holdings)
                    close_all_position(client)

                elif signal == "HOLD":
                    logger.info("Hold position, no action taken")

            minute_count += 1
            # 3. Loop interval (avoid frequent requests)
            time.sleep(60)  # Check every 1 minute

        except KeyboardInterrupt:
            logger.info("Program stopped manually")
            break
        except Exception as e:
            logger.error(f"Main loop exception: {e}")
            time.sleep(10)  # Pause for 10 seconds before retrying after exception

if __name__ == "__main__":
    main()