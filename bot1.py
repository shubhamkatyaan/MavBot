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

        if not pairs:
            logger.warning(f"No pairs found for contract: {contract_address}")
            return None

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

# Check for new tokens added to the database every 1 minute
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

# Check all tokens every 1 minute for market cap to buy or track gains
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
            try_buy_at_min = token['try_buy_at_min']
            try_buy_at_max = token['try_buy_at_max']
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

            # Check if market cap is within buy zone range
            if market_cap >= try_buy_at_min and market_cap <= try_buy_at_max:
                logger.info(f"Token {token_name} entered buy zone: {try_buy_at_min} <= {market_cap} <= {try_buy_at_max}")
                send_token_in_buy_zone_message(token, market_cap)
                update_token_after_buy_initiated(token['id'], market_cap)
            else:
                logger.info(f"Token {token_name} not in buy zone - Market Cap: {market_cap}, Range: {try_buy_at_min}-{try_buy_at_max}")
            
            # Check for market cap multiples (gains)
            if initial_market_cap > 0:
                multiple = market_cap / initial_market_cap
                multiples_to_check = [5, 7, 10, 15, 20, 25, 50, 100, 200, 250, 300, 400, 500]
                for m in multiples_to_check:
                    if multiple >= m and last_notified_multiple < m:
                        send_multiple_achieved_message(token, market_cap, m)
                        update_last_notified_multiple(token['id'], m)
                        break

            time.sleep(1)  # Sleep to avoid rate limits
    except mysql.connector.Error as err:
        logger.error(f"Error: {err}")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

# Send message when token enters buy zone
def send_token_in_buy_zone_message(token, market_cap):
    try:
        market_cap_text = f"${market_cap:,.2f}" if market_cap else "N/A"
        message = (
            f"🚀 *Token Entered Buy Zone!* ${token['try_buy_at_min']:,.2f} - ${token['try_buy_at_max']:,.2f}\n\n"
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
        logger.info(f"Buy zone message sent for {token['token_name']}.")
    except Exception as e:
        logger.error(f"Failed to send buy zone message: {e}")

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
        logger.info(f"Token {token_id} updated after entering buy zone.")
    except mysql.connector.Error as err:
        logger.error(f"Error updating token after buy zone: {err}")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

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
    
    # Schedule to check for new tokens every 1 minute
    scheduler.add_job(check_for_new_tokens, 'interval', minutes=1)

    # Schedule to check all tokens for buy conditions and gains every 1 minute
    scheduler.add_job(check_market_caps_for_all_tokens, 'interval', minutes=1)

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
