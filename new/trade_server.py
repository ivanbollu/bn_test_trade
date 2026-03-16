# 创建一个 handler 来确保 UTF-8 编码
import io
import sys
import logging

class UTF8Filter(logging.Filter):
    def filter(self, record):
        # 确保消息是字符串
        if isinstance(record.msg, str):
            return True
        return False

# 设置 stdout 为 UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)
logger.addFilter(UTF8Filter())

# ===============================================================================

from flask import Flask, request, jsonify
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException
import os
from dotenv import load_dotenv

app = Flask(__name__)

# 加载 .env 文件中的环境变量
load_dotenv()

# API 配置
# 尝试从多个环境变量名读取API密钥
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
TESTNET = True
SYMBOL = "BTCUSDT"

# 验证读取成功
if not API_KEY or not SECRET_KEY:
    print("错误: 未找到API密钥！请确保已设置API_KEY和SECRET_KEY环境变量，或在项目根目录创建.env文件。")
    print("API_KEY:", "已设置" if API_KEY else "未设置")
    print("SECRET_KEY:", "已设置" if SECRET_KEY else "未设置")
    exit(1)

# 初始化客户端
client = Client(API_KEY, SECRET_KEY, testnet=TESTNET)

def get_usdt_amount_from_quantity(quantity):
    """根据 BTC 数量计算需要的 USDT 金额"""
    ticker = client.get_symbol_ticker(symbol=SYMBOL)
    price = float(ticker["price"])
    return quantity * price

def get_quantity_from_usdt(usdt_amount):
    """根据 USDT 金额计算可购买的 BTC 数量"""
    ticker = client.get_symbol_ticker(symbol=SYMBOL)
    price = float(ticker["price"])
    return usdt_amount / price

def format_quantity(quantity):
    """格式化数量以满足Binance的步长要求（BTCUSDT的步长为0.00001000）"""
    step_size = 0.00001000  # BTCUSDT步长
    return round(quantity / step_size) * step_size

@app.route('/')
def index():
    """返回 HTML 页面"""
    return open('trade_interface.html', 'r', encoding='utf-8').read()

@app.route('/api/account-info')
def get_account_info():
    """获取账户信息"""
    try:
        # 获取账户余额
        account_info = client.get_account()
        usdt_balance = 0.0
        btc_balance = 0.0

        for balance in account_info["balances"]:
            if balance["asset"] == "USDT":
                usdt_balance = float(balance["free"])
            elif balance["asset"] == "BTC":
                btc_balance = float(balance["free"])

        # 获取当前价格
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
    """买入 BTC"""
    try:
        data = request.get_json()
        quantity = float(data['quantity'])

        # 格式化数量以满足步长要求
        formatted_quantity = format_quantity(quantity)

        # 下买单
        order = client.create_order(
            symbol=SYMBOL,
            side=Client.SIDE_BUY,
            type=Client.ORDER_TYPE_MARKET,
            quantity=formatted_quantity
        )

        usdt_amount = get_usdt_amount_from_quantity(quantity)

        return jsonify({
            "success": True,
            "message": f"买入成功！订单ID: {order['orderId']}, 成交数量: {order['executedQty']} BTC, 花费: {usdt_amount:.2f} USDT",
            "order_id": order['orderId'],
            "executed_qty": order['executedQty']
        })
    except (BinanceAPIException, BinanceOrderException) as e:
        return jsonify({"success": False, "message": f"买入失败: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"系统错误: {str(e)}"}), 500

@app.route('/api/buy-with-usdt', methods=['POST'])
def buy_with_usdt():
    """使用指定 USDT 金额买入 BTC"""
    try:
        data = request.get_json()
        usdt_amount = float(data['usdtAmount'])

        # 计算可购买的 BTC 数量
        quantity = get_quantity_from_usdt(usdt_amount)

        # 格式化数量以满足步长要求
        formatted_quantity = format_quantity(quantity)

        # 下买单
        order = client.create_order(
            symbol=SYMBOL,
            side=Client.SIDE_BUY,
            type=Client.ORDER_TYPE_MARKET,
            quantity=formatted_quantity
        )

        return jsonify({
            "success": True,
            "message": f"买入成功！订单ID: {order['orderId']}, 成交数量: {order['executedQty']} BTC, 花费: {usdt_amount:.2f} USDT",
            "order_id": order['orderId'],
            "executed_qty": order['executedQty']
        })
    except (BinanceAPIException, BinanceOrderException) as e:
        return jsonify({"success": False, "message": f"买入失败: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"系统错误: {str(e)}"}), 500

@app.route('/api/sell', methods=['POST'])
def sell():
    """卖出 BTC"""
    try:
        data = request.get_json()
        quantity = float(data['quantity'])

        # 格式化数量以满足步长要求
        formatted_quantity = format_quantity(quantity)

        # 下卖单
        order = client.create_order(
            symbol=SYMBOL,
            side=Client.SIDE_SELL,
            type=Client.ORDER_TYPE_MARKET,
            quantity=formatted_quantity
        )

        usdt_amount = get_usdt_amount_from_quantity(quantity)

        return jsonify({
            "success": True,
            "message": f"卖出成功！订单ID: {order['orderId']}, 成交数量: {order['executedQty']} BTC, 获得: {usdt_amount:.2f} USDT",
            "order_id": order['orderId'],
            "executed_qty": order['executedQty']
        })
    except (BinanceAPIException, BinanceOrderException) as e:
        return jsonify({"success": False, "message": f"卖出失败: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"系统错误: {str(e)}"}), 500

if __name__ == '__main__':
    print("交易服务器启动中...")
    print("请在浏览器中访问: http://localhost:5003")
    app.run(debug=True, port=5003)