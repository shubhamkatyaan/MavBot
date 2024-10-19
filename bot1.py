import os
import logging
import time
from telegram import ParseMode, Bot
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from decimal import Decimal
import mysql.connector
import requests

# Load environment variables from .env file
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Replace with your actual group chat ID
GROUP_CHAT_ID = int(os.getenv('GROUP_CHAT_ID'))

# DexScreener API URL
DEXSCREENER_API_URL = "https://api.dexscreener.com/latest/dex/tokens/"

# Initialize the Telegram bot
second_bot_token = os.getenv('SECOND_BOT_API_TOKEN')
second_bot = Bot(token=second_bot_token)

# Fetch market cap from DexScreener
def get_market_cap_from_dexscreener(contract_address):
    try:
        logger.info(f"Fetching market cap for contract: {contract_address}")
        response = requests.get(f"{DEXSCREENER_API_URL}{contract_address}")
        
        if response.status_code != 200:
            logger.error(f"Failed to fetch data from DexScreener for {contract_address}: {response.status_code}")
            return None

        data = response.json()
        pairs = data.get('pairs', [])

        for pair in pairs:
            if 'marketCap' in pair:
                market_cap = float(pair['marketCap'])
                logger.info(f"Market cap for {contract_address}: {market_cap}")
                return market_cap
        
        logger.warning(f"Market cap data not available for {contract_address} on DexScreener.")
        return None
    except Exception as e:
        logger.error(f"Error fetching market cap from DexScreener: {e}")
        return None

# Send new token notification
def send_new_token_message(token):
    try:
        market_cap = get_market_cap_from_dexscreener(token['contract_address'])

        market_cap_text = f"${market_cap:,.2f}" if market_cap else "N/A"

        message = (
            f"🎉 *New Token Added to Watchlist!*\n\n"
            f"📝 *Token Name:* {token['token_name']}\n"
            f"🌐 *Chain:* {token['chain']}\n"
            f"🔗 *Contract Address:* `{token['contract_address']}`\n"
            f"💰 *Current Market Cap:* {market_cap_text}\n"
            f"🔐 *Liquidity Locked:* {token['liquidity_locked']}\n"
            f"🔏 *Ownership Renounced:* {token['ownership_renounced']}\n"
            f"🔥 *Liquidity Burned:* {token['liquidity_burned']}\n"
            f"💰 *Buy Tax:* {token['buy_tax']}%\n"
            f"💸 *Sell Tax:* {token['sell_tax']}%\n"
            f"💼 *Transfer Tax:* {token['transfer_tax']}%\n\n"
        )
        second_bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=message,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
        logger.info(f"New token message sent for {token['token_name']}.")
    except Exception as e:
        logger.error(f"Failed to send new token message: {e}")

# Check for new tokens added to the database every 2 minutes
def check_for_new_tokens():
    logger.info("Checking for newly added tokens...")
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM token_details WHERE notified_at IS NULL")  # Fetch tokens with no notification
        new_tokens = cursor.fetchall()

        for token in new_tokens:
            logger.info(f"New token found: {token['token_name']}")
            send_new_token_message(token)
            update_token_notified_at(token['id'])
            time.sleep(1)  # Sleep to avoid rate limits

    except mysql.connector.Error as err:
        logger.error(f"Error: {err}")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

# Update the token as notified in the database
def update_token_notified_at(token_id):
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        cursor = conn.cursor()
        update_query = """
            UPDATE token_details
            SET notified_at = %s
            WHERE id = %s
        """
        cursor.execute(update_query, (datetime.utcnow(), token_id))
        conn.commit()
        logger.info(f"Token {token_id} updated with notified_at timestamp.")
    except mysql.connector.Error as err:
        logger.error(f"Error updating token: {err}")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

