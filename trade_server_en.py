from flask import Flask, request, jsonify
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException
import os

app = Flask(__name__)

# API Configuration
API_KEY = "***"
SECRET_KEY = "***"
TESTNET = True
SYMBOL = "BTCUSDT"

# Initialize client
client = Client(API_KEY, SECRET_KEY, testnet=TESTNET)

def get_usdt_amount_from_quantity(quantity):
    """Calculate required USDT amount from BTC quantity"""
    ticker = client.get_symbol_ticker(symbol=SYMBOL)
    price = float(ticker["price"])
    return quantity * price

def get_quantity_from_usdt(usdt_amount):
    """Calculate purchasable BTC quantity from USDT amount"""
    ticker = client.get_symbol_ticker(symbol=SYMBOL)
    price = float(ticker["price"])
    return usdt_amount / price

def format_quantity(quantity):
    """Format quantity to meet Binance's step size requirement (0.00001000 for BTCUSDT)"""
    step_size = 0.00001000  # BTCUSDT step size
    return round(quantity / step_size) * step_size

@app.route('/')
def index():
    """Return HTML page"""
    return open('trade_interface_en.html', 'r', encoding='utf-8').read()

@app.route('/api/account-info')
def get_account_info():
    """Get account information"""
    try:
        # Get account balances
        account_info = client.get_account()
        usdt_balance = 0.0
        btc_balance = 0.0

        for balance in account_info["balances"]:
            if balance["asset"] == "USDT":
                usdt_balance = float(balance["free"])
            elif balance["asset"] == "BTC":
                btc_balance = float(balance["free"])

        # Get current price
        ticker = client.get_symbol_ticker(symbol=SYMBOL)
        current_price = float(ticker["price"])

        return jsonify({
            "success": True,
            "usdt_balance": usdt_balance,
            "btc_balance": btc_balance,
            "current_price": current_price
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/buy', methods=['POST'])
def buy():
    """Buy BTC"""
    try:
        data = request.get_json()
        quantity = float(data['quantity'])

        # Format quantity to meet step size requirement
        formatted_quantity = format_quantity(quantity)

        # Place buy order
        order = client.create_order(
            symbol=SYMBOL,
            side=Client.SIDE_BUY,
            type=Client.ORDER_TYPE_MARKET,
            quantity=formatted_quantity
        )

        usdt_amount = get_usdt_amount_from_quantity(formatted_quantity)

        return jsonify({
            "success": True,
            "message": f"Buy successful! Order ID: {order['orderId']}, Executed quantity: {order['executedQty']} BTC, Cost: {usdt_amount:.2f} USDT",
            "order_id": order['orderId'],
            "executed_qty": order['executedQty']
        })
    except (BinanceAPIException, BinanceOrderException) as e:
        return jsonify({"success": False, "message": f"Buy failed: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"System error: {str(e)}"}), 500

@app.route('/api/buy-with-usdt', methods=['POST'])
def buy_with_usdt():
    """Buy BTC with specified USDT amount"""
    try:
        data = request.get_json()
        usdt_amount = float(data['usdtAmount'])

        # Calculate BTC quantity to buy
        quantity = get_quantity_from_usdt(usdt_amount)

        # Format quantity to meet step size requirement
        formatted_quantity = format_quantity(quantity)

        # Place buy order
        order = client.create_order(
            symbol=SYMBOL,
            side=Client.SIDE_BUY,
            type=Client.ORDER_TYPE_MARKET,
            quantity=formatted_quantity
        )

        return jsonify({
            "success": True,
            "message": f"Buy successful! Order ID: {order['orderId']}, Executed quantity: {order['executedQty']} BTC, Cost: {usdt_amount:.2f} USDT",
            "order_id": order['orderId'],
            "executed_qty": order['executedQty']
        })
    except (BinanceAPIException, BinanceOrderException) as e:
        return jsonify({"success": False, "message": f"Buy failed: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"System error: {str(e)}"}), 500

@app.route('/api/sell', methods=['POST'])
def sell():
    """Sell BTC"""
    try:
        data = request.get_json()
        quantity = float(data['quantity'])

        # Format quantity to meet step size requirement
        formatted_quantity = format_quantity(quantity)

        # Place sell order
        order = client.create_order(
            symbol=SYMBOL,
            side=Client.SIDE_SELL,
            type=Client.ORDER_TYPE_MARKET,
            quantity=formatted_quantity
        )

        usdt_amount = get_usdt_amount_from_quantity(formatted_quantity)

        return jsonify({
            "success": True,
            "message": f"Sell successful! Order ID: {order['orderId']}, Executed quantity: {order['executedQty']} BTC, Proceeds: {usdt_amount:.2f} USDT",
            "order_id": order['orderId'],
            "executed_qty": order['executedQty']
        })
    except (BinanceAPIException, BinanceOrderException) as e:
        return jsonify({"success": False, "message": f"Sell failed: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"System error: {str(e)}"}), 500

if __name__ == '__main__':
    print("Trading server starting...")
    print("Please visit: http://localhost:5000")
    app.run(debug=True, port=5001)