# Check all tokens every 30 minutes for market cap to buy or track gains
def check_market_caps_for_all_tokens():
    logger.info("Checking market caps for all tokens...")
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM token_details")
        tokens = cursor.fetchall()

        for token in tokens:
            contract_address = token['contract_address']
            try_buy_at_mc = token['try_buy_at_mc']
            token_name = token['token_name']
            initial_market_cap = token['initial_market_cap']
            last_notified_multiple = token['last_notified_multiple'] or 1

            # Fetch current market cap
            market_cap = get_market_cap_from_dexscreener(contract_address)
            if market_cap is None:
                logger.warning(f"Could not fetch market cap for {token_name}")
                continue

            # Convert initial_market_cap to float if it's Decimal
            if isinstance(initial_market_cap, Decimal):
                initial_market_cap = float(initial_market_cap)

            # Check if market cap meets buy conditions or achieves multiples
            logger.info(f"Checking token {token_name} for gains - Current Market Cap: {market_cap}, Try Buy At: {try_buy_at_mc}")

            if token['notified_at'] is None:
                # Check if market cap is less than or equal to try_buy_at_mc
                if market_cap <= try_buy_at_mc:
                    logger.info(f"Condition met for buy initiated - {token_name}: {market_cap} <= {try_buy_at_mc}")
                    send_buy_initiated_message(token, market_cap)
                    update_token_after_buy_initiated(token['id'], market_cap)
                else:
                    logger.info(f"Condition NOT met for {token_name} - Market Cap: {market_cap}, Try Buy At: {try_buy_at_mc}")
            else:
                if initial_market_cap > 0:
                    multiple = market_cap / initial_market_cap
                    multiples_to_check = [5, 7, 10, 15, 20, 25, 50, 100, 200, 250, 300, 400, 500, 750, 1000, 2000, 5000, 10000]
                    for m in multiples_to_check:
                        if multiple >= m and last_notified_multiple < m:
                            send_multiple_achieved_message(token, market_cap, m)
                            update_last_notified_multiple(token['id'], m)
                            break
                else:
                    logger.warning(f"Initial market cap is not set or is zero for {token_name}.")

            time.sleep(1)  # Sleep to avoid rate limits
    except mysql.connector.Error as err:
        logger.error(f"Error: {err}")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

# Send buy initiated message
def send_buy_initiated_message(token, market_cap):
    try:
        market_cap_text = f"${market_cap:,.2f}" if market_cap else "N/A"
        message = (
            f"🚀 *Buy Initiated!*\n\n"
            f"🔹 *Token Name:* {token['token_name']}\n"
            f"🌐 *Chain:* {token['chain']}\n"
            f"🔹 *Contract Address:* `{token['contract_address']}`\n"
            f"💰 *Current Market Cap:* {market_cap_text}\n"
            f"⏰ *Time:* {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        )
        second_bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=message,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
        logger.info(f"Buy initiated message sent for {token['token_name']}.")
    except Exception as e:
        logger.error(f"Failed to send buy initiated message: {e}")

# Update token after buy initiated
def update_token_after_buy_initiated(token_id, market_cap):
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        cursor = conn.cursor()
        update_query = """
            UPDATE token_details
            SET notified_at = %s, initial_market_cap = %s
            WHERE id = %s
        """
        cursor.execute(update_query, (datetime.utcnow(), market_cap, token_id))
        conn.commit()
        logger.info(f"Token {token_id} updated after buy initiated.")
    except mysql.connector.Error as err:
        logger.error(f"Error updating token after buy initiated: {err}")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

# Send multiple achieved notification
def send_multiple_achieved_message(token, market_cap, multiple):
    try:
        message = (
            f"🎉 *{multiple}x Achieved!*\n\n"
            f"🔹 *Token Name:* {token['token_name']}\n"
            f"🌐 *Chain:* {token['chain']}\n"
            f"🔹 *Contract Address:* `{token['contract_address']}`\n"
            f"💰 *Initial Market Cap:* ${token['initial_market_cap']:,.2f}\n"
            f"💰 *Current Market Cap:* ${market_cap:,.2f}\n"
            f"📈 *Gain:* {multiple}x\n"
        )
        second_bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=message,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
        logger.info(f"{multiple}x achieved message sent for {token['token_name']}.")
    except Exception as e:
        logger.error(f"Failed to send multiple achieved message: {e}")

# Update the last notified multiple in the database
def update_last_notified_multiple(token_id, multiple):
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        cursor = conn.cursor()
        update_query = """
            UPDATE token_details
            SET last_notified_multiple = %s
            WHERE id = %s
        """
        cursor.execute(update_query, (multiple, token_id))
        conn.commit()
        logger.info(f"Token {token_id} last notified multiple updated to {multiple}.")
    except mysql.connector.Error as err:
        logger.error(f"Error updating last notified multiple: {err}")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

# Main function to run the bot with different schedules
def main():
    scheduler = BackgroundScheduler(timezone='UTC')
    
    # Schedule to check for new tokens every 2 minute
    scheduler.add_job(check_for_new_tokens, 'interval', minutes=2)

    # Schedule to check all tokens for buy conditions and gains every 120 minute
    scheduler.add_job(check_market_caps_for_all_tokens, 'interval', minutes=120)

    scheduler.start()
    logger.info("Scheduler started.")

    try:
        while True:
            time.sleep(1)  # Sleep to prevent high CPU usage
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Scheduler stopped.")

if __name__ == '__main__':
    main()
